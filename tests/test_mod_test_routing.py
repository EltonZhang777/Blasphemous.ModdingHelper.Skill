import re
import unittest
from pathlib import Path


SKILL_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = SKILL_ROOT / "references" / "sub-skills"
SHARED = REFERENCES / "blasphemous-modding-test.md"
AUTOMATED = REFERENCES / "blasphemous-modding-test-automated-xunit.md"
REAL_PROFILE = REFERENCES / "blasphemous-modding-test-real-profile.md"
COORDINATION = REFERENCES / "blasphemous-modding-test-in-game-coordination.md"
PLAYER = REFERENCES / "blasphemous-modding-test-player-verification.md"
LOG_ANALYZER = REFERENCES / "log-analyzer.md"
DELEGATION_REFERENCES = SKILL_ROOT / "references" / "subagent-delegation"
GENERAL_DELEGATION = DELEGATION_REFERENCES / "subagent-delegation-general-guidelines.md"
XUNIT_DELEGATION = DELEGATION_REFERENCES / "xunit-testing-delegation.md"
REAL_PROFILE_DELEGATION = DELEGATION_REFERENCES / "real-profile-testing-delegation.md"
READ_ONLY_DELEGATION = DELEGATION_REFERENCES / "read-only-evidence-delegation.md"
ROUTING_SPEC = REPOSITORY_ROOT / "docs" / "specs" / "modding-test-routing.md"
MOD_TEST_SPEC = REPOSITORY_ROOT / "docs" / "specs" / "blasphemous-modding-test.md"
VERIFICATION = REPOSITORY_ROOT / "docs" / "verification" / "blasphemous-modding-test.md"
DOCUMENTS = (
    SHARED,
    AUTOMATED,
    REAL_PROFILE,
    COORDINATION,
    PLAYER,
    GENERAL_DELEGATION,
    XUNIT_DELEGATION,
    REAL_PROFILE_DELEGATION,
    READ_ONLY_DELEGATION,
)
PLAYER_HANDOFF_TURN_PHRASES = (
    "mod_loaded",
    "every planned test item and expected result",
    "currently identifiable test session",
    "current target scene or save state",
    "explicit request for the player to perform the listed test and "
    "report in the next user turn",
    "until a new user message arrives",
    "must not produce a player handoff or claim in-game evidence",
    "must not be reported as test completion",
)


def read(path):
    return path.read_text(encoding="utf-8")


def links(text):
    return re.findall(r"\]\(([^)#]+)(?:#[^)]+)?\)", text)


