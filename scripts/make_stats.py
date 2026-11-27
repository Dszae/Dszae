#!/usr/bin/env python3
"""Fetch GitHub activity and render the stats cards and the terminal profile card.

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
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import card
from theme import MONO, SANS, THEMES, Theme, esc, font_faces, ink_on, language_colors, text_width

LOGIN = "Dszae"
API = "https://api.github.com/graphql"
EXCLUDED_LANGUAGES = {"Jupyter Notebook"}   # notebook JSON outweighs the code in it
TOP_LANGUAGES = 5
DAYS_SHOWN = 31                             # daily activity graph: about one month
RANK_LEVELS = ((1, "S"), (12.5, "A+"), (25, "A"), (37.5, "A-"), (50, "B+"),
               (62.5, "B"), (75, "B-"), (87.5, "C+"), (100, "C"))

# --- fetching ----------------------------------------------------------------------

PROFILE_QUERY = """
query($login: String!, $merged: String!, $reviewed: String!) {
  user(login: $login) {
    id
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(first: 1, includeUserRepositories: false,
      contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, PULL_REQUEST_REVIEW, REPOSITORY]) { totalCount }
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
      totalCommitContributions
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""

REPOS_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, privacy: PUBLIC) {
      pageInfo { hasNextPage endCursor }
      nodes { name isFork stargazerCount forkCount languages(first: 25, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
    }
  }
}"""

# Additions and deletions of the user's own commits on a repository's default branch.
HISTORY_QUERY = """
query($owner: String!, $name: String!, $author: ID!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, after: $cursor, author: {id: $author}) {
        pageInfo { hasNextPage endCursor }
        nodes { additions deletions }
      }
    } } }
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
    commits_all = 0
    start = created
    while start < now:
        end = min(start + timedelta(days=365), now)
        window = graphql(CALENDAR_QUERY, {"login": LOGIN, "from": start.isoformat(), "to": end.isoformat()}, token)
        commits_all += window["user"]["contributionsCollection"]["totalCommitContributions"]
        for week in window["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                history[day["date"]] = day["contributionCount"]
        start = end

    repos, cursor = [], None
    while True:
        page = graphql(REPOS_QUERY, {"login": LOGIN, "cursor": cursor}, token)["user"]["repositories"]
        repos += [
            {"name": r["name"], "fork": r["isFork"], "stars": r["stargazerCount"], "forks": r["forkCount"],
             "languages": {e["node"]["name"]: e["size"] for e in r["languages"]["edges"]}}
            for r in page["nodes"]
        ]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    added = deleted = 0
    for repo in repos:
        if repo["fork"]:
            continue
        cursor = None
        while True:
            data = graphql(HISTORY_QUERY, {"owner": LOGIN, "name": repo["name"], "author": user["id"], "cursor": cursor}, token)
            branch = data["repository"]["defaultBranchRef"]
            if not branch:
                break                                   # empty repository
            history_page = branch["target"]["history"]
            added += sum(n["additions"] for n in history_page["nodes"])
            deleted += sum(n["deletions"] for n in history_page["nodes"])
            if not history_page["pageInfo"]["hasNextPage"]:
                break
            cursor = history_page["pageInfo"]["endCursor"]

    return {
        "login": LOGIN,
        "fetched_at": now.isoformat(timespec="seconds"),
        "contributions_year": year["contributionCalendar"]["totalContributions"],
        "commits_year": year["totalCommitContributions"],
        "commits_all": commits_all,
        "followers": user["followers"]["totalCount"],
        "contributed_to": user["repositoriesContributedTo"]["totalCount"],
        "loc_added": added,
        "loc_deleted": deleted,
        "prs_merged": profile["merged"]["issueCount"],
        "prs_reviewed": profile["reviewed"]["issueCount"],
        "prs_total": user["pullRequests"]["totalCount"],
        "issues_total": user["issues"]["totalCount"],
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
    commits_all: int = 0
    followers: int = 0
    contributed_to: int = 0
    loc_added: int = 0
    loc_deleted: int = 0
    forks: int = 0
    contributions_all: int = 0
    prs_total: int = 0
    issues_total: int = 0
    days: list[tuple[date, int]] = field(default_factory=list)
    joined: date | None = None


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
        commits_all=raw.get("commits_all", raw["commits_year"]),
        followers=raw.get("followers", 0),
        contributed_to=raw.get("contributed_to", 0),
        loc_added=raw.get("loc_added", 0),
        loc_deleted=raw.get("loc_deleted", 0),
        forks=sum(repo.get("forks", 0) for repo in raw["repos"]),
        contributions_all=sum(n for _, n in raw["history"]),
        prs_total=raw.get("prs_total", raw["prs_merged"]),
        issues_total=raw.get("issues_total", 0),
        days=[(date.fromisoformat(d), n) for d, n in raw["history"][-DAYS_SHOWN:]],
        joined=date.fromisoformat(raw["history"][0][0]) if raw["history"] else None,
    )


@dataclass(frozen=True)
class Rank:
    level: str
    percentile: float          # lower is better: 5.0 means top 5%


def _exponential_cdf(x: float) -> float:
    return 1 - 2 ** -x


def _log_normal_cdf(x: float) -> float:
    return x / (1 + x)


def rank(stats: Stats) -> Rank:
    """Grade on the github-readme-stats scale, so it reads like the familiar card.

    Each count is scored against a typical GitHub user (the median) and weighted;
    the weights, medians and grade bands are the ones that card uses.
    """
    scored = [
        (2, _exponential_cdf(stats.commits_year / 250)),
        (3, _exponential_cdf(stats.prs_total / 50)),
        (1, _exponential_cdf(stats.issues_total / 25)),
        (1, _exponential_cdf(stats.prs_reviewed / 2)),
        (4, _log_normal_cdf(stats.stars / 50)),
        (1, _log_normal_cdf(stats.followers / 10)),
    ]
    percentile = (1 - sum(w * s for w, s in scored) / sum(w for w, _ in scored)) * 100
    for threshold, level in RANK_LEVELS:
        if percentile <= threshold:
            return Rank(level, percentile)
    return Rank(RANK_LEVELS[-1][1], percentile)


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


def _card(title: str, summary: str, height: float, body: list[str], theme: Theme, defs: str = "") -> str:
    """Wrap a 900px-wide card body in the shared frame, fonts and accessible title."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height:.0f}" width="{W}" height="{height:.0f}" role="img" aria-labelledby="t d">'
        f'<title id="t">{esc(title)}</title><desc id="d">{esc(summary)}</desc>'
        f'<style>{font_faces()}.s{{font-family:{SANS}}}.m{{font-family:{MONO}}}.tab{{font-variant-numeric:tabular-nums}}</style>'
        f'{defs}<rect x=".5" y=".5" width="{W - 1}" height="{height - 1:.0f}" rx="16" fill="{theme.surface}" stroke="{theme.border}"/>'
        + "".join(body) + "</svg>\n"
    )


def _header(title: str, note: str, theme: Theme) -> list[str]:
    return [
        f'<text x="{PAD}" y="48" class="s" font-size="18" font-weight="700" fill="{theme.text_primary}">{esc(title)}</text>',
        f'<text x="{W - PAD}" y="48" text-anchor="end" class="m" font-size="12" fill="{theme.text_muted}">{esc(note)}</text>',
    ]


def smooth_path(points: list[tuple[float, float]]) -> str:
    """Monotone cubic curve through the points: it never overshoots a point, so it never dips below zero."""
    if len(points) < 2:
        return "".join(f"M{x:.1f} {y:.1f}" for x, y in points)
    slopes = [(y1 - y0) / (x1 - x0) for (x0, y0), (x1, y1) in zip(points, points[1:])]
    tangents = [slopes[0]]
    for before, after in zip(slopes, slopes[1:]):
        tangents.append(0.0 if before * after <= 0 else 2 * before * after / (before + after))
    tangents.append(slopes[-1])
    d = [f"M{points[0][0]:.1f} {points[0][1]:.1f}"]
    for i, ((x0, y0), (x1, y1)) in enumerate(zip(points, points[1:])):
        h = (x1 - x0) / 3
        d.append(f"C{x0 + h:.1f} {y0 + tangents[i] * h:.1f} {x1 - h:.1f} {y1 - tangents[i + 1] * h:.1f} {x1:.1f} {y1:.1f}")
    return "".join(d)


def render_activity(stats: Stats, theme: Theme) -> str:
    """Daily contributions over the last month as a smooth line with a soft area beneath."""
    out = _header("Daily contributions", f"@{LOGIN} · last {len(stats.days)} days", theme)
    days = stats.days
    total = sum(n for _, n in days)
    active = sum(1 for _, n in days if n > 0)
    today = days[-1][1] if days else 0
    out.append(f'<text x="{PAD}" y="76" class="m" font-size="11.5" fill="{theme.text_muted}">'
               f'{total:,} contributions · active on {active} of {len(days)} days · today {today:,}</text>')

    plot_left, plot_right, plot_top, base = PAD + 34, W - PAD, 116, 286
    peak = max((n for _, n in days), default=0)
    # Three to five gridline steps, whichever leaves the least empty space above the peak.
    ticks, step = min(((t, nice_step(peak, ticks=t)) for t in (3, 4, 5)), key=lambda ts: (ts[0] * ts[1], ts[0]))
    scale_top = step * ticks
    for k in range(ticks + 1):
        tick = step * k
        y = base - (base - plot_top) * tick / scale_top
        out.append(f'<path d="M{plot_left} {y:.1f}H{plot_right}" stroke="{theme.grid}"/>')
        out.append(f'<text x="{plot_left - 8}" y="{y + 4:.1f}" text-anchor="end" class="m tab" font-size="11" fill="{theme.text_muted}">{tick:,}</text>')

    inset = 12
    gap = (plot_right - plot_left - 2 * inset) / max(len(days) - 1, 1)
    points = [(plot_left + inset + i * gap, base - (base - plot_top) * n / scale_top) for i, (_, n) in enumerate(days)]
    defs = ""
    if points:
        line = smooth_path(points)
        defs = (f'<defs><linearGradient id="area" x1="0" y1="{plot_top}" x2="0" y2="{base}" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0" stop-color="{theme.accent}" stop-opacity=".30"/>'
                f'<stop offset="1" stop-color="{theme.accent}" stop-opacity="0"/></linearGradient></defs>')
        out.append(f'<path d="{line}L{points[-1][0]:.1f} {base}L{points[0][0]:.1f} {base}Z" fill="url(#area)"/>')
        out.append(f'<path d="{line}" fill="none" stroke="{theme.accent}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')

    peak_index = max(range(len(days)), key=lambda i: days[i][1]) if days and peak > 0 else None
    for i, ((x, y), (day, n)) in enumerate(zip(points, days)):
        if i == peak_index:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{theme.amber_mark}" stroke="{theme.surface}" stroke-width="2"/>')
        else:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{theme.surface}" stroke="{theme.accent}" stroke-width="2"/>')
        out.append(f'<text x="{x:.1f}" y="{base + 20}" text-anchor="middle" class="m tab" font-size="10.5" fill="{theme.text_muted}">{day.day}</text>')
        if i == 0 or day.day == 1:
            out.append(f'<text x="{x:.1f}" y="{base + 37}" text-anchor="middle" class="s" font-size="11.5" font-weight="600" fill="{theme.text_secondary}">{day:%b}</text>')
    if peak_index is not None:
        x, y = points[peak_index]
        label = f"peak {peak:,} · {_day(days[peak_index][0])}"
        width = text_width(label, 11, mono=True)
        anchor = "middle"
        if x + width / 2 > plot_right:
            anchor = "end"
        elif x - width / 2 < plot_left:
            anchor = "start"
        out.append(f'<text x="{x:.1f}" y="{y - 12:.1f}" text-anchor="{anchor}" class="m" font-size="11" fill="{theme.text_secondary}">{esc(label)}</text>')

    first = _day(days[0][0]) if days else "–"
    last = _day(days[-1][0]) if days else "–"
    summary = (f"Daily contributions from {first} to {last}: {total:,} in total, active on {active} of {len(days)} days, "
               f"busiest day {peak:,}" + (f" on {_day(days[peak_index][0])}" if peak_index is not None else "") + ".")
    return _card(f"Daily GitHub contributions for {LOGIN}", summary, base + 56, out, theme, defs)


def render_overview(stats: Stats, theme: Theme) -> str:
    """All-time totals in two columns, with the rank grade in a ring beside them."""
    grade = rank(stats)
    since = f" · since {stats.joined.year}" if stats.joined else ""
    out = _header("All-time overview", f"@{LOGIN}{since}", theme)

    rows = [
        ("Contributions", f"{stats.contributions_all:,}"),
        ("Commits", f"{stats.commits_all:,}"),
        ("Pull requests opened", f"{stats.prs_total:,}"),
        ("Issues opened", f"{stats.issues_total:,}"),
        ("Stars earned", f"{stats.stars:,}"),
        ("Forks of my repositories", f"{stats.forks:,}"),
        ("Lines of code changed", f"{stats.loc_added + stats.loc_deleted:,}"),
        ("Repositories contributed to", f"{stats.contributed_to:,}"),
    ]
    divider_x = 640
    col_gap = 44
    col_w = (divider_x - 40 - PAD - col_gap) / 2
    row_h, top = 40, 78
    per_col = (len(rows) + 1) // 2
    for i, (label, value) in enumerate(rows):
        col, row = divmod(i, per_col)
        x0 = PAD + col * (col_w + col_gap)
        y = top + row * row_h
        out.append(f'<text x="{x0:.1f}" y="{y + 25}" class="s" font-size="13.5" font-weight="500" fill="{theme.text_secondary}">{esc(label)}</text>')
        out.append(f'<text x="{x0 + col_w:.1f}" y="{y + 25}" text-anchor="end" class="s tab" font-size="16" font-weight="700" fill="{theme.text_primary}">{esc(value)}</text>')
        if row < per_col - 1:
            out.append(f'<path d="M{x0:.1f} {y + row_h:.1f}H{x0 + col_w:.1f}" stroke="{theme.grid}"/>')
    bottom = top + per_col * row_h
    out.append(f'<path d="M{divider_x} {top + 6}V{bottom - 6}" stroke="{theme.grid}"/>')

    # Rank ring: the filled share is how far ahead of the typical user the profile sits.
    cx, cy, r = (divider_x + W - PAD) / 2, top + (bottom - top) / 2 - 10, 52
    circumference = 2 * math.pi * r
    filled = max(0.02, min(1.0, 1 - grade.percentile / 100))
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="none" stroke="{theme.grid}" stroke-width="10"/>')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="none" stroke="{theme.accent}" stroke-width="10" stroke-linecap="round" '
               f'stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{circumference * (1 - filled):.1f}" transform="rotate(-90 {cx:.1f} {cy:.1f})"/>')
    out.append(f'<text x="{cx:.1f}" y="{cy + 12:.1f}" text-anchor="middle" class="s" font-size="34" font-weight="800" fill="{theme.text_primary}">{esc(grade.level)}</text>')
    top_share = max(1, round(grade.percentile))
    out.append(f'<text x="{cx:.1f}" y="{cy + r + 30:.1f}" text-anchor="middle" class="m" font-size="11.5" fill="{theme.text_muted}">rank · top {top_share}%</text>')

    summary = ("All time: " + ", ".join(f"{label.lower()} {value}" for label, value in rows)
               + f". Rank {grade.level} (top {top_share}%) on the github-readme-stats scale.")
    return _card(f"All-time GitHub overview for {LOGIN}", summary, bottom + 26, out, theme)


def to_json(stats: Stats) -> dict:
    data = asdict(stats)
    data["weeks"] = [[d.isoformat(), n] for d, n in stats.weeks]
    data["days"] = [[d.isoformat(), n] for d, n in stats.days]
    grade = rank(stats)
    data["rank"] = {"level": grade.level, "percentile": round(grade.percentile, 2)}
    data["languages"] = [[n, round(s, 4)] for n, s in stats.languages]
    for key in ("current", "longest"):
        data[key] = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in data[key].items()}
    for key in ("last_active", "updated", "joined"):
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
        (args.out / f"card-{theme.name}.svg").write_text(card.render(stats, theme), encoding="utf-8")
        (args.out / f"activity-{theme.name}.svg").write_text(render_activity(stats, theme), encoding="utf-8")
        (args.out / f"overview-{theme.name}.svg").write_text(render_overview(stats, theme), encoding="utf-8")
    (args.out / "stats.json").write_text(json.dumps(to_json(stats), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote stats cards to {args.out}: {stats.contributions_year:,} contributions, "
          f"{stats.commits_year:,} commits, {stats.prs_merged} PRs merged, {stats.stars} stars, "
          f"{stats.followers} followers, {stats.loc_added - stats.loc_deleted:,} lines of code, "
          f"streak {stats.current.days} (longest {stats.longest.days}), rank {rank(stats).level}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
