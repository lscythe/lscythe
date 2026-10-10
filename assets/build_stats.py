"""Builds the GitHub stats card in the Circuit 炼器 look of lscythe.dev.

Writes assets/stats-dark.svg and assets/stats-light.svg from GitHub's
GraphQL API: the last year's contribution calendar and counts, and the
languages across public, non-fork repos. The profile-refresh workflow runs
it daily; locally it borrows the gh CLI's token.

    python3 assets/build_stats.py

Only public data goes in: repos are queried with privacy: PUBLIC, and the
contribution counts are the ones the public profile shows.
"""

import json
import os
import subprocess
import urllib.request
from collections import Counter
from datetime import date

from circuit import HERE, THEMES, font_faces, grid

LOGIN = "lscythe"
W, H = 1200, 600

# Build scripts and platform-runner glue (Flutter's generated desktop
# runners are most of the C++ and CMake), not languages I write in.
IGNORED_LANGUAGES = {"Shell", "PowerShell", "CMake", "C++", "C", "Batchfile", "Dockerfile", "Makefile", "Ruby", "Objective-C"}

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      totalCount
      nodes { languages(first: 20) { edges { size node { name } } } }
    }
  }
}
"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def token() -> str:
    return os.environ.get("GITHUB_TOKEN") or subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, check=True
    ).stdout.strip()


def fetch() -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        body = json.load(res)
    if "errors" in body:
        raise SystemExit(f"GitHub API: {body['errors']}")
    return body["data"]["user"]


def summarise(user: dict) -> dict:
    cc = user["contributionsCollection"]
    weeks = [[(d["date"], d["contributionCount"], LEVELS[d["contributionLevel"]]) for d in w["contributionDays"]]
             for w in cc["contributionCalendar"]["weeks"]]
    days = [d for w in weeks for d in w]

    longest = run = 0
    for _, count, _ in days:
        run = run + 1 if count else 0
        longest = max(longest, run)

    langs = Counter()
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            if e["node"]["name"] not in IGNORED_LANGUAGES:
                langs[e["node"]["name"]] += e["size"]
    total = sum(langs.values()) or 1

    return dict(
        weeks=weeks,
        readouts=[
            ("CONTRIBUTIONS", cc["contributionCalendar"]["totalContributions"]),
            ("COMMITS", cc["totalCommitContributions"]),
            ("PULL REQUESTS", cc["totalPullRequestContributions"]),
            ("ACTIVE DAYS", sum(1 for d in days if d[1])),
            ("LONGEST STREAK", longest),
        ],
        repos=user["repositories"]["totalCount"],
        languages=[(name, size / total) for name, size in langs.most_common(6)],
        updated=date.today().strftime("%Y.%m.%d"),
    )


