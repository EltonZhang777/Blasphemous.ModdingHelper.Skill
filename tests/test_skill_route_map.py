import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAIN_SKILL = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "SKILL.md"


class SkillRouteMapTests(unittest.TestCase):
    def test_supported_game_scope_is_clear_before_request_routing(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")
        description = next(
            line.split(":", 1)[1].strip()
            for line in text.split("---", 2)[1].splitlines()
            if line.startswith("description:")
        )
        opening = text.split("## Request routing", 1)[0]
        normalized_description = " ".join(description.split())
        normalized_opening = " ".join(opening.split())
        normalized_text = " ".join(text.split())

        self.assertLess(len(description.strip()), 599)
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
        for route in ("localization-lookup.md", "save-analysis.md"):
            self.assertIn(
                "[Invocation preflight](references/config/invocation-preflight.md)",
                destinations[f"references/sub-skills/{route}"][2],
                route,
            )

        mod_test_boundary = destinations[
            "references/sub-skills/blasphemous-modding-test.md"
        ][2]
        for classification in ("Real-profile", "xUnit", "both", "ambiguous"):
            self.assertIn(classification, mod_test_boundary)

    def test_coding_standards_heading_points_to_its_route_owner(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")
        section = text.split("## Coding standards", 1)[1].split("\n## ", 1)[0]
        normalized = " ".join(section.split())

        self.assertIn("coding-standards.md", section)
        self.assertIn("C#", normalized)
        self.assertEqual(
            len([line for line in section.splitlines() if line.strip()]),
            1,
        )

    def test_step_four_defines_checkable_completion(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")
        section = text.split("### Step 4: Solve User Question", 1)[1].split(
            "\n### ",
            1,
        )[0]
        normalized = " ".join(section.split())

        for phrase in (
            "completion criteria",
            "claiming completion",
            "blocked or failed",
            "next action",
            "path",
            "artifact",
            "evidence",
        ):
            self.assertIn(phrase, normalized.casefold())

    def test_xunit_exception_is_owned_by_the_mod_test_entry(self):
        documents = {
            "entry": MAIN_SKILL,
            "preflight": (
                MAIN_SKILL.parent / "references/config/invocation-preflight.md"
            ),
            "mod-test": (
                MAIN_SKILL.parent
                / "references/sub-skills/blasphemous-modding-test.md"
            ),
        }
        expected_owner = {
            "entry": r"\bmod-test entry\b",
            "preflight": r"\bmod-test entry\b",
            "mod-test": r"\bthis entry\b",
        }
        all_sentences = []
        for name, document in documents.items():
            text = " ".join(document.read_text(encoding="utf-8").split()).casefold()
            sentences = [
                re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", sentence)
                for sentence in re.split(r"(?<=[.!?;])\s+", text)
            ]
            all_sentences.extend(sentences)
            self.assertTrue(
                any(
                    "xunit" in sentence
                    and re.search(
                        rf"{expected_owner[name]}\s+owns?\b",
                        sentence,
                    )
                    and not re.search(r"\b(?:not|never)\b", sentence)
                    for sentence in sentences
                ),
                name,
            )
            if name == "mod-test":
                self.assertTrue(
                    any(
                        "does not" in sentence and "configuration" in sentence
                        for sentence in sentences
                    )
                )

        self.assertFalse(
            any(
                "xunit" in sentence
                and re.search(
                    r"\binvocation preflight\b[^.;]*\bowns?\b",
                    sentence,
                )
                and not re.search(r"\b(?:not|never)\b", sentence)
                for sentence in all_sentences
            )
        )

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
