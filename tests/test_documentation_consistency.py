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
