#!/usr/bin/env python3
"""Refresh the "Writing" list in README.md from the latest DEV articles.

Each article links to its copy on dipeshsapkota7.com.np when that page exists,
otherwise to DEV. The README is rewritten only when the list changes. A failed
fetch leaves the README untouched and prints a workflow warning instead of failing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEV_API = "https://dev.to/api/articles?username=dszae&per_page={count}"
PORTFOLIO_POST = "https://www.dipeshsapkota7.com.np/blog/{slug}"
USER_AGENT = "Dszae-profile-readme/1.0 (+https://github.com/Dszae/Dszae)"
START, END = "<!-- WRITING:START -->", "<!-- WRITING:END -->"


def _get(url: str, method: str = "GET"):
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    return urllib.request.urlopen(request, timeout=20)


def fetch_articles(count: int) -> list[dict]:
    with _get(DEV_API.format(count=count)) as response:
        return json.load(response)


def portfolio_has(slug: str) -> bool:
    try:
        with _get(PORTFOLIO_POST.format(slug=slug), method="HEAD") as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def format_entry(article: dict, link: str) -> str:
    title = article["title"].strip().lstrip("#").strip()
    title = title.replace("[", "\\[").replace("]", "\\]")
    published = datetime.fromisoformat(article["published_at"].replace("Z", "+00:00"))
    minutes = article.get("reading_time_minutes")
    meta = f"{published.day} {published:%b %Y}" + (f" · {minutes} min read" if minutes else "")
    return f"- [{title}]({link}) <sub>{meta}</sub>"


def replace_block(readme: str, entries: list[str]) -> str:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(readme):
        raise ValueError(f"README has no {START} ... {END} block")
    block = START + "\n" + "\n".join(entries) + "\n" + END
    return pattern.sub(lambda _: block, readme, count=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    try:
        articles = fetch_articles(args.count)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"::warning::Could not fetch DEV articles, README left unchanged: {exc}")
        return 0
    if not articles:
        print("::warning::DEV returned no articles, README left unchanged")
        return 0

    entries = []
    for article in articles[: args.count]:
        slug = article.get("slug", "")
        link = PORTFOLIO_POST.format(slug=slug) if slug and portfolio_has(slug) else article["url"]
        entries.append(format_entry(article, link))

    readme = args.readme.read_text(encoding="utf-8")
    updated = replace_block(readme, entries)
    if updated == readme:
        print("Writing list unchanged")
        return 0
    args.readme.write_text(updated, encoding="utf-8")
    print(f"Updated Writing list with {len(entries)} articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
