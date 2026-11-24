#!/usr/bin/env python3
"""Turn a portrait photo into the masks that shape the card's code portrait.

The card fills a panel with flowing source code; these masks decide how strongly
each spot of that code shows, so the face appears in the code. Runs locally only
(Pillow, NumPy, OpenCV and rembg from requirements-portrait.txt):

    python scripts/make_portrait.py photo.jpg --box 372,110,520

--box is x,y,width of the crop in the photo; its height follows from the panel.
Writes assets/portrait-dark.png (bright features strong, for a dark card) and
assets/portrait-light.png (dark features strong, for a light card).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PANEL_W, PANEL_H = 340, 404       # must match ART_W, ART_H in card.py
SCALE = 0.5                        # masks are stored at half the panel resolution
FLOOR = 0.10                       # keeps the silhouette faintly visible where it is dark
FADE_FROM = 0.74                   # shoulders fade out below this fraction of the height


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photo", type=Path)
    parser.add_argument("--box", required=True, help="x,y,width of the crop in photo pixels")
    parser.add_argument("--gamma", type=float, default=1.8, help=">1 deepens shadows, <1 lifts them")
    parser.add_argument("--out", type=Path, default=ROOT / "assets")
    args = parser.parse_args()

    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageFilter
        os.environ.setdefault("U2NET_HOME", str(Path(os.environ.get("TEMP", "/tmp")) / "u2net"))
        from rembg import new_session, remove
    except ImportError as exc:
        print(f"Missing {exc.name}; install scripts/requirements-portrait.txt", file=sys.stderr)
        return 2

    x, y, width = (int(v) for v in args.box.split(","))
    height = round(width * PANEL_H / PANEL_W)
    photo = Image.open(args.photo).convert("RGB")
    if x < 0 or y < 0 or x + width > photo.width or y + height > photo.height:
        print(f"Crop {x},{y} {width}x{height} falls outside the {photo.width}x{photo.height} photo", file=sys.stderr)
        return 2
    crop = photo.crop((x, y, x + width, y + height))
    size = (round(PANEL_W * SCALE), round(PANEL_H * SCALE))

    alpha = remove(crop, only_mask=True, session=new_session("u2netp")).filter(ImageFilter.GaussianBlur(2))
    alpha = np.asarray(alpha.resize(size, Image.Resampling.LANCZOS), dtype=float) / 255

    gray = cv2.cvtColor(np.asarray(crop), cv2.COLOR_RGB2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(6, 6)).apply(gray)
    lum = np.asarray(Image.fromarray(gray).resize(size, Image.Resampling.LANCZOS), dtype=float)
    inside = lum[alpha > 0.5]
    lo, hi = np.percentile(inside, 2), np.percentile(inside, 98)
    lum = np.clip((lum - lo) / max(hi - lo, 1), 0, 1)

    rows = np.arange(size[1]) / (size[1] - 1)
    fade = (1 - 0.85 * np.clip((rows - FADE_FROM) / (1 - FADE_FROM), 0, 1))[:, None]

    for name, tone in (("dark", lum), ("light", 1 - lum)):
        value = (FLOOR + (1 - FLOOR) * tone ** args.gamma) * alpha * fade
        image = Image.fromarray(np.uint8(np.clip(value, 0, 1) * 255), mode="L")
        target = args.out / f"portrait-{name}.png"
        image.save(target, optimize=True)
        print(f"Wrote {target} ({size[0]} x {size[1]}, {target.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
