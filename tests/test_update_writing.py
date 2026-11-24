"""README writing list: formatting, block replacement, and failure handling (no network)."""

import urllib.error

import pytest

import update_writing
from update_writing import END, START, format_entry, replace_block

ARTICLE = {
    "title": "#IOE Admission Hub: [Rank] Predictor",
    "published_at": "2026-10-12T07:15:00Z",
    "reading_time_minutes": 4,
    "slug": "ioe-admission-hub",
    "url": "https://dev.to/dszae/ioe-admission-hub",
}


def test_entry_strips_the_hashtag_and_escapes_brackets():
    line = format_entry(ARTICLE, "https://example.com/post")
    assert line == "- [IOE Admission Hub: \\[Rank\\] Predictor](https://example.com/post) <sub>12 Oct 2026 · 4 min read</sub>"


def test_replace_block_only_touches_the_markers():
    readme = f"intro\n{START}\nold\n{END}\noutro\n"
    assert replace_block(readme, ["- a", "- b"]) == f"intro\n{START}\n- a\n- b\n{END}\noutro\n"


def test_replace_block_requires_markers():
    with pytest.raises(ValueError):
        replace_block("no markers here", ["- a"])


def run(monkeypatch, tmp_path, fetch, has_page=lambda slug: True):
    readme = tmp_path / "README.md"
    readme.write_text(f"x\n{START}\n{END}\n", encoding="utf-8")
    monkeypatch.setattr(update_writing, "fetch_articles", fetch)
    monkeypatch.setattr(update_writing, "portfolio_has", has_page)
    monkeypatch.setattr("sys.argv", ["update_writing.py", "--readme", str(readme)])
    assert update_writing.main() == 0
    return readme.read_text(encoding="utf-8")


def test_links_prefer_the_portfolio_copy(monkeypatch, tmp_path):
    text = run(monkeypatch, tmp_path, lambda count: [ARTICLE])
    assert "https://www.dipeshsapkota7.com.np/blog/ioe-admission-hub" in text


def test_links_fall_back_to_dev(monkeypatch, tmp_path):
    text = run(monkeypatch, tmp_path, lambda count: [ARTICLE], has_page=lambda slug: False)
    assert "https://dev.to/dszae/ioe-admission-hub" in text


def test_a_failed_fetch_leaves_the_readme_alone(monkeypatch, tmp_path, capsys):
    def broken(count):
        raise urllib.error.URLError("offline")
    assert run(monkeypatch, tmp_path, broken) == f"x\n{START}\n{END}\n"
    assert "::warning::" in capsys.readouterr().out
