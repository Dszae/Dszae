"""Header banner: valid SVG, a left-to-right trace, beats that fire within each loop."""

import xml.etree.ElementTree as ET

import pytest

import make_hero
from theme import DARK, LIGHT


def test_trace_runs_left_to_right_inside_the_banner():
    trace, motion = make_hero.build_trace()
    for points in (trace, motion):
        xs = [x for x, _ in points]
        assert xs == sorted(xs)
        assert xs[0] == make_hero.LEFT and xs[-1] == make_hero.RIGHT
        assert all(0 < y < make_hero.HEIGHT for _, y in points)


def test_probe_keys_are_monotonic_and_complete():
    _, motion = make_hero.build_trace()
    points, times = (list(map(float, s.split(";"))) for s in make_hero.probe_keys(motion))
    assert len(points) == len(times)
    assert points[0] == times[0] == 0 and points[-1] == times[-1] == 1
    assert points == sorted(points) and times == sorted(times)


def test_every_beat_lights_within_the_first_pass():
    for bx in make_hero.beat_positions():
        offset = (bx - make_hero.LEFT) / (make_hero.RIGHT - make_hero.LEFT) * make_hero.LOOP_SECONDS
        assert 0 < offset < make_hero.LOOP_SECONDS


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_render_is_valid_svg_with_reduced_motion_support(theme):
    svg = make_hero.render(theme)
    root = ET.fromstring(svg)
    assert root.get("viewBox") == f"0 0 {make_hero.WIDTH} {make_hero.HEIGHT}"
    assert "prefers-reduced-motion:reduce" in svg
    assert make_hero.NAME in " ".join(root.itertext())


def test_committed_banners_match_the_generator(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["make_hero.py", "--out", str(tmp_path)])
    assert make_hero.main() == 0
    for theme in (DARK, LIGHT):
        name = f"hero-{theme.name}.svg"
        committed = (make_hero.ROOT / "assets" / name).read_text(encoding="utf-8")
        assert (tmp_path / name).read_text(encoding="utf-8") == committed, f"run scripts/make_hero.py to refresh {name}"
