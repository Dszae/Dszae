#!/usr/bin/env python3
"""Fetch GitHub activity for the profile and render stats-dark.svg / stats-light.svg.

Runs in GitHub Actions every few hours, so the numbers are fresh without a
third-party card service. Uses PROFILE_STATS_TOKEN when set (a read-only token
that also counts private commits), otherwise GITHUB_TOKEN (public activity).

    python scripts/make_stats.py --out dist                 # fetch and render
    python scripts/make_stats.py --out dist --from-json x   # render saved data
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from theme import MONO, SANS, THEMES, Theme, esc, font_faces, ink_on, language_colors, text_width

LOGIN = "Dszae"
API = "https://api.github.com/graphql"
EXCLUDED_LANGUAGES = {"Jupyter Notebook"}   # notebook JSON outweighs the code in it
TOP_LANGUAGES = 5

# --- fetching ----------------------------------------------------------------------

PROFILE_QUERY = """
query($login: String!, $merged: String!, $reviewed: String!) {
  user(login: $login) {
    createdAt
    contributionsCollection {
      totalCommitContributions
      contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
    }
  }
  merged: search(query: $merged, type: ISSUE, first: 1) { issueCount }
  reviewed: search(query: $reviewed, type: ISSUE, first: 1) { issueCount }
}"""

CALENDAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""

REPOS_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, privacy: PUBLIC) {
      pageInfo { hasNextPage endCursor }
      nodes { name isFork stargazerCount languages(first: 25, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
  }
}"""


def graphql(query: str, variables: dict, token: str, attempts: int = 3) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(API, data=body, method="POST", headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Dszae-profile-stats",
        })
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except (urllib.error.URLError, TimeoutError) as exc:
            status = getattr(exc, "code", None)
            if attempt == attempts or (status is not None and status < 500):
                raise RuntimeError(f"GitHub API request failed: {exc}") from exc
            time.sleep(2 ** attempt)
            continue
        if payload.get("errors"):
            raise RuntimeError(f"GitHub API returned errors: {payload['errors']}")
        return payload["data"]
    raise AssertionError("unreachable")


