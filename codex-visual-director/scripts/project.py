#!/usr/bin/env python3
"""Manage local visual-project files; never generate images or judge quality."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone


STATE = "TASK_STATE.json"
VERSION = re.compile(r"v[0-9]{3,}\Z")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def inside(root, relative):
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError("Project state must use relative artifact paths")
    target = (root / candidate).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("Artifact path escapes the project") from None
    return target


def load(root):
    data = json.loads((root / STATE).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("versions"), dict):
        raise ValueError("Unsupported or invalid project state")
    for key, entry in data["versions"].items():
        if not VERSION.fullmatch(key) or not isinstance(entry, dict):
            raise ValueError("Invalid version entry")
        inside(root, entry["artifact"])
    for key in ("current_version", "selected_version"):
        if data.get(key) is not None and data[key] not in data["versions"]:
            raise ValueError("State refers to an unregistered version")
    return data


def save(root, data):
    data["updated_at"] = now()
    path = root / STATE
    if path.exists():
        shutil.copy2(path, root / "TASK_STATE.previous.json")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root,
                                         prefix="state-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def copy_new(source, destination):
    """Create a copy without overwriting; check the bytes during this operation."""
    created = False
    try:
        with destination.open("xb") as output:
            created = True
            with source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
        if destination.read_bytes() != source.read_bytes():
            raise ValueError("Copied bytes do not match the source")
    except Exception:
        if created and destination.exists():
            destination.unlink()
        raise


def init_project(args, root):
    root.mkdir(parents=True, exist_ok=True)
    if (root / STATE).exists():
        raise ValueError("Project state already exists; refusing to overwrite")
    for name in ("versions", "selected"):
        inside(root, name).mkdir(exist_ok=True)
    brief = root / "brief.md"
    if not brief.exists():
        template = Path(__file__).resolve().parent.parent / "assets" / "project-brief.md"
        copy_new(template, brief)
    data = {
        "schema_version": 1,
        "title": args.title or root.name,
        "stage": "D0",
        "brief": "brief.md",
        "current_version": None,
        "selected_version": None,
        "selected_artifact": None,
        "versions": {},
        "next_action": "读取并补全 brief.md 中的有效需求",
        "created_at": now(),
    }
    save(root, data)
    return {"status": "initialized", "project": str(root), "state": str(root / STATE)}


def add_version(args, root, data):
    if not VERSION.fullmatch(args.id):
        raise ValueError("Version IDs must look like v001 or v0001")
    if args.id in data["versions"]:
        raise ValueError("Version ID already registered; use a new ID")
    if args.parent and args.parent not in data["versions"]:
        raise ValueError("Parent version is not registered")
    source = Path(args.source).expanduser().resolve()
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Source must be an existing nonempty file")
    edit_input = args.edit_input or ("unverified" if args.parent else "not_applicable")
    if edit_input == "confirmed" and (not args.parent or not args.evidence.strip()):
        raise ValueError("Confirmed edit input requires a parent and recorded evidence")
    suffix = source.suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9_-]{1,16}", suffix):
        suffix = ".bin"
    directory = inside(root, "versions/" + args.id)
    directory.mkdir()
    target = directory / ("artifact" + suffix)
    try:
        copy_new(source, target)
    except Exception:
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()
        raise
    relative = target.relative_to(root).as_posix()
    data["versions"][args.id] = {
        "artifact": relative,
        "parent": args.parent,
        "edit_input_status": edit_input,
        "edit_input_evidence": args.evidence,
        "note": args.note,
        "registered_at": now(),
        "visual_review": "unverified",
    }
    data["current_version"] = args.id
    data["stage"] = "D3"
    data["next_action"] = "实际查看 " + args.id + " 并按完整 Brief 分项验收"
    save(root, data)
    return {"status": "registered", "version": args.id, "artifact": str(target),
            "visual_review": "unverified"}


def select_version(args, root, data):
    if args.version not in data["versions"]:
        raise ValueError("Selected version is not registered")
    source = inside(root, data["versions"][args.version]["artifact"])
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("Version artifact is missing or empty; cannot restore it")
    directory = inside(root, "selected")
    directory.mkdir(exist_ok=True)
    target = directory / (args.version + source.suffix)
    if target.exists():
        if target.read_bytes() != source.read_bytes():
            raise ValueError("Selected target differs; refusing to overwrite")
    else:
        copy_new(source, target)
    previous = data.get("selected_version")
    data["selected_version"] = args.version
    data["selected_artifact"] = target.relative_to(root).as_posix()
    data["selection_reason"] = args.reason
    data["stage"] = "D4"
    data["next_action"] = "查看选定稿并记录验收或等待用户接受；不自动生成"
    save(root, data)
    return {"status": "selected", "version": args.version, "previous_selection": previous,
            "artifact": str(target), "user_acceptance": "not_determined"}


def project_status(root, data):
    missing = []
    paths = {key: entry["artifact"] for key, entry in data["versions"].items()}
    paths["brief"] = data.get("brief", "brief.md")
    if data.get("selected_artifact"):
        paths["selected_artifact"] = data["selected_artifact"]
    for key, relative in paths.items():
        p = inside(root, relative)
        if not p.is_file() or p.stat().st_size == 0:
            missing.append(key)
    return {"status": "loaded", "project": str(root), "state": data,
            "storage_ok": not missing, "missing_or_empty": missing,
            "scope": "file presence only; not image decoding or visual acceptance"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("init", help="Create a project without overwriting existing state")
    p.add_argument("project")
    p.add_argument("--title", default="")
    p = commands.add_parser("add", help="Register a nonempty file as a new version")
    p.add_argument("project")
    p.add_argument("source")
    p.add_argument("--id", required=True)
    p.add_argument("--parent")
    p.add_argument("--edit-input", choices=("confirmed", "unverified", "not_applicable"))
    p.add_argument("--evidence", default="")
    p.add_argument("--note", default="")
    p = commands.add_parser("select", help="Copy and select an existing version")
    p.add_argument("project")
    p.add_argument("version")
    p.add_argument("--reason", required=True)
    p = commands.add_parser("update", help="Record stage and next action, without judging quality")
    p.add_argument("project")
    p.add_argument("--stage", choices=tuple("D" + str(i) for i in range(6)), required=True)
    p.add_argument("--next", dest="next_action", required=True)
    p = commands.add_parser("status", help="Read state and check registered file presence")
    p.add_argument("project")
    args = parser.parse_args()
    root = Path(args.project).expanduser().resolve()
    try:
        if args.command == "init":
            result = init_project(args, root)
        else:
            data = load(root)
            if args.command == "add":
                result = add_version(args, root, data)
            elif args.command == "select":
                result = select_version(args, root, data)
            elif args.command == "update":
                data["stage"] = args.stage
                data["next_action"] = args.next_action
                save(root, data)
                result = {"status": "updated", "stage": args.stage, "next_action": args.next_action}
            else:
                result = project_status(root, data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("storage_ok") is False else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
