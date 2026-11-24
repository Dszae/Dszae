"""Profile card: a portrait drawn in flowing source code beside a profile written as code.

The portrait panel is filled with the source of this very file, streaming upward a
line at a time. A mask made from a photo (make_portrait.py) sets how strongly each
spot of code shows, so the face appears in the code. The right side carries the
name, tagline and a syntax-highlighted profile object with live GitHub numbers
from make_stats.py, which re-renders the card every few hours.
"""

from __future__ import annotations

import base64
import re
from datetime import date
from pathlib import Path

from theme import MONO, ROOT, SANS, Theme, esc, font_faces, text_width

W, H = 1000, 452
PAD = 24
ART_X, ART_Y, ART_W, ART_H = PAD, PAD, 340, 404      # must match PANEL_W/H in make_portrait.py
ART_FONT, ART_CHAR, ART_LINE = 6.4, 3.84, 6.3       # Geist Mono: 600/1000 em advance
TEXT_X = ART_X + ART_W + 40
CODE_FONT, CODE_CHAR, CODE_LINE = 13, 7.8, 21
FLOW_SECONDS_PER_LINE = 0.55

NAME = "Dipesh Sapkota"
TAGLINE = "Computer Engineering Student · AI/ML Enthusiast · Motion Designer"
PLACE = "IOE Thapathali Campus, Tribhuvan University · Kathmandu, Nepal"

Segment = tuple[str, str]


# --- the profile, written as code ---------------------------------------------------

def _s(text: str) -> Segment:
    return (f'"{text}"', "str")


def _n(value: int) -> Segment:
    return (f"{value:_}", "num")


def _list(items: list[str]) -> list[Segment]:
    out: list[Segment] = [("[", "p")]
    for i, item in enumerate(items):
        out += ([(", ", "p")] if i else []) + [_s(item)]
    return out + [("]", "p")]


def _prop(key: str, value: list[Segment], indent: int = 1, comma: bool = True) -> list[Segment]:
    return [("  " * indent, "p"), (key, "key"), (": ", "p"), *value] + ([(",", "p")] if comma else [])


def code_lines(stats) -> list[list[Segment]]:
    gh = [
        [("  ", "p"), ("github", "key"), (": {", "p")],
        [("    ", "p"), ("repos", "key"), (": ", "p"), _n(stats.public_repos), (", ", "p"),
         ("stars", "key"), (": ", "p"), _n(stats.stars), (", ", "p"),
         ("followers", "key"), (": ", "p"), _n(stats.followers), (",", "p")],
        [("    ", "p"), ("commits", "key"), (": ", "p"), _n(stats.commits_all), (", ", "p"),
         ("linesOfCode", "key"), (": ", "p"), _n(stats.loc_added - stats.loc_deleted), (",", "p")],
        [("  ", "p"), ("},", "p")],
    ]
    return [
        [(f"// dipesh.ts · synced {stats.updated.day} {stats.updated:%b %Y}", "com")],
        [("export const ", "kw"), ("dipesh", "id"), (" = {", "p")],
        _prop("handle", [_s("@Dszae")]),
        _prop("focus", _list(["AI/ML", "Embedded Systems", "Motion Design"])),
        _prop("stack", _list(["C", "C++", "Python", "TypeScript"])),
        _prop("tools", _list(["After Effects", "DaVinci Resolve", "Proteus"])),
        *gh,
        _prop("site", [_s("dipeshsapkota7.com.np")]),
        [("} ", "p"), ("satisfies ", "kw"), ("Human", "id"), (";", "p")],
    ]


# --- the code portrait ---------------------------------------------------------------

def code_stream() -> str:
    """This file's own source, flattened into one continuous line of code."""
    source = Path(__file__).read_text(encoding="utf-8")
    source = re.sub(r'"""[\s\S]*?"""', " ", source)            # drop docstrings
    return re.sub(r"\s+", " ", source).strip()


