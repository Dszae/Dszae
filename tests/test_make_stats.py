"""Stats maths and rendering, on generated data (no network)."""

import dataclasses
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import pytest

import make_stats
from make_stats import (Streak, compute, language_shares, nice_step, rank, render, render_activity,
                        render_overview, smooth_path, span, streaks)
from theme import DARK, LIGHT, language_colors


def history(counts, last=date(2026, 11, 24)):
    """counts[0] is the oldest day, counts[-1] is ``last``."""
    first = last - timedelta(days=len(counts) - 1)
    return [((first + timedelta(days=i)).isoformat(), n) for i, n in enumerate(counts)]


def test_longest_streak_and_its_dates():
    _, longest = streaks(history([1, 1, 0, 2, 3, 4, 0, 1]))
    assert longest == Streak(3, date(2026, 11, 20), date(2026, 11, 22))


def test_current_streak_counts_through_today():
    current, _ = streaks(history([0, 5, 1, 2]))
    assert current == Streak(3, date(2026, 11, 22), date(2026, 11, 24))


def test_a_quiet_today_does_not_break_the_current_streak():
    current, _ = streaks(history([0, 5, 1, 0]))
    assert current == Streak(2, date(2026, 11, 22), date(2026, 11, 23))


def test_two_quiet_days_end_the_current_streak():
    current, longest = streaks(history([4, 4, 0, 0]))
    assert current.days == 0
    assert longest.days == 2


def test_no_history():
    assert streaks([]) == (Streak(0, None, None), Streak(0, None, None))


def repos(*entries):
    return [{"name": f"r{i}", "fork": fork, "stars": 1, "languages": langs} for i, (langs, fork) in enumerate(entries)]


def test_languages_skip_forks_and_notebooks():
    shares = dict(language_shares(repos(
        ({"Python": 300, "Jupyter Notebook": 10_000}, False),
        ({"C++": 100}, False),
        ({"Rust": 5_000}, True),
    )))
    assert shares == {"Python": 0.75, "C++": 0.25}


def test_language_tail_folds_into_other():
    shares = language_shares(repos(({f"L{i}": 100 - i for i in range(9)}, False)), top=5)
    assert [name for name, _ in shares] == ["L0", "L1", "L2", "L3", "L4", "Other"]
    assert sum(share for _, share in shares) == pytest.approx(1)


def test_six_languages_are_shown_without_other():
    shares = language_shares(repos(({f"L{i}": 10 for i in range(6)}, False)), top=5)
    assert "Other" not in dict(shares) and len(shares) == 6


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_a_language_keeps_its_colour_whatever_its_rank(theme):
    first = language_colors(["JavaScript", "TypeScript", "Zig"], theme)
    second = language_colors(["Zig", "TypeScript", "JavaScript"], theme)
    assert first == second
    assert len(set(first.values())) == 3


@pytest.mark.parametrize("peak,expected", [(0, 1), (1, 1), (5, 5), (7, 5), (499, 250), (1001, 1000), (180, 100)])
def test_nice_step_reaches_the_peak_in_two_steps(peak, expected):
    step = nice_step(peak)
    assert step == expected and step * 2 >= peak


def test_span_formats():
    assert span(date(2026, 9, 16), date(2026, 10, 14)) == "16 Sep – 14 Oct 2026"
    assert span(date(2025, 12, 28), date(2026, 1, 3)) == "28 Dec 2025 – 3 Jan 2026"


