"""Profile card: code portrait, profile-as-code panel, valid SVG (no network)."""

import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import replace

import pytest

import card
import make_stats
from theme import DARK, LIGHT
from test_make_stats import raw_data


def stats(**overrides):
    base = make_stats.compute(raw_data())
    numbers = dict(public_repos=24, stars=73, commits_all=1415, followers=6, loc_added=402_178, loc_deleted=106_504)
    return replace(base, **{**numbers, **overrides})


def text(line):
    return "".join(t for t, _ in line)


def test_profile_object_carries_live_numbers():
    code = "\n".join(text(line) for line in card.code_lines(stats()))
    assert "repos: 24, stars: 73, followers: 6," in code
    assert "commits: 1_415, linesOfCode: 295_674," in code
    assert code.splitlines()[0].startswith("// dipesh.ts · synced ")


def test_code_rows_fill_the_panel_exactly():
    rows = card.code_rows(80, 30)
    assert len(rows) == 30 and all(len(r) == 80 for r in rows)
    stream = card.code_stream()
    assert "def code_stream()" in stream          # the portrait is drawn with the card's own source
    assert '"""' not in stream and "\n" not in stream


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_committed_masks_match_the_panel(theme):
    png = (card.ROOT / "assets" / f"portrait-{theme.name}.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (card.ART_W // 2, card.ART_H // 2)


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_render_is_valid_svg(theme):
    svg = card.render(stats(), theme)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    content = "".join(root.itertext())
    assert card.NAME in content and "295_674" in content
    assert 'mask="url(#face)"' in svg and "data:image/png;base64," in svg
    assert "prefers-reduced-motion:reduce" in svg


def test_large_numbers_still_fit():
    card.render(stats(public_repos=999, stars=99_999, followers=99_999, commits_all=999_999,
                      loc_added=99_999_999, loc_deleted=1), DARK)


def test_text_follows_the_persona_rules():
    words = " ".join([card.TAGLINE, card.PLACE] + [text(line) for line in card.code_lines(stats())])
    assert not re.search(r"full[- ]?stack|developer|web dev|software engineer", words, re.I)
