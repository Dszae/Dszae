#!/usr/bin/env python3
"""Render the profile header as assets/hero-dark.svg and assets/hero-light.svg.

One signal runs across the banner in three movements: a 555 astable square wave
(hardware), a damped curve settling as a model converges (AI/ML), and an audio
waveform with After Effects style beat markers (motion design). The trace sweeps
in from the left, then a probe travels it at constant speed and each beat marker
lights as the probe passes. Under prefers-reduced-motion the full trace is shown
and nothing moves.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from theme import MONO, ROOT, SANS, THEMES, Theme, esc, font_faces, hex_motif, text_width

WIDTH, HEIGHT = 1000, 340
LEFT, RIGHT = 56, 944
BASE = 262                  # trace baseline
REVEAL_DELAY, REVEAL_SECONDS = 0.25, 2.4
PROBE_BEGIN = REVEAL_DELAY + REVEAL_SECONDS + 0.2
LOOP_SECONDS = 7.0          # one probe pass, left to right
KEY_STEP = 4                # px between probe keyframes

PROMPT = "dipesh@thapathali:~$"
COMMAND = "whoami"
NAME = "Dipesh Sapkota"
TAGLINE = "Computer Engineering Student · AI/ML Enthusiast · Motion Designer"
PLACE = "IOE Thapathali Campus, Tribhuvan University · Kathmandu, Nepal"
SEGMENTS = (
    ("555 astable · square wave", 72, 300),
    ("model training · converging", 336, 604),
    ("audio waveform · beat markers", 636, 944),
)
BEATS = 8

Point = tuple[float, float]


def _noise(i: int) -> float:
    """Deterministic pseudo-random value in [0, 1) so every render is identical."""
    x = math.sin(i * 12.9898 + 78.233) * 43758.5453
    return x - math.floor(x)


def beat_positions() -> list[float]:
    _, c0, c1 = SEGMENTS[2]
    step = (c1 - c0 - 30) / BEATS
    return [c0 + 14 + k * step for k in range(BEATS)]


def build_trace() -> tuple[list[Point], list[Point]]:
    """Polyline of the drawn signal, and the smoother path the probe follows."""
    pts: list[Point] = [(LEFT, BASE)]

    # 1. Square wave: 555 astable, duty cycle about 60 %, five periods.
    _, a0, a1 = SEGMENTS[0]
    amp, period = 17, (a1 - a0) / 5
    x = a0
    pts.append((x, BASE))
    for _ in range(5):
        high_end, low_end = x + period * 0.6, x + period
        pts += [(x, BASE - amp), (high_end, BASE - amp), (high_end, BASE + amp), (low_end, BASE + amp)]
        x = low_end
    pts += [(a1, BASE), (SEGMENTS[1][1], BASE)]

    # 2. Damped oscillation: a training curve settling as the model converges.
    _, b0, b1 = SEGMENTS[1]
    steps = int(b1 - b0)
    for i in range(steps + 1):
        t = i / steps
        pts.append((b0 + i, BASE - 30 * math.exp(-2.9 * t) * math.sin(2 * math.pi * 4.5 * t)))
    pts.append((SEGMENTS[2][1], BASE))
    motion = list(pts)

    # 3. Audio: a mirrored waveform, quiet between beats, accents on beats 1, 3, 5, 7.
    _, c0, c1 = SEGMENTS[2]
    beats = beat_positions()
    samples = int((c1 - c0) * 2)
    for i in range(samples + 1):
        px = c0 + i / 2
        env = 1.8
        for k, bx in enumerate(beats):
            dx = px - bx
            peak = 30 if k % 2 == 0 else 20
            if -2 <= dx < 0:
                env += peak * (dx + 2) / 2          # fast attack
            elif dx >= 0:
                env += peak * math.exp(-dx / 6.5)   # exponential release
        env = min(env, 32) * (0.55 + 0.45 * _noise(i))
        pts.append((px, BASE + (env if i % 2 else -env)))
    pts.append((RIGHT, BASE))
    motion.append((RIGHT, BASE))   # the probe crosses the audio like a playhead
    return pts, motion


def _cumulative(pts: list[Point]) -> list[float]:
    acc, out = 0.0, [0.0]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        acc += math.hypot(x1 - x0, y1 - y0)
        out.append(acc)
    return out


def length_at_x(pts: list[Point], cumulative: list[float], x: float) -> float:
    """Arc length where a left-to-right path first reaches ``x``."""
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        if x1 > x0 and x0 <= x <= x1:
            t = (x - x0) / (x1 - x0)
            return cumulative[i] + t * math.hypot(x1 - x0, y1 - y0)
    return cumulative[-1]


def probe_keys(motion: list[Point]) -> tuple[str, str]:
    """keyPoints/keyTimes that move the probe at constant horizontal speed."""
    cumulative = _cumulative(motion)
    total = cumulative[-1]
    xs = [LEFT + k * KEY_STEP for k in range(int((RIGHT - LEFT) / KEY_STEP) + 1)]
    if xs[-1] != RIGHT:
        xs.append(RIGHT)
    points = [min(1.0, length_at_x(motion, cumulative, x) / total) for x in xs]
    points[0], points[-1] = 0.0, 1.0
    times = [(x - LEFT) / (RIGHT - LEFT) for x in xs]
    return ";".join(f"{p:.4f}" for p in points), ";".join(f"{t:.4f}" for t in times)


def _d(pts: list[Point]) -> str:
    return "M" + " ".join(f"{x:.1f} {y:.1f}" for x, y in pts)


def render(theme: Theme) -> str:
    trace, motion = build_trace()
    key_points, key_times = probe_keys(motion)
    prompt_w = text_width(PROMPT + " ", 15, mono=True)
    cursor_x = LEFT + text_width(f"{PROMPT} {COMMAND}", 15, mono=True) + 4
    pin = "h9 v4 l-4.5 4.5 l-4.5 -4.5 z"
    pin_y = BASE - 50

    markers, pulses = [], []
    for k, bx in enumerate(beat_positions()):
        peak = 30 if k % 2 == 0 else 20
        begin = PROBE_BEGIN + (bx - LEFT) / (RIGHT - LEFT) * LOOP_SECONDS
        markers.append(
            f'<path d="M{bx - 4.5:.1f} {pin_y - 6} {pin}" fill="{theme.amber_mark}" fill-opacity=".6" stroke="none"/>'
            f'<path d="M{bx:.1f} {pin_y + 5} V{BASE - peak - 3}" stroke="{theme.amber_mark}" stroke-opacity=".3"/>'
        )
        pulses.append(
            f'<g opacity="0"><animate attributeName="opacity" values="0;1;0;0" keyTimes="0;.025;.16;1" '
            f'dur="{LOOP_SECONDS}s" begin="{begin:.3f}s" repeatCount="indefinite"/>'
            f'<circle cx="{bx:.1f}" cy="{pin_y - 2}" r="12" fill="url(#beatGlow)"/>'
            f'<path d="M{bx - 4.5:.1f} {pin_y - 6} {pin}" fill="{theme.amber_mark}"/></g>'
        )

    captions = "".join(
        f'<text x="{(a + b) / 2:.1f}" y="318" text-anchor="middle" class="cap">{esc(label)}</text>'
        for label, a, b in SEGMENTS
    )
    dividers = "".join(
        f'<path d="M{x:.1f} 234 V290" stroke="{theme.grid}"/>'
        for x in ((SEGMENTS[0][2] + SEGMENTS[1][1]) / 2, (SEGMENTS[1][2] + SEGMENTS[2][1]) / 2)
    )
    ease = 'calcMode="spline" keyTimes="0;1" keySplines=".16 1 .3 1"'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" role="img" aria-labelledby="t d">
<title id="t">{esc(NAME)}, {esc(TAGLINE)}</title>
<desc id="d">{esc(PLACE)}. A signal runs from a 555 timer square wave, through a converging training curve, to an audio waveform with beat markers.</desc>
<style>{font_faces()}
.sans{{font-family:{SANS}}}.mono{{font-family:{MONO}}}
.cap{{font:400 12.5px {MONO};fill:{theme.text_muted}}}
.reveal{{clip-path:url(#sweep)}}
.cursor{{animation:blink 1.1s steps(1) infinite}}
@keyframes blink{{50%{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{.reveal{{clip-path:none}}.cursor{{animation:none}}.motion{{display:none}}}}
</style>
<defs>
<linearGradient id="page" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{theme.page_top}"/><stop offset="1" stop-color="{theme.page_bottom}"/></linearGradient>
<radialGradient id="amber" cx=".72" cy="-.12" r="1" gradientTransform="translate(.72 -.12) scale(.58 .82) translate(-.72 .12)">
<stop offset="0" stop-color="rgb({theme.amber_rgb})" stop-opacity="{theme.glow_opacity}"/>
<stop offset=".32" stop-color="rgb({theme.amber_rgb})" stop-opacity="{theme.glow_opacity * 0.41:.3f}"/>
<stop offset=".58" stop-color="rgb({theme.amber_rgb})" stop-opacity="{theme.glow_opacity * 0.14:.3f}"/>
<stop offset=".76" stop-color="rgb({theme.amber_rgb})" stop-opacity="0"/></radialGradient>
<radialGradient id="probeGlow"><stop offset="0" stop-color="{theme.accent_glow}" stop-opacity=".55"/><stop offset="1" stop-color="{theme.accent_glow}" stop-opacity="0"/></radialGradient>
<radialGradient id="beatGlow"><stop offset="0" stop-color="{theme.amber_mark}" stop-opacity=".5"/><stop offset="1" stop-color="{theme.amber_mark}" stop-opacity="0"/></radialGradient>
<clipPath id="card"><rect width="{WIDTH}" height="{HEIGHT}" rx="16"/></clipPath>
<clipPath id="sweep"><rect x="{LEFT - 8}" y="0" width="0" height="{HEIGHT}"><animate attributeName="width" from="0" to="{RIGHT - LEFT + 16}" begin="{REVEAL_DELAY}s" dur="{REVEAL_SECONDS}s" fill="freeze" {ease}/></rect></clipPath>
<path id="sig" d="{_d(trace)}"/>
<path id="probePath" d="{_d(motion)}"/>
</defs>
<g clip-path="url(#card)">
<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#page)"/>
<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#amber)"/>
{hex_motif(theme, 724, -36, scale=0.66, boost=1.7)}
</g>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="15.5" fill="none" stroke="{theme.border}"/>
<text x="{LEFT}" y="72" class="mono" font-size="15"><tspan fill="{theme.accent}">{esc(PROMPT)}</tspan><tspan x="{LEFT + prompt_w:.1f}" fill="{theme.text_secondary}">{COMMAND}</tspan></text>
<rect class="cursor" x="{cursor_x:.1f}" y="59" width="8" height="16" rx="1" fill="{theme.accent}"/>
<text x="{LEFT - 3}" y="136" class="sans" font-size="60" font-weight="800" letter-spacing="-1.2" fill="{theme.text_primary}">{esc(NAME)}</text>
<text x="{LEFT}" y="174" class="sans" font-size="20" font-weight="600" fill="{theme.text_secondary}">{esc(TAGLINE)}</text>
<text x="{LEFT}" y="202" class="mono" font-size="14" fill="{theme.text_muted}">{esc(PLACE)}</text>
{dividers}
<g class="reveal" fill="none" stroke="{theme.accent}" stroke-linejoin="round" stroke-linecap="round">
{"".join(markers)}
<use href="#sig" stroke-opacity=".16" stroke-width="7"/>
<use href="#sig" stroke-width="2"/>
</g>
<g class="motion">
{"".join(pulses)}
<g opacity="0"><set attributeName="opacity" to="1" begin="{PROBE_BEGIN}s"/>
<animateMotion dur="{LOOP_SECONDS}s" begin="{PROBE_BEGIN}s" repeatCount="indefinite" calcMode="linear" keyPoints="{key_points}" keyTimes="{key_times}"><mpath href="#probePath"/></animateMotion>
<circle r="14" fill="url(#probeGlow)"/><circle r="4.5" fill="{theme.accent_glow}" stroke="{theme.page_top}" stroke-width="2"/></g>
</g>
{captions}
</svg>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "assets")
    args = parser.parse_args()
    tagline_end = LEFT + text_width(TAGLINE, 20, 600)
    if tagline_end > WIDTH - 40:
        raise SystemExit(f"Tagline overflows the banner ({tagline_end:.0f}px)")
    args.out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        target = args.out / f"hero-{theme.name}.svg"
        target.write_text(render(theme), encoding="utf-8")
        print(f"Wrote {target} ({target.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
