#!/usr/bin/env python3
"""Render a prepared grayscale portrait as an animated monochrome SVG."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

CHARS = " .`:-=+*cs#%@"  # dark pixels map to dense glyphs; bright pixels to spaces
INPUT = Path("source-prepped.png")
OUTPUT = Path("dipesh-ascii.svg")
COLS, ROWS = 100, 53
CELL_W, CELL_H = 8.0, 12.5


def fallback_svg() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 168" role="img" aria-labelledby="title desc">
<title id="title">Dipesh Sapkota — portrait pending</title><desc id="desc">Add a personal source-photo.jpg and run the portrait scripts to generate the ASCII portrait.</desc>
<rect width="820" height="168" rx="10" fill="#0d1117"/><rect x="1" y="1" width="818" height="166" rx="9" fill="none" stroke="#30363d"/>
<text x="24" y="42" fill="#7d8590" font-family="monospace" font-size="14">portrait renderer / awaiting source image</text>
<text x="24" y="82" fill="#c9d1d9" font-family="monospace" font-size="14">Place your own source-photo.jpg in the repository</text>
<text x="24" y="108" fill="#c9d1d9" font-family="monospace" font-size="14">then run prep_photo.py and make_ascii_svg.py.</text>
<text x="24" y="143" fill="#3fb950" font-family="monospace" font-size="14">$ _</text></svg>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        from PIL import Image
    except ImportError as exc:
        parser.error(f"Pillow is required: {exc}. Install scripts/requirements-portrait.txt")
    if not args.input.is_file():
        args.output.write_text(fallback_svg(), encoding="utf-8")
        print(f"No prepared portrait at {args.input}; wrote an informative placeholder to {args.output}. Supply your own image to create the portrait.")
        return 0

    image = Image.open(args.input).convert("L")
    image.thumbnail((COLS, ROWS), Image.Resampling.LANCZOS)
    # Pad to a consistent, centered character canvas.
    canvas = Image.new("L", (COLS, ROWS), 255)
    canvas.paste(image, ((COLS - image.width) // 2, (ROWS - image.height) // 2))
    pixels = canvas.load()
    lines: list[str] = []
    for y in range(ROWS):
        chars = []
        for x in range(COLS):
            brightness = pixels[x, y]
            index = round((255 - brightness) / 255 * (len(CHARS) - 1))
            chars.append(CHARS[index])
        lines.append("".join(chars))

    width, height = COLS * CELL_W + 40, ROWS * CELL_H + 52
    text_x, text_y = 20, 34
    row_elements = []
    for idx, line in enumerate(lines):
        y = text_y + idx * CELL_H
        row_elements.append(f'<text class="row" x="{text_x}" y="{y:.1f}" style="--i:{idx}">{html.escape(line)}</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" role="img" aria-labelledby="title desc">
<title id="title">Dipesh Sapkota — ASCII portrait</title><desc id="desc">A monochrome terminal portrait drawn row by row.</desc>
<style>.row{{font:10px/1 monospace;white-space:pre;fill:#c9d1d9;opacity:0;animation:draw .12s ease-out calc(var(--i)*.055s) forwards}}@keyframes draw{{to{{opacity:1}}}}@media(prefers-reduced-motion:reduce){{.row{{animation:none;opacity:1}}}}</style>
<rect x=".5" y=".5" width="{width-1:.0f}" height="{height-1:.0f}" rx="10" fill="#0d1117" stroke="#30363d"/>
<text x="20" y="22" fill="#7d8590" font-family="monospace" font-size="12">dipesh@profile:~$ render --mode ascii</text>
{''.join(row_elements)}
</svg>'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(f"Wrote {args.output} ({COLS} × {ROWS} character grid)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
