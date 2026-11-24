#!/usr/bin/env python3
"""Turn a portrait photo into the ASCII art shown on the profile card.

Runs locally only (Pillow, NumPy, OpenCV and rembg from requirements-portrait.txt):

    python scripts/make_portrait.py photo.jpg --box 352,120,560

--box is x,y,width of the head-and-shoulders crop in the photo; its height follows
from the card's character grid. Writes assets/portrait-dark.txt (bright areas drawn
dense, for light text on a dark card) and assets/portrait-light.txt (dark areas
drawn dense, for dark text on a light card). The background is left blank.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLS, ROWS = 50, 40
CELL_W, CELL_H = 6.3, 12.5            # must match ART_CHAR and ART_LINE in card.py
FADE_FROM = 0.72                       # shoulders fade out below this fraction of the height
RAMP = " .`:-=+*cs#%@"                 # sparse to dense
SUBJECT_FLOOR = 1                      # keep the silhouette visible where the subject is dark


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photo", type=Path)
    parser.add_argument("--box", required=True, help="x,y,width of the crop in photo pixels")
    parser.add_argument("--gamma", type=float, default=1.0, help="<1 brightens mid-tones, >1 darkens them")
    parser.add_argument("--out", type=Path, default=ROOT / "assets")
    args = parser.parse_args()

    try:
        import cv2
        import numpy as np
        from PIL import Image
        os.environ.setdefault("U2NET_HOME", str(Path(os.environ.get("TEMP", "/tmp")) / "u2net"))
        from rembg import new_session, remove
    except ImportError as exc:
        print(f"Missing {exc.name}; install scripts/requirements-portrait.txt", file=sys.stderr)
        return 2

    x, y, width = (int(v) for v in args.box.split(","))
    height = round(width * (ROWS * CELL_H) / (COLS * CELL_W))
    photo = Image.open(args.photo).convert("RGB")
    if x < 0 or y < 0 or x + width > photo.width or y + height > photo.height:
        print(f"Crop {x},{y} {width}x{height} falls outside the {photo.width}x{photo.height} photo", file=sys.stderr)
        return 2
    crop = photo.crop((x, y, x + width, y + height))

    mask = remove(crop, only_mask=True, session=new_session("u2netp"))
    gray = cv2.cvtColor(np.asarray(crop), cv2.COLOR_RGB2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

    def to_grid(img) -> np.ndarray:
        return np.asarray(Image.fromarray(img).resize((COLS, ROWS), Image.Resampling.BOX), dtype=float) / 255

    light = to_grid(gray) ** args.gamma
    subject = to_grid(np.asarray(mask)) > 0.5

    fade = np.clip((np.arange(ROWS) / (ROWS - 1) - FADE_FROM) / (1 - FADE_FROM), 0, 1)
    fade = (1 - 0.6 * fade)[:, None]
    for name, density in (("dark", light), ("light", 1 - light)):
        levels = np.rint(density * fade * (len(RAMP) - 1)).astype(int)
        levels = np.where(subject, np.maximum(levels, SUBJECT_FLOOR), 0)
        rows = ["".join(RAMP[v] for v in row).rstrip() for row in levels]
        target = args.out / f"portrait-{name}.txt"
        target.write_text("\n".join(rows) + "\n", encoding="utf-8")
        print(f"Wrote {target} ({COLS} x {ROWS})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
