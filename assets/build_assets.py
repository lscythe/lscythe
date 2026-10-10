"""Builds the profile banner and project sigils in the Circuit 炼器 look of lscythe.dev.

Writes assets/banner-dark.svg, assets/banner-light.svg and one
assets/sigils/<repo>.svg per entry in PROJECTS. GitHub shows
README images through <img>, which can't fetch web fonts, so Tektur and
Share Tech Mono are embedded as base64 (latin subsets, ~30 KB in total).

    python3 assets/build_assets.py [path/to/website]

The website repo (default ~/Documents/personal/research/website) must have
its node_modules installed; the fonts come from @fontsource there. The
sigil and barcode are ports of src/lib/sigil.ts and src/lib/hud.ts, so
they come out the same as on the site.
"""

import base64
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
SITE = Path(sys.argv[1] if len(sys.argv) > 1 else "~/Documents/personal/research/website").expanduser()
FONTS = SITE / "node_modules/@fontsource"

W, H = 1200, 460

# Tokens from src/lib/styles/global.css: lime at night, violet by day.
THEMES = {
    "dark": dict(
        bg="#050505", grid="rgb(255 255 255 / 0.04)", trace="#2a2a2a", line_strong="#3a3a3a",
        text="#e9e9e9", text2="#b3b3b3", muted="#7a7a7a", signal="#d4f53c", violet="#7c3dff",
    ),
    "light": dict(
        bg="#ecece8", grid="rgb(10 10 10 / 0.06)", trace="#c9c9c2", line_strong="#0a0a0a",
        text="#0a0a0a", text2="#3b3b38", muted="#6c6c66", signal="#5512e8", violet="#5512e8",
    ),
}

# Hairline traces, bending at 45°. Accents are drawn in violet.
TRACES = [
    "M0 44 H520 L556 80 H900 L936 44 H1200",
    "M0 452 H740 L760 432 H820",
    "M40 0 V460",
    "M1160 0 V460",
    "M1124 300 L1160 336",
]
ACCENTS = ["M40 150 V250", "M1160 360 V420", "M700 80 H820"]
PADS = [(556, 80), (900, 80), (820, 432), (1124, 300)]

# Repos that get a sigil in the README, drawn from their names like a
# project card's on the site.
PROJECTS = ["navigo", "xuefu", "gradlens", "domain-probe"]

U32 = 0xFFFFFFFF


# --- ports of src/lib/hud.ts -------------------------------------------------

def fnv(s: str) -> int:
    h = 2166136261
    for c in s:
        h = ((h ^ ord(c)) * 16777619) & U32
    return h


def imul(a: int, b: int) -> int:
    return (a * b) & U32


def mulberry(seed: int):
    state = [seed & U32]

    def r() -> float:
        state[0] = (state[0] + 0x6D2B79F5) & U32
        s = state[0]
        t = imul(s ^ (s >> 15), 1 | s)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & U32) ^ t
        return ((t ^ (t >> 14)) & U32) / 4294967296

    return r


def barcode(s: str, bars: int = 28) -> list[int]:
    r = mulberry(fnv(s) ^ 0x5BD1E9)
    return [1 + math.floor(r() * 3) for _ in range(bars)]


# --- port of sigilCurve() in src/lib/sigil.ts --------------------------------

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def sigil_curve(name: str, n: int = 2200):
    values = [ALPHABET.index(c) + 1 for c in name.upper() if c in ALPHABET] or [1]
    at = lambda i: values[i % len(values)]
    fold = 3 + sum(values) % 6
    base = [2, 3, fold]
    detune = lambda i: ((at(i) % 10) - 4.5) * 0.004
    phase = lambda i: (at(i) / 36) * math.tau
    damp = 0.012 + (values[-1] % 10) * 0.003
    T = 70

    pts = []
    for i in range(n + 1):
        t = i / n * T
        e = math.exp(-damp * t)
        axis = lambda k: e * (
            math.sin((base[k] + detune(k)) * t + phase(k))
            + 0.6 * math.sin((base[(k + 1) % 3] + detune(k + 3)) * t + phase(k + 3))
        )
        pts.append((axis(0), axis(1), axis(2)))
    peak = max(math.hypot(*p) for p in pts)
    return [tuple(v / peak for v in p) for p in pts]


