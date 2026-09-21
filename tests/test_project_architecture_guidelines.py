import unittest
from pathlib import Path


SKILL_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
)
ROUTER = SKILL_ROOT / "references" / "sub-skills" / "coding-standards.md"
HARMONY = (
    SKILL_ROOT
    / "references"
    / "coding-standards"
    / "coding-standards-harmony-patching.md"
)
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

    def test_route_contract_covers_activation_scope_and_result(self):
        router = ROUTER.read_text(encoding="utf-8").casefold()
        guide = GUIDE.read_text(encoding="utf-8").casefold()

        for phrase in (
            "no established directory, namespace, module, or feature boundaries",
            "explicitly asks how to organize or place new files or directories",
            "ordinary request in a project with established or feature-oriented structure",
            "must not impose the default role categories",
        ):
            self.assertIn(phrase, router)
        for phrase in (
            "new files and directories in mod-owned code",
            "decompiled game code, dependency code, upstream code, generated output, and build output",
            "must not move, rename, or restructure existing files",
            "activation status",
            "activation reason",
            "preserved boundary",
            "primary responsibility",
            "suggested directory",
            "suggested namespace",
        ):
            self.assertIn(phrase, guide)

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

    def test_guide_covers_placement_precedence_and_category_boundaries(self):
        guide = GUIDE.read_text(encoding="utf-8").casefold()

        for phrase in (
            "project root is limited to entrypoints, startup orchestration, and project-level public types",
            "configuration, serialized settings, and persistence data models",
            "reusable mod-owned runtime or domain objects, state, registries",
            "extension methods and support types tightly coupled",
            "mod console command classes and command-specific behavior",
            "established feature-oriented structure takes precedence",
            "must not move, rename, or restructure existing files",
            "generic utils, helpers, or managers buckets",
            "documented gap",
            "does not redefine naming, compiler compatibility, lifecycle behavior, patch target resolution, or patch discovery",
        ):
            self.assertIn(phrase, guide)

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

    def test_patch_and_event_ownership_matches_harmony_reference(self):
        guide = GUIDE.read_text(encoding="utf-8").casefold()
        harmony = HARMONY.read_text(encoding="utf-8").casefold()

        for phrase in (
            "patches is the default harmony category",
            "projects that already use harmonypatches may keep that name",
            "harmonypatches is justified for a project that genuinely separates multiple patch mechanisms",
            "a harmony bridge that raises an event remains here",
            "event definitions, handlers, and subscription orchestration",
        ):
            self.assertIn(phrase, guide)
        for phrase in (
            "new mod-owned patch files must live under mod root's `patches/` directory by default",
            "established `harmonypatches/` boundary",
            "must not require a rename or migration",
            "framework-managed discovery",
        ):
            self.assertIn(phrase, harmony)


if __name__ == "__main__":
    unittest.main()
