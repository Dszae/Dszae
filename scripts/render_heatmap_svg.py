#!/usr/bin/env python3
"""Render data/contributions.json as a compact GitHub-style contribution calendar."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

INPUT = Path("data/contributions.json")
OUTPUT = Path("contrib-heatmap.svg")
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def main() -> int:
    try:
        payload = json.loads(INPUT.read_text(encoding="utf-8"))
        days = {date.fromisoformat(item["date"]): item for item in payload["days"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot read contribution data at {INPUT}: {exc}")
        return 1
    if not days:
        print("Contribution data contains no days")
        return 1

    last = max(days)
    # Align the 53-column display to Sunday and include the trailing days of the year view.
    end = last + timedelta(days=(6 - last.weekday()) % 7)
    start = end - timedelta(days=7 * 52 + 6)
    start -= timedelta(days=(start.weekday() + 1) % 7)
    total_weeks = ((end - start).days + 1) // 7
    cell, gap, left, top = 11, 3, 42, 45
    width = left + total_weeks * (cell + gap) + 12
    height = top + 7 * (cell + gap) + 36
    nodes = []
    month_seen = set()
    for week in range(total_weeks):
        for weekday in range(7):
            current = start + timedelta(days=week * 7 + weekday)
            entry = days.get(current, {"count": 0, "level": 0})
            level = max(0, min(4, int(entry.get("level", 0))))
            x, y = left + week * (cell + gap), top + weekday * (cell + gap)
            nodes.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{PALETTE[level]}"><title>{current.isoformat()}: {int(entry.get("count", 0))} contributions</title></rect>')
            month_key = (current.year, current.month)
            if current.day <= 7 and month_key not in month_seen and current >= start:
                month_seen.add(month_key)
                nodes.append(f'<text x="{x}" y="20" fill="#7d8590" font-family="sans-serif" font-size="11">{current.strftime("%b")}</text>')
    stats = payload.get("statistics", {})
    summary = f"{stats.get('total_contributions', 0):,} contributions · {stats.get('active_days', 0)} active days · public GitHub calendar"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">GitHub contribution calendar for Dszae</title><desc id="desc">{escape(summary)}. Each square represents a day.</desc>
<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="8" fill="#0d1117" stroke="#30363d"/>
<text x="12" y="{top+10}" fill="#7d8590" font-family="sans-serif" font-size="10">Mon</text><text x="12" y="{top+4*(cell+gap)+10}" fill="#7d8590" font-family="sans-serif" font-size="10">Fri</text>
{''.join(nodes)}
<text x="{left}" y="{height-11}" fill="#8b949e" font-family="sans-serif" font-size="11">{escape(summary)}</text>
<g transform="translate({width-145},{height-20})">{''.join(f'<rect x="{i*14}" y="0" width="10" height="10" rx="2" fill="{color}"/>' for i, color in enumerate(PALETTE))}<text x="75" y="9" fill="#7d8590" font-family="sans-serif" font-size="10">Less</text><text x="137" y="9" fill="#7d8590" font-family="sans-serif" font-size="10">More</text></g>
</svg>'''
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(days)} source days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
