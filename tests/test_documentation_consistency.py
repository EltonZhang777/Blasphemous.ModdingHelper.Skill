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
DELEGATION_REFERENCE = "references/read-only-evidence-delegation.md"
DELEGATION_ROUTES = (
    ("references/sub-skills/source-analyzer.md", "## Read-only evidence delegation"),
    ("references/sub-skills/log-analyzer.md", "## Read-only evidence delegation"),
    ("references/sub-skills/referencing-modding-api.md", "## Read-only lookup delegation"),
    ("references/sub-skills/localization-lookup.md", "## Read-only lookup delegation"),
)
MOD_TEST_DOCUMENT = "references/sub-skills/blasphemous-modding-test.md"
NORMATIVE_HOST_DEPENDENCY = re.compile(
    r"\b(?:MUST|SHOULD|SHALL)\s+(?:use|require|depend on|run on|invoke|select)\b"
    r"[^.!?;\n]{0,120}\b(?:"
    r"(?:specific|particular|named)\s+(?:model|harness|IDE|shell|provider|"
    r"vendor(?:[- ]specific)?(?:\s+API)?)|"
    r"Codex|Claude|ChatGPT|Gemini|OpenAI|PowerShell|Bash|VS Code)\b",
    re.IGNORECASE,
)

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


def normalized(path):
    return " ".join(read(path).split()).casefold()


def markdown_section(path, heading):
    document = read(path)
    start = document.find(heading)
    if start < 0:
        return ""
    end = document.find("\n## ", start + len(heading))
    return document[start:] if end < 0 else document[start:end]


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

    def test_enabled_evidence_routes_link_to_the_shared_contract(self):
        shared = (SKILL_ROOT / DELEGATION_REFERENCE).resolve()
        self.assertIn(shared, set(local_links(MAIN_SKILL)))
        for relative, _ in DELEGATION_ROUTES:
            document = SKILL_ROOT / relative
            self.assertIn(shared, set(local_links(document)), relative)

    def test_shared_contract_defines_eligibility_ownership_handoff_and_fallback(self):
        contract = normalized(SKILL_ROOT / DELEGATION_REFERENCE)
        for phrase in (
            "read-only",
            "bounded clearly",
            "independently",
            "broad or context-heavy enough",
            "small, targeted lookup",
            "configuration or reference-lifecycle change",
            "one coherent evidence slice",
            "exactly one child owner",
            "child task must not delegate further",
            "shared workspace as read-only",
            "must not create a worktree or branch",
            "modify repository or caller files",
            "must not modify any source tree, source file, or game-code copy",
            "whether inside or outside the shared workspace",
            "every path named in",
            "references/config/first-time-setup.md",
            "main agent must retain ownership",
            "configuration and reference lifecycle changes",
            "code or document edits",
            "repository or tracker write and publication",
            "publish results",
            "compact handoff",
            "missing evidence, ambiguity, or conflicts",
            "if the available environment cannot create or safely scope a child task",
            "this contract does not require a particular model, harness, ide, shell, provider, or vendor api",
        ):
            self.assertIn(phrase, contract)

        setup = normalized(SKILL_ROOT / "references/config/first-time-setup.md")
        for source_copy in (
            "lightweight_source_code_path",
            "full_source_code_path",
            "<skill-root>/source_code/",
            "steam game installation",
        ):
            self.assertIn(source_copy, setup)
            self.assertIn(source_copy, contract)

    def test_delegation_branches_preserve_their_evidence_boundaries(self):
        source = normalized(SKILL_ROOT / DELEGATION_ROUTES[0][0])
        for phrase in (
            "any delegated source evidence work",
            "full_source_code_path",
            "lightweight_source_code_path",
            "source-path gate",
            "source code navigation guide",
            "source identity",
            "exact file path",
            "line number",
            "must not guess or switch source trees",
        ):
            self.assertIn(phrase, source)

        logs = normalized(SKILL_ROOT / DELEGATION_ROUTES[1][0])
        for phrase in (
            "any delegated log evidence work",
            "modding_profile_path",
            "unity_log_dir",
            "explicit `--current` for live diagnosis",
            "`--snapshot` for a completed test session",
            "bepinex-first analysis",
            "must not switch or silently fall back",
            "exact source/path, gap",
        ):
            self.assertIn(phrase, logs)

        modding_api = normalized(SKILL_ROOT / DELEGATION_ROUTES[2][0])
        for phrase in (
            "a small lookup on a known topic page should stay with the main agent",
            "selected local checkout or release-aware remote reference",
            "for a remote reference, the selector, resolved release/tag or version, commit",
            "for a local checkout, its absolute path, configured selector and available lock identity, and checkout head",
            "docs/development/main.md",
            "follow only linked topic pages directly required by the question",
            "version-sensitive claims",
            "must not select or resolve another reference",
            "must not clone, fetch, update, check out, replace",
        ):
            self.assertIn(phrase, modding_api)

        localization = normalized(SKILL_ROOT / DELEGATION_ROUTES[3][0])
        for phrase in (
            "full-language comparison",
            "broad index search",
            "ambiguous multi-candidate lookup",
            "small targeted lookup",
            "core or all-language index",
            "semantic-aliases.md",
            "exact localization key",
            "requested-language tsv values",
            "plausible candidates and ambiguity",
            "must not choose a different index or language scope",
            "localization evidence",
            "gameplay evidence",
            "must not perform or initiate source analysis",
        ):
            self.assertIn(phrase, localization)

        mod_test = SKILL_ROOT / MOD_TEST_DOCUMENT
        self.assertNotIn((SKILL_ROOT / DELEGATION_REFERENCE).resolve(), set(local_links(mod_test)))
        mod_test_content = normalized(mod_test)
        self.assertIn(
            "sole authoritative owner of real-profile operations and player-operated verification",
            mod_test_content,
        )
        self.assertIn("manual verification", mod_test_content)

    def test_delegation_contract_has_no_normative_host_dependency(self):
        shared = SKILL_ROOT / DELEGATION_REFERENCE
        documents = [(shared, read(shared))]
        for relative, heading in DELEGATION_ROUTES:
            document = SKILL_ROOT / relative
            delegation = markdown_section(document, heading)
            self.assertTrue(delegation, relative)
            documents.append((document, delegation))

        for document, delegation in documents:
            self.assertIsNone(
                NORMATIVE_HOST_DEPENDENCY.search(delegation),
                document,
            )

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
