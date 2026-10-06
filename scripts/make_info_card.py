#!/usr/bin/env python3
"""Generate a compact, terminal-inspired profile information card."""

from __future__ import annotations

import os
from pathlib import Path

OUTPUT = Path("info-card.svg")
LINES = [
    ("name", "Dipesh Sapkota", "#f0f6fc", True),
    ("role", "Computer Engineering Student", "#c9d1d9", False),
    ("college", "Thapathali Campus / IOE · Nepal", "#c9d1d9", False),
    ("focus", "Web Development / Creative Media", "#c9d1d9", False),
    ("creative", "Video Editing / Motion Graphics", "#c9d1d9", False),
    ("stack", "C / C++ / Python / JavaScript / React", "#c9d1d9", False),
]


def main() -> int:
    static = os.getenv("STATIC", "").strip() == "1"
    rows = []
    for index, (label, value, color, strong) in enumerate(LINES):
        y = 113 + index * 31
        style = ""
        if not static:
            style = f' class="entry" style="--i:{index}"'
        weight = "600" if strong else "400"
        rows.append(f'<text{style} x="34" y="{y}" fill="{color}" font-family="monospace" font-size="14" font-weight="{weight}"><tspan fill="#3fb950">{label:8}</tspan><tspan dx="12">{value}</tspan></text>')
    animation = "" if static else '<style>.entry{opacity:0;animation:enter .32s ease-out calc(var(--i)*.11s) forwards}@keyframes enter{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}@media(prefers-reduced-motion:reduce){.entry{animation:none;opacity:1}}</style>'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 330" role="img" aria-labelledby="title desc">
<title id="title">Dipesh Sapkota — profile</title><desc id="desc">Terminal profile card with role, focus, creative interests, stack, and links.</desc>
{animation}<rect x=".5" y=".5" width="719" height="329" rx="12" fill="#0d1117" stroke="#30363d"/>
<path d="M1 46h718" stroke="#30363d"/><circle cx="23" cy="23" r="5" fill="#ff7b72"/><circle cx="41" cy="23" r="5" fill="#d29922"/><circle cx="59" cy="23" r="5" fill="#3fb950"/>
<text x="360" y="28" fill="#7d8590" text-anchor="middle" font-family="monospace" font-size="12">dipesh@github: ~/profile</text>
<text x="34" y="79" fill="#58a6ff" font-family="monospace" font-size="13">$ neofetch --profile</text>
{''.join(rows)}
<path d="M34 304h652" stroke="#30363d"/>
<text x="34" y="321" fill="#7d8590" font-family="monospace" font-size="12">portfolio  <tspan fill="#58a6ff">dipeshsapkota7.com.np</tspan></text>
<text x="686" y="321" fill="#7d8590" text-anchor="end" font-family="monospace" font-size="12">github.com/Dszae</text>
</svg>'''
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({'static' if static else 'animated'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
