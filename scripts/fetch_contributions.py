#!/usr/bin/env python3
"""Fetch the public GitHub contribution calendar without authentication."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

URL = "https://github.com/users/Dszae/contributions"
OUTPUT = Path("data/contributions.json")


def main() -> int:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        print(f"Missing dependency: {exc.name}. Install scripts/requirements.txt", file=sys.stderr)
        return 2
    try:
        response = requests.get(URL, timeout=30, headers={"User-Agent": "Dszae-profile-art/1.0", "Accept": "text/html"})
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Could not fetch public contributions from {URL}: {exc}", file=sys.stderr)
        return 1

    soup = BeautifulSoup(response.text, "html.parser")
    cells = soup.select("td.ContributionCalendar-day, [data-date][data-level]")
    # GitHub currently puts each human-readable count in a sibling <tool-tip>
    # instead of on the day cell itself. Keep aria/title parsing as fallback.
    labels = {tip.get("for"): tip.get_text(" ", strip=True) for tip in soup.select("tool-tip[for]")}
    days = []
    for cell in cells:
        day = cell.get("data-date")
        if not day:
            continue
        try:
            date.fromisoformat(day)
        except ValueError:
            continue
        label = " ".join((cell.get("aria-label", ""), labels.get(cell.get("id"), "")))
        title = cell.get("title", "")
        text = " ".join((label, title, cell.get_text(" ", strip=True)))
        match = re.search(r"([\d,]+)\s+contributions?", text, re.I)
        count = int(match.group(1).replace(",", "")) if match else 0
        level = cell.get("data-level")
        if level is None:
            level_match = re.search(r"data-level=[\"']?(\d)", str(cell))
            level = level_match.group(1) if level_match else "0"
        try:
            level = max(0, min(4, int(level)))
        except (TypeError, ValueError):
            level = 0
        days.append({"date": day, "count": count, "level": level})

    if not days:
        print("No contribution day cells found in GitHub's public HTML; markup may have changed or the request was blocked.", file=sys.stderr)
        return 1
    days.sort(key=lambda item: item["date"])
    counts = [entry["count"] for entry in days]
    payload = {
        "username": "Dszae",
        "source": URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "statistics": {
            "total_contributions": sum(counts),
            "active_days": sum(count > 0 for count in counts),
            "days_in_calendar": len(days),
            "peak_day_contributions": max(counts),
            "first_day": days[0]["date"],
            "last_day": days[-1]["date"],
        },
        "days": days,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(days)} contribution days to {OUTPUT} ({payload['statistics']['total_contributions']} contributions in the visible calendar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
