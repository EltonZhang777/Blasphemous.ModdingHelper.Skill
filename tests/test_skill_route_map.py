import re
import unittest
from pathlib import Path

from test_documentation_consistency import (
    canonical_route_tables,
    markdown_table_cells,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAIN_SKILL = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "SKILL.md"
SOURCE_NAVIGATION = (
    MAIN_SKILL.parent / "references" / "source-code-navigation" / "MAIN.md"
)


def navigation_routes():
    table = canonical_route_tables(
        SOURCE_NAVIGATION.read_text(encoding="utf-8")
    )[0][1]
    return [
        cells
        for line in table.splitlines()[2:]
        if (cells := markdown_table_cells(line))
    ]


class SkillRouteMapTests(unittest.TestCase):
    def test_supported_game_scope_is_clear_before_request_routing(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")
        description = text.split("---", 2)[1]
        opening = text.split("## Request routing", 1)[0]
        normalized_description = " ".join(description.split())
        normalized_opening = " ".join(opening.split())

        self.assertIn("Blasphemous 1 only", normalized_description)
        self.assertIn("Blasphemous 2 is not supported", normalized_description)
        self.assertIn("Blasphemous 2-only requests", normalized_opening)
        self.assertIn(
            "MUST briefly state that Blasphemous 2 is out of scope",
            normalized_opening,
        )
        self.assertIn(
            "MUST invite the user to ask about Blasphemous 1",
            normalized_opening,
        )
        self.assertIn(
            "MUST NOT start a Skill route or Blasphemous 2-specific work",
            normalized_opening,
        )

    def test_requirement_levels_precede_request_routing(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")

        self.assertLess(
            text.index("## Requirement levels"),
            text.index("## Request routing"),
        )

    def test_routes_have_one_existing_authority_and_explicit_boundaries(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        expected_routes = (
            "localization-lookup.md",
            "source-analyzer.md",
            "unity-project-navigation.md",
            "log-analyzer.md",
            "blasphemous-modding-test.md",
            "coding-standards.md",
            "referencing-modding-api.md",
            "save-analysis.md",
        )

        for route in expected_routes:
            self.assertIn(route, text)
            self.assertTrue(
                (MAIN_SKILL.parent / "references" / "sub-skills" / route).is_file(),
                route,
            )
        for phrase in (
            "configuration-free operational exception",
            "Unity project navigation",
            "Caller-owned xUnit does not wait",
            "Real-profile",
            "both",
            "ambiguous",
            "completion report",
            "next document/action",
        ):
            self.assertIn(phrase, normalized)

    def test_achievement_requests_have_one_source_navigation_destination(self):
        routes = navigation_routes()
        self.assertEqual(len(routes), 10)
        signals = (
            ("bare achievements", "[items.md](items.md)"),
            ("framework/achievements/*", "[items.md](items.md)"),
            (
                "framework/achievements/* persistence",
                "[items.md](items.md)",
            ),
            ("achievementsmanager", "[core.md](core.md)"),
            ("lifecycle, persistence, wiring, and runtime flow", "[core.md](core.md)"),
            (
                "achievementsmanager achievement entities",
                "[core.md](core.md)",
            ),
            ("achievement ui widgets runtime flow", "[ui.md](ui.md)"),
            (
                "achievement playmaker actions runtime flow",
                "[tools.md](tools.md)",
            ),
        )
        for signal, expected in signals:
            with self.subTest(signal=signal):
                destinations = {
                    destination
                    for request_signal, destination, _ in routes
                    if signal in request_signal.casefold()
                }
                self.assertEqual(destinations, {expected})

    def test_top_level_relative_links_resolve(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#]+)", text):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            self.assertTrue(
                (MAIN_SKILL.parent / target).is_file(),
                target,
            )

if __name__ == "__main__":
    unittest.main()