def fetch(token: str, today: date | None = None) -> dict:
    """Everything the card needs, as plain JSON-serialisable data."""
    profile = graphql(PROFILE_QUERY, {
        "login": LOGIN,
        "merged": f"author:{LOGIN} is:pr is:merged",
        "reviewed": f"reviewed-by:{LOGIN} is:pr",
    }, token)
    user = profile["user"]
    year = user["contributionsCollection"]

    # The calendar API spans at most one year per call; walk from account creation.
    created = datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    history: dict[str, int] = {}
    start = created
    while start < now:
        end = min(start + timedelta(days=365), now)
        window = graphql(CALENDAR_QUERY, {"login": LOGIN, "from": start.isoformat(), "to": end.isoformat()}, token)
        for week in window["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                history[day["date"]] = day["contributionCount"]
        start = end

    repos, cursor = [], None
    while True:
        page = graphql(REPOS_QUERY, {"login": LOGIN, "cursor": cursor}, token)["user"]["repositories"]
        repos += [
            {"name": r["name"], "fork": r["isFork"], "stars": r["stargazerCount"],
             "languages": {e["node"]["name"]: e["size"] for e in r["languages"]["edges"]}}
            for r in page["nodes"]
        ]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    return {
        "login": LOGIN,
        "fetched_at": now.isoformat(timespec="seconds"),
        "contributions_year": year["contributionCalendar"]["totalContributions"],
        "commits_year": year["totalCommitContributions"],
        "prs_merged": profile["merged"]["issueCount"],
        "prs_reviewed": profile["reviewed"]["issueCount"],
        "weeks": [[[d["date"], d["contributionCount"]] for d in w["contributionDays"]]
                  for w in year["contributionCalendar"]["weeks"]],
        "history": sorted(history.items()),
        "repos": repos,
    }


# --- computing ---------------------------------------------------------------------

@dataclass(frozen=True)
class Streak:
    days: int
    start: date | None
    end: date | None


def streaks(history: list[tuple[str, int]]) -> tuple[Streak, Streak]:
    """(current, longest). The current streak survives a quiet today, as on GitHub."""
    days = {date.fromisoformat(d): n for d, n in history}
    if not days:
        empty = Streak(0, None, None)
        return empty, empty
    first, last = min(days), max(days)

    longest = Streak(0, None, None)
    run_start, run = None, 0
    day = first
    while day <= last:
        if days.get(day, 0) > 0:
            run_start = day if run == 0 else run_start
            run += 1
            if run > longest.days:
                longest = Streak(run, run_start, day)
        else:
            run = 0
        day += timedelta(days=1)

    end = last if days.get(last, 0) > 0 else last - timedelta(days=1)
    start, count = end, 0
    while days.get(start, 0) > 0:
        count += 1
        start -= timedelta(days=1)
    current = Streak(count, start + timedelta(days=1), end) if count else Streak(0, None, None)
    return current, longest


def last_active(history: list[tuple[str, int]]) -> date | None:
    active = [date.fromisoformat(d) for d, n in history if n > 0]
    return max(active) if active else None


def weekly_totals(weeks: list[list[list]]) -> list[tuple[date, int]]:
    return [(date.fromisoformat(week[0][0]), sum(n for _, n in week)) for week in weeks if week]


def language_shares(repos: list[dict], top: int = TOP_LANGUAGES) -> list[tuple[str, float]]:
    """Largest languages by bytes across public, non-fork repositories; the tail folds into Other."""
    totals: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        for name, size in repo["languages"].items():
            if name not in EXCLUDED_LANGUAGES:
                totals[name] = totals.get(name, 0) + size
    grand = sum(totals.values())
    if not grand:
        return []
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) > top + 1:
        ranked = ranked[:top] + [("Other", sum(size for _, size in ranked[top:]))]
    return [(name, size / grand) for name, size in ranked]


@dataclass(frozen=True)
class Stats:
    contributions_year: int
    active_days_year: int
    commits_year: int
    prs_merged: int
    prs_reviewed: int
    stars: int
    public_repos: int
    current: Streak
    longest: Streak
    last_active: date | None
    weeks: list[tuple[date, int]]
    languages: list[tuple[str, float]]
    updated: date


def compute(raw: dict) -> Stats:
    current, longest = streaks(raw["history"])
    weeks = weekly_totals(raw["weeks"])
    return Stats(
        contributions_year=raw["contributions_year"],
        active_days_year=sum(1 for week in raw["weeks"] for _, n in week if n > 0),
        commits_year=raw["commits_year"],
        prs_merged=raw["prs_merged"],
        prs_reviewed=raw["prs_reviewed"],
        stars=sum(repo["stars"] for repo in raw["repos"]),
        public_repos=len(raw["repos"]),
        current=current,
        longest=longest,
        last_active=last_active(raw["history"]),
        weeks=weeks,
        languages=language_shares(raw["repos"]),
        updated=datetime.fromisoformat(raw["fetched_at"]).date(),
    )


# --- rendering ---------------------------------------------------------------------

W, PAD = 900, 32


def _day(d: date) -> str:
    return f"{d.day} {d:%b}"


def span(start: date, end: date) -> str:
    if start == end:
        return f"{_day(start)} {start.year}"
    if start.year != end.year:
        return f"{_day(start)} {start.year} – {_day(end)} {end.year}"
    return f"{_day(start)} – {_day(end)} {end.year}"


def nice_step(peak: float, ticks: int = 2) -> int:
    """Smallest 1/2/2.5/5 x 10^k step so that ``ticks`` steps reach the peak."""
    raw = max(peak, 1) / ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        step = factor * magnitude
        if step >= raw and step >= 1 and step == int(step):   # ticks are whole contributions
            return int(step)
    return max(1, int(10 * magnitude))


