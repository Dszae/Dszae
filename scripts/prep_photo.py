#!/usr/bin/env python3
"""Prepare a portrait for terminal-style ASCII rendering."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

OUTPUT = Path("source-prepped.png")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Portrait image to prepare")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Output PNG (default: source-prepped.png)")
    args = parser.parse_args()
    if not args.input.is_file():
        print(f"Error: input image not found: {args.input}\nPass the path to your own portrait image.", file=sys.stderr)
        return 2

    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        print(f"Error: missing portrait dependency ({exc.name}). Install with: python -m pip install -r scripts/requirements-portrait.txt", file=sys.stderr)
        return 2

    try:
        image = Image.open(args.input).convert("RGBA")
        try:
            from rembg import remove
            image = remove(image).convert("RGBA")
        except Exception as exc:
            print(f"Background removal unavailable ({exc}); continuing with the supplied image.", file=sys.stderr)

        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        background.alpha_composite(image)
        rgb = np.asarray(background.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(enhanced, mode="L").save(args.output)
        print(f"Prepared portrait: {args.output}")
        return 0
    except Exception as exc:
        print(f"Error preparing {args.input}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
