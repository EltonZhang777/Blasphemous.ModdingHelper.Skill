import re
import unittest
from pathlib import Path


SKILL_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
)
REFERENCES = SKILL_ROOT / "references" / "sub-skills"
SHARED = REFERENCES / "blasphemous-modding-test.md"
AUTOMATED = REFERENCES / "blasphemous-modding-test-automated-xunit.md"
REAL_PROFILE = REFERENCES / "blasphemous-modding-test-real-profile.md"
DOCUMENTS = (SHARED, AUTOMATED, REAL_PROFILE)


def read(path):
    return path.read_text(encoding="utf-8")


def links(text):
    return re.findall(r"\]\(([^)#]+)(?:#[^)]+)?\)", text)


class ModTestRoutingDocumentationTests(unittest.TestCase):
    def test_shared_entry_links_to_existing_branch_owners(self):
        shared = read(SHARED)
        expected = {
            AUTOMATED.name,
            REAL_PROFILE.name,
        }

        self.assertTrue(SHARED.is_file())
        self.assertTrue(AUTOMATED.is_file())
        self.assertTrue(REAL_PROFILE.is_file())
        self.assertTrue(expected.issubset(set(links(shared))))

        for document in DOCUMENTS:
            for target in links(read(document)):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                self.assertTrue(
                    (document.parent / target).is_file(),
                    f"broken documentation link in {document}: {target}",
                )

    def test_shared_entry_routes_runtime_and_deterministic_requests(self):
        rows = [line.casefold() for line in read(SHARED).splitlines()]
        real_rows = [
            line
            for line in rows
            if REAL_PROFILE.name.casefold() in line
        ]
        automated_rows = [
            line
            for line in rows
            if AUTOMATED.name.casefold() in line
        ]

        self.assertTrue(
            any(
                "modding profile" in line
                and "game process" in line
                and "player actions" in line
                for line in real_rows
            )
        )
        self.assertTrue(
            any(
                "deterministic" in line
                and "without a game process" in line
                and "player action" in line
                for line in automated_rows
            )
        )

    def test_shared_entry_keeps_ambiguity_and_evidence_separate(self):
        text = read(SHARED).casefold()

        for phrase in (
            "ask the user to clarify",
            "automated xunit first",
            "each phase",
            "manual verification",
            "mod_loaded",
            "must not be reported as gameplay verification",
        ):
            self.assertIn(phrase, text)

    def test_shared_entry_declares_one_of_four_route_results(self):
        text = read(SHARED).casefold()

        for phrase in (
            "exactly one route result",
            "real-profile",
            "xunit",
            "both",
            "ambiguous",
            "no-execution result",
            "must not execute a",
        ):
            self.assertIn(phrase, text)

    def test_automated_branch_defines_xunit_consumer_boundary(self):
        text = read(AUTOMATED).casefold()

        for phrase in (
            "xunit",
            "normal .net test runner",
            "<modreponame>.tests",
            "main mod project",
            "dotnet test",
            "mocks, stubs",
            "must not build, deploy, launch",
            "not a deployable game plugin",
            "test mod",
            "must not require",
            "modding_profile_path",
        ):
            self.assertIn(phrase, text)

    def test_automated_branch_covers_both_reference_architectures(self):
        text = read(AUTOMATED).casefold()

        for phrase in (
            "prerequisite library",
            "optional external test mod",
            "standalone mod",
            "not mandatory",
            "existing project architecture takes precedence",
        ):
            self.assertIn(phrase, text)

    def test_real_profile_branch_owns_existing_runtime_workflow(self):
        real = read(REAL_PROFILE).casefold()
        shared = read(SHARED).casefold()

        for phrase in (
            "<test_cli> run",
            "stop session_id",
            "clean session_id",
            "status",
            "profile-local",
            "process tree",
            "newest-first",
            "mod_loaded",
            "manual verification",
        ):
            self.assertIn(phrase, real)
        self.assertNotIn("<test_cli> run", shared)

    def test_skill_python_tests_remain_outside_caller_xunit_rule(self):
        text = read(SHARED).casefold()

        self.assertIn("skill repository's python cli and fixture tests", text)
        self.assertIn("caller-mod xunit convention does not redirect", text)


if __name__ == "__main__":
    unittest.main()
