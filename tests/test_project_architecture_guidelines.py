import unittest
from pathlib import Path


SKILL_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
)
ROUTER = SKILL_ROOT / "references" / "sub-skills" / "coding-standards.md"
GUIDE = (
    SKILL_ROOT
    / "references"
    / "sub-skills"
    / "project-architecture-guidelines.md"
)


def table_rows(text, heading):
    lines = text.splitlines()
    heading_index = lines.index(heading)
    header_index = next(
        index
        for index in range(heading_index + 1, len(lines))
        if lines[index].startswith("|")
    )
    rows = []
    for line in lines[header_index + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


class ProjectArchitectureDocumentationTests(unittest.TestCase):
    def test_router_starts_with_a_complete_route_map(self):
        router = ROUTER.read_text(encoding="utf-8")
        route_rows = table_rows(router, "## Route map")
        route_text = "\n".join(" | ".join(row) for row in route_rows).casefold()

        self.assertTrue(GUIDE.exists())
        self.assertLess(router.index("## Route map"), router.index("## Coding specifications"))
        for target in (
            "project-architecture-guidelines.md",
            "coding-standards-csharp-unity.md",
            "coding-standards-moddingapi.md",
            "coding-standards-harmony-patching.md",
        ):
            self.assertIn(target, route_text)
        self.assertIn("scope gate", route_text)

    def test_guide_covers_categories_and_primary_responsibility(self):
        guide = GUIDE.read_text(encoding="utf-8")
        categories = {
            row[0]: " ".join(row[1:]).casefold()
            for row in table_rows(guide, "## Default shape")
        }

        self.assertEqual(
            set(categories),
            {"Components", "Configs", "Extensions", "Patches", "Events", "Commands"},
        )
        for category, terms in {
            "Components": ("runtime", "domain"),
            "Configs": ("configuration", "persistence"),
            "Extensions": ("extension methods",),
            "Patches": ("harmony patch",),
            "Events": ("event", "handlers"),
            "Commands": ("console command",),
        }.items():
            for term in terms:
                self.assertIn(term, categories[category])
        guide_lower = guide.casefold()
        for phrase in (
            "primary responsibility",
            "new namespaces",
            "independently meaningful responsibilities",
            "stable responsibility",
        ):
            self.assertIn(phrase, guide_lower)

    def test_guide_preserves_existing_structure_and_boundaries(self):
        guide = GUIDE.read_text(encoding="utf-8").casefold()

        for phrase in (
            "must not move, rename, or restructure existing files",
            "harmonypatches",
            "harmony bridge that raises an event remains here",
            "generic utils, helpers, or managers buckets",
            "traverseutils.cs",
            "must not be copied as an architecture requirement",
        ):
            self.assertIn(phrase, guide)
        for repository in (
            "https://github.com/EltonZhang777/Blasphemous.LocalizationPatcher",
            "https://github.com/EltonZhang777/Blasphemous.InventorySorting",
        ):
            self.assertIn(repository.casefold(), guide)


if __name__ == "__main__":
    unittest.main()
