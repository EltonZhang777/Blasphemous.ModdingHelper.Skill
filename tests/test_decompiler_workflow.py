import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
)
import sys

sys.path.insert(0, str(SCRIPT_ROOT))

from blasphemous_modding_helper.decompiler import (  # noqa: E402
    DLL_NAMES,
    DecompileError,
    DecompileWorkflow,
    PlatformAdapter,
)
from blasphemous_modding_helper.runtime import CommandResult  # noqa: E402


class FixtureCommands:
    def __init__(self, managed, output):
        self.managed = managed
        self.output = output
        self.commands = []

    def locate(self, name, path=None):
        if name in {"steam-fixture", "dotnet-fixture", "ilspy-fixture"}:
            return name
        return None

    def __call__(self, command, *, env, timeout):
        self.commands.append(tuple(str(part) for part in command))
        name = Path(str(command[0])).name
        if name == "steam-fixture":
            for dll in DLL_NAMES:
                (self.managed / dll).write_bytes(b"restored assembly")
            return CommandResult(tuple(str(part) for part in command), 0)
        if name == "dotnet-fixture" and command[1] == "--version":
            return CommandResult(tuple(str(part) for part in command), 0, stdout="8.0.100\n")
        if name == "dotnet-fixture" and command[1:3] == ("tool", "list"):
            return CommandResult(tuple(str(part) for part in command), 0, stdout="Package Id Version\n")
        if name == "dotnet-fixture" and command[1:3] == ("tool", "install"):
            return CommandResult(tuple(str(part) for part in command), 1, stderr="offline")
        if name == "dotnet-fixture" and command[1:3] == ("new", "sln"):
            self.output.joinpath("BlasphemousSourceCode.sln").write_text("solution\n", encoding="utf-8")
            return CommandResult(tuple(str(part) for part in command), 0)
        if name == "dotnet-fixture" and command[1] == "sln":
            return CommandResult(tuple(str(part) for part in command), 0)
        if name == "ilspy-fixture":
            output_index = command.index("-o") + 1
            decompiled = Path(str(command[output_index]))
            decompiled.mkdir(parents=True, exist_ok=True)
            (decompiled / "Assembly.csproj").write_text("<Project />\n", encoding="utf-8")
            return CommandResult(tuple(str(part) for part in command), 0)
        return CommandResult(tuple(str(part) for part in command), 1, stderr="unexpected fixture command")


class DecompilerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.game = self.root / "game"
        self.managed = self.game / "Blasphemous_Data" / "Managed"
        self.managed.mkdir(parents=True)
        self.output = self.root / "output"
        self.environment = os.environ.copy()
        self.environment["HOME"] = str(self.home)
        self.environment["PATH"] = ""
        self.adapter = PlatformAdapter.detect("Linux", environment=self.environment)

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_workflow(self, commands, **kwargs):
        options = {
            "command_runner": commands,
            "tool_locator": commands.locate,
            "environment": self.environment,
        }
        options.update(kwargs)
        return DecompileWorkflow(
            platform_adapter=self.adapter,
            output=lambda message: None,
            **options,
        )

    def test_permission_failure_reports_manual_access_step_without_elevation(self):
        commands = FixtureCommands(self.managed, self.output)
        workflow = self.create_workflow(commands)

        with mock.patch("blasphemous_modding_helper.decompiler.os.access", return_value=False):
            with self.assertRaises(DecompileError) as failure:
                workflow.run(
                    game_path=self.game,
                    output_path=self.output,
                    poll_timeout=0,
                )

        self.assertEqual(failure.exception.category, "decompile/permissions")
        self.assertIn("sudo", failure.exception.action)
        self.assertIn("does not auto-elevate", failure.exception.action)
        self.assertEqual(commands.commands, [])

    def test_timeout_reports_steam_manual_recovery(self):
        commands = FixtureCommands(self.managed, self.output)

        def no_restore(command, *, env, timeout):
            commands.commands.append(tuple(str(part) for part in command))
            return CommandResult(tuple(str(part) for part in command), 0)

        workflow = self.create_workflow(commands, command_runner=no_restore)
        with self.assertRaises(DecompileError) as failure:
            workflow.run(
                game_path=self.game,
                output_path=self.output,
                poll_timeout=0,
                steam_launcher="steam-fixture",
            )

        self.assertEqual(failure.exception.category, "decompile/restore-timeout")
        self.assertIn("Timed out after 0s", failure.exception.message)
        self.assertIn("verify Blasphemous files", failure.exception.action)

    def test_missing_steam_launcher_does_not_delete_dlls(self):
        commands = FixtureCommands(self.managed, self.output)
        for name in DLL_NAMES:
            (self.managed / name).write_bytes(b"original assembly")

        workflow = self.create_workflow(commands)
        with self.assertRaises(DecompileError) as failure:
            workflow.run(
                game_path=self.game,
                output_path=self.output,
                steam_launcher="missing-steam",
            )

        self.assertEqual(failure.exception.category, "decompile/steam")
        self.assertTrue(all((self.managed / name).is_file() for name in DLL_NAMES))
        self.assertEqual(commands.commands, [])

    def test_dll_permission_failure_does_not_partially_delete_installation(self):
        commands = FixtureCommands(self.managed, self.output)
        for name in DLL_NAMES:
            (self.managed / name).write_bytes(b"original assembly")

        def access(path, mode):
            if Path(path).name == DLL_NAMES[1] and mode & os.W_OK:
                return False
            return True

        workflow = self.create_workflow(commands)
        with mock.patch("blasphemous_modding_helper.decompiler.os.access", side_effect=access):
            with self.assertRaises(DecompileError) as failure:
                workflow.run(
                    game_path=self.game,
                    output_path=self.output,
                    steam_launcher="steam-fixture",
                )

        self.assertEqual(failure.exception.category, "decompile/permissions")
        self.assertTrue(all((self.managed / name).is_file() for name in DLL_NAMES))
        self.assertEqual(commands.commands, [])

    def test_missing_ilspy_install_failure_is_reported(self):
        commands = FixtureCommands(self.managed, self.output)
        workflow = self.create_workflow(commands)

        with self.assertRaises(DecompileError) as failure:
            workflow.run(
                game_path=self.game,
                output_path=self.output,
                poll_timeout=0,
                steam_launcher="steam-fixture",
                dotnet="dotnet-fixture",
            )

        self.assertEqual(failure.exception.category, "decompile/tools")
        self.assertIn("install ilspycmd", failure.exception.action.lower())

    def test_missing_dotnet_is_reported_after_game_validation(self):
        commands = FixtureCommands(self.managed, self.output)

        def locate(name, path=None):
            if name == "steam-fixture":
                return name
            return None

        workflow = self.create_workflow(commands, tool_locator=locate)
        with self.assertRaises(DecompileError) as failure:
            workflow.run(
                game_path=self.game,
                output_path=self.output,
                poll_timeout=0,
                steam_launcher="steam-fixture",
            )

        self.assertEqual(failure.exception.category, "decompile/tools")
        self.assertIn("dotnet", failure.exception.message.lower())
        self.assertIn("Install .NET SDK", failure.exception.action)

    def test_success_restores_dlls_decompiles_both_assemblies_and_creates_solution(self):
        commands = FixtureCommands(self.managed, self.output)
        workflow = self.create_workflow(commands)

        result = workflow.run(
            game_path=self.game,
            output_path=self.output,
            poll_timeout=0,
            steam_launcher="steam-fixture",
            dotnet="dotnet-fixture",
            ilspycmd="ilspy-fixture",
        )

        self.assertEqual(result.game_path, self.game.resolve())
        self.assertEqual(result.output_path, self.output.resolve())
        self.assertEqual(result.solution_path, self.output / "BlasphemousSourceCode.sln")
        self.assertEqual(len(result.project_paths), 2)
        self.assertTrue((self.output / "Assembly-CSharp" / "Assembly.csproj").is_file())
        self.assertTrue((self.output / "Assembly-CSharp-firstpass" / "Assembly.csproj").is_file())
        self.assertTrue(all((self.managed / name).is_file() for name in DLL_NAMES))
        for command in commands.commands:
            self.assertNotIn("&&", command)
            self.assertNotIn(";", command)

    def test_platform_adapters_use_native_game_paths(self):
        windows = PlatformAdapter.detect(
            "Windows",
            environment={"ProgramFiles(x86)": r"C:\SteamRoot", "PATH": ""},
        )
        linux = PlatformAdapter.detect("Linux", environment={"HOME": str(self.home)})
        macos = PlatformAdapter.detect("Darwin", environment={"HOME": str(self.home)})

        self.assertEqual(
            windows.default_game_path(),
            Path(r"C:\SteamRoot") / "Steam" / "steamapps" / "common" / "Blasphemous",
        )
        self.assertEqual(
            linux.default_game_path(),
            self.home / ".local" / "share" / "Steam" / "steamapps" / "common" / "Blasphemous",
        )
        self.assertIn(Path("Library").name, macos.default_game_path().parts)


if __name__ == "__main__":
    unittest.main()
