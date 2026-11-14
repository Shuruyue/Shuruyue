"""Build the rotating quote card (assets/quotes-light.svg, assets/quotes-dark.svg).

The quotes take turns, fading in and out with a CSS animation. SVG has no automatic line wrapping,
so lines are broken here using Georgia Italic metrics (the first font the card asks for); the wrap
width keeps a margin for readers whose fallback serif font is wider.

Run:  python cards/quote_card.py
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from PIL import ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "assets"
METRIC_FONT = "C:/Windows/Fonts/georgiai.ttf"

QUOTES = [
    {
        "text": ("The deepest secret is that life is not a process of discovery, but a process of "
                 "creation. You are not discovering yourself, but creating yourself anew. Seek therefore, "
                 "not to find out Who You Are, but seek to determine Who You Want to Be."),
        "author": "Neale Donald Walsch",
    },
    {
        # Wording as quoted by Mease & Wyner, JMLR 9 (2008) 131-156, from A. Buja, discussion of
        # "Additive logistic regression: a statistical view of boosting", Ann. Statist. 28 (2000) 387-391.
        "text": ("There is no single true interpretation of anything; interpretation is a vehicle in the "
                 "service of human comprehension. The value of an interpretation is in enabling others "
                 "to fruitfully think about an idea."),
        "author": "Andreas Buja (2000)",
    },
]

WIDTH = 840
PAD_X = 48
FONT_SIZE = 17
LINE_HEIGHT = 27
WRAP = (WIDTH - 2 * PAD_X) * 0.93   # margin for wider fallback fonts
SECONDS_PER_QUOTE = 11
FADE_SECONDS = 0.9

THEMES = {
    "light": {"bg": "#ffffff", "border": "#d0d7de", "text": "#1f2328", "muted": "#656d76", "mark": "#d0d7de"},
    "dark": {"bg": "#0d1117", "border": "#30363d", "text": "#e6edf3", "muted": "#8b949e", "mark": "#30363d"},
}


def wrap(text: str, font: ImageFont.FreeTypeFont, width: float) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if font.getlength(trial) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def build(theme: dict) -> str:
    metric = ImageFont.truetype(METRIC_FONT, FONT_SIZE)
    wrapped = [wrap(q["text"], metric, WRAP) for q in QUOTES]
    n_lines = max(len(w) for w in wrapped)
    top = 40
    height = top + n_lines * LINE_HEIGHT + 56
    cycle = SECONDS_PER_QUOTE * len(QUOTES)
    fade = 100 * FADE_SECONDS / cycle
    share = 100 / len(QUOTES)

    css = [
        f".q{{opacity:0;animation:show {cycle}s infinite}}",
        f"@keyframes show{{0%{{opacity:0}}{fade:.2f}%{{opacity:1}}{share - fade:.2f}%{{opacity:1}}"
        f"{share:.2f}%{{opacity:0}}100%{{opacity:0}}}}",
        f".t{{font:italic {FONT_SIZE}px Georgia,'Times New Roman',serif;fill:{theme['text']}}}",
        f".a{{font:600 13px -apple-system,'Segoe UI',Helvetica,Arial,sans-serif;fill:{theme['muted']};"
        "letter-spacing:.04em}",
        f".m{{font:72px Georgia,serif;fill:{theme['mark']}}}",
        "@media (prefers-reduced-motion:reduce){.q{animation:none}.q0{opacity:1}}",
    ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title">',
        f"<title id=\"title\">{escape(' / '.join(q['author'] + ': ' + q['text'] for q in QUOTES))}</title>",
        f"<style>{''.join(css)}</style>",
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="10" '
        f'fill="{theme["bg"]}" stroke="{theme["border"]}"/>',
        f'<text class="m" x="{PAD_X - 34}" y="{top + 38}">\u201c</text>',
    ]
    for i, (q, lines) in enumerate(zip(QUOTES, wrapped)):
        block_h = len(lines) * LINE_HEIGHT
        y0 = top + (n_lines * LINE_HEIGHT - block_h) / 2 + FONT_SIZE
        out.append(f'<g class="q q{i}" style="animation-delay:{i * SECONDS_PER_QUOTE}s">')
        for j, line in enumerate(lines):
            out.append(f'<text class="t" x="{PAD_X}" y="{y0 + j * LINE_HEIGHT:.1f}">{escape(line)}</text>')
        out.append(f'<text class="a" x="{WIDTH - PAD_X}" y="{height - 26}" text-anchor="end">'
                   f"\u2014 {escape(q['author'].upper())}</text>")
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        path = ASSETS / f"quotes-{name}.svg"
        path.write_text(build(theme), encoding="utf-8")
        print(f"{path.name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
