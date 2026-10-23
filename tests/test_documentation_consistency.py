import re
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper"
MAIN_SKILL = SKILL_ROOT / "SKILL.md"
RFC_AUDIT = REPOSITORY_ROOT / "ci" / "audit_rfc2119.py"
MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")
DELEGATION_REFERENCE = "references/subagent-delegation/read-only-evidence-delegation.md"
GENERAL_DELEGATION_REFERENCE = "references/subagent-delegation/subagent-delegation-general-guidelines.md"
XUNIT_DELEGATION_REFERENCE = "references/subagent-delegation/xunit-testing-delegation.md"
REAL_PROFILE_DELEGATION_REFERENCE = "references/subagent-delegation/real-profile-testing-delegation.md"
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
DEPENDENCY_GUIDANCE = (
    REPOSITORY_ROOT / "README.md",
    MAIN_SKILL,
    SKILL_ROOT / "references" / "config" / "first-time-setup.md",
    SKILL_ROOT / "references" / "config" / "python-runtime.md",
    SKILL_ROOT / "references" / "sub-skills" / "blasphemous-modding-test-real-profile.md",
    SKILL_ROOT / "references" / "sub-skills" / "log-analyzer.md",
    SKILL_ROOT / "references" / "sub-skills" / "referencing-modding-api.md",
)

APPROVED_CANONICAL_OWNERS = frozenset(
    {
        "SKILL.md",
        "references/config/invocation-preflight.md",
        "references/sub-skills/coding-standards.md",
        "references/sub-skills/blasphemous-modding-test.md",
        "references/sub-skills/referencing-modding-api.md",
        "references/coding-standards/coding-standards-moddingAPI.md",
        "references/source-code-navigation/MAIN.md",
    }
)

