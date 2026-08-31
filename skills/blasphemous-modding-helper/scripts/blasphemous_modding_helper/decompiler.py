"""Cross-platform Blasphemous source decompilation workflow."""

from __future__ import annotations

import math
import os
import platform as host_platform
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple, Union

from .runtime import CommandPart, CommandResult, run_command


EXIT_SUCCESS = 0
EXIT_FAILURE = 1
STEAM_APP_ID = "774361"
MANAGED_RELATIVE_PATH = Path("Blasphemous_Data") / "Managed"
DLL_NAMES = ("Assembly-CSharp.dll", "Assembly-CSharp-firstpass.dll")
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_POLL_TIMEOUT_SECONDS = 60.0
SOLUTION_NAME = "BlasphemousSourceCode"
STEAM_COMMAND_TIMEOUT_SECONDS = 10.0
TOOL_COMMAND_TIMEOUT_SECONDS = 120.0


class DecompileError(Exception):
    """A user-facing failure in one decompilation workflow stage."""

    def __init__(
        self,
        category: str,
        message: str,
        action: str,
        details: Sequence[str] = (),
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.action = action
        self.details = tuple(detail for detail in details if detail)


@dataclass(frozen=True)
class PlatformAdapter:
    """OS-specific paths and direct Steam URI launcher candidates."""

    name: str
    environment: Mapping[str, str]

    @classmethod
    def detect(
        cls,
        system: Optional[str] = None,
        environment: Optional[Mapping[str, str]] = None,
    ) -> "PlatformAdapter":
        values = dict(os.environ if environment is None else environment)
        compatibility_variables = (
            "MSYSTEM",
            "CYGWIN",
            "WSL_DISTRO_NAME",
            "WSL_INTEROP",
            "STEAM_COMPAT_DATA_PATH",
            "STEAM_COMPAT_CLIENT_INSTALL_PATH",
            "PROTON",
            "WINEPREFIX",
            "WINEDLLOVERRIDES",
        )
        if any(values.get(variable) for variable in compatibility_variables):
            raise DecompileError(
                "decompile/platform",
                "Unsupported compatibility environment; use a native Windows, Linux, or macOS session.",
                "Run this setup from a native OS terminal, not Git Bash, WSL, Proton, or Wine.",
            )
        system_name = system or host_platform.system()
        if system_name in {"Darwin", "macOS"}:
            normalized = "macOS"
        elif system_name in {"Windows", "win32"}:
            normalized = "Windows"
        elif system_name == "Linux":
            normalized = "Linux"
        else:
            raise DecompileError(
                "decompile/platform",
                f"Unsupported operating system: {system_name or 'unknown'}.",
                "Run decompilation on Windows, Linux, or macOS.",
            )
        return cls(normalized, values)

    def _home(self) -> Path:
        if self.name == "Windows":
            configured = self.environment.get("USERPROFILE") or self.environment.get("HOME")
        else:
            configured = self.environment.get("HOME") or self.environment.get("USERPROFILE")
        return Path(configured).expanduser() if configured else Path.home()

    def default_game_path(self) -> Path:
        if self.name == "Windows":
            program_files_x86 = self.environment.get("ProgramFiles(x86)")
            program_files = self.environment.get("ProgramFiles")
            roots = []
            if program_files_x86:
                roots.append(Path(program_files_x86))
            if program_files:
                roots.append(Path(program_files))
            if not roots:
                roots.append(Path(r"C:\Program Files (x86)"))
            return roots[0] / "Steam" / "steamapps" / "common" / "Blasphemous"
        if self.name == "macOS":
            return (
                self._home()
                / "Library"
                / "Application Support"
                / "Steam"
                / "steamapps"
                / "common"
                / "Blasphemous"
            )
        steam_home = self._home() / ".steam" / "steam" / "steamapps" / "common"
        if steam_home.exists():
            return steam_home / "Blasphemous"
        return (
            self._home()
            / ".local"
            / "share"
            / "Steam"
            / "steamapps"
            / "common"
            / "Blasphemous"
        )

    def _windows_steam_candidates(self, uri: str) -> Tuple[Tuple[CommandPart, ...], ...]:
        candidates = []
        explorer = shutil.which("explorer.exe", path=self.environment.get("PATH"))
        if explorer:
            candidates.append((explorer, uri))
        windir = self.environment.get("WINDIR") or self.environment.get("SystemRoot")
        if windir:
            system_explorer = Path(windir) / "System32" / "explorer.exe"
            if system_explorer.is_file():
                candidates.append((system_explorer, uri))

        for variable in ("ProgramFiles(x86)", "ProgramFiles"):
            root = self.environment.get(variable)
            if not root:
                continue
            steam = Path(root) / "Steam" / "steam.exe"
            if steam.is_file():
                candidates.append((steam, uri))
        if not candidates:
            candidates.append(("explorer.exe", uri))
        return tuple(candidates)

    def steam_command_candidates(self, uri: str) -> Tuple[Tuple[CommandPart, ...], ...]:
        if self.name == "Windows":
            return self._windows_steam_candidates(uri)
        if self.name == "macOS":
            return (("open", uri),)
        return (("xdg-open", uri),)

    def permission_action(self, path: Path) -> str:
        if self.name == "Windows":
            return (
                f"Grant write/delete access to {path} or open an Administrator "
                "PowerShell and rerun the command; this script does not auto-elevate."
            )
        return (
            f"Grant write/delete access to {path} or rerun the command with sudo; "
            "this script does not auto-elevate."
        )


CommandRunner = Callable[..., CommandResult]
ToolLocator = Callable[..., Optional[str]]


@dataclass(frozen=True)
class DecompileResult:
    """Paths produced by a successful decompilation."""

    game_path: Path
    output_path: Path
    solution_path: Optional[Path]
    project_paths: Tuple[Path, ...]


class DecompileWorkflow:
    """Run decompilation with injectable external-command and clock seams."""

    def __init__(
        self,
        *,
        platform_adapter: Optional[PlatformAdapter] = None,
        command_runner: Optional[CommandRunner] = None,
        tool_locator: Optional[ToolLocator] = None,
        sleep: Optional[Callable[[float], None]] = None,
        clock: Optional[Callable[[], float]] = None,
        environment: Optional[Mapping[str, str]] = None,
        output: Callable[[str], None] = print,
    ) -> None:
        values = dict(os.environ if environment is None else environment)
        self.platform = platform_adapter or PlatformAdapter.detect(environment=values)
        self.environment: Dict[str, str] = values
        self.command_runner = command_runner or run_command
        self.tool_locator = tool_locator or shutil.which
        self.sleep = sleep or time.sleep
        self.clock = clock or time.monotonic
        self.output = output

    def _info(self, message: str) -> None:
        self.output(f"  [INFO] {message}")

    def _ok(self, message: str) -> None:
        self.output(f"  [OK]   {message}")

    def _warn(self, message: str) -> None:
        self.output(f"  [WARN] {message}")

    def _step(self, message: str) -> None:
        self.output(f"\n[STEP] {message}")

    def _permission_error(self, path: Path, operation: str) -> DecompileError:
        return DecompileError(
            "decompile/permissions",
            f"Insufficient access to {path} while {operation}.",
            self.platform.permission_action(path),
        )

    def _resolve_path(self, value: Union[str, Path]) -> Path:
        return Path(value).expanduser().resolve(strict=False)

    def validate_paths(self, game_path: Path, output_path: Path) -> Tuple[Path, Path]:
        """Validate game/Managed/output paths before destructive work."""

        game = self._resolve_path(game_path)
        output = self._resolve_path(output_path)
        if not game.exists():
            raise DecompileError(
                "decompile/game-path",
                f"Game installation directory not found: {game}",
                "Pass -g/--game-path with the installed Blasphemous directory, then rerun setup.",
            )
        if not game.is_dir():
            raise DecompileError(
                "decompile/game-path",
                f"Game installation path is not a directory: {game}",
                "Pass -g/--game-path with the installed Blasphemous directory, then rerun setup.",
            )
        managed = game / MANAGED_RELATIVE_PATH
        if not managed.exists():
            raise DecompileError(
                "decompile/game-path",
                f"Managed directory not found at: {managed}",
                "Select a complete Blasphemous installation containing Blasphemous_Data/Managed, then rerun setup.",
            )
        if not managed.is_dir():
            raise DecompileError(
                "decompile/game-path",
                f"Managed path is not a directory: {managed}",
                "Select a complete Blasphemous installation containing Blasphemous_Data/Managed, then rerun setup.",
            )

        if not os.access(managed, os.R_OK | os.X_OK):
            raise self._permission_error(managed, "reading game assemblies")
        if not os.access(managed, os.W_OK):
            raise self._permission_error(managed, "restoring game assemblies")
        try:
            output.mkdir(parents=True, exist_ok=True)
        except PermissionError as error:
            raise self._permission_error(output, "creating the output directory") from error
        except OSError as error:
            raise DecompileError(
                "decompile/output-path",
                f"Could not create output directory: {output}: {error}",
                "Choose a writable output directory and rerun setup.",
            ) from error
        if not output.is_dir():
            raise DecompileError(
                "decompile/output-path",
                f"Output path is not a directory: {output}",
                "Choose a directory for decompiled source output and rerun setup.",
            )
        if not os.access(output, os.W_OK):
            raise self._permission_error(output, "writing decompiled source")
        return game, output

    def _resolve_executable(self, command: CommandPart, category: str, action: str) -> str:
        raw = str(command)
        candidate = Path(raw).expanduser()
        if candidate.is_absolute() or candidate.parent != Path("."):
            resolved = candidate.resolve(strict=False)
            if resolved.is_file():
                if self.platform.name != "Windows" and not os.access(resolved, os.X_OK):
                    raise DecompileError(
                        category,
                        f"Required executable is not executable: {resolved}",
                        action,
                    )
                return str(resolved)
            raise DecompileError(category, f"Required tool was not found: {resolved}", action)
        located = self.tool_locator(raw, path=self.environment.get("PATH"))
        if located:
            return str(Path(located).resolve(strict=False))
        raise DecompileError(category, f"Required tool was not found: {raw}", action)

    @staticmethod
    def _command_detail(result: CommandResult) -> str:
        return (
            result.stderr.strip()
            or result.stdout.strip()
            or result.error
            or f"exit code {result.returncode}"
        )

    def _run(
        self,
        command: Sequence[CommandPart],
        *,
        timeout: Optional[float] = None,
    ) -> CommandResult:
        return self.command_runner(
            tuple(command),
            env=self.environment,
            timeout=timeout,
        )

    def _resolve_steam_commands(
        self,
        steam_launcher: Optional[str],
    ) -> Tuple[Tuple[CommandPart, ...], ...]:
        uri = f"steam://validate/{STEAM_APP_ID}"
        if steam_launcher:
            candidates = ((steam_launcher, uri),)
        else:
            candidates = self.platform.steam_command_candidates(uri)

        commands = []
        failures = []
        for candidate in candidates:
            try:
                executable = self._resolve_executable(
                    candidate[0],
                    "decompile/steam",
                    "Open Steam and verify Blasphemous files manually, then rerun setup.",
                )
            except DecompileError as error:
                failures.append(error.message)
                continue
            commands.append((executable, *candidate[1:]))

        if commands:
            return tuple(commands)

        detail = "; ".join(failures)
        raise DecompileError(
            "decompile/steam",
            "Could not find a Steam validation launcher." + (f" {detail}" if detail else ""),
            "Open Steam manually and verify Blasphemous files: Library > Blasphemous > Properties > Installed Files > Verify integrity of game files, then rerun setup.",
        )

    def _launch_steam(self, commands: Sequence[Sequence[CommandPart]]) -> None:
        self._step(f"Launching Steam file integrity validation (AppID: {STEAM_APP_ID})...")
        failures = []
        for command in commands:
            result = self._run(command, timeout=STEAM_COMMAND_TIMEOUT_SECONDS)
            if result.succeeded:
                self._info(f"Steam validation launched via {command[0]}")
                return
            failures.append(f"{command[0]}: {self._command_detail(result)}")

        detail = "; ".join(failures)
        raise DecompileError(
            "decompile/steam",
            "Could not launch Steam validation." + (f" {detail}" if detail else ""),
            "Open Steam manually and verify Blasphemous files: Library > Blasphemous > Properties > Installed Files > Verify integrity of game files, then rerun setup.",
        )

    def _remove_existing_dlls(self, managed: Path) -> None:
        self._step("Removing existing DLLs to trigger Steam validation...")
        existing = []
        for name in DLL_NAMES:
            path = managed / name
            if not path.exists():
                self._info(f"Already absent: {name}")
                continue
            if not path.is_file():
                raise DecompileError(
                    "decompile/assemblies",
                    f"Assembly path is not a file: {path}",
                    "Restore the expected game assembly files, then rerun setup.",
                )
            existing.append((name, path))

        if existing and not os.access(managed, os.W_OK):
            raise self._permission_error(existing[0][1], "removing existing game assemblies")
        for name, path in existing:
            if not os.access(path, os.W_OK):
                raise self._permission_error(path, "removing existing game assemblies")

        for name, path in existing:
            try:
                path.unlink()
            except PermissionError as error:
                raise self._permission_error(path, "removing existing game assemblies") from error
            except OSError as error:
                raise DecompileError(
                    "decompile/assemblies",
                    f"Could not remove {path}: {error}",
                    self.platform.permission_action(path),
                ) from error
            self._info(f"Deleted: {name}")

    def _dlls_restored(self, managed: Path) -> bool:
        return all((managed / name).is_file() for name in DLL_NAMES)

    def _wait_for_restoration(
        self,
        managed: Path,
        poll_interval: float,
        poll_timeout: float,
    ) -> None:
        self._info("Steam validation launched. Polling for DLL restoration...")
        started = self.clock()
        elapsed = 0.0
        while True:
            if self._dlls_restored(managed):
                shown_elapsed = float(elapsed)
                shown = (
                    int(round(shown_elapsed))
                    if shown_elapsed.is_integer()
                    else round(shown_elapsed, 2)
                )
                self._ok(f"All DLLs restored after ~{shown}s.")
                return
            elapsed = self.clock() - started
            if elapsed >= poll_timeout:
                raise DecompileError(
                    "decompile/restore-timeout",
                    f"Timed out after {poll_timeout:g}s. DLLs were not restored by Steam.",
                    "Open Steam manually and verify Blasphemous files: Library > Blasphemous > Properties > Installed Files > Verify integrity of game files, then rerun setup.",
                    (
                        "Possible causes: Steam is not running, game is not owned on this Steam account, "
                        "or validation takes longer than expected.",
                    ),
                )
            remaining = poll_timeout - elapsed
            self.sleep(min(poll_interval, remaining))

    def _verify_dlls(self, managed: Path) -> None:
        for name in DLL_NAMES:
            path = managed / name
            if not os.access(path, os.R_OK):
                raise self._permission_error(path, "reading restored game assemblies")
            try:
                size = path.stat().st_size
            except PermissionError as error:
                raise self._permission_error(path, "reading restored game assemblies") from error
            except OSError as error:
                raise DecompileError(
                    "decompile/assemblies",
                    f"Could not inspect restored assembly {path}: {error}",
                    "Rerun Steam validation and retry setup.",
                ) from error
            if size == 0:
                raise DecompileError(
                    "decompile/assemblies",
                    f"DLL is empty after restoration: {name}.",
                    "Rerun Steam validation and retry setup.",
                )
            self._ok(f"Verified: {name} ({size / 1048576:.2f} MB)")
        self._ok("All DLLs restored and verified successfully.")

    def _dotnet_tool_directory(self) -> Path:
        return self.platform._home() / ".dotnet" / "tools"

    def _resolve_tool_override(
        self,
        value: str,
        *,
        category: str,
        action: str,
    ) -> str:
        return self._resolve_executable(value, category, action)

    def _find_ilspycmd(self) -> Optional[str]:
        for name in ("ilspycmd", "ilspycmd.exe"):
            located = self.tool_locator(name, path=self.environment.get("PATH"))
            if located:
                return str(Path(located).resolve(strict=False))
        tool_directory = self._dotnet_tool_directory()
        for name in ("ilspycmd", "ilspycmd.exe"):
            candidate = tool_directory / name
            if candidate.is_file():
                return str(candidate.resolve(strict=False))
        return None

    def _refresh_tool_path(self) -> None:
        directory = self._dotnet_tool_directory()
        current = self.environment.get("PATH", "")
        if directory.is_dir() and str(directory) not in current.split(os.pathsep):
            self.environment["PATH"] = str(directory) + os.pathsep + current

    def _check_tools(self, dotnet_override: Optional[str], ilspy_override: Optional[str]) -> Tuple[str, str]:
        self._step("Checking .NET SDK installation...")
        dotnet_action = "Install .NET SDK from https://dotnet.microsoft.com/download, then rerun setup."
        dotnet = self._resolve_tool_override(
            dotnet_override or "dotnet",
            category="decompile/tools",
            action=dotnet_action,
        )
        version_result = self._run((dotnet, "--version"), timeout=TOOL_COMMAND_TIMEOUT_SECONDS)
        if not version_result.succeeded:
            raise DecompileError(
                "decompile/tools",
                f".NET SDK check failed: {self._command_detail(version_result)}",
                dotnet_action,
            )
        version = version_result.stdout.strip().splitlines()[0] if version_result.stdout.strip() else "unknown"
        self._ok(f".NET SDK detected: version {version}")

        self._step("Checking ilspycmd installation...")
        if ilspy_override:
            ilspy = self._resolve_tool_override(
                ilspy_override,
                category="decompile/tools",
                action="Install ilspycmd with 'dotnet tool install --global ilspycmd', then rerun setup.",
            )
            self._ok("ilspycmd detected.")
            return dotnet, ilspy

        ilspy = self._find_ilspycmd()
        if ilspy:
            self._ok("ilspycmd detected.")
            return dotnet, ilspy

        list_result = self._run(
            (dotnet, "tool", "list", "--global"),
            timeout=TOOL_COMMAND_TIMEOUT_SECONDS,
        )
        if not list_result.succeeded:
            raise DecompileError(
                "decompile/tools",
                f"Could not inspect global .NET tools: {self._command_detail(list_result)}",
                "Install ilspycmd with 'dotnet tool install --global ilspycmd', then rerun setup.",
            )
        if re.search(r"(?im)^\s*ilspycmd\s+", list_result.stdout):
            self._refresh_tool_path()
            ilspy = self._find_ilspycmd()
        if not ilspy:
            self._info("ilspycmd is not installed. Installing it globally...")
            install_result = self._run(
                (dotnet, "tool", "install", "--global", "ilspycmd"),
                timeout=TOOL_COMMAND_TIMEOUT_SECONDS,
            )
            if not install_result.succeeded:
                raise DecompileError(
                    "decompile/tools",
                    f"Failed to install ilspycmd: {self._command_detail(install_result)}",
                    "Install ilspycmd manually with 'dotnet tool install --global ilspycmd', then rerun setup.",
                )
            self._refresh_tool_path()
            ilspy = self._find_ilspycmd()
        if not ilspy:
            raise DecompileError(
                "decompile/tools",
                "ilspycmd installation completed but executable was not found.",
                "Add the .NET global tools directory to PATH or pass --ilspycmd PATH, then rerun setup.",
            )
        self._ok("ilspycmd is ready.")
        return dotnet, ilspy

    def _decompile_assembly(
        self,
        ilspycmd: str,
        managed: Path,
        output: Path,
        name: str,
    ) -> Path:
        dll = managed / name
        output_directory = output / Path(name).stem
        try:
            output_directory.mkdir(parents=True, exist_ok=True)
        except PermissionError as error:
            raise self._permission_error(output_directory, "creating decompiled source output") from error
        except OSError as error:
            raise DecompileError(
                "decompile/output-path",
                f"Could not create decompilation directory {output_directory}: {error}",
                "Choose a writable output directory and rerun setup.",
            ) from error
        self._step(f"Decompiling {name}...")
        result = self._run(
            (
                ilspycmd,
                "--nested-directories",
                "-p",
                "-o",
                output_directory,
                dll,
            ),
            timeout=TOOL_COMMAND_TIMEOUT_SECONDS,
        )
        if not result.succeeded:
            raise DecompileError(
                "decompile/decompilation",
                f"ilspycmd failed for {name}: {self._command_detail(result)}",
                "Verify ilspycmd and restored DLLs, then rerun setup.",
            )
        self._ok(f"{name} decompiled to {output_directory}")
        return output_directory

    def _find_projects(self, directories: Sequence[Path]) -> Tuple[Path, ...]:
        projects = []
        self._step("Locating .csproj files from decompiled output...")
        for directory in directories:
            if not directory.is_dir():
                continue
            projects.extend(
                sorted(
                    (path for path in directory.rglob("*.csproj") if path.is_file()),
                    key=lambda path: (str(path).casefold(), str(path)),
                )[:1]
            )
        for project in projects:
            self._info(f"Found: {project.name}")
        return tuple(projects)

    def _create_solution(
        self,
        dotnet: str,
        output: Path,
        projects: Sequence[Path],
    ) -> Optional[Path]:
        if not projects:
            self._warn("No .csproj files found. Skipping solution creation.")
            return None
        self._ok(f"Found {len(projects)} project file(s).")
        self._step("Creating Visual Studio solution...")
        solution = output / f"{SOLUTION_NAME}.sln"
        if solution.exists():
            try:
                solution.unlink()
            except PermissionError as error:
                raise self._permission_error(solution, "replacing the solution") from error
            except OSError as error:
                raise DecompileError(
                    "decompile/solution",
                    f"Could not remove existing solution {solution}: {error}",
                    "Remove or make the existing solution writable, then rerun setup.",
                ) from error
            self._info(f"Removed existing solution: {solution}")

        result = self._run(
            (dotnet, "new", "sln", "-n", SOLUTION_NAME, "-o", output),
            timeout=TOOL_COMMAND_TIMEOUT_SECONDS,
        )
        if not result.succeeded:
            raise DecompileError(
                "decompile/solution",
                f"Failed to create .sln file: {self._command_detail(result)}",
                "Verify the .NET SDK and output directory, then rerun setup.",
            )
        if not solution.is_file():
            raise DecompileError(
                "decompile/solution",
                f".NET SDK reported success but did not create the solution: {solution}",
                "Verify the .NET SDK and output directory, then rerun setup.",
            )
        for project in projects:
            add_result = self._run(
                (dotnet, "sln", solution, "add", project),
                timeout=TOOL_COMMAND_TIMEOUT_SECONDS,
            )
            if add_result.succeeded:
                self._ok(f"Added to solution: {project}")
            else:
                self._warn(
                    f"Failed to add project: {project}. Log: {self._command_detail(add_result)}"
                )
        self._ok(f"Solution ready: {solution}")
        return solution

    def run(
        self,
        *,
        game_path: Optional[Union[str, Path]] = None,
        output_path: Optional[Union[str, Path]] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        poll_timeout: float = DEFAULT_POLL_TIMEOUT_SECONDS,
        steam_launcher: Optional[str] = None,
        dotnet: Optional[str] = None,
        ilspycmd: Optional[str] = None,
        skill_root: Optional[Path] = None,
    ) -> DecompileResult:
        if not math.isfinite(poll_interval) or poll_interval <= 0:
            raise DecompileError(
                "decompile/options",
                "Poll interval must be greater than zero.",
                "Pass --poll-interval with a positive number of seconds.",
            )
        if not math.isfinite(poll_timeout) or poll_timeout < 0:
            raise DecompileError(
                "decompile/options",
                "Poll timeout must be zero or greater.",
                "Pass --poll-timeout with zero or a positive number of seconds.",
            )
        selected_game = Path(game_path) if game_path is not None else self.platform.default_game_path()
        self._step("Validating game path...")
        selected_output = (
            Path(output_path)
            if output_path is not None
            else (skill_root or Path(__file__).resolve().parents[2]) / "source_code"
        )
        if output_path is None:
            self._info(f"Output path not specified. Defaulting to: {selected_output}")
        game, output = self.validate_paths(selected_game, selected_output)
        managed = game / MANAGED_RELATIVE_PATH
        self._ok(f"Game installation directory: {game}")
        self._ok(f"Managed directory: {managed}")
        self._step("Resolving output path...")
        self._ok(f"Output path ready: {output}")
        steam_commands = self._resolve_steam_commands(steam_launcher)
        self._remove_existing_dlls(managed)
        self._launch_steam(steam_commands)
        self._wait_for_restoration(managed, poll_interval, poll_timeout)
        self._verify_dlls(managed)
        dotnet_path, ilspy_path = self._check_tools(dotnet, ilspycmd)
        output_directories = tuple(
            self._decompile_assembly(ilspy_path, managed, output, name)
            for name in DLL_NAMES
        )
        projects = self._find_projects(output_directories)
        solution = self._create_solution(dotnet_path, output, projects)
        self.output("\n============================================")
        self.output("  Decompilation Complete!")
        self.output("============================================")
        self.output(f"  Game:     {game}")
        self.output(f"  Output:   {output}")
        if solution is not None:
            self.output(f"  Solution: {solution}")
        self.output(f"  Projects: {len(projects)} decompiled")
        self.output("")
        self.output("Next step:")
        self.output("  Update preferences.md 'lightweight_source_code_path' to:")
        self.output(f"    {output}")
        return DecompileResult(game, output, solution, projects)
