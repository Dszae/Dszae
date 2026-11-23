"""Run scripts/render_heatmap_svg.py on generated calendars and read back the SVG."""

import importlib.util
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "render_heatmap_svg.py"


def render(tmp_path, monkeypatch, last: date) -> str:
    days = [{"date": (last - timedelta(days=i)).isoformat(), "count": 1, "level": 1} for i in range(400)]
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "contributions.json").write_text(json.dumps({"days": days, "statistics": {}}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location("render_heatmap_svg", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 0
    return (tmp_path / "contrib-heatmap.svg").read_text(encoding="utf-8")


@pytest.mark.parametrize("last", [date(2026, 11, 22) + timedelta(days=offset) for offset in range(7)])
def test_the_latest_day_is_drawn_whatever_its_weekday(tmp_path, monkeypatch, last):
    drawn = [date.fromisoformat(d) for d in re.findall(r"<title>(\d{4}-\d{2}-\d{2}):", render(tmp_path, monkeypatch, last))]
    assert last in drawn
    assert len(drawn) == 53 * 7
    assert drawn[0].weekday() == 6  # each column starts on a Sunday
    assert drawn[-1] - last < timedelta(days=7)  # no column past the latest week


def test_weekday_labels_sit_on_their_rows(tmp_path, monkeypatch):
    svg = render(tmp_path, monkeypatch, date(2026, 11, 25))
    cell_y = {date.fromisoformat(d).weekday(): int(y) for y, d in re.findall(r'<rect x="\d+" y="(\d+)"[^>]*><title>(\d{4}-\d{2}-\d{2}):', svg)}
    labels = {name: int(y) for y, name in re.findall(r'<text x="12" y="(\d+)"[^>]*>(Mon|Fri)</text>', svg)}
    # A label's baseline is 10px below the top of the row it names.
    assert labels["Mon"] == cell_y[0] + 10
    assert labels["Fri"] == cell_y[4] + 10
