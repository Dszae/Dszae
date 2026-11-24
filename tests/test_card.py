"""Terminal profile card: aligned readout, committed portrait, valid SVG (no network)."""

import re
import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest

import card
import make_stats
from theme import DARK, LIGHT
from test_make_stats import raw_data


def stats(**overrides):
    base = make_stats.compute(raw_data())
    numbers = dict(public_repos=24, contributed_to=8, stars=73, commits_all=1415, followers=6,
                   loc_added=402_178, loc_deleted=106_504)
    return replace(base, **{**numbers, **overrides})


def text(line):
    return "".join(t for t, _ in line)


def test_every_readout_line_fits_and_key_value_rows_align():
    for line in card.readout(stats()):
        assert len(text(line)) <= card.WIDTH
        if line and text(line).startswith(". ") and " | " not in text(line):
            assert len(text(line)) == card.WIDTH, text(line)


def test_stats_lines_carry_the_numbers():
    lines = [text(line) for line in card.stat_lines(stats())]
    assert "24 {Contributed: 8}" in lines[0] and lines[0].endswith("73")
    assert "1,415" in lines[1] and lines[1].endswith("6")
    assert "295,674 ( 402,178++, 106,504-- )" in lines[2]


def test_large_numbers_still_fit():
    big = stats(public_repos=999, contributed_to=999, stars=99_999, commits_all=99_999,
                followers=99_999, loc_added=9_999_999, loc_deleted=999_999)
    for line in card.readout(big):
        assert len(text(line)) <= card.WIDTH


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_committed_portraits_match_the_card_grid(theme):
    rows = card.load_portrait(theme)
    assert len(rows) * card.ART_LINE <= len(card.readout(stats())) * card.LINE + card.ART_LINE
    assert max(len(r) for r in rows) <= 50
    assert set("".join(rows)) <= set(" .`:-=+*cs#%@")


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_render_is_valid_svg(theme):
    svg = card.render(stats(), theme)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    content = "".join(root.itertext())
    assert "dipesh@sapkota" in content and "295,674" in content
    assert "prefers-reduced-motion:reduce" in svg


def test_profile_text_follows_the_persona_rules():
    words = " ".join(" ".join(row) if isinstance(row, tuple) else row or "" for row in card.PROFILE)
    assert not re.search(r"full[- ]?stack|developer|web dev|software engineer", words, re.I)
