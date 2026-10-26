#!/usr/bin/env python3
"""Search or extend explicit technique cards; never infer evidence or promote status."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile


DEFAULT = Path(__file__).resolve().parent.parent / "references" / "techniques.json"
STATUSES = ("proposed", "observed", "tested", "supported")
FIELDS = ("id", "title", "status", "task_types", "tags", "problem", "mechanism",
          "use_when", "avoid_when", "evidence")


def validate(card):
    if not isinstance(card, dict) or any(k not in card for k in FIELDS):
        raise ValueError("Card is missing required fields: " + ", ".join(FIELDS))
    if not isinstance(card["id"], str) or not re.fullmatch(r"[A-Z][A-Z0-9-]{2,47}", card["id"]):
        raise ValueError("Card ID must be a stable uppercase namespace, for example VD-T001")
    if card["status"] not in STATUSES:
        raise ValueError("Unknown evidence status")
    for key in ("title", "problem", "mechanism", "use_when", "avoid_when"):
        if not isinstance(card[key], str) or not card[key].strip():
            raise ValueError("Card needs a nonempty " + key)
    for key in ("task_types", "tags"):
        if not isinstance(card[key], list) or not card[key] or any(
                not isinstance(v, str) or not v.strip() for v in card[key]):
            raise ValueError(key + " must contain nonempty strings")
    if not isinstance(card["evidence"], list):
        raise ValueError("evidence must be an array")
    for item in card["evidence"]:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip()
                                            for k in ("ref", "observation", "verification")):
            raise ValueError("Evidence needs ref, observation and verification")
        if item["verification"] not in ("reported", "checked", "unverified"):
            raise ValueError("Unknown evidence verification")
    if card["status"] != "proposed" and not card["evidence"]:
        raise ValueError("An observed/tested/supported card needs recorded evidence")
    return card


def read_library(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("cards"), list):
        raise ValueError("Unsupported technique library")
    seen = set()
    for card in data["cards"]:
        validate(card)
        if card["id"] in seen:
            raise ValueError("Duplicate card ID: " + card["id"])
        seen.add(card["id"])
    return data


def tokens(query):
    result = set()
    for word in re.findall(r"[a-z0-9_-]+|[\u3400-\u9fff]+", query.casefold()):
        result.add(word)
        if re.fullmatch(r"[\u3400-\u9fff]+", word) and len(word) > 2:
            result.update(word[i:i + 2] for i in range(len(word) - 1))
    return result


def search(paths, query, task_type, limit):
    query_tokens = tokens(query)
    if not query_tokens:
        raise ValueError("Search needs a nonempty Chinese or Latin query")
    by_id = {}
    for path in paths:
        for card in read_library(path)["cards"]:
            key = card["id"]
            if key in by_id and card != by_id[key][0]:
                raise ValueError("Conflicting card ID across libraries: " + key)
            by_id[key] = (card, str(path))
    found = []
    for card, source in by_id.values():
        if task_type and task_type not in card["task_types"] and "general" not in card["task_types"]:
            continue
        fields = {"title": 4, "tags": 4, "problem": 3, "mechanism": 2, "use_when": 1}
        score, matched = 0, set()
        for key, weight in fields.items():
            text = " ".join(card[key]) if isinstance(card[key], list) else card[key]
            for token in query_tokens:
                if token in text.casefold():
                    score += weight
                    matched.add(token)
        if score:
            found.append({"card": card, "library": source, "matched_terms": sorted(matched),
                          "relevance_score": score})
    found.sort(key=lambda v: (-v["relevance_score"], v["card"]["id"]))
    return {"status": "searched", "results": found[:limit],
            "scope": "keyword relevance only; read conditions and evidence before applying"}


def add(path, card_path):
    if path.resolve() == DEFAULT.resolve():
        raise ValueError("Write task experience into a project library, not the bundled seed library")
    card = validate(json.loads(card_path.read_text(encoding="utf-8")))
    data = read_library(path) if path.exists() else {"schema_version": 1, "cards": []}
    if any(v["id"] == card["id"] for v in data["cards"]):
        raise ValueError("Card ID already exists; refusing to overwrite")
    data["cards"].append(card)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return {"status": "added", "id": card["id"], "evidence_status": card["status"],
            "scope": "metadata validation only; evidence truth and transfer are not checked"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("search")
    p.add_argument("--query", required=True)
    p.add_argument("--task-type", default="")
    p.add_argument("--library", action="append", type=Path)
    p.add_argument("--limit", type=int, default=3)
    p = commands.add_parser("list")
    p.add_argument("--library", type=Path, default=DEFAULT)
    p = commands.add_parser("add")
    p.add_argument("--library", type=Path, required=True)
    p.add_argument("--card", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "search":
            if not 1 <= args.limit <= 20:
                raise ValueError("limit must be between 1 and 20")
            result = search(args.library or [DEFAULT], args.query, args.task_type, args.limit)
        elif args.command == "add":
            result = add(args.library, args.card)
        else:
            result = {"status": "listed", "library": str(args.library),
                      "cards": read_library(args.library)["cards"]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