def _column(x: float, y_base: float, width: float, height: float, radius: float = 4) -> str:
    """Column with a rounded data end and a square foot on the baseline."""
    r = min(radius, width / 2, height)
    top = y_base - height
    return (f"M{x:.1f} {y_base:.1f}V{top + r:.1f}Q{x:.1f} {top:.1f} {x + r:.1f} {top:.1f}"
            f"H{x + width - r:.1f}Q{x + width:.1f} {top:.1f} {x + width:.1f} {top + r:.1f}V{y_base:.1f}Z")


def _tile(x: float, y: float, label: str, value: str, unit: str, sub: str, theme: Theme) -> str:
    unit_svg = ""
    if unit:
        unit_x = x + text_width(value, 26, 700) + 5
        unit_svg = f'<text x="{unit_x:.1f}" y="{y + 31}" class="s" font-size="14" font-weight="500" fill="{theme.text_secondary}">{esc(unit)}</text>'
    return (
        f'<text x="{x}" y="{y}" class="s" font-size="13" font-weight="500" fill="{theme.text_secondary}">{esc(label)}</text>'
        f'<text x="{x}" y="{y + 31}" class="s" font-size="26" font-weight="700" fill="{theme.text_primary}">{esc(value)}</text>'
        f'{unit_svg}'
        f'<text x="{x}" y="{y + 50}" class="m" font-size="11.5" fill="{theme.text_muted}">{esc(sub)}</text>'
    )