def sigil(name: str, cx: float, cy: float, size: float, yaw=0.0, pitch=0.45, bands=6, n=2200) -> tuple[str, str, str]:
    """The still sigil, projected like makeSigil(): near side bright, far side dim.

    Returns (faint full trace + axes, accent trace split into depth bands)."""
    cyaw, syaw, cp, sp, cam = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), 3.4

    def P(p):
        x, y, z = p
        x1, z1 = x * cyaw - z * syaw, x * syaw + z * cyaw
        y1, z2 = y * cp - z1 * sp, y * sp + z1 * cp
        k = cam / (cam + z2)
        return cx + x1 * size * k, cy - y1 * size * k, z2

    curve = [P(p) for p in sigil_curve(name, n)]
    axes = []
    for a, b in [((-1.1, 0, 0), (1.1, 0, 0)), ((0, -1.1, 0), (0, 1.1, 0)), ((0, 0, -1.1), (0, 0, 1.1))]:
        (ax, ay, _), (bx, by, _) = P(a), P(b)
        axes.append(f"M{ax:.1f} {ay:.1f}L{bx:.1f} {by:.1f}")
    full = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y, _ in curve)

    # Runs of segments in the same band become one polyline, to keep the file small.
    paths, prev = [[] for _ in range(bands)], None
    for a, b in zip(curve, curve[1:]):
        near = max(0, min(0.999, 1 - (a[2] + b[2] + 2) / 4))
        band = int(near * bands)
        paths[band].append(f"{'L' if band == prev else f'M{a[0]:.1f} {a[1]:.1f}L'}{b[0]:.1f} {b[1]:.1f}")
        prev = band
    lit = "".join(
        f'<path d="{"".join(p)}" opacity="{0.25 + 0.75 * ((k + 0.5) / bands):.2f}"/>' for k, p in enumerate(paths) if p
    )
    faint = "".join(f'<path d="{d}" opacity="0.45"/>' for d in axes) + f'<path d="{full}" opacity="0.3"/>'
    # The pen draws the trace in once: one continuous path for the animation
    # mask, so the banded strokes appear in order along the curve.
    mask = f'<path d="{full}" pathLength="1" class="pen"/>'
    return faint, lit, mask


def font(name: str, file: str) -> str:
    data = base64.b64encode((FONTS / name / "files" / file).read_bytes()).decode()
    return f"url(data:font/woff2;base64,{data}) format('woff2')"


def build(theme: str) -> str:
    t = THEMES[theme]

    bars, x = [], 0
    for i, w in enumerate(barcode("Rendra Prasetia")):
        if i % 2 == 0:
            bars.append(f'<rect x="{x * 3}" y="0" width="{w * 3}" height="24"/>')
        x += w + 1
    bars_w = x * 3

    faint, lit, mask = sigil("lscythe", 840, 240, 118)

    traces = "".join(f'<path d="{d}" pathLength="1" style="--i:{i}"/>' for i, d in enumerate(TRACES))
    accents = "".join(
        f'<path class="accent" d="{d}" pathLength="1" style="--i:{len(TRACES) + i}"/>' for i, d in enumerate(ACCENTS)
    )
    pads = "".join(f'<rect x="{x - 3}" y="{y - 3}" width="6" height="6" class="pad"/>' for x, y in PADS)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="title">
<title id="title">Rendra Prasetia (lscythe), mobile systems engineer</title>
<style>
@font-face {{ font-family: Tektur; font-weight: 800; src: {font("tektur", "tektur-latin-800-normal.woff2")}; }}
@font-face {{ font-family: Tektur; font-weight: 500; src: {font("tektur", "tektur-latin-500-normal.woff2")}; }}
@font-face {{ font-family: "Share Tech Mono"; src: {font("share-tech-mono", "share-tech-mono-latin-400-normal.woff2")}; }}
.mono {{ font-family: "Share Tech Mono", ui-monospace, Menlo, monospace; font-size: 18px; letter-spacing: 0.1em; fill: {t["muted"]}; }}
.signal {{ fill: {t["signal"]}; }}
.display {{ font-family: Tektur, "Space Grotesk", sans-serif; font-size: 108px; letter-spacing: -0.01em; }}
.filled {{ font-weight: 800; fill: {t["signal"]}; }}
.outline {{ font-weight: 500; fill: none; stroke: {t["text"]}; stroke-width: 1.5; }}
.hanzi {{ font-family: "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
  font-weight: 900; font-size: 92px; fill: none; stroke: {t["violet"]}; stroke-width: 1.2; }}