ROUTING_CONTRACTS = (
    (
        "SKILL.md",
        "## Request routing",
        "## Shared entry gate",
        (
            ("natural-language identify", "Localization lookup", "MUST NOT require configuration"),
            ("Find or explain decompiled game source", "Source analyzer", "source-path gate"),
            ("Diagnose BepInEx or Unity logs", "Log analyzer", "MUST resolve required log sources"),
            ("Test a Mod; build/deploy/launch a profile", "Mod-test entry", "classify the request"),
            ("Generate, modify, review, or refactor Mod-owned C#", "Coding standards", "ownership boundary"),
            ("Need ModdingAPI documentation", "Referencing ModdingAPI", "local or release-aware reference"),
        ),
    ),
    (
        "references/config/invocation-preflight.md",
        "# Invocation preflight",
        "## Command context",
        (
            ("Localization lookup", "bundled index", "MUST NOT run scripts"),
            ("Operational branches", "shared preflight", "complete this preflight before specialized work"),
            ("First-time setup and Python validation", "Python Runtime → First-Time Setup", "MUST complete [Python Runtime]"),
            ("Configuration result", "selected config", "MUST consume"),
            ("Tracked-session stop", "recorded process tree", "MUST NOT read or edit configuration"),
            ("Path recovery", "path-recovery prompt", "MUST use the exact prompt below"),
            ("Preflight completion", "preflight result", "before mutations"),
        ),
    ),
    (
        "references/sub-skills/coding-standards.md",
        "## Route map",
        "## Coding specifications",
        (
            ("New Mod-owned file or directory placement", "Project architecture guidelines", "established structure MUST take precedence"),
            ("Mod-owned C# conventions", "C# and runtime Unity standards", "caller compiler and referenced assemblies MUST govern compatibility"),
            ("ModdingAPI APIs", "ModdingAPI standards", "caller's referenced assembly MUST govern API facts"),
            ("Harmony targets", "Harmony patching standards", "manual `Harmony.Patch` MUST follow its approval gate"),
            ("unmodifiable linked, generated, build, cached, derived", "Scope gate", "MUST preserve excluded or copied source"),
        ),
    ),
    (
        "references/sub-skills/blasphemous-modding-test.md",
        "## Route decision table",
        "## Route result contract",
        (
            ("Needs a real or mirror Modding profile", "Real-profile branch", "keep startup evidence separate"),
            ("Is deterministic and can run without a game process", "Automated xUnit branch", "MUST NOT be reported as gameplay proof"),
            ("Explicitly requests both kinds of test", "Both branch owners", "MUST run Automated xUnit first"),
            ("Runtime or evidence conditions are unclear or conflicting", "Ambiguous result", "MUST ask the user to clarify"),
        ),
    ),
    (
        "references/sub-skills/referencing-modding-api.md",
        "## Reference and topic routing",
        "## Advanced and archived topics",
        (
            ("Configured local reference", "<modding_api_reference_path>/docs/development/main.md", "MUST NOT clone or update it for an ordinary question"),
            ("Release-aware remote fallback", "<MODDING_API_DOCS_URL>/development/main.md", "MUST NOT use an unqualified moving branch"),
            ("Decompiled Blasphemous game class", "Blasphemous Source Code Navigation", "MUST NOT require or load a ModdingAPI reference"),
            ("Stable topic: Project setup", "docs/development/setup.md", "MUST follow direct links to"),
            ("Stable topic: Mod class", "docs/development/mod.md", "MUST follow"),
            ("Stable topic: Initialization", "docs/development/execution.md", "MUST follow"),
            ("Stable topic: Persistent data", "docs/development/persistence.md", "MUST follow"),
            ("Stable topic: ModLog methods", "docs/development/logging.md", "MUST verify version-sensitive facts"),
            ("Stable topic: Mod configuration", "docs/development/config.md", "MUST follow"),
            ("Stable topic: File utilities", "docs/development/files.md", "MUST follow"),
            ("Stable topic: Input and keybindings", "docs/development/input.md", "MUST follow"),
            ("Stable topic: Localization and translations", "docs/development/localization.md", "MUST follow"),
            ("Advanced / archived topic: Console commands", "docs/development/console.md", "MUST read only on demand"),
            ("Advanced / archived topic: Custom items", "docs/development/items.md", "MUST read only on demand"),
            ("Advanced / archived topic: Level modifications", "docs/development/levels.md", "MUST read only on demand"),
            ("Advanced / archived topic: Custom penitences", "docs/development/penitence.md", "MUST read only on demand"),
            ("Topic absent from the table, unlisted, or newly added", "docs/development/main.md", "MUST NOT copy the upstream documentation tree"),
        ),
    ),
    (
        "references/coding-standards/coding-standards-moddingAPI.md",
        "## ModdingAPI development-document index",
        "## BlasMod lifecycle",
        (
            ("Stable responsibilities:", "docs/development/main.md", "MUST use the index's current page list and labels"),
            ("Advanced / archived responsibilities:", "docs/development/main.md", "MUST load only on demand"),
            ("Unknown, unlisted, or newly added topic", "docs/development/main.md", "MUST use the index's actual page list and labels"),
        ),
    ),
    (
        "references/source-code-navigation/MAIN.md",
        "## Navigation Routes",
        "## Quick Access for Mod Development",
        (
            ("**Core.**", "core.md", "matching manager or framework class within the selected `Assembly-CSharp/` tree"),
            ("**Player.**", "player.md", "relevant Penitent behavior within the selected `Assembly-CSharp/` tree"),
            ("**Enemy.**", "enemy.md", "enemy AI or shared entity bases within the selected `Assembly-CSharp/` tree"),
            ("**Bosses.**", "bosses.md", "boss or shared combat behavior within the selected `Assembly-CSharp/` tree"),
            ("**UI.**", "ui.md", "screen/widget or console path that matches the request within the selected `Assembly-CSharp/` tree"),
            ("**Items.**", "items.md", "item or effect implementation within the selected `Assembly-CSharp/` tree"),
            ("**Level.**", "level.md", "matching level mechanic within the selected `Assembly-CSharp/` tree"),
            ("**Tools.**", "tools.md", "matching tool family as the search entry within the selected `Assembly-CSharp/` tree"),
            ("**Localization.**", "localization.md", "I2 localization or the game LocalizationManager as indicated within the selected `Assembly-CSharp/` tree"),
        ),
    ),
)


