"""Terminal-style profile card: ASCII portrait beside a dotted key/value readout.

Static details live in PROFILE below; the GitHub numbers come from make_stats.py,
which re-renders the card every few hours. The portrait text is produced once by
make_portrait.py and committed under assets/.
"""

from __future__ import annotations

from pathlib import Path

from theme import MONO, ROOT, Theme, esc, font_faces

FONT, LINE, CHAR = 14, 20, 8.4         # readout: Geist Mono 14px, 600/1000 em advance
ART_FONT, ART_LINE, ART_CHAR = 10.5, 12.5, 6.3   # portrait: smaller glyphs, twice the detail
WIDTH = 66                              # characters in the readout column
HEADER = "dipesh@sapkota"

# (key, value) rows; None is a blank line, a bare string starts a titled section.
PROFILE: list = [
    ("OS", "Windows 11"),
    ("Host", "IOE Thapathali Campus, Tribhuvan University"),
    ("Kernel", "Computer Engineering Student"),
    ("Location", "Kathmandu, Nepal"),
    ("IDE", "VS Code, After Effects, DaVinci Resolve"),
    None,
    ("Languages.Programming", "C, C++, Python, TypeScript, JavaScript"),
    ("Languages.Real", "Nepali, English"),
    None,
    ("Focus.AI/ML", "Neural networks, NumPy, Jupyter"),
    ("Focus.Hardware", "ESP32, NE555 circuits, Proteus"),
    ("Focus.Motion", "4+ years, 50+ clients worldwide"),
    ("Hobbies.Software", "Windhawk mods, After Effects tools"),
    None,
    "Contact",
    ("Portfolio", "dipeshsapkota7.com.np"),
    ("Email", "contact@dipeshsapkota7.com.np"),
    ("LinkedIn", "dipeshsapkota7"),
    ("DEV", "dszae"),
    None,
    "GitHub Stats",
]

Segment = tuple[str, str]   # (text, css class)


def _dots(n: int) -> Segment:
    if n < 2:
        raise ValueError("readout line too long for the card")
    return (" " + "." * (n - 2) + " ", "d")


def kv(key: str, value: list[Segment] | str, width: int = WIDTH, lead: bool = True) -> list[Segment]:
    """'. Key: ....... value' padded to exactly ``width`` characters."""
    value_parts = [(value, "v")] if isinstance(value, str) else value
    head = [(". ", "d")] if lead else []
    head += [(key, "k"), (":", "d")]
    used = sum(len(t) for t, _ in head) + sum(len(t) for t, _ in value_parts)
    return head + [_dots(width - used)] + value_parts


def rule(title: str) -> list[Segment]:
    text = f"- {title} " if title != HEADER else f"{title} "
    return [(text, "h"), ("—" * (WIDTH - len(text)), "d")]


def stat_lines(stats) -> list[list[Segment]]:
    left_w = 36
    right_w = WIDTH - left_w - 3
    repos = kv("Repos", [(f"{stats.public_repos:,}", "v"), (" {", "d"), ("Contributed: ", "k"),
                         (f"{stats.contributed_to:,}", "v"), ("}", "d")], left_w)
    commits = kv("Commits", f"{stats.commits_all:,}", left_w)
    stars = kv("Stars", f"{stats.stars:,}", right_w, lead=False)
    followers = kv("Followers", f"{stats.followers:,}", right_w, lead=False)
    net = stats.loc_added - stats.loc_deleted
    loc = kv("Lines of Code on GitHub", [(f"{net:,}", "v"), (" ( ", "d"), (f"{stats.loc_added:,}++", "add"),
                                         (", ", "d"), (f"{stats.loc_deleted:,}--", "del"), (" )", "d")])
    return [repos + [(" | ", "d")] + stars, commits + [(" | ", "d")] + followers, loc]


def readout(stats) -> list[list[Segment]]:
    lines = [rule(HEADER)]
    for row in PROFILE:
        if row is None:
            lines.append([])
        elif isinstance(row, str):
            lines.append(rule(row))
        else:
            lines.append(kv(*row))
    return lines + stat_lines(stats)


def load_portrait(theme: Theme) -> list[str]:
    path = ROOT / "assets" / f"portrait-{theme.name}.txt"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def render(stats, theme: Theme, portrait: list[str] | None = None) -> str:
    portrait = load_portrait(theme) if portrait is None else portrait
    lines = readout(stats)
    for line in lines:
        length = sum(len(t) for t, _ in line)
        if length > WIDTH:
            raise ValueError(f"readout line is {length} characters, over {WIDTH}: {''.join(t for t, _ in line)}")

    pad_x, pad_top = 28, 34
    art_cols = max((len(r) for r in portrait), default=0)
    text_x = pad_x + (art_cols * ART_CHAR + 30 if art_cols else 0)
    width = round(text_x + WIDTH * CHAR + pad_x)
    content = max(len(lines) * LINE, len(portrait) * ART_LINE)
    height = round(pad_top + content - LINE + 26)
    art_top = pad_top - (LINE - ART_LINE) / 2       # centre the art's rows on the readout's

    art = "".join(
        f'<text x="{pad_x}" y="{art_top + i * ART_LINE:.1f}" class="a" style="--i:{i // 2}">{esc(row)}</text>'
        for i, row in enumerate(portrait)
    )
    body = []
    for i, line in enumerate(lines):
        if not line:
            continue
        spans = "".join(f'<tspan class="{cls}">{esc(text)}</tspan>' for text, cls in line)
        body.append(f'<text x="{text_x:.1f}" y="{pad_top + i * LINE}" class="r" style="--i:{i}">{spans}</text>')

    red = "#e66767" if theme.name == "dark" else "#c0392b"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-labelledby="ct cd">'
        f'<title id="ct">Dipesh Sapkota (Dszae)</title>'
        f'<desc id="cd">ASCII portrait of Dipesh Sapkota beside a terminal-style readout: Computer Engineering '
        f'Student at IOE Thapathali Campus, Kathmandu, Nepal, with contact details and live GitHub stats.</desc>'
        f'<style>{font_faces()}'
        f'text{{font:400 {FONT}px {MONO};white-space:pre}}'
        f'.a{{font-size:{ART_FONT}px;fill:{theme.text_secondary}}}.k{{fill:{theme.amber_mark}}}.v{{fill:{theme.accent_text}}}'
        f'.d{{fill:{theme.text_muted}}}.h{{fill:{theme.text_primary}}}.add{{fill:{theme.accent}}}.del{{fill:{red}}}'
        f'.a,.r{{opacity:0;animation:in .35s ease-out forwards;animation-delay:calc(var(--i) * 35ms)}}'
        f'@keyframes in{{to{{opacity:1}}}}'
        f'@media (prefers-reduced-motion:reduce){{.a,.r{{animation:none;opacity:1}}}}'
        f'</style>'
        f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="12" fill="{theme.surface}" stroke="{theme.border}"/>'
        f'<g xml:space="preserve">{art}{"".join(body)}</g>'
        f'</svg>\n'
    )