def build(theme: str, s: dict) -> str:
    t = THEMES[theme]
    x0 = 100

    readouts = "".join(
        f'<text class="mono" x="{x0 + i * 200}" y="128">{label}</text>'
        f'<text class="num{" lead" if i == 0 else ""}" x="{x0 - 2 + i * 200}" y="180">{value:,}</text>'
        for i, (label, value) in enumerate(s["readouts"])
    )

    # The calendar: one column a week, lit by GitHub's own quartiles. Columns
    # switch on left to right, like the site's segment meters.
    pitch, cell, top = 18, 14, 250
    cells, months, last_month = [], [], None
    for wi, week in enumerate(s["weeks"]):
        for day, count, level in week:
            row = date.fromisoformat(day).isoweekday() % 7  # Sunday first, as GitHub draws it
            cells.append(
                f'<rect class="l{level}" x="{x0 + wi * pitch}" y="{top + row * pitch}" width="{cell}" height="{cell}" style="--w:{wi}">'
                f"<title>{day}: {count}</title></rect>"
            )
        month = date.fromisoformat(week[0][0]).strftime("%b").upper()
        if month != last_month and wi < len(s["weeks"]) - 2:
            months.append(f'<text class="mono small" x="{x0 + wi * pitch}" y="{top - 12}">{month}</text>')
        last_month = month
    legend_x = 1100 - 5 * pitch
    legend = "".join(
        f'<rect class="l{lv}" x="{legend_x + lv * pitch}" y="{top + 7 * pitch + 10}" width="{cell}" height="{cell}"/>' for lv in range(5)
    )

    # Languages, as the site's stack panel: twenty segments, lit to the leader.
    lead = s["languages"][0][1] if s["languages"] else 1
    langs = []
    for i, (name, share) in enumerate(s["languages"]):
        col, row = divmod(i, 3)
        x, y = x0 + col * 520, 474 + row * 30
        lit = max(1, round(share / lead * 20))
        segs = "".join(
            f'<rect class="{"on" if k < lit else "off"}" x="{x + 140 + k * 13}" y="{y - 11}" width="10" height="10"/>' for k in range(20)
        )
        langs.append(
            f'<text class="mono" x="{x}" y="{y}">{name.upper()}</text>{segs}'
            f'<text class="mono" x="{x + 470}" y="{y}" text-anchor="end">{share * 100:.1f}%</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="title">
<title id="title">GitHub activity for {LOGIN}: {", ".join(f"{v} {k.lower()}" for k, v in s["readouts"])} in the last year</title>
<style>
{font_faces()}
.mono {{ font-family: "Share Tech Mono", ui-monospace, Menlo, monospace; font-size: 17px; letter-spacing: 0.1em; fill: {t["muted"]}; }}
.small {{ font-size: 14px; }}
.signal {{ fill: {t["signal"]}; }}
.num {{ font-family: Tektur, "Space Grotesk", sans-serif; font-weight: 800; font-size: 46px; fill: {t["text"]}; }}
.lead {{ fill: {t["signal"]}; }}
.frame {{ fill: none; stroke: {t["line_strong"]}; stroke-width: 1; }}
.rule {{ stroke: {t["line"]}; stroke-width: 1; }}
.trace {{ fill: none; stroke: {t["trace"]}; stroke-width: 1; }}
.accent {{ fill: none; stroke: {t["violet"]}; stroke-width: 2; }}
.l0, .off {{ fill: {t["off"]}; }}
.l1 {{ fill: {t["signal"]}; fill-opacity: .3; }}
.l2 {{ fill: {t["signal"]}; fill-opacity: .55; }}
.l3 {{ fill: {t["signal"]}; fill-opacity: .8; }}
.l4, .on {{ fill: {t["signal"]}; }}
@media (prefers-reduced-motion: no-preference) {{
  [style*="--w"] {{ animation: on .25s steps(1) calc(0.2s + var(--w) * 0.02s) backwards; }}
}}
@keyframes on {{ from {{ fill: {t["off"]}; fill-opacity: 1; }} }}
</style>
{grid(t, W, H)}
<path class="trace" d="M40 0 V{H} M1160 0 V{H} M0 {H - 18} H700 L716 {H - 34} H800"/>
<path class="accent" d="M40 200 V280 M1160 380 V440"/>
<path class="frame" d="M76 40 H1092 L1124 72 V{H - 44} H76 Z"/>

<text class="mono signal" x="{x0}" y="80">SIG.04 · SIGNAL LOG</text>
<text class="mono" x="1100" y="80" text-anchor="end">@{LOGIN.upper()} · {s["repos"]} PUBLIC REPOS · LAST 12 MONTHS</text>
{readouts}
<line class="rule" x1="76" x2="1124" y1="206" y2="206"/>
{"".join(months)}
{"".join(cells)}
<text class="mono small" x="{legend_x - 12}" y="{top + 7 * pitch + 22}" text-anchor="end">LESS</text>
{legend}
<text class="mono small" x="{legend_x + 5 * pitch + 2}" y="{top + 7 * pitch + 22}">MORE</text>
<text class="mono small" x="{x0}" y="{top + 7 * pitch + 22}">UPDATED {s["updated"]}</text>
<line class="rule" x1="76" x2="1124" y1="420" y2="420"/>
<text class="mono signal" x="{x0}" y="448">STK.05 · LANGUAGES BY CODE SIZE</text>
{"".join(langs)}
</svg>
"""


if __name__ == "__main__":
    stats = summarise(fetch())
    for name in THEMES:
        (HERE / f"stats-{name}.svg").write_text(build(name, stats))
        print(f"wrote assets/stats-{name}.svg")