TABLE_SEPARATOR = re.compile(r":?-{3,}:?")
RFC2119_KEYWORDS = re.compile(r"\b(?:MUST|SHOULD|MAY)\b")
DESTINATION_COMMAND_WORDS = re.compile(
    r"\b(?:read|use|route|load|follow|ask|complete|resolve|consume|apply|stop|"
    r"inspect|verify|run|keep|select|choose|supply|return|classify)\b",
    re.IGNORECASE,
)


def markdown_table_cells(line):
    line = line.strip()
    if not line.startswith("|"):
        return ()
    line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return tuple(cell.strip() for cell in line.split("|"))


def markdown_tables(document_text):
    lines = document_text.splitlines()
    tables = []
    for row, line in enumerate(lines[:-1]):
        headers = markdown_table_cells(line)
        separators = markdown_table_cells(lines[row + 1])
        if len(headers) < 2 or len(separators) != len(headers):
            continue
        if not all(TABLE_SEPARATOR.fullmatch(cell) for cell in separators):
            continue
        end = row + 2
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        tables.append((row, headers, "\n".join(lines[row:end])))
    return tables


def canonical_route_tables(document_text):
    tables = []
    for row, headers, table_text in markdown_tables(document_text):
        if len(headers) != 3:
            continue
        first, second, third = (header.casefold() for header in headers)
        if not any(token in first for token in ("request", "signal", "condition", "invocation")):
            continue
        if not any(token in second for token in ("destination", "owner", "route")):
            continue
        if not any(token in third for token in ("boundary", "handoff", "next")):
            continue
        tables.append((row, table_text))
    return tables


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
    def test_dependency_guidance_links_to_shared_inventory(self):
        inventory = (
            SKILL_ROOT / "references" / "config" / "invocation-preflight.md"
        ).resolve()
        for document in DEPENDENCY_GUIDANCE:
            targets = []
            for raw_target in MARKDOWN_LINK.findall(read(document)):
                path, separator, anchor = raw_target.partition("#")
                if (
                    separator
                    and anchor.casefold() == "dependencies"
                    and (document.parent / path).resolve() == inventory
                ):
                    targets.append(raw_target)
            self.assertTrue(targets, document)

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

    def test_subagent_guidance_is_reachable_from_shared_and_phase_owners(self):
        general = SKILL_ROOT / GENERAL_DELEGATION_REFERENCE
        read_only = SKILL_ROOT / DELEGATION_REFERENCE
        xunit = SKILL_ROOT / XUNIT_DELEGATION_REFERENCE
        real_profile = SKILL_ROOT / REAL_PROFILE_DELEGATION_REFERENCE
        mod_test = SKILL_ROOT / MOD_TEST_DOCUMENT
        automated = SKILL_ROOT / "references/sub-skills/blasphemous-modding-test-automated-xunit.md"
        real_branch = SKILL_ROOT / "references/sub-skills/blasphemous-modding-test-real-profile.md"

        for document in (general, read_only, xunit, real_profile):
            self.assertTrue(document.is_file(), document)
        for owner, target in (
            (read_only, general),
            (mod_test, general),
            (automated, general),
            (automated, xunit),
            (real_branch, general),
            (real_branch, real_profile),
        ):
            self.assertIn(target.resolve(), set(local_links(owner)), owner)

        general_text = normalized(general)
        for phrase in (
            "one bounded responsibility",
            "clear scope, acceptance criteria",
            "parent retains user intent, user decisions",
            "parent must inspect delegated results",
            "or delegate further",
            "host-neutral",
        ):
            self.assertIn(phrase, general_text)

        xunit_text = normalized(xunit)
        for phrase in (
            "standard .net test runner",
            "must not use a modding profile",
            "launch or inspect the game, deploy an artifact",
            "runner result, exit status",
            "must not be reported as gameplay proof",
        ):
            self.assertIn(phrase, xunit_text)

        real_text = normalized(real_profile)
        for phrase in (
            "exactly one test session",
            "disposable or mirror modding profile",
            "must not switch profiles or sessions",
            "player-operated **manual verification**",
            "session id",
            "process id and tracked process tree identity recorded in that session manifest",
            "approval-gated action",
            "must not make or infer that decision",
            "next action",
        ):
            self.assertIn(phrase, real_text)

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
        general = SKILL_ROOT / GENERAL_DELEGATION_REFERENCE
        documents = [(shared, read(shared)), (general, read(general))]
        for relative in (XUNIT_DELEGATION_REFERENCE, REAL_PROFILE_DELEGATION_REFERENCE):
            document = SKILL_ROOT / relative
            documents.append((document, read(document)))
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

        self.assertLess(setup.index("[Python runtime gate]"), setup.index("## Question Batches"))
        order = (
            "### Q1: Save Location",
            "### Q2: Decompiled Source Branch",
            "### Q3: Lightweight Source Code Path",
            "### Q4: Full Source Code (optional)",
            "### Q4b: Full Source Code Path (conditional)",
            "### Q5: Modding Profile Path",
            "### Q6: Local ModdingAPI Reference",
            "### Reference Selector",
        )
        positions = [setup.index(marker) for marker in order]
        self.assertEqual(positions, sorted(positions))
        for phrase in (
            "the first message MUST ask Q1 and Q2 together, in that order",
            "agent MUST ask Q4, Q5, and Q6 together",
            "MUST ask Q3 only if the user chooses manual paths",
            "agent MUST ask Q4b only after Q4 is answered **Yes**",
            "the selector only after Q6 is answered **Yes**",
            "agent MUST defer a question only when an unresolved answer determines",
            "corresponding single question",
            "retain every unrelated valid answer",
            "agent MUST NOT use agent or harness question components",
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

    def test_canonical_routing_tables_have_one_owner_per_document(self):
        contract_owners = frozenset(contract[0] for contract in ROUTING_CONTRACTS)
        self.assertEqual(contract_owners, APPROVED_CANONICAL_OWNERS)
        self.assertEqual(len(APPROVED_CANONICAL_OWNERS), 7)

        discovered_owners = {
            path.relative_to(SKILL_ROOT).as_posix()
            for path in SKILL_ROOT.rglob("*.md")
            if canonical_route_tables(read(path))
        }
        self.assertEqual(discovered_owners, APPROVED_CANONICAL_OWNERS)

        for relative, route_section, detail_section, expected_routes in ROUTING_CONTRACTS:
            with self.subTest(document=relative):
                document_text = read(SKILL_ROOT / relative)
                lines = document_text.splitlines()
                tables = canonical_route_tables(document_text)
                self.assertEqual(len(tables), 1, relative)
                if len(tables) != 1:
                    continue

                if relative == "references/sub-skills/coding-standards.md":
                    self.assertEqual(len(markdown_tables(document_text)), 1, relative)

                table_line, table_text = tables[0]
                self.assertLess(lines.index(route_section), table_line, relative)
                self.assertLess(table_line, lines.index(detail_section), relative)

                rows = [
                    markdown_table_cells(row)
                    for row in table_text.splitlines()[2:]
                ]
                self.assertEqual(len(rows), len(expected_routes), relative)
                self.assertTrue(rows, relative)
                for cells in rows:
                    self.assertEqual(len(cells), 3, f"{relative}: {cells}")
                if any(len(cells) != 3 for cells in rows):
                    continue

                for signal, destination, boundary in expected_routes:
                    matches = [
                        cells
                        for cells in rows
                        if signal.casefold() in cells[0].casefold()
                        and destination.casefold() in cells[1].casefold()
                    ]
                    self.assertEqual(len(matches), 1, f"{relative}: {signal} -> {destination}")
                    if matches:
                        self.assertIn(boundary.casefold(), matches[0][2].casefold())

                for cells in rows:
                    self.assertNotRegex(
                        cells[1],
                        DESTINATION_COMMAND_WORDS,
                        f"{relative}: actions belong in the boundary cell",
                    )
                    self.assertRegex(
                        cells[2],
                        RFC2119_KEYWORDS,
                        f"{relative}: boundary cell must use RFC 2119 wording",
                    )


if __name__ == "__main__":
    unittest.main()