.traces path {{ fill: none; stroke: {t["trace"]}; stroke-width: 1; }}
.traces .accent {{ stroke: {t["violet"]}; stroke-width: 2; }}
.pad {{ fill: {t["bg"]}; stroke: {t["violet"]}; stroke-width: 1.5; }}
.frame {{ fill: none; stroke: {t["line_strong"]}; stroke-width: 1; }}
.sigil-ink path {{ fill: none; stroke: {t["muted"]}; stroke-width: 1; }}
.sigil-lit path {{ fill: none; stroke: {t["violet"]}; stroke-width: 1.5; stroke-linejoin: round; }}
.pen {{ fill: none; stroke: #fff; stroke-width: 14; stroke-linejoin: round; }}
.led, .barcode {{ fill: {t["signal"]}; }}
@media (prefers-reduced-motion: no-preference) {{
  .traces path {{ stroke-dasharray: 1; animation: draw 1.4s cubic-bezier(.7,0,.2,1) calc(0.2s + var(--i) * 0.12s) backwards; }}
  .pen {{ stroke-dasharray: 1; animation: draw 6s cubic-bezier(.45,0,.2,1) .6s backwards; }}
  .led {{ animation: blink 2.4s steps(1) infinite; }}
}}
@keyframes draw {{ from {{ stroke-dashoffset: 1; }} }}
@keyframes blink {{ 50% {{ opacity: .2; }} }}
</style>
<defs>
  <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
    <path d="M24 0H0V24" fill="none" stroke="{t["grid"]}" stroke-width="1"/>
  </pattern>
  <mask id="pen" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">{mask}</mask>
</defs>
<rect width="{W}" height="{H}" fill="{t["bg"]}"/>
<rect width="{W}" height="{H}" fill="url(#grid)"/>
<g class="traces">{traces}{accents}</g>
{pads}
<path class="frame" d="M76 84 H1092 L1124 116 V400 H76 Z"/>

<g class="sigil-ink">{faint}</g>
<g class="sigil-lit" mask="url(#pen)">{lit}</g>

<text class="mono" x="100" y="126">HANDLE // LSCYTHE</text>
<text class="mono signal" x="100" y="156">&gt; RP-2019 · MOBILE SYSTEMS ENGINEER</text>

<text class="display filled" x="94" y="262">RENDRA</text>
<text class="display outline" x="94" y="358">PRASETIA</text>

<g class="hanzi" aria-hidden="true">
  <text x="1004" y="200">炼</text>
  <text x="1004" y="296">器</text>
</g>
<text class="mono" x="1100" y="384" text-anchor="end">LSCYTHE.DEV</text>

<g transform="translate(76 438)">
  <rect class="led" x="0" y="-12" width="8" height="8"/>
  <text class="mono" x="18" y="0">LINK STABLE</text>
  <text class="mono" x="176" y="0">JKT -6.21 / 106.85</text>
  <text class="mono" x="420" y="0">ANDROID SINCE 2019</text>
</g>
<g class="barcode" transform="translate({1124 - bars_w} 418)">{"".join(bars)}</g>
</svg>
"""


def build_sigil(name: str, size: int = 120) -> str:
    """A project's sigil on a transparent square, in fewer segments than the
    banner's, as the site does for small canvases. Violet and grey read on
    both GitHub themes, so one file serves both. The yaw comes from the
    name, so it is fixed like everything else."""
    yaw = fnv(name) % 1000 / 1000 * math.tau
    faint, lit, mask = sigil(name, size / 2, size / 2, size * 0.46, yaw=yaw, n=900)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="Sigil for {name}">
<style>
.ink path {{ fill: none; stroke: #8a8a8a; stroke-width: 1; }}
.lit path {{ fill: none; stroke: #7c3dff; stroke-width: 1.5; stroke-linejoin: round; }}
.pen {{ fill: none; stroke: #fff; stroke-width: 10; stroke-linejoin: round; }}
@media (prefers-reduced-motion: no-preference) {{
  .pen {{ stroke-dasharray: 1; animation: draw 4s cubic-bezier(.45,0,.2,1) .4s backwards; }}
}}
@keyframes draw {{ from {{ stroke-dashoffset: 1; }} }}
</style>
<defs><mask id="pen" maskUnits="userSpaceOnUse" x="0" y="0" width="{size}" height="{size}">{mask}</mask></defs>
<g class="ink">{faint}</g>
<g class="lit" mask="url(#pen)">{lit}</g>
</svg>
"""


for name in THEMES:
    (HERE / f"banner-{name}.svg").write_text(build(name))
    print(f"wrote assets/banner-{name}.svg")

(HERE / "sigils").mkdir(exist_ok=True)
for name in PROJECTS:
    (HERE / "sigils" / f"{name}.svg").write_text(build_sigil(name))
    print(f"wrote assets/sigils/{name}.svg")
