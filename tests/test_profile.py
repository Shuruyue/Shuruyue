"""Checks for the profile repository (standard library only).

- every file the README points to exists
- every SVG in assets/ is well-formed XML with no scripts, event handlers or external references
- the stats card escapes text from the API and rejects colors that are not plain hex
"""

from __future__ import annotations

import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cards"))

import stats_card  # noqa: E402


def fake_user(languages: list[tuple[str, str | None, int]]) -> dict:
    return {
        "pullRequests": {"totalCount": 9},
        "issues": {"totalCount": 1},
        "contributionsCollection": {"totalCommitContributions": 150},
        "repositories": {
            "totalCount": 2,
            "nodes": [
                {"stargazerCount": 3, "languages": {"edges": [
                    {"size": size, "node": {"name": name, "color": color}} for name, color, size in languages]}},
                {"stargazerCount": 4, "languages": {"edges": []}},
            ],
        },
    }


class ReadmeLinks(unittest.TestCase):
    def test_local_files_exist(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        targets = re.findall(r'(?:src|srcset)="([^"]+)"', text)
        targets += re.findall(r"\]\(([^)]+)\)", text)
        local = [t for t in targets if not re.match(r"[a-z]+:", t)]
        self.assertTrue(local, "README should reference local assets")
        for target in local:
            self.assertTrue((ROOT / target).exists(), f"README points to a missing file: {target}")


class SvgAssets(unittest.TestCase):
    def test_well_formed_and_inert(self):
        svgs = sorted((ROOT / "assets").glob("*.svg"))
        self.assertTrue(svgs)
        for path in svgs:
            text = path.read_text(encoding="utf-8")
            ET.fromstring(text)  # raises on malformed XML
            self.assertNotRegex(text, r"(?i)<script", path.name)
            self.assertNotRegex(text, r"(?i)\son[a-z]+\s*=", path.name)
            self.assertNotRegex(text, r"(?i)(href|src)\s*=\s*\"(https?:|//)", path.name)


class StatsCard(unittest.TestCase):
    def test_summary_numbers(self):
        stats = stats_card.summarize(fake_user([("Python", "#3572A5", 300), ("TeX", "#3D6117", 100)]))
        self.assertEqual(stats["stars"], 7)
        self.assertEqual(stats["repos"], 2)
        self.assertEqual([n for n, _, _ in stats["languages"]], ["Python", "TeX"])
        self.assertAlmostEqual(stats["languages"][0][1], 0.75)

    def test_hostile_api_values_are_neutralised(self):
        user = fake_user([("<script>alert(1)</script>", 'red" onload="x', 10), ("Go", None, 10)])
        stats = stats_card.summarize(user)
        colors = {c for _, _, c in stats["languages"]}
        self.assertEqual(colors, {stats_card.FALLBACK_COLOR})
        for theme in stats_card.THEMES.values():
            svg = stats_card.build(stats, theme)
            ET.fromstring(svg)
            self.assertNotIn("<script>", svg)
            self.assertNotIn("onload", svg)
            self.assertIn("&lt;script&gt;", svg)

    def test_safe_color(self):
        self.assertEqual(stats_card.safe_color("#abc"), "#abc")
        self.assertEqual(stats_card.safe_color("#A1B2C3"), "#A1B2C3")
        for bad in ("abc", "#abcd", "url(#x)", None, 5, "#12345g"):
            self.assertEqual(stats_card.safe_color(bad), stats_card.FALLBACK_COLOR)


if __name__ == "__main__":
    unittest.main()
