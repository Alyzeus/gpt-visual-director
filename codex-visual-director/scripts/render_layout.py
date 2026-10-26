#!/usr/bin/env python3
"""Render explicit CJK/Latin text layouts to PNG and SVG; check real ink, not font size."""

import argparse
import base64
from io import BytesIO
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


def keys(value, allowed, label):
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    extra = set(value) - set(allowed)
    if extra:
        raise ValueError(label + " has unsupported fields: " + ", ".join(sorted(extra)))


def number(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + " must be a finite number")
    if positive and value <= 0:
        raise ValueError(label + " must be positive")
    return value


def rect(value, label, width, height):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(label + " must be [x, y, width, height]")
    x, y, w, h = [number(v, label) for v in value]
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError(label + " must fit inside the canvas")
    return x, y, w, h


def color(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Use an opaque #RRGGBB color")
    return value


def local_file(value, base):
    if not isinstance(value, str) or not value:
        raise ValueError("A real local file is required")
    p = Path(value).expanduser()
    p = p if p.is_absolute() else base / p
    if not p.is_file():
        raise ValueError("File unavailable: " + str(p))
    return p.resolve()


def wrap(text, font, width):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for character in paragraph:
            if line and font.getlength(line + character) > width:
                # Prefer a Latin word boundary; retain all original characters.
                split = line.rfind(" ") + 1
                if split and split < len(line):
                    lines.append(line[:split])
                    line = line[split:]
                else:
                    lines.append(line)
                    line = ""
            line += character
            if font.getlength(line) > width:
                raise ValueError("A word or glyph cannot fit in its text rectangle")
        lines.append(line)
    return lines


def render(config, base, fallback_font):
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps
        from fontTools.ttLib import TTFont
        from fontTools import subset
    except ImportError as error:
        raise ValueError("Layout rendering needs Pillow and fonttools in this Python environment; "
                         "missing dependency: " + str(error.name)) from None
    keys(config, ("schema_version", "canvas", "background", "safe_margin", "protected_regions", "blocks"), "layout")
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported layout schema_version")
    canvas = config["canvas"]
    keys(canvas, ("width", "height"), "canvas")
    width, height = canvas["width"], canvas["height"]
    if any(isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 8192 for v in (width, height)) or width * height > 24_000_000:
        raise ValueError("Canvas must use integer pixels, at most 8192 per side and 24 million total")
    margin = number(config.get("safe_margin", 0), "safe_margin")
    if margin < 0 or margin * 2 >= min(width, height):
        raise ValueError("Invalid safe margin")
    background = config.get("background", {"color": "#FFFFFF"})
    keys(background, ("color", "image", "fit"), "background")
    base_color = color(background.get("color", "#FFFFFF"))
    image = Image.new("RGBA", (width, height), base_color)
    svg_background = None
    if background.get("image"):
        path = local_file(background["image"], base)
        with Image.open(path) as source:
            source = ImageOps.exif_transpose(source).convert("RGBA")
            fit = background.get("fit", "exact")
            if fit == "exact":
                if source.size != (width, height):
                    raise ValueError("Background size differs; set fit=contain or cover explicitly")
                layer = source
            elif fit == "cover":
                layer = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS)
            elif fit == "contain":
                fitted = ImageOps.contain(source, (width, height), method=Image.Resampling.LANCZOS)
                layer = Image.new("RGBA", (width, height))
                layer.alpha_composite(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
            else:
                raise ValueError("background.fit must be exact, contain or cover")
            image.alpha_composite(layer)
            buffer = BytesIO()
            layer.save(buffer, format="PNG")
            svg_background = base64.b64encode(buffer.getvalue()).decode("ascii")
    elif "fit" in background:
        raise ValueError("background.fit requires an image")
    protected = []
    for item in config.get("protected_regions", []):
        keys(item, ("id", "rect"), "protected region")
        protected.append((item["id"], rect(item["rect"], "protected region", width, height)))
    blocks = config.get("blocks")
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 100:
        raise ValueError("Provide 1 to 100 text blocks")
    total_ink = Image.new("L", (width, height))
    fonts, records, instructions, ids = {}, [], [], set()
    for block in blocks:
        keys(block, ("id", "text", "rect", "font_file", "font_index", "font_size", "line_height",
                     "align", "color", "wrap", "min_ink_height"), "text block")
        name, text = block["id"], block["text"]
        if not isinstance(name, str) or not name or name in ids:
            raise ValueError("Each block needs a unique nonempty ID")
        ids.add(name)
        if not isinstance(text, str) or not text.strip() or len(text) > 10000 or any(ord(c) < 32 and c != "\n" for c in text):
            raise ValueError(name + ": use nonempty text with LF line breaks and no control characters")
        x, y, w, h = rect(block["rect"], name, width, height)
        font_path = local_file(block.get("font_file") or fallback_font, base)
        index, size = block.get("font_index", 0), block["font_size"]
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError("font_index must be a nonnegative integer")
        if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 2048:
            raise ValueError("font_size must be integer pixels from 1 to 2048")
        height_step = number(block["line_height"], "line_height", positive=True)
        minimum = number(block.get("min_ink_height", 0), "min_ink_height")
        if minimum < 0:
            raise ValueError("min_ink_height cannot be negative")
        align, fill = block.get("align", "left"), color(block.get("color", "#000000"))
        if align not in ("left", "center", "right") or not isinstance(block.get("wrap", True), bool):
            raise ValueError("Unsupported align or wrap value")
        font_key = (str(font_path), index)
        if font_key not in fonts:
            try:
                tt = TTFont(font_path, fontNumber=index)
                cmap = tt.getBestCmap() or {}
            except Exception as error:
                raise ValueError("Font cannot be decoded: " + str(font_path) +
                                 " (" + type(error).__name__ + ")") from None
            if "OS/2" in tt and tt["OS/2"].fsType & 0x202:
                tt.close()
                raise ValueError("Selected font restricts outline embedding; choose another font")
            fonts[font_key] = {"font": tt, "cmap": cmap, "chars": set(), "name": "VDfont" + str(len(fonts))}
        info = fonts[font_key]
        cmap = info["cmap"]
        missing = sorted(set(c for c in text if c != "\n" and ord(c) not in cmap))
        if missing:
            raise ValueError(name + ": font has no glyphs for " + repr("".join(missing)))
        info["chars"].update(text.replace("\n", ""))
        font = ImageFont.truetype(str(font_path), size, index=index)
        lines = wrap(text, font, w) if block.get("wrap", True) else text.split("\n")
        ascent, _ = font.getmetrics()
        block_mask = Image.new("L", (width, height))
        line_records = []
        for n, line in enumerate(lines):
            advance = font.getlength(line)
            left = x + (w - advance) * {"left": 0, "center": 0.5, "right": 1}[align]
            baseline = y + ascent + n * height_step
            line_mask = Image.new("L", (width, height))
            box = ImageDraw.Draw(line_mask).textbbox((left, baseline), line, font=font, anchor="ls")
            # Measure ink before clipping to the canvas. Advance widths and textbbox
            # can include whitespace or a rounding pixel at a right-aligned edge.
            origin_x, origin_y = math.floor(box[0]) - 2, math.floor(box[1]) - 2
            local_size = (max(1, math.ceil(box[2]) - origin_x + 2),
                          max(1, math.ceil(box[3]) - origin_y + 2))
            if local_size[0] * local_size[1] > 24_000_000:
                raise ValueError(name + ": text measurement exceeds the supported raster area")
            local_mask = Image.new("L", local_size)
            ImageDraw.Draw(local_mask).text((left - origin_x, baseline - origin_y), line,
                                           font=font, fill=255, anchor="ls")
            ink = local_mask.getbbox()
            actual = (ink[0] + origin_x, ink[1] + origin_y,
                      ink[2] + origin_x, ink[3] + origin_y) if ink else None
            if actual:
                if actual[0] < x or actual[1] < y or actual[2] > x + w or actual[3] > y + h:
                    raise ValueError(name + ": rendered text exceeds its rectangle")
                line_mask.paste(local_mask, (origin_x, origin_y))
                if actual[0] < margin or actual[1] < margin or actual[2] > width - margin or actual[3] > height - margin:
                    raise ValueError(name + ": visible ink crosses the safe margin")
                if actual[3] - actual[1] < minimum:
                    raise ValueError(name + ": visible line ink is below min_ink_height")
                if ImageChops.multiply(block_mask, line_mask).getbbox():
                    raise ValueError(name + ": rendered lines overlap")
            block_mask = ImageChops.lighter(block_mask, line_mask)
            line_records.append({"text": line, "advance": advance, "ink_bbox": actual})
            instructions.append({"text": line, "x": left, "baseline": baseline, "font": info["name"],
                                 "size": size, "fill": fill, "advance": advance})
            ImageDraw.Draw(image).text((left, baseline), line, font=font, fill=fill, anchor="ls")
        for region_id, (rx, ry, rw, rh) in protected:
            area = (math.floor(rx), math.floor(ry), math.ceil(rx + rw), math.ceil(ry + rh))
            if block_mask.crop(area).getbbox():
                raise ValueError(name + ": visible ink enters protected region " + str(region_id))
        if ImageChops.multiply(total_ink, block_mask).getbbox():
            raise ValueError(name + ": visible ink overlaps another text block")
        total_ink = ImageChops.lighter(total_ink, block_mask)
        records.append({"id": name, "text": text, "font_file": str(font_path), "font_index": index,
                        "font_size": size, "ink_bbox": block_mask.getbbox(), "lines": line_records})
    ns = "http://www.w3.org/2000/svg"
    ET.register_namespace("", ns)
    svg = ET.Element("{" + ns + "}svg", {"width": str(width), "height": str(height),
                                         "viewBox": f"0 0 {width} {height}"})
    styles = []
    for info in fonts.values():
        tt = info["font"]
        options = subset.Options()
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text="".join(sorted(info["chars"])))
        subsetter.subset(tt)
        buffer = BytesIO()
        tt.save(buffer)
        mime = "font/otf" if tt.sfntVersion == "OTTO" else "font/ttf"
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        styles.append("@font-face{font-family:'" + info["name"] + "';src:url(data:" + mime + ";base64," + encoded + ")}")
        tt.close()
    ET.SubElement(svg, "{" + ns + "}style").text = "\n".join(styles)
    ET.SubElement(svg, "{" + ns + "}rect", {"width": str(width), "height": str(height), "fill": base_color})
    if svg_background:
        ET.SubElement(svg, "{" + ns + "}image", {"width": str(width), "height": str(height),
                                                 "href": "data:image/png;base64," + svg_background})
    for line in instructions:
        attrs = {"x": str(line["x"]), "y": str(line["baseline"]), "font-family": line["font"],
                 "font-size": str(line["size"]), "fill": line["fill"],
                 "{http://www.w3.org/XML/1998/namespace}space": "preserve"}
        if line["text"].strip() and line["advance"] > 0:
            attrs.update(textLength=str(line["advance"]), lengthAdjust="spacingAndGlyphs")
        ET.SubElement(svg, "{" + ns + "}text", attrs).text = line["text"]
    png = BytesIO()
    image.convert("RGB").save(png, format="PNG")
    report = {"status": "rendered", "canvas": [width, height], "blocks": records,
              "checks": {"glyph_coverage": "pass", "text_overflow": "pass", "safe_margin": "pass",
                         "protected_regions": "pass" if protected else "not_applicable",
                         "text_ink_overlap": "pass", "minimum_ink_height": "pass" if any(
                             b.get("min_ink_height", 0) > 0 for b in blocks) else "not_applicable"},
              "scope": "PNG ink geometry only; not design acceptance or cross-renderer SVG equivalence"}
    return png.getvalue(), ET.tostring(svg, encoding="utf-8", xml_declaration=True), report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="New output prefix, without an extension")
    parser.add_argument("--font", help="Actual local fallback font for blocks without font_file")
    args = parser.parse_args()
    created = []
    try:
        config = json.loads(args.layout.read_text(encoding="utf-8"))
        targets = [Path(str(args.out) + suffix) for suffix in (".png", ".svg", ".report.json")]
        if any(p.exists() for p in targets):
            raise ValueError("An output already exists; use a new prefix instead of overwriting")
        fallback = str(Path(args.font).expanduser().resolve()) if args.font else None
        png, svg, report = render(config, args.layout.resolve().parent, fallback)
        payloads = (png, svg, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        for path, payload in zip(targets, payloads):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                created.append(path)
                stream.write(payload)
        print(json.dumps({"status": "rendered", "files": [str(p.resolve()) for p in targets],
                          "scope": report["scope"]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        for path in created:
            path.unlink(missing_ok=True)
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
