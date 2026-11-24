"""Search engines read the README's text, not the banner image, so the name must appear as text."""

import re
from pathlib import Path

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
VISIBLE = re.sub(r"<[^>]+>", " ", README)   # drop tags, including image alt attributes


def test_name_and_handle_appear_as_text():
    assert "Dipesh Sapkota" in VISIBLE
    assert "Dszae" in VISIBLE


def test_no_prohibited_titles():
    assert not re.search(r"full[- ]?stack|developer|web dev", VISIBLE, re.I)