def raw_data():
    last = date(2026, 11, 24)
    days = [((last - timedelta(days=i)).isoformat(), (i * 7) % 5) for i in range(370)][::-1]
    weeks, week = [], []
    for d, n in days[-371:]:
        week.append([d, n])
        if date.fromisoformat(d).weekday() == 5:
            weeks.append(week)
            week = []
    if week:
        weeks.append(week)
    return {
        "login": "Dszae", "fetched_at": "2026-11-24T08:00:00+00:00",
        "contributions_year": sum(n for _, n in days[-365:]), "commits_year": 1234,
        "prs_merged": 146, "prs_reviewed": 24, "weeks": weeks, "history": days,
        "repos": repos(({"TypeScript": 500, "Python": 300, "C++": 50}, False), ({"Go": 9}, True)),
    }


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_render_is_valid_svg_with_the_numbers(theme):
    stats = compute(raw_data())
    svg = render(stats, theme)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    text = " ".join(t for t in root.itertext())
    for expected in (f"{stats.contributions_year:,}", "1,234", "146", "24", "TypeScript"):
        assert expected in text
    assert stats.stars == 2 and stats.public_repos == 2


def test_week_labels_sit_above_every_column_they_cross():
    raw = raw_data()
    raw["weeks"][-1] = [[d, 1] for d, _ in raw["weeks"][-1]]           # a short final week
    raw["weeks"][-2] = [[d, 40] for d, _ in raw["weeks"][-2]]          # a tall neighbour
    svg = render(compute(raw), DARK)
    label_y = float(re.search(r'y="([\d.]+)"[^>]*>this week', svg).group(1))
    tops = [float(m) for m in re.findall(r'<path d="M[\d.]+ [\d.]+V([\d.]+)Q', svg)]
    assert label_y < min(tops[-2:])


def test_main_needs_a_token(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("PROFILE_STATS_TOKEN", raising=False)
    monkeypatch.setattr("sys.argv", ["make_stats.py", "--out", str(tmp_path)])
    assert make_stats.main() == 2
    assert not list(tmp_path.iterdir())


def stats_with(**overrides):
    return dataclasses.replace(compute(raw_data()), **overrides)


@pytest.mark.parametrize("counts,level", [
    (dict(commits_year=0, prs_total=0, issues_total=0, prs_reviewed=0, stars=0, followers=0), "C"),
    (dict(commits_year=1359, prs_total=90, issues_total=46, prs_reviewed=24, stars=70, followers=6), "A-"),
    (dict(commits_year=10_000, prs_total=2_000, issues_total=500, prs_reviewed=500, stars=100_000, followers=50_000), "S"),
])
def test_rank_follows_the_readme_stats_bands(counts, level):
    assert rank(stats_with(**counts)).level == level


def test_smooth_line_never_overshoots_its_points():
    points = [(i * 20.0, y) for i, y in enumerate([200, 200, 20, 200, 200, 180, 20, 20, 200])]
    numbers = [float(n) for n in re.findall(r"-?[\d.]+", smooth_path(points))]
    ys = numbers[1::2]
    assert min(ys) >= 20 and max(ys) <= 200


def test_raw_data_without_the_newer_fields_still_renders():
    stats = compute(raw_data())          # no forks, prs_total or issues_total
    assert stats.forks == 0 and stats.prs_total == 146 and stats.issues_total == 0
    assert len(stats.days) == make_stats.DAYS_SHOWN


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_activity_and_overview_are_valid_svg_with_the_numbers(theme):
    stats = stats_with(forks=7, issues_total=12, loc_added=1000, loc_deleted=500, contributed_to=5)
    activity = " ".join(ET.fromstring(render_activity(stats, theme)).itertext())
    assert f"{sum(n for _, n in stats.days):,} contributions" in activity
    overview = " ".join(ET.fromstring(render_overview(stats, theme)).itertext())
    for expected in (f"{stats.contributions_all:,}", "1,500", "12", rank(stats).level):
        assert expected in overview


def test_main_renders_every_card_from_saved_data(monkeypatch, tmp_path):
    saved = tmp_path / "raw.json"
    saved.write_text(json.dumps(raw_data()), encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["make_stats.py", "--out", str(out), "--from-json", str(saved)])
    assert make_stats.main() == 0
    names = {p.name for p in out.iterdir()}
    for kind in ("stats", "card", "activity", "overview"):
        assert {f"{kind}-dark.svg", f"{kind}-light.svg"} <= names
