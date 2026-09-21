import re
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
MAIN_SKILL = SKILL_ROOT / "SKILL.md"
RFC_AUDIT = SKILL_ROOT / "scripts" / "audit_rfc2119.py"
MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")

ROUTE_DOCUMENTS = (
    "references/sub-skills/localization-lookup.md",
    "references/sub-skills/source-analyzer.md",
    "references/sub-skills/log-analyzer.md",
    "references/sub-skills/blasphemous-modding-test.md",
    "references/sub-skills/blasphemous-modding-test-automated-xunit.md",
    "references/sub-skills/blasphemous-modding-test-real-profile.md",
    "references/sub-skills/coding-standards.md",
    "references/sub-skills/referencing-modding-api.md",
)


def read(path):
    return path.read_text(encoding="utf-8")


def local_links(document):
    for raw_target in MARKDOWN_LINK.findall(read(document)):
        target = raw_target.split("#", 1)[0].strip()
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        yield (document.parent / target).resolve()


class DocumentationConsistencyTests(unittest.TestCase):
    def test_relative_links_resolve_across_reached_skill_documents(self):
        pending = [MAIN_SKILL]
        reached = set()

        while pending:
            document = pending.pop()
            if document in reached:
                continue
            self.assertTrue(document.is_file(), document)
            self.assertTrue(
                document.is_relative_to(SKILL_ROOT),
                document,
            )
            reached.add(document)
            for target in local_links(document):
                self.assertTrue(target.is_file(), f"{document}: {target}")
                if target.suffix.lower() == ".md":
                    pending.append(target)

        self.assertIn(MAIN_SKILL, reached)
        for relative in ROUTE_DOCUMENTS:
            self.assertIn((SKILL_ROOT / relative).resolve(), reached, relative)

    def test_reuses_strict_rfc2119_audit(self):
        result = subprocess.run(
            [sys.executable, str(RFC_AUDIT), "--strict"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RFC 2119 candidate audit: PASS", result.stdout)

    def test_setup_order_conditional_inputs_and_retry_preservation_are_explicit(self):
        setup = read(SKILL_ROOT / "references" / "config" / "first-time-setup.md")
        normalized = setup.casefold()

        self.assertLess(setup.index("[Python runtime gate]"), setup.index("1. Q1"))
        order = ("1. Q1", "2. Q3", "3. Q4", "4. Q4b", "5. Q5", "6. Selector")
        positions = [setup.index(marker) for marker in order]
        self.assertEqual(positions, sorted(positions))
        for phrase in (
            "q3 only when q2 is **yes**",
            "q4b only when q4 is **yes**",
            "selector details only when q6 is **yes**",
            "conditional inputs must not be presented",
            "corresponding single question",
            "retain every unrelated valid answer",
            "askuserquestion",
        ):
            self.assertIn(phrase.casefold(), normalized)

    def test_shell_templates_share_one_native_python_context(self):
        preflight = read(SKILL_ROOT / "references" / "config" / "invocation-preflight.md")
        self.assertIn(
            '`"$PYTHON3" "$SKILL_ROOT/scripts/<script>.py" [arguments]`',
            preflight,
        )
        self.assertIn(
            "`& $PYTHON3 (Join-Path $SkillRoot 'scripts\\<script>.py') [arguments]`",
            preflight,
        )
        for phrase in (
            "same native Python entry point",
            "caller's Mod repository as working directory",
            "same script and",
            "Paths remain separate quoted arguments",
            "MUST NOT use a checkout-relative Skill path",
        ):
            self.assertIn(phrase, preflight)

        for relative in (
            "references/config/first-time-setup.md",
            "references/config/python-runtime.md",
            "references/sub-skills/blasphemous-modding-test-real-profile.md",
            "references/sub-skills/referencing-modding-api.md",
        ):
            text = read(SKILL_ROOT / relative)
            self.assertIn('"$PYTHON3"', text, relative)
            self.assertIn("$SKILL_ROOT", text, relative)
            self.assertIn("& $PYTHON3", text, relative)
            self.assertIn("$SkillRoot", text, relative)

    def test_evidence_terms_keep_sources_and_gameplay_boundaries_distinct(self):
        shared = " ".join(
            read(SKILL_ROOT / "references/sub-skills/blasphemous-modding-test.md").split()
        )
        for term in (
            "Current log",
            "Test log snapshot",
            "Manual verification",
            "Automated xUnit test",
            "Real-profile test",
        ):
            self.assertIn(term, shared)
        self.assertIn("--current", shared)
        self.assertIn("not completed-session evidence", shared)
        self.assertIn("--snapshot", shared)
        self.assertIn("never falls back to a live log", shared)
        self.assertIn("mod_loaded", shared)
        self.assertIn("not gameplay proof", shared)

        real_profile = read(
            SKILL_ROOT
            / "references/sub-skills/blasphemous-modding-test-real-profile.md"
        )
        self.assertIn("complete **Test log snapshot**", real_profile)
        self.assertIn("Current log", real_profile)
        self.assertIn("There is no implicit source mode", real_profile)

        xunit = read(
            SKILL_ROOT
            / "references/sub-skills/blasphemous-modding-test-automated-xunit.md"
        )
        self.assertIn("xUnit is not gameplay proof", xunit)
        self.assertIn("Manual verification", xunit)

    def test_reached_workflows_expose_completion_evidence_and_next_action(self):
        for relative in ROUTE_DOCUMENTS:
            text = " ".join(read(SKILL_ROOT / relative).split())
            self.assertRegex(text, r"(?i)(completion criterion|completion criteria|done when)", relative)
            self.assertRegex(text, r"(?i)next (action|step|source|code|implementation|verification|maintenance|setup)", relative)

        for relative in (
            "references/config/first-time-setup.md",
            "references/config/python-runtime.md",
            "references/config/invocation-preflight.md",
        ):
            text = " ".join(read(SKILL_ROOT / relative).split())
            self.assertIn("completion evidence", text, relative)
            self.assertIn("next action", text, relative)


if __name__ == "__main__":
    unittest.main()
