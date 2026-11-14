"""Build the GitHub stats card (assets/stats-light.svg, assets/stats-dark.svg).

Numbers come from the GitHub GraphQL API (public data only):
  stars earned        sum of stargazers over the user's own public, non-fork repositories
  commits (last year) public commit contributions in the last 365 days
  pull requests       all pull requests opened by the user
  issues              all issues opened by the user
  public repositories the user's own public, non-fork repositories
  languages           code size per language over the same repositories (GitHub linguist bytes)

Standard library only, so the GitHub Action needs no installs. Token: $GITHUB_TOKEN or $GH_TOKEN,
or `gh auth token` when run locally.

Run:  python cards/stats_card.py [--user Shuruyue]
Icons: Primer Octicons (MIT License, Copyright GitHub Inc.).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import urllib.request
from html import escape
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?")
FALLBACK_COLOR = "#8b949e"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection(from: $from, to: $to) { totalCommitContributions }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

ICONS = {  # Primer Octicons, 16 px
    "star": '<path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z"/>',
    "commit": '<path d="M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z"/>',
    "pr": '<path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"/>',
    "issue": '<path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"/><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"/>',
    "repo": '<path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"/>',
}

THEMES = {
    "light": {"bg": "#ffffff", "border": "#d0d7de", "text": "#1f2328", "muted": "#656d76",
              "icon": "#0969da", "track": "#eaeef2"},
    "dark": {"bg": "#0d1117", "border": "#30363d", "text": "#e6edf3", "muted": "#8b949e",
             "icon": "#4493f8", "track": "#21262d"},
}
WIDTH, HEIGHT = 495, 195
FONT = "-apple-system,'Segoe UI',Ubuntu,Helvetica,Arial,sans-serif"


def token() -> str:
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def fetch(login: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    variables = {"login": login, "from": (now - dt.timedelta(days=365)).isoformat(), "to": now.isoformat()}
    body = json.dumps({"query": QUERY, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token()}", "Content-Type": "application/json",
        "User-Agent": "profile-stats-card"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def safe_color(value: object) -> str:
    """API colors go into SVG attributes, so accept only #RGB / #RRGGBB."""
    if isinstance(value, str) and HEX_COLOR.fullmatch(value):
        return value
    return FALLBACK_COLOR


def summarize(user: dict) -> dict:
    repos = user["repositories"]["nodes"]
    sizes: dict[str, list] = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name, color = str(edge["node"]["name"]), safe_color(edge["node"]["color"])
            sizes.setdefault(name, [0, color])[0] += int(edge["size"])
    total = sum(v[0] for v in sizes.values()) or 1
    langs = sorted(((n, s / total, c) for n, (s, c) in sizes.items()), key=lambda x: -x[1])
    return {
        "stars": sum(int(r["stargazerCount"]) for r in repos),
        "commits": int(user["contributionsCollection"]["totalCommitContributions"]),
        "prs": int(user["pullRequests"]["totalCount"]),
        "issues": int(user["issues"]["totalCount"]),
        "repos": int(user["repositories"]["totalCount"]),
        "languages": langs,
        "date": dt.date.today().isoformat(),
    }


def build(stats: dict, theme: dict) -> str:
    rows = [("star", "Total stars earned", stats["stars"]),
            ("commit", "Commits (last year)", stats["commits"]),
            ("pr", "Pull requests", stats["prs"]),
            ("issue", "Issues", stats["issues"]),
            ("repo", "Public repositories", stats["repos"])]
    css = (
        f".l{{font:600 14px {FONT};fill:{theme['text']}}}"
        f".v{{font:700 14px {FONT};fill:{theme['text']}}}"
        f".s{{font:400 11px {FONT};fill:{theme['muted']}}}"
        f".i{{fill:{theme['icon']}}}"
        ".row{opacity:0;animation:fade .5s ease-out forwards}"
        "@keyframes fade{to{opacity:1}}"
        ".seg{animation:draw 1.2s ease-out}"
        "@keyframes draw{from{stroke-dasharray:0 999}}"
        "@media (prefers-reduced-motion:reduce){.row{animation:none;opacity:1}.seg{animation:none}}"
    )
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
           f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="t">',
           f"<title id=\"t\">GitHub stats: {stats['stars']} stars, {stats['commits']} commits in the last "
           f"year, {stats['prs']} pull requests, {stats['issues']} issues</title>",
           f"<style>{css}</style>",
           f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="6" fill="{theme["bg"]}" '
           f'stroke="{theme["border"]}"/>']
    for k, (icon, label, value) in enumerate(rows):
        y = 38 + 29 * k
        out.append(f'<g class="row" style="animation-delay:{0.15 * k:.2f}s" transform="translate(25 {y})">'
                   f'<g class="i" transform="translate(0 -12)">{ICONS[icon]}</g>'
                   f'<text class="l" x="26" y="0">{label}:</text>'
                   f'<text class="v" x="230" y="0">{value:,}</text></g>')
    out.append(f'<text class="s" x="25" y="{HEIGHT - 14}">public repositories only</text>')

    # language ring: top 4 languages + other
    cx, cy, r, width = 402, 76, 34, 9
    circ = 2 * 3.141592653589793 * r
    langs = stats["languages"][:4]
    other = 1.0 - sum(f for _, f, _ in langs)
    segments = langs + ([("Other", other, theme["muted"])] if other > 0.005 else [])
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{theme["track"]}" stroke-width="{width}"/>')
    start = 0.0
    for name, frac, color in segments:
        length = frac * circ
        out.append(f'<circle class="seg" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
                   f'stroke-width="{width}" stroke-dasharray="{length:.2f} {circ:.2f}" '
                   f'stroke-dashoffset="{-start:.2f}" '
                   f'transform="rotate(-90 {cx} {cy})"><title>{escape(name)} {100 * frac:.1f}%</title></circle>')
        start += length
    out.append(f'<text class="s" x="{cx}" y="{cy - r - 14}" text-anchor="middle">languages by code size</text>')
    for k, (name, frac, color) in enumerate(segments[:3]):
        y = 138 + 17 * k
        out.append(f'<circle cx="{cx - 60}" cy="{y - 4}" r="4.5" fill="{color}"/>'
                   f'<text class="s" x="{cx - 50}" y="{y}">{escape(name)} {100 * frac:.1f}%</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="Shuruyue")
    args = parser.parse_args()
    stats = summarize(fetch(args.user))
    print({k: v for k, v in stats.items() if k != "languages"})
    print("languages:", [(n, round(100 * f, 1)) for n, f, _ in stats["languages"][:8]])
    ASSETS.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        (ASSETS / f"stats-{name}.svg").write_text(build(stats, theme), encoding="utf-8")


if __name__ == "__main__":
    main()