def render(stats: Stats, theme: Theme) -> str:
    out: list[str] = []
    right = W - PAD

    # Header
    out.append(f'<text x="{PAD}" y="48" class="s" font-size="18" font-weight="700" fill="{theme.text_primary}">GitHub activity</text>')
    out.append(f'<text x="{right}" y="48" text-anchor="end" class="m" font-size="12" fill="{theme.text_muted}">'
               f'@{esc(LOGIN)} · updated {_day(stats.updated)} {stats.updated.year}</text>')

    # Hero figure and tiles
    out.append(f'<text x="{PAD}" y="98" class="s" font-size="13" font-weight="500" fill="{theme.text_secondary}">Contributions in the last year</text>')
    out.append(f'<text x="{PAD - 2}" y="156" class="s" font-size="54" font-weight="700" letter-spacing="-1" fill="{theme.text_primary}">{stats.contributions_year:,}</text>')
    out.append(f'<text x="{PAD}" y="184" class="m" font-size="11.5" fill="{theme.text_muted}">{stats.active_days_year} active days</text>')
    out.append(f'<path d="M286 82V228" stroke="{theme.grid}"/>')

    current_sub = (f"since {_day(stats.current.start)}" if stats.current.days and stats.current.start
                   else f"last active {_day(stats.last_active)}" if stats.last_active else "no activity yet")
    longest_sub = span(stats.longest.start, stats.longest.end) if stats.longest.start else "–"
    tiles = [
        ("Commits", f"{stats.commits_year:,}", "", "last 12 months"),
        ("PRs merged", f"{stats.prs_merged:,}", "", "all time"),
        ("PR reviews", f"{stats.prs_reviewed:,}", "", "all time"),
        ("Stars earned", f"{stats.stars:,}", "", f"{stats.public_repos} public repositories"),
        ("Longest streak", f"{stats.longest.days:,}", "day" if stats.longest.days == 1 else "days", longest_sub),
        ("Current streak", f"{stats.current.days:,}", "day" if stats.current.days == 1 else "days", current_sub),
    ]
    col_w = (right - 314) / 3
    for i, (label, value, unit, sub) in enumerate(tiles):
        out.append(_tile(314 + (i % 3) * col_w, 96 + (i // 3) * 82, label, value, unit, sub, theme))

    # Weekly contributions: single series, columns, peak and latest week labelled.
    top_y = 272
    out.append(f'<text x="{PAD}" y="{top_y}" class="s" font-size="14" font-weight="600" fill="{theme.text_primary}">Contributions per week</text>')
    plot_left, plot_right, plot_top, base = PAD + 34, right, top_y + 34, top_y + 150
    weeks = stats.weeks
    peak = max((n for _, n in weeks), default=0)
    step = nice_step(peak)
    scale_top = step * 2
    for tick in (0, step, step * 2):
        y = base - (base - plot_top) * tick / scale_top
        out.append(f'<path d="M{plot_left} {y:.1f}H{plot_right}" stroke="{theme.grid}"/>')
        out.append(f'<text x="{plot_left - 8}" y="{y + 4:.1f}" text-anchor="end" class="m tab" font-size="11" fill="{theme.text_muted}">{tick:,}</text>')
    slot = (plot_right - plot_left) / max(len(weeks), 1)
    bar = min(24.0, slot - 4)
    peak_index = max(range(len(weeks)), key=lambda i: weeks[i][1]) if weeks else None
    months_seen: set[tuple[int, int]] = set()
    last_label_x = -100.0
    for i, (start, total) in enumerate(weeks):
        x = plot_left + i * slot + (slot - bar) / 2
        if total > 0:
            height = max(2.0, (base - plot_top) * total / scale_top)
            out.append(f'<path d="{_column(x, base, bar, height)}" fill="{theme.accent}"/>')
        first_of_month = next((start + timedelta(days=k) for k in range(7) if (start + timedelta(days=k)).day == 1), None)
        if first_of_month and (first_of_month.year, first_of_month.month) not in months_seen and x - last_label_x > 30:
            months_seen.add((first_of_month.year, first_of_month.month))
            last_label_x = x
            out.append(f'<text x="{x:.1f}" y="{base + 20}" class="m" font-size="11" fill="{theme.text_muted}">{first_of_month:%b}</text>')
    labelled = []
    if peak_index is not None and peak > 0:
        labelled.append((peak_index, f"peak {weeks[peak_index][1]:,}"))
    if weeks and len(weeks) - 1 != peak_index:
        labelled.append((len(weeks) - 1, f"this week {weeks[-1][1]:,}"))
    def column_top(index: int) -> float:
        total = weeks[index][1]
        return base - max(2.0, (base - plot_top) * total / scale_top) if total > 0 else base

    for i, label in labelled:
        width = text_width(label, 11, mono=True)
        cx = plot_left + i * slot + slot / 2
        x0, x1, anchor = cx - width / 2, cx + width / 2, "middle"
        if x1 > plot_right:
            anchor, cx = "end", plot_left + i * slot + (slot + bar) / 2
            x0, x1 = cx - width, cx
        # Sit above the tallest column the label spans, so it never collides with a neighbour.
        spanned = [j for j in range(len(weeks)) if plot_left + j * slot < x1 and plot_left + (j + 1) * slot > x0]
        y = min(column_top(j) for j in spanned) - 8
        out.append(f'<text x="{cx:.1f}" y="{y:.1f}" text-anchor="{anchor}" class="m" font-size="11" fill="{theme.text_secondary}">{esc(label)}</text>')

    # Languages: tall segmented bar, share printed inside where it fits, legend below.
    lang_y = base + 66
    out.append(f'<text x="{PAD}" y="{lang_y}" class="s" font-size="14" font-weight="600" fill="{theme.text_primary}">Languages</text>')
    out.append(f'<text x="{right}" y="{lang_y}" text-anchor="end" class="m" font-size="11.5" fill="{theme.text_muted}">public repositories · share of code</text>')
    colors = language_colors([n for n, _ in stats.languages if n != "Other"], theme)
    colors["Other"] = theme.other
    bar_y, gap, total_w = lang_y + 16, 2, right - PAD
    usable = total_w - gap * max(len(stats.languages) - 1, 0)
    x = float(PAD)
    printed: set[str] = set()
    for name, share in stats.languages:
        width = usable * share
        if width <= 0:
            continue
        fill = colors[name]
        out.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{width:.1f}" height="28" rx="{min(4, width / 2):.1f}" fill="{fill}"/>')
        label = f"{share * 100:.1f}%"
        if text_width(label, 12, 600) + 16 <= width:
            printed.add(name)
            out.append(f'<text x="{x + 8:.1f}" y="{bar_y + 18.5}" class="s tab" font-size="12" font-weight="600" fill="{ink_on(fill)}">{label}</text>')
        x += width + gap
    lx, ly = float(PAD), bar_y + 52
    for name, share in stats.languages:
        text = name if name in printed else f"{name} {share * 100:.1f}%"
        item_w = 16 + text_width(text, 13, 500) + 22
        if lx + item_w > right + 22 and lx > PAD:
            lx, ly = float(PAD), ly + 22
        out.append(f'<rect x="{lx:.1f}" y="{ly - 10}" width="10" height="10" rx="3" fill="{colors[name]}"/>')
        out.append(f'<text x="{lx + 16:.1f}" y="{ly}" class="s" font-size="13" font-weight="500" fill="{theme.text_secondary}">{esc(text)}</text>')
        lx += item_w
    height = ly + 30

    summary = (f"{stats.contributions_year:,} contributions in the last year, {stats.commits_year:,} commits, "
               f"{stats.prs_merged:,} pull requests merged, {stats.prs_reviewed:,} reviews, {stats.stars:,} stars. "
               f"Longest streak {stats.longest.days} days, current streak {stats.current.days} days. Languages: "
               + ", ".join(f"{n} {s * 100:.1f}%" for n, s in stats.languages) + ".")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height:.0f}" width="{W}" height="{height:.0f}" role="img" aria-labelledby="t d">'
        f'<title id="t">GitHub activity for {esc(LOGIN)}</title><desc id="d">{esc(summary)}</desc>'
        f'<style>{font_faces()}.s{{font-family:{SANS}}}.m{{font-family:{MONO}}}.tab{{font-variant-numeric:tabular-nums}}</style>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{height - 1:.0f}" rx="16" fill="{theme.surface}" stroke="{theme.border}"/>'
        + "".join(out) + "</svg>\n"
    )


def to_json(stats: Stats) -> dict:
    data = asdict(stats)
    data["weeks"] = [[d.isoformat(), n] for d, n in stats.weeks]
    data["languages"] = [[n, round(s, 4)] for n, s in stats.languages]
    for key in ("current", "longest"):
        data[key] = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in data[key].items()}
    for key in ("last_active", "updated"):
        data[key] = data[key].isoformat() if data[key] else None
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="directory for the SVGs and stats.json")
    parser.add_argument("--from-json", type=Path, help="render previously fetched raw data instead of calling the API")
    parser.add_argument("--save-raw", type=Path, help="also write the raw API data here")
    args = parser.parse_args()

    if args.from_json:
        raw = json.loads(args.from_json.read_text(encoding="utf-8"))
    else:
        token = os.environ.get("PROFILE_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            print("Set GITHUB_TOKEN (or PROFILE_STATS_TOKEN) to read the GitHub API.", file=sys.stderr)
            return 2
        try:
            raw = fetch(token)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 1
        if args.save_raw:
            args.save_raw.write_text(json.dumps(raw, indent=1) + "\n", encoding="utf-8")

    stats = compute(raw)
    args.out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (args.out / f"stats-{theme.name}.svg").write_text(render(stats, theme), encoding="utf-8")
    (args.out / "stats.json").write_text(json.dumps(to_json(stats), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote stats cards to {args.out}: {stats.contributions_year:,} contributions, "
          f"{stats.commits_year:,} commits, {stats.prs_merged} PRs merged, {stats.stars} stars, "
          f"streak {stats.current.days} (longest {stats.longest.days})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
