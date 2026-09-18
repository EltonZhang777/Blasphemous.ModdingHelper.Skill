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


class ProjectArchitectureDocumentationTests(unittest.TestCase):
    def test_router_links_the_conditional_architecture_route(self):
        router = ROUTER.read_text(encoding="utf-8")

        self.assertTrue(GUIDE.exists())
        self.assertIn("project-architecture-guidelines.md", router)
        self.assertIn("no established directory, namespace, module, or feature boundaries", router)
        self.assertIn("explicitly asks how to organize or place new files or directories", router)
        self.assertIn("MUST NOT impose the default role categories", router)
        self.assertIn(
            "ordinary request in a project with established or feature-oriented structure",
            router,
        )
        self.assertIn("An explicit organization request still activates the guide", router)

    def test_guide_covers_categories_and_primary_responsibility(self):
        guide = GUIDE.read_text(encoding="utf-8")

        for category in ("Components", "Configs", "Extensions", "Patches", "Events", "Commands"):
            self.assertIn(category, guide)
        self.assertIn("primary responsibility", guide)
        self.assertIn("New namespaces SHOULD mirror their directories", guide)
        self.assertIn("independently meaningful responsibilities MUST be split", guide)
        self.assertIn("stable responsibility", guide)
        for phrase in (
            "runtime or domain objects",
            "User configuration, serialized settings",
            "Extension methods and support types",
            "Harmony Patch files and Patch classes",
            "Event definitions, handlers",
            "Mod console command classes",
        ):
            self.assertIn(phrase, guide)

    def test_guide_preserves_existing_structure_and_boundaries(self):
        guide = GUIDE.read_text(encoding="utf-8")

        for phrase in (
            "MUST NOT move, rename, or restructure existing files",
            "HarmonyPatches",
            "Harmony bridge that raises an event remains here",
            "generic Utils, Helpers, or Managers buckets",
            "TraverseUtils.cs is a legacy example explicitly excluded",
            "Blasphemous.LocalizationPatcher",
            "Blasphemous.InventorySorting",
            "not templates",
        ):
            self.assertIn(phrase, guide)


if __name__ == "__main__":
    unittest.main()