def code_rows(cols: int, rows: int) -> list[str]:
    stream = code_stream()
    needed = cols * rows
    text = (stream + " ") * (needed // (len(stream) + 1) + 1)
    return [text[i * cols:(i + 1) * cols] for i in range(rows)]


def mask_data(theme: Theme) -> str | None:
    path = ROOT / "assets" / f"portrait-{theme.name}.png"
    return base64.b64encode(path.read_bytes()).decode("ascii") if path.exists() else None


def _flow_block(rows: list[str], css_class: str) -> str:
    """Two stacked copies of the rows, so scrolling by one copy's height loops seamlessly."""
    out = []
    for copy in range(2):
        for i, row in enumerate(rows):
            y = ART_Y + (copy * len(rows) + i + 1) * ART_LINE
            out.append(f'<text x="{ART_X}" y="{y:.1f}">{esc(row)}</text>')
    return f'<g class="{css_class}">{"".join(out)}</g>'


# --- rendering -------------------------------------------------------------------------

def render(stats, theme: Theme) -> str:
    cols = int(ART_W / ART_CHAR)
    rows = int(ART_H / ART_LINE) + 1
    lines = code_rows(cols, rows)
    mask = mask_data(theme)
    loop_px = rows * ART_LINE
    loop_s = rows * FLOW_SECONDS_PER_LINE

    tagline_size = 15
    if TEXT_X + text_width(TAGLINE, tagline_size, 500) > W - PAD:
        raise ValueError("tagline does not fit the card")

    code = []
    code_top = 176
    for i, line in enumerate(code_lines(stats)):
        width = sum(len(t) for t, _ in line) + 4
        if TEXT_X + width * CODE_CHAR > W - PAD:
            raise ValueError(f"code line {i + 1} does not fit the card")
        y = code_top + i * CODE_LINE
        spans = "".join(f'<tspan class="{c}">{esc(t)}</tspan>' for t, c in line)
        code.append(f'<text x="{TEXT_X}" y="{y}" class="ln">{i + 1:>2}</text>'
                    f'<text x="{TEXT_X + 4 * CODE_CHAR:.1f}" y="{y}" class="code" style="--i:{i}">{spans}</text>')

    dark = theme.name == "dark"
    grad = ("#a7f3d0", "#34d399", "#f5c07a") if dark else ("#047857", "#065f46", "#b45309")
    portrait = ""
    if mask:
        portrait = (
            f'<mask id="face" maskUnits="userSpaceOnUse" x="{ART_X}" y="{ART_Y}" width="{ART_W}" height="{ART_H}">'
            f'<image href="data:image/png;base64,{mask}" x="{ART_X}" y="{ART_Y}" width="{ART_W}" height="{ART_H}" '
            f'preserveAspectRatio="none"/></mask>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="ct cd">
<title id="ct">{esc(NAME)} (Dszae)</title>
<desc id="cd">A portrait of {esc(NAME)} drawn in flowing source code, beside a profile written as a TypeScript object: {esc(TAGLINE)}, {esc(PLACE)}, with live GitHub numbers.</desc>
<style>{font_faces()}
.sans{{font-family:{SANS}}}
.art text{{font:800 {ART_FONT}px {MONO};white-space:pre}}
.flow{{animation:flow {loop_s:.1f}s steps({rows}) infinite}}
@keyframes flow{{to{{transform:translateY(-{loop_px:.1f}px)}}}}
.code,.ln{{font:400 {CODE_FONT}px {MONO};white-space:pre}}
.ln{{fill:{theme.text_muted};opacity:.55}}
.p{{fill:{theme.text_muted}}}.key{{fill:{theme.text_secondary}}}.str{{fill:{theme.accent_text}}}
.num{{fill:{theme.amber_mark}}}.kw{{fill:{theme.amber_mark}}}.id{{fill:{theme.text_primary}}}
.com{{fill:{theme.text_muted};font-style:italic}}
.place{{font:400 12px {MONO};fill:{theme.text_muted}}}
.code{{opacity:0;animation:in .4s ease-out forwards;animation-delay:calc(.3s + var(--i) * 60ms)}}
@keyframes in{{from{{opacity:0;transform:translateX(-4px)}}to{{opacity:1;transform:none}}}}
@media (prefers-reduced-motion:reduce){{.flow{{animation:none}}.code{{animation:none;opacity:1}}}}
</style>
<defs>
<linearGradient id="ink" gradientUnits="userSpaceOnUse" x1="{ART_X}" y1="{ART_Y}" x2="{ART_X + ART_W}" y2="{ART_Y + ART_H}">
<stop offset="0" stop-color="{grad[0]}"/><stop offset=".55" stop-color="{grad[1]}"/><stop offset="1" stop-color="{grad[2]}"/></linearGradient>
<radialGradient id="vignette" cx=".5" cy=".42" r=".62"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<mask id="soft" maskUnits="userSpaceOnUse" x="{ART_X}" y="{ART_Y}" width="{ART_W}" height="{ART_H}"><rect x="{ART_X}" y="{ART_Y}" width="{ART_W}" height="{ART_H}" fill="url(#vignette)"/></mask>
<clipPath id="panel"><rect x="{ART_X}" y="{ART_Y}" width="{ART_W}" height="{ART_H}" rx="10"/></clipPath>
{portrait}
</defs>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="{theme.surface}" stroke="{theme.border}"/>
<g class="art" clip-path="url(#panel)">
<g mask="url(#soft)" fill="{theme.text_muted}" opacity="{.16 if dark else .12}">{_flow_block(lines, "flow")}</g>
{f'<rect x="{ART_X}" y="{ART_Y}" width="{ART_W}" height="{ART_H}" fill="url(#ink)" mask="url(#face)" opacity="{.42 if dark else .24}"/>' if mask else ''}
<g{' mask="url(#face)"' if mask else ''} fill="url(#ink)">{_flow_block(lines, "flow")}</g>
</g>
<text x="{TEXT_X}" y="70" class="sans" font-size="40" font-weight="800" letter-spacing="-.8" fill="{theme.text_primary}">{esc(NAME)}</text>
<text x="{TEXT_X}" y="102" class="sans" font-size="{tagline_size}" font-weight="500" fill="{theme.text_secondary}">{esc(TAGLINE)}</text>
<text x="{TEXT_X}" y="128" class="place">{esc(PLACE)}</text>
<path d="M{TEXT_X} 148 H{W - PAD}" stroke="{theme.border}"/>
{"".join(code)}
</svg>
'''
