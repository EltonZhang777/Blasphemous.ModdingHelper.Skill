import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MAIN_SKILL = REPOSITORY_ROOT / "skills" / "blasphemous-modding-helper" / "SKILL.md"
SOURCE_NAVIGATION = (
    MAIN_SKILL.parent / "references" / "source-code-navigation" / "MAIN.md"
)


def navigation_routes():
    text = SOURCE_NAVIGATION.read_text(encoding="utf-8")
    header = "| Request signal / condition | Route destination | Boundary / next action |"
    table = text.split(header, 1)[1].split("\n\n", 1)[0]
    routes = []
    for line in table.splitlines()[2:]:
        cells = tuple(cell.strip() for cell in line.strip("|").split("|"))
        if len(cells) != 3:
            continue
        routes.append(cells)
    return routes


def route_row(route_name):
    return next(
        row
        for row in navigation_routes()
        if row[0].startswith(f"**{route_name}.**")
    )


def route_tokens(value):
    tokens = set()
    for token in re.findall(r"[a-z0-9_/*.-]+", value.casefold()):
        token = token.rstrip(".,;:")
        tokens.add(token)
        if token.endswith(".cs"):
            tokens.add(token.rsplit("/", 1)[-1][:-3])
    return tokens


def source_navigation_destination(request):
    request_tokens = route_tokens(request)
    manager_flow = {"lifecycle", "persistence", "wiring", "runtime", "flow"}
    achievement_request = any("achievement" in token for token in request_tokens)

    if "achievementsmanager" in request_tokens:
        core_tokens = route_tokens(route_row("Core")[0])
        if "achievementsmanager" in core_tokens:
            return route_row("Core")[1]
    if "playmaker" in request_tokens:
        return route_row("Tools")[1]
    if request_tokens & {"ui"} or any(
        marker in token
        for token in request_tokens
        for marker in ("widget", "command")
    ):
        return route_row("UI")[1]
    if achievement_request and request_tokens & manager_flow:
        core_tokens = route_tokens(route_row("Core")[0])
        manager_signals = request_tokens & ({"achievementsmanager"} | manager_flow)
        if manager_signals <= core_tokens:
            return route_row("Core")[1]
    if (
        achievement_request
        or "framework/achievements/*" in request_tokens
        or any(
            token.startswith("framework/achievements/")
            for token in request_tokens
        )
    ):
        entity_signals = request_tokens & {
            "framework/achievements/*",
            "achievement",
            "achievements",
            "entities",
            "state",
            "behavior",
            "backend",
            "helpers",
            "checkers",
        }
        items_tokens = route_tokens(route_row("Items")[0])
        if entity_signals <= items_tokens:
            return route_row("Items")[1]
    return None


class SkillRouteMapTests(unittest.TestCase):
    def test_supported_game_scope_is_clear_before_request_routing(self):
        text = MAIN_SKILL.read_text(encoding="utf-8")
        description = text.split("---", 2)[1]
        opening = text.split("## Request routing", 1)[0]
        normalized_description = " ".join(description.split())
        normalized_opening = " ".join(opening.split())

        self.assertIn("Blasphemous 1 only", normalized_description)
        self.assertIn("Blasphemous 2 is not supported", normalized_description)
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
        normalized = " ".join(text.split())
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

        for route in expected_routes:
            self.assertIn(route, text)
            self.assertTrue(
                (MAIN_SKILL.parent / "references" / "sub-skills" / route).is_file(),
                route,
            )
        for phrase in (
            "configuration-free operational exception",
            "Unity project navigation",
            "Caller-owned xUnit does not wait",
            "Real-profile",
            "both",
            "ambiguous",
            "completion report",
            "next document/action",
        ):
            self.assertIn(phrase, normalized)

    def test_achievement_requests_have_one_source_navigation_destination(self):
        routes = navigation_routes()
        self.assertEqual(len(routes), 10)
        core_signal = route_row("Core")[0].casefold()
        items_signal = route_row("Items")[0].casefold()
        for phrase in (
            "achievementsmanager",
            "lifecycle",
            "persistence",
            "wiring",
            "runtime flow",
            "must take precedence",
        ):
            self.assertIn(phrase, core_signal)
        for phrase in (
            "bare achievements",
            "framework/achievements/*",
            "state behavior",
            "backend helpers",
            "checkers",
        ):
            self.assertIn(phrase, items_signal)
        self.assertIn("achievement ui widgets", route_row("UI")[0].casefold())
        self.assertIn(
            "achievement playmaker actions, conditions, and events",
            route_row("Tools")[0].casefold(),
        )

        cases = (
            ("Achievements", "[items.md](items.md)"),
            ("Achievement entities", "[items.md](items.md)"),
            ("Achievement backend helpers", "[items.md](items.md)"),
            ("Achievement backend helper", "[items.md](items.md)"),
            ("Achievement checker", "[items.md](items.md)"),
            ("Framework/Achievements/AC44Checker.cs", "[items.md](items.md)"),
            ("Framework/Achievements/AC39Enemies.cs", "[items.md](items.md)"),
            ("AchievementsManager.cs", "[core.md](core.md)"),
            ("Framework/Managers/AchievementsManager.cs", "[core.md](core.md)"),
            ("AchievementsManager.cs.", "[core.md](core.md)"),
            (
                "Framework/Achievements/* achievement entities, state behavior, backend helpers, and checkers",
                "[items.md](items.md)",
            ),
            ("AchievementsManager", "[core.md](core.md)"),
            (
                "Achievement manager lifecycle persistence wiring runtime flow",
                "[core.md](core.md)",
            ),
            ("Achievement UI widgets", "[ui.md](ui.md)"),
            ("Achievement UI widgets runtime flow", "[ui.md](ui.md)"),
            ("AchievementElementWidget", "[ui.md](ui.md)"),
            ("PopupAchievementWidget", "[ui.md](ui.md)"),
            ("AchievementCommand", "[ui.md](ui.md)"),
            (
                "Achievement PlayMaker actions conditions events",
                "[tools.md](tools.md)",
            ),
            (
                "Achievement PlayMaker actions runtime flow",
                "[tools.md](tools.md)",
            ),
            (
                "AchievementsManager achievement entities",
                "[core.md](core.md)",
            ),
            (
                "Framework/Achievements/* manager persistence",
                "[core.md](core.md)",
            ),
            (
                "Framework/Achievements/* achievement manager entity state",
                "[items.md](items.md)",
            ),
        )

        for request, expected in cases:
            with self.subTest(request=request):
                self.assertEqual(source_navigation_destination(request), expected)

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