class ModTestRoutingDocumentationTests(unittest.TestCase):
    def test_player_verification_label_is_canonical_across_route_owners(self):
        for document in (SHARED, REAL_PROFILE, COORDINATION, PLAYER, ROUTING_SPEC):
            text = read(document)
            self.assertIn("Player-performed in-game verification", text, document)

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

    def test_subagent_guidance_follows_shared_and_branch_ownership(self):
        self.assertTrue(GENERAL_DELEGATION.is_file())
        self.assertTrue(XUNIT_DELEGATION.is_file())
        self.assertTrue(REAL_PROFILE_DELEGATION.is_file())

        self.assertIn("../subagent-delegation/" + GENERAL_DELEGATION.name, links(read(SHARED)))
        self.assertIn("../subagent-delegation/" + GENERAL_DELEGATION.name, links(read(AUTOMATED)))
        self.assertIn("../subagent-delegation/" + XUNIT_DELEGATION.name, links(read(AUTOMATED)))
        self.assertIn("../subagent-delegation/" + GENERAL_DELEGATION.name, links(read(REAL_PROFILE)))
        self.assertIn("../subagent-delegation/" + REAL_PROFILE_DELEGATION.name, links(read(REAL_PROFILE)))

        shared = read(SHARED).casefold()
        for phrase in (
            "for a `both` result, the parent must assign the automated xunit phase to one child first",
            "then assign the real-profile phase to a separate child after the xunit handoff",
            "each child must report only its own phase",
            "keeping status, evidence, blocked reason, and next action independent",
            "if a child for a selected test phase is unavailable",
            "must not run the assigned tests as a fallback",
        ):
            self.assertIn(phrase, shared)
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

    def test_shared_entry_leaves_xunit_free_of_real_profile_gate(self):
        text = read(SHARED).casefold()

        self.assertIn("caller-owned automated xunit", text)
        self.assertIn("before branch-specific gates", text)

    def test_shared_entry_keeps_ambiguity_and_evidence_separate(self):
        text = read(SHARED).casefold()

        for phrase in (
            "ask the user to clarify",
            "automated xunit first",
            "each phase",
            "player-performed in-game verification",
            "computer use automated in-game test",
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

    def test_shared_entry_defines_both_phase_and_report_contract(self):
        text = read(SHARED).casefold()

        for phrase in (
            "xunit phase first",
            "real-profile phase second",
            "does not wait for real-profile configuration",
            "own branch gate independently",
            "independent commands",
            "independent evidence",
            "independent statuses",
            "does not fabricate",
            "both is complete only after",
            "all required phases complete",
            "ambiguous requests execute no",
            "per-phase command",
            "blocked reason",
            "next action",
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
            "does not require",
            "modding_profile_path",
            "config.yml",
            "python",
            "launcher",
            "unity logs",
            "bepinex",
            "game process",
            "dotnet test",
            "may compile the",
            "dotnet run",
            "hand-written runner",
            "real-profile cli",
            "delegates to the standard xunit runner",
            "passed",
            "failed",
            "blocked",
            "runner",
            "exit status",
            "not gameplay proof",
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

    def test_real_profile_branch_owns_lifecycle_and_hands_off_gameplay(self):
        real = read(REAL_PROFILE).casefold()
        shared = read(SHARED).casefold()

        for phrase in (
            "`run`",
            "tracked-session stop exception",
            "cleanup uses newest-first session stack",
            "status",
            "profile-local",
            "process tree",
            "newest-first",
            "mod_loaded",
            "profile operations and in-game evidence handoff",
            "player-performed in-game verification",
            "computer use automated in-game test",
        ):
            self.assertIn(phrase, real)
        self.assertNotIn("<test_cli> run", shared)

        canonical = real[real.index("canonical lifecycle order"):]
        ordered = ("`run`", "`logs`", "`snapshot`", "`stop`", "`clean`", "`status`")
        positions = [canonical.index(command) for command in ordered]
        self.assertEqual(positions, sorted(positions))

    def test_test_docs_keep_compatibility_policy_with_the_real_profile_owner(self):
        real = read(REAL_PROFILE)
        verification = read(VERIFICATION)
        spec = read(MOD_TEST_SPEC)

        self.assertIn("native Windows, Linux, or macOS", real)
        self.assertIn("Bash or PowerShell may host the Python process", real)
        self.assertIn("neither host is a platform or support combination", real)
        for compatibility_layer in ("Git Bash", "Cygwin", "WSL", "Proton", "Wine"):
            self.assertIn(compatibility_layer, real)

        for document, text in (
            (VERIFICATION, verification),
            (MOD_TEST_SPEC, spec),
        ):
            text = text.casefold()
            self.assertNotIn("native windows and bash contract", text, document)
            prose = "\n".join(
                line for line in text.splitlines() if "`test_" not in line
            )
            for compatibility_layer in ("git bash", "cygwin", "wsl", "proton", "wine"):
                self.assertNotIn(compatibility_layer, prose, document)

        self.assertIn("native Windows, Linux, and macOS", verification)
        self.assertIn("compatibility-layer policy", verification)

    def test_cli_help_and_parser_tests_are_the_only_argument_grammar_owners(self):
        owners = (REAL_PROFILE, VERIFICATION, MOD_TEST_SPEC)
        for document in owners:
            text = read(document)
            self.assertIn("`--help`", text, document)
            self.assertIn("root and subcommand `--help`", text.casefold(), document)
            self.assertIn("parser tests", text.casefold(), document)
            self.assertIn("sole owners of flags and argument grammar", text.casefold(), document)

        for document in (*owners, SHARED, LOG_ANALYZER):
            text = read(document)
            self.assertNotIn("<TEST_CLI>", text, document)
            self.assertNotIn("Common options are accepted", text, document)
            self.assertNotIn("| Option | Meaning |", text, document)
            self.assertNotIn("Invocation template", text, document)
            self.assertNotIn("```powershell", text.casefold(), document)
            self.assertNotIn("```bash", text.casefold(), document)
            self.assertIsNone(
                re.search(
                    r"(?<![\w-])--(?:current|snapshot|full|force|"
                    r"stop-decision|force-stop-decision|unity-log-dir)\b",
                    text.casefold(),
                ),
                document,
            )

    def test_real_profile_contract_covers_gate_prerequisites_and_states(self):
        text = read(REAL_PROFILE).casefold()

        for phrase in (
            "preferences_scope",
            "preferences_file",
            "validation status",
            "python 3.9+",
            "skill root",
            "caller mod repository",
            "modding_profile_path",
            "`modding` root",
            "bepinex",
            "launcher",
            "build, artifact, deployment, launch, startup, and process evidence",
            "session/process boundary",
            "cannot cross session identity",
            "complete",
            "failed",
            "blocked",
            "pending-manual",
            "pending-computer-use",
            "next action",
        ):
            self.assertIn(phrase, text)

    def test_skill_python_tests_remain_outside_caller_xunit_rule(self):
        text = read(SHARED).casefold()

        self.assertIn("skill repository's python cli and fixture tests", text)
        self.assertIn("caller-mod xunit convention does not redirect", text)

    def test_player_guide_links_to_coordination_turn_boundary(self):
        player = read(PLAYER)

        self.assertIn(
            "](blasphemous-modding-test-in-game-coordination.md"
            "#player-performed-in-game-verification-handoff-and-turn-boundary)",
            player,
        )
        self.assertIn(
            "selects player-performed in-game verification and reaches the "
            "[player-performed in-game verification handoff and turn boundary]",
            player.casefold(),
        )
        self.assertNotIn("has produced startup evidence", player.casefold())

    def test_coordination_owns_player_handoff_and_post_handoff_inactivity(self):
        text = read(COORDINATION).casefold()

        for phrase in PLAYER_HANDOFF_TURN_PHRASES:
            self.assertIn(phrase, text)
        for phrase in (
            "## player-performed in-game verification handoff and turn boundary",
            "after the real-profile branch has produced `mod_loaded` startup evidence",
            "`launched`, `ready`, and `timeout` startup states must not satisfy "
            "the handoff precondition",
            "exact test session and required scene or save state are known",
            "handoff must be the last user-visible output",
            "no-input player observation uses the same boundary",
            "must not make tool calls, poll, sleep, perform background monitoring",
            "retain a waiting interactive session",
            "game process and tracked test session may remain active",
            "must not stop, force-stop, clean, snapshot, or roll back",
            "computer use automated in-game testing and automated xunit are outside",
            "readiness or startup-evidence failure before this boundary",
            "existing blocked-report behavior",
            "session-identity",
            "ambiguity, approval, stop, force-stop, snapshot, cleanup, and "
            "evidence-separation rules must remain unchanged",
            "method switching must remain prohibited without user authorization",
        ):
            self.assertIn(phrase, text)

        self.assertLess(
            text.index("lifecycle-only requests such as build/deploy/launch"),
            text.index(
                "## player-performed in-game verification handoff and turn boundary"
            ),
        )

    def test_player_guide_keeps_detail_without_copying_turn_or_lifecycle_rules(self):
        player = " ".join(read(PLAYER).split()).casefold()

        self.assertIn(
            "this guide owns the detailed in-game actions, observations, and "
            "evidence below",
            player,
        )
        self.assertIn(
            "real-profile branch remains authoritative for every command, "
            "profile safeguard, session operation, and snapshot",
            player,
        )
        for phrase in PLAYER_HANDOFF_TURN_PHRASES:
            self.assertNotIn(phrase, player)
        for phrase in (
            "last user-visible output",
            "must not make tool calls",
            "perform background monitoring",
            "waiting interactive session",
            "computer use automated in-game testing",
            "automated xunit are outside",
            "force-stop",
            "clean session_id",
            "snapshot session_id",
            "roll back",
            "<test_cli> stop",
        ):
            self.assertNotIn(phrase, player)


if __name__ == "__main__":
    unittest.main()
