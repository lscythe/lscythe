"""Shared pieces of the Circuit 炼器 look of lscythe.dev, for the SVGs in assets/.

Tokens come from the website's src/lib/styles/global.css; fnv, mulberry
and barcode are ports of its src/lib/hud.ts. The fonts in assets/fonts are
latin subsets from @fontsource (SIL OFL 1.1), embedded as base64 because
GitHub shows README images through <img>, which can't fetch web fonts.
"""

import base64
import math
from pathlib import Path

HERE = Path(__file__).parent

# Lime at night, violet by day.
THEMES = {
    "dark": dict(
        bg="#050505", grid="rgb(255 255 255 / 0.04)", trace="#2a2a2a", line="#1f1f1f", line_strong="#3a3a3a",
        text="#e9e9e9", text2="#b3b3b3", muted="#7a7a7a", off="#171717", signal="#d4f53c", violet="#7c3dff",
    ),
    "light": dict(
        bg="#ecece8", grid="rgb(10 10 10 / 0.06)", trace="#c9c9c2", line="#c9c9c2", line_strong="#0a0a0a",
        text="#0a0a0a", text2="#3b3b38", muted="#6c6c66", off="#d6d6cf", signal="#5512e8", violet="#5512e8",
    ),
}


def _font(file: str) -> str:
    data = base64.b64encode((HERE / "fonts" / file).read_bytes()).decode()
    return f"url(data:font/woff2;base64,{data}) format('woff2')"


def font_faces() -> str:
    return f"""@font-face {{ font-family: Tektur; font-weight: 800; src: {_font("tektur-latin-800-normal.woff2")}; }}
@font-face {{ font-family: Tektur; font-weight: 500; src: {_font("tektur-latin-500-normal.woff2")}; }}
@font-face {{ font-family: "Share Tech Mono"; src: {_font("share-tech-mono-latin-400-normal.woff2")}; }}"""


def grid(t: dict, w: int, h: int) -> str:
    """The blueprint grid the whole site sits on."""
    return f"""<defs>
  <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
    <path d="M24 0H0V24" fill="none" stroke="{t["grid"]}" stroke-width="1"/>
  </pattern>
</defs>
<rect width="{w}" height="{h}" fill="{t["bg"]}"/>
<rect width="{w}" height="{h}" fill="url(#grid)"/>"""


U32 = 0xFFFFFFFF


def fnv(s: str) -> int:
    """FNV-1a, 32-bit."""
    h = 2166136261
    for c in s:
        h = ((h ^ ord(c)) * 16777619) & U32
    return h


def _imul(a: int, b: int) -> int:
    return (a * b) & U32


def mulberry(seed: int):
    """Mulberry32: a seeded random in [0, 1)."""
    state = [seed & U32]

    def r() -> float:
        state[0] = (state[0] + 0x6D2B79F5) & U32
        s = state[0]
        t = _imul(s ^ (s >> 15), 1 | s)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & U32) ^ t
        return ((t ^ (t >> 14)) & U32) / 4294967296

    return r


def barcode(s: str, bars: int = 28) -> list[int]:
    """Bar widths (in units) for a decorative barcode."""
    r = mulberry(fnv(s) ^ 0x5BD1E9)
    return [1 + math.floor(r() * 3) for _ in range(bars)]
