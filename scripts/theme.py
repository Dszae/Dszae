"""Shared palette, fonts, text metrics and SVG helpers for the profile images.

The colours follow dipeshsapkota7.com.np: a warm near-black (dark) or cream (light)
page, emerald accents, and the amber hexagon motif. Chart colours follow a
validated categorical palette; each language keeps its colour whatever its rank.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"

# Embedded under private names so a locally installed copy never shadows them.
SANS = "'DS Manrope', Manrope, 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
MONO = "'DS Geist Mono', 'Geist Mono', ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace"


@dataclass(frozen=True)
class Theme:
    name: str
    page_top: str
    page_bottom: str
    surface: str
    border: str
    text_primary: str
    text_secondary: str
    text_muted: str
    grid: str
    accent: str
    accent_glow: str
    amber_rgb: str
    amber_mark: str
    glow_opacity: float
    hex_scale: float
    other: str
    languages: dict[str, str] = field(default_factory=dict)
    spare: tuple[str, ...] = ()


# Categorical slots (validated in both modes on their chart surface): blue, orange,
# aqua, yellow, magenta, green, violet, red. Languages are pinned to a slot by name.
_LANGUAGE_SLOTS = ("TypeScript", "HTML", "Python", "JavaScript", "C++", "C", "CSS", "Astro")
_LIGHT_SLOTS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
_DARK_SLOTS = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767")

DARK = Theme(
    name="dark",
    page_top="#0b0908",
    page_bottom="#050404",
    surface="#0e1217",
    border="#ffffff1a",
    text_primary="#f8fafc",
    text_secondary="#94a3b8",
    text_muted="#64748b",
    grid="#ffffff14",
    accent="#34d399",
    accent_glow="#6ee7b7",
    amber_rgb="226,178,118",
    amber_mark="#e2b276",
    glow_opacity=0.22,
    hex_scale=1.0,
    other="#5c5c57",
    languages=dict(zip(_LANGUAGE_SLOTS, _DARK_SLOTS)),
    spare=_DARK_SLOTS,
)

LIGHT = Theme(
    name="light",
    page_top="#fcfaf6",
    page_bottom="#f3efe6",
    surface="#ffffff",
    border="#0f172a1a",
    text_primary="#0f172a",
    text_secondary="#1e293b",
    text_muted="#475569",
    grid="#0f172a14",
    accent="#059669",
    accent_glow="#10b981",
    amber_rgb="150,104,48",
    amber_mark="#966830",
    glow_opacity=0.12,
    hex_scale=0.9,
    other="#a3a29c",
    languages=dict(zip(_LANGUAGE_SLOTS, _LIGHT_SLOTS)),
    spare=_LIGHT_SLOTS,
)

THEMES = (DARK, LIGHT)


def language_colors(names: list[str], theme: Theme) -> dict[str, str]:
    """Colour per language, stable across runs: pinned slots first, then unused slots by name."""
    colors = {name: theme.languages[name] for name in names if name in theme.languages}
    free = [c for c in theme.spare if c not in colors.values()]
    for name in sorted(n for n in names if n not in colors):
        colors[name] = free.pop(0) if free else theme.other
    return colors


# --- fonts -----------------------------------------------------------------------

@lru_cache(maxsize=None)
def _font_data(filename: str) -> str:
    return base64.b64encode((FONT_DIR / filename).read_bytes()).decode("ascii")


def font_faces() -> str:
    """@font-face rules with both variable fonts embedded (GitHub images cannot fetch fonts)."""
    return (
        "@font-face{font-family:'DS Manrope';font-weight:200 800;"
        f"src:url(data:font/woff2;base64,{_font_data('Manrope-latin.woff2')}) format('woff2')}}"
        "@font-face{font-family:'DS Geist Mono';font-weight:100 900;"
        f"src:url(data:font/woff2;base64,{_font_data('GeistMono-latin.woff2')}) format('woff2')}}"
    )


# --- text measurement ------------------------------------------------------------
# Advance widths per 1000 em, extracted from the embedded Manrope at each weight.
# Kerning is ignored, so layouts keep a few pixels of slack.

SANS_CHARS = ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~·–—…'
SANS_ADVANCE = {
    500: (200, 329, 417, 924, 602, 901, 657, 229, 435, 435, 446, 575, 278, 420, 270, 402, 626, 406, 578, 562, 596, 580, 621, 512, 591, 621, 314, 318, 622, 750, 622, 534, 907, 646, 619, 723, 681, 575, 510, 714, 697, 249, 476, 612, 518, 846, 696, 732, 616, 732, 640, 630, 600, 708, 616, 949, 622, 574, 630, 412, 402, 412, 673, 660, 506, 562, 600, 561, 600, 590, 362, 600, 604, 249, 263, 510, 249, 865, 604, 600, 600, 600, 374, 530, 412, 604, 523, 779, 536, 538, 531, 430, 269, 430, 680, 240, 540, 780, 658),
    600: (200, 344, 442, 928, 615, 900, 662, 244, 444, 444, 456, 574, 290, 420, 286, 418, 642, 422, 587, 572, 602, 584, 622, 523, 602, 622, 328, 330, 630, 750, 630, 544, 910, 658, 625, 730, 690, 580, 516, 723, 710, 264, 488, 630, 526, 850, 706, 740, 627, 740, 650, 644, 604, 714, 628, 962, 639, 593, 647, 418, 418, 418, 676, 660, 522, 570, 608, 568, 608, 596, 370, 608, 615, 264, 276, 524, 264, 882, 615, 610, 608, 608, 386, 536, 422, 615, 538, 790, 545, 548, 532, 439, 284, 439, 698, 254, 540, 780, 684),
    700: (200, 360, 467, 932, 628, 900, 668, 260, 453, 453, 464, 572, 304, 420, 304, 433, 658, 438, 596, 582, 608, 586, 622, 534, 612, 622, 342, 344, 638, 750, 638, 553, 914, 670, 631, 738, 700, 585, 524, 732, 722, 280, 500, 647, 534, 855, 718, 750, 638, 750, 660, 658, 606, 720, 640, 976, 656, 612, 664, 424, 433, 424, 680, 660, 538, 576, 616, 576, 617, 602, 378, 616, 626, 280, 288, 538, 280, 899, 626, 618, 616, 617, 399, 542, 433, 626, 553, 802, 554, 560, 534, 449, 300, 449, 716, 266, 540, 780, 710),
    800: (200, 376, 492, 935, 641, 900, 674, 276, 462, 462, 474, 570, 316, 420, 320, 448, 674, 454, 604, 591, 615, 589, 622, 544, 623, 622, 357, 356, 645, 750, 645, 563, 917, 683, 637, 746, 710, 590, 530, 741, 734, 296, 513, 665, 541, 860, 729, 758, 650, 758, 670, 671, 610, 726, 653, 989, 672, 630, 680, 429, 448, 429, 684, 660, 555, 583, 624, 583, 625, 608, 386, 624, 636, 296, 301, 552, 296, 916, 636, 627, 624, 625, 412, 547, 444, 636, 568, 814, 563, 570, 535, 459, 316, 459, 734, 280, 540, 780, 736),
}
_SANS_INDEX = {ch: i for i, ch in enumerate(SANS_CHARS)}
MONO_ADVANCE = 600


def text_width(text: str, size: float, weight: int = 500, mono: bool = False) -> float:
    """Rendered width in px of ``text`` in the embedded fonts (unknown glyphs count as 'M')."""
    if mono:
        return len(text) * MONO_ADVANCE * size / 1000
    table = SANS_ADVANCE[min(SANS_ADVANCE, key=lambda w: abs(w - weight))]
    fallback = table[_SANS_INDEX["M"]]
    return sum(table[_SANS_INDEX[ch]] if ch in _SANS_INDEX else fallback for ch in text) * size / 1000


# --- colour maths ----------------------------------------------------------------

def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")[:6]
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def ink_on(fill: str) -> str:
    """White or near-black, whichever reads better on ``fill``."""
    return "#ffffff" if contrast("#ffffff", fill) >= contrast("#0b0b0b", fill) else "#0b0b0b"


# --- svg helpers -----------------------------------------------------------------

def esc(text: object) -> str:
    return escape(str(text), {'"': "&quot;"})


# Centres and opacities of the right-hand hexagon cluster in the portfolio background
# (pointy-top cells, radius 29, on a 1440 x 900 canvas).
_PORTFOLIO_HEXES = (
    (855.4, 94, 0.020), (716.9, 142, 0.030), (827.7, 142, 0.040), (938.6, 142, 0.025),
    (800.0, 190, 0.070), (855.4, 190, 0.050), (910.9, 190, 0.030),
    (772.3, 238, 0.050), (827.7, 238, 0.090), (883.1, 238, 0.060), (938.6, 238, 0.040),
    (689.1, 286, 0.020), (800.0, 286, 0.040), (855.4, 286, 0.070), (910.9, 286, 0.080),
    (772.3, 334, 0.030), (883.1, 334, 0.050), (938.6, 334, 0.060), (966.3, 382, 0.030),
)


def hex_motif(theme: Theme, x: float, y: float, scale: float = 1.0, boost: float = 1.0) -> str:
    """The portfolio's amber hexagon cluster, its top-left corner placed at (x, y)."""
    r, half = 29.0, 25.1
    min_x = min(cx for cx, _, _ in _PORTFOLIO_HEXES) - half
    min_y = min(cy for _, cy, _ in _PORTFOLIO_HEXES) - r
    parts = []
    for cx, cy, alpha in _PORTFOLIO_HEXES:
        pts = " ".join(
            f"{x + (cx + dx * half - min_x) * scale:.1f},{y + (cy + dy * r - min_y) * scale:.1f}"
            for dx, dy in ((0, -1), (1, -0.5), (1, 0.5), (0, 1), (-1, 0.5), (-1, -0.5))
        )
        opacity = min(1.0, alpha * boost * theme.hex_scale)
        parts.append(f'<polygon points="{pts}" fill="rgb({theme.amber_rgb})" fill-opacity="{opacity:.3f}"/>')
    return "".join(parts)
