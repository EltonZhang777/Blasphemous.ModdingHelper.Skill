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
        normalized_text = " ".join(text.split())

        self.assertLess(len(description.strip()), 400)
        self.assertNotIn("Blasphemous 2 is not supported", normalized_description)
        for cue in (
            "Blasphemous 1",
            "mod development",
            "Mod testing",
            "BepInEx/Unity diagnostics",
            "decompiled source",
            "save analysis",
            "exported Unity project navigation",
            "ModdingAPI",
            "localization",
        ):
            self.assertIn(cue.casefold(), normalized_description.casefold())

        self.assertEqual(
            normalized_text.count("Blasphemous 1 only"),
            1,
        )
        self.assertEqual(
            normalized_text.count("Blasphemous 2 is not supported"),
            1,
        )
        self.assertEqual(
            normalized_opening.count("Blasphemous 2 is not supported"),
            1,
        )
        self.assertLess(
            normalized_text.rfind("Blasphemous 2"),
            normalized_text.index("## Request routing"),
        )
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
        route_section = text.split("## Request routing", 1)[1].split(
            "\n## ",
            1,
        )[0]
        route_rows = []
        for line in route_section.splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
            if len(cells) == 3:
                route_rows.append(cells)
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

        destinations = {}
        for row in route_rows:
            match = re.fullmatch(
                r"\[[^\]]+\]\((references/sub-skills/[^)#]+\.md)\)",
                row[1],
            )
            if match:
                destinations[match.group(1)] = row

        self.assertEqual(
            set(destinations),
            {
                f"references/sub-skills/{route}"
                for route in expected_routes
            },
        )
        for route in expected_routes:
            self.assertTrue(
                (MAIN_SKILL.parent / "references" / "sub-skills" / route).is_file(),
                route,
            )

        mod_test_boundary = destinations[
            "references/sub-skills/blasphemous-modding-test.md"
        ][2]
        for classification in ("Real-profile", "xUnit", "both", "ambiguous"):
            self.assertIn(classification, mod_test_boundary)
        self.assertIn("Mod-test entry's classification", mod_test_boundary)

    def test_coding_standards_heading_points_to_its_route_owner(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")
        section = text.split("## Coding standards", 1)[1].split("\n## ", 1)[0]
        normalized = " ".join(section.split())

        self.assertIn("coding-standards.md", section)
        self.assertIn("Coding-standards sub-skill", normalized)
        self.assertEqual(normalized.count("Mod-owned C#"), 1)
        self.assertNotIn("Unity `2017.4.40f1`", section)
        self.assertNotIn("Harmony patching standards", section)
        self.assertNotIn("Referencing ModdingAPI", section)

    def test_step_four_defines_checkable_completion(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")
        section = text.split("### Step 4: Solve User Question", 1)[1].split(
            "\n### ",
            1,
        )[0]
        normalized = " ".join(section.split())

        for phrase in (
            "owner-defined completion criteria",
            "without claiming completion",
            "verified every cited",
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
