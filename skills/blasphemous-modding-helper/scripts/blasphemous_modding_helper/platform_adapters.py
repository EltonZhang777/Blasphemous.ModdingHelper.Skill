"""Native platform behavior for the Blasphemous mod-test lifecycle.

Lifecycle orchestration stores one :class:`ProcessIdentity` and calls this
module through :class:`PlatformAdapter`. Windows, Linux, and macOS keep their
launcher, process inspection, process-tree, and termination differences here.
No adapter selects or terminates a process by name alone.
"""

from __future__ import annotations

import ctypes
import os
import shlex
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import runtime as shared_runtime


CommandRunner = Callable[..., shared_runtime.CommandResult]
ProcessEntry = Tuple[int, int, str]
IdentityReader = Callable[..., Optional["ProcessIdentity"]]
EntriesReader = Callable[[], Tuple[ProcessEntry, ...]]
IdsReader = Callable[[], Tuple[int, ...]]
ImageNameReader = Callable[..., Optional[str]]
ParentMapReader = Callable[[], Dict[int, int]]


@dataclass(frozen=True)
class ProcessIdentity:
    """OS process identity used to prove ownership before lifecycle actions."""

    pid: int
    start_token: str
    executable: Optional[Path]


class PlatformUnavailableError(ValueError):
    """Raised when no supported native platform adapter exists."""


def _normalise_executable(path: Optional[Path]) -> Optional[Path]:
    if path is None:
        return None
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def _same_executable(first: Optional[Path], second: Optional[Path]) -> bool:
    first_value = _normalise_executable(first)
    second_value = _normalise_executable(second)
    if first_value is None or second_value is None:
        return False
    return first_value.as_posix().casefold() == second_value.as_posix().casefold()


def _same_process_identity(
    expected: ProcessIdentity,
    current: Optional[ProcessIdentity],
) -> bool:
    if (
        current is None
        or current.pid != expected.pid
        or current.start_token != expected.start_token
    ):
        return False
    if expected.executable and current.executable and not _same_executable(
        current.executable,
        expected.executable,
    ):
        return False
    return True


def _command_error(result: shared_runtime.CommandResult, fallback: str) -> str:
    return result.stderr.strip() or result.stdout.strip() or result.error or fallback


class PlatformAdapter:
    """Shared lifecycle operations with explicit native hooks."""

    environment = "unsupported"

    def __init__(
        self,
        command_runner: Optional[CommandRunner] = None,
        process_identity: Optional[IdentityReader] = None,
        process_entries: Optional[EntriesReader] = None,
        process_ids: Optional[IdsReader] = None,
        process_image_name: Optional[ImageNameReader] = None,
        process_parent_map: Optional[ParentMapReader] = None,
    ) -> None:
        self._command_runner = command_runner
        self._identity_reader = process_identity
        self._entries_reader = process_entries
        self._ids_reader = process_ids
        self._image_name_reader = process_image_name
        self._parent_map_reader = process_parent_map

    def _run_command(self, command: Sequence[object]) -> shared_runtime.CommandResult:
        runner = (
            self._command_runner
            if self._command_runner is not None
            else shared_runtime.run_command
        )
        return runner(command)

    def _ps_process_identity(
        self,
        pid: int,
        *,
        strict: bool = False,
    ) -> Optional[ProcessIdentity]:
        start_result = self._run_command(("ps", "-p", str(pid), "-o", "lstart="))
        if not start_result.succeeded or not start_result.stdout.strip():
            if strict and start_result.error:
                raise OSError(_command_error(start_result, "ps failed"))
            return None
        command_result = self._run_command(("ps", "-p", str(pid), "-o", "command="))
        command = command_result.stdout.strip()
        executable: Optional[Path] = None
        if command:
            try:
                first_word = shlex.split(command)[0]
            except (ValueError, IndexError):
                first_word = command.split()[0]
            if "/" in first_word:
                executable = _normalise_executable(Path(first_word))
        return ProcessIdentity(pid, start_result.stdout.strip(), executable)

    def unity_log_filenames(self) -> Tuple[str, ...]:
        return ("Player.log", "output_log.txt")

    def launcher_candidates(self, profile: Path) -> Tuple[Path, ...]:
        raise NotImplementedError

    @property
    def requires_executable_bit(self) -> bool:
        return True

    def start(self, launcher: Path, working_directory: Path) -> object:
        return shared_runtime.start_process(
            (launcher,),
            cwd=working_directory,
            start_new_session=True,
        )

    def identify(self, pid: int, *, strict: bool = False) -> Optional[ProcessIdentity]:
        raise NotImplementedError

    def process_entries(self) -> Tuple[ProcessEntry, ...]:
        if self._entries_reader is not None:
            return self._entries_reader()
        return ()

    def process_ids(self) -> Tuple[int, ...]:
        if self._ids_reader is not None:
            return self._ids_reader()
        raise NotImplementedError

    def process_image_name(
        self,
        pid: int,
        known_name: Optional[str] = None,
    ) -> Optional[str]:
        if self._image_name_reader is not None:
            return self._image_name_reader(pid, known_name)
        del pid
        return known_name

    def process_parent_map(self) -> Dict[int, int]:
        if self._parent_map_reader is not None:
            return self._parent_map_reader()
        raise NotImplementedError

    def find_conflict(self, launcher: Path) -> Optional[ProcessIdentity]:
        current_pid = os.getpid()
        entries = self.process_entries()
        process_ids = (
            tuple(entry[0] for entry in entries)
            if self._entries_reader is not None
            or (self.environment == "Windows" and self._ids_reader is None)
            else self.process_ids()
        )
        image_names = {
            pid: image_name.casefold()
            for pid, _, image_name in entries
        }
        for pid in process_ids:
            if pid == current_pid:
                continue
            identity = self.identify(pid)
            if identity is not None and _same_executable(
                identity.executable,
                launcher,
            ):
                return identity
            if identity is not None and identity.executable is not None:
                continue
            image_name = self.process_image_name(pid, image_names.get(pid))
            if (
                image_name == launcher.name.casefold()
                and (identity is None or identity.executable is None)
            ):
                return identity or ProcessIdentity(pid, "uninspectable", None)
        return None

    def is_alive(self, identity: ProcessIdentity) -> bool:
        current = self.identify(identity.pid, strict=True)
        if current is None:
            return False
        if current.start_token != identity.start_token:
            raise OSError(
                f"Tracked process ID {identity.pid} was reused by another process; "
                "refusing to stop it."
            )
        if identity.executable and current.executable and not _same_executable(
            current.executable,
            identity.executable,
        ):
            raise OSError(
                f"Tracked process ID {identity.pid} no longer belongs to the "
                "selected launcher; refusing to stop it."
            )
        return True

    def snapshot_tree(self, identity: ProcessIdentity) -> Tuple[ProcessIdentity, ...]:
        current = self.identify(identity.pid, strict=True)
        if current is None:
            return ()
        if not _same_process_identity(identity, current):
            raise OSError(
                f"tracked process ID {identity.pid} changed before termination"
            )
        tree = [current]
        for pid in self.descendant_pids(identity.pid):
            child = self.identify(pid, strict=True)
            if child is not None:
                tree.append(child)
        return tuple(tree)

    def descendant_pids(self, root_pid: int) -> Tuple[int, ...]:
        children: Dict[int, List[int]] = {}
        for pid, parent_pid in self.process_parent_map().items():
            children.setdefault(parent_pid, []).append(pid)
        descendants: List[int] = []
        pending = list(children.get(root_pid, ()))
        while pending:
            pid = pending.pop(0)
            descendants.append(pid)
            pending.extend(children.get(pid, ()))
        return tuple(descendants)

    def wait_for_alive(
        self,
        identity: ProcessIdentity,
        *,
        timeout: float = 0.5,
    ) -> Tuple[bool, Optional[ProcessIdentity]]:
        deadline = time.monotonic() + timeout
        while True:
            current = self.identify(identity.pid, strict=True)
            if not _same_process_identity(identity, current):
                return False, current
            if time.monotonic() >= deadline:
                return True, current
            time.sleep(0.05)

    def wait_for_exit(self, identity: ProcessIdentity, *, timeout: float = 1.0) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            current = self.identify(identity.pid, strict=True)
            if current is None:
                return True
            if not _same_process_identity(identity, current):
                raise OSError(
                    f"tracked process ID {identity.pid} changed before termination"
                )
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)

    def terminate_tree(self, identity: ProcessIdentity, *, force: bool = False) -> bool:
        tree = self.snapshot_tree(identity)
        if not tree:
            return False
        termination_signal = signal.SIGKILL if force else signal.SIGTERM
        root_requested = False
        for process in reversed(tree):
            current = self.identify(process.pid, strict=True)
            if current is None:
                continue
            if not _same_process_identity(process, current):
                raise OSError(
                    f"process ID {process.pid} changed before termination"
                )
            try:
                os.kill(current.pid, termination_signal)
                if process.pid == identity.pid:
                    root_requested = True
            except ProcessLookupError:
                continue
            except PermissionError as error:
                raise OSError(
                    f"could not stop process {current.pid}: {error}"
                ) from error
        return root_requested


class WindowsPlatformAdapter(PlatformAdapter):
    """Windows launcher, Toolhelp identity, and taskkill adapter."""

    environment = "Windows"

    def unity_log_filenames(self) -> Tuple[str, ...]:
        return ("output_log.txt",)

    def launcher_candidates(self, profile: Path) -> Tuple[Path, ...]:
        return (profile / "Blasphemous.exe",)

    @property
    def requires_executable_bit(self) -> bool:
        return False

    def start(self, launcher: Path, working_directory: Path) -> object:
        return shared_runtime.start_process(
            (launcher,),
            cwd=working_directory,
            creationflags=getattr(
                shared_runtime.subprocess,
                "CREATE_NEW_PROCESS_GROUP",
                0,
            ),
        )

    def identify(self, pid: int, *, strict: bool = False) -> Optional[ProcessIdentity]:
        if self._identity_reader is not None:
            return self._identity_reader(pid, strict=strict)
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            error_code = ctypes.get_last_error()
            if error_code == 5:
                if strict:
                    raise PermissionError(error_code, "OpenProcess access denied")
                return None
            if error_code not in {2, 6, 87, 1168}:
                raise OSError(error_code, "OpenProcess failed")
            return None
        try:
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel_time = wintypes.FILETIME()
            user_time = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                error_code = ctypes.get_last_error()
                if error_code == 5:
                    if strict:
                        raise PermissionError(
                            error_code,
                            "GetProcessTimes access denied",
                        )
                    return None
                if error_code not in {2, 6, 87, 1168}:
                    raise OSError(error_code, "GetProcessTimes failed")
                return None
            if (int(exit_time.dwHighDateTime) << 32) | int(exit_time.dwLowDateTime):
                return None
            start_token = f"{creation.dwHighDateTime:08x}{creation.dwLowDateTime:08x}"
            executable: Optional[Path] = None
            buffer = ctypes.create_unicode_buffer(32768)
            buffer_size = wintypes.DWORD(len(buffer))
            if kernel32.QueryFullProcessImageNameW(
                handle,
                0,
                buffer,
                ctypes.byref(buffer_size),
            ):
                executable = _normalise_executable(Path(buffer.value))
            return ProcessIdentity(pid, start_token, executable)
        finally:
            kernel32.CloseHandle(handle)

    def process_entries(self) -> Tuple[ProcessEntry, ...]:
        if self._entries_reader is not None:
            return self._entries_reader()
        from ctypes import wintypes

        class ProcessEntry32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.argtypes = [
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Process32FirstW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessEntry32W),
        ]
        kernel32.Process32FirstW.restype = wintypes.BOOL
        kernel32.Process32NextW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessEntry32W),
        ]
        kernel32.Process32NextW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if snapshot in (None, ctypes.c_void_p(-1).value):
            raise OSError(
                ctypes.get_last_error(),
                "CreateToolhelp32Snapshot failed",
            )
        try:
            entry = ProcessEntry32W()
            entry.dwSize = ctypes.sizeof(ProcessEntry32W)
            entries: List[ProcessEntry] = []
            if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
                return ()
            while True:
                entries.append(
                    (
                        int(entry.th32ProcessID),
                        int(entry.th32ParentProcessID),
                        str(entry.szExeFile),
                    )
                )
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
            return tuple(entries)
        finally:
            kernel32.CloseHandle(snapshot)

    def process_ids(self) -> Tuple[int, ...]:
        if self._ids_reader is not None:
            return self._ids_reader()
        return tuple(pid for pid, _, _ in self.process_entries())

    def process_image_name(
        self,
        pid: int,
        known_name: Optional[str] = None,
    ) -> Optional[str]:
        if self._image_name_reader is not None:
            return self._image_name_reader(pid, known_name)
        del pid
        return known_name.casefold() if known_name is not None else None

    def process_parent_map(self) -> Dict[int, int]:
        if self._parent_map_reader is not None:
            return self._parent_map_reader()
        return {
            pid: parent_pid
            for pid, parent_pid, _ in self.process_entries()
        }

    def terminate_tree(self, identity: ProcessIdentity, *, force: bool = False) -> bool:
        tree = self.snapshot_tree(identity)
        if not tree:
            return False
        current = self.identify(identity.pid, strict=True)
        if not _same_process_identity(identity, current):
            raise OSError(
                f"tracked process ID {identity.pid} changed before taskkill"
            )
        command = ["taskkill", "/PID", str(identity.pid), "/T"]
        if force:
            command.append("/F")
        result = self._run_command(command)
        if result.succeeded:
            return True
        current = self.identify(identity.pid, strict=True)
        if current is None:
            return False
        if not _same_process_identity(identity, current):
            raise OSError(
                f"tracked process ID {identity.pid} changed before taskkill"
            )
        raise OSError(_command_error(result, "taskkill failed"))


class LinuxPlatformAdapter(PlatformAdapter):
    """Linux launcher and procfs process adapter."""

    environment = "Linux"

    def launcher_candidates(self, profile: Path) -> Tuple[Path, ...]:
        return (profile / "Blasphemous.x86_64", profile / "Blasphemous")

    def identify(self, pid: int, *, strict: bool = False) -> Optional[ProcessIdentity]:
        if self._identity_reader is not None:
            return self._identity_reader(pid, strict=strict)
        if not Path("/proc").is_dir():
            return self._ps_process_identity(pid, strict=strict)
        stat_path = Path("/proc") / str(pid) / "stat"
        try:
            contents = stat_path.read_text(encoding="utf-8")
        except OSError as error:
            if strict and getattr(error, "errno", None) == 13:
                raise
            return None
        except UnicodeError:
            return None
        closing_parenthesis = contents.rfind(")")
        if closing_parenthesis < 0:
            return None
        fields = contents[closing_parenthesis + 2 :].split()
        if len(fields) < 20:
            return None
        start_token = fields[19]
        executable: Optional[Path] = None
        executable_path = Path("/proc") / str(pid) / "exe"
        try:
            executable = _normalise_executable(executable_path.resolve(strict=True))
        except OSError:
            pass
        return ProcessIdentity(pid, start_token, executable)

    def process_ids(self) -> Tuple[int, ...]:
        if self._ids_reader is not None:
            return self._ids_reader()
        proc_root = Path("/proc")
        if not proc_root.is_dir():
            return self._ps_process_ids()
        process_ids: List[int] = []
        for candidate in proc_root.iterdir():
            if candidate.name.isdigit():
                process_ids.append(int(candidate.name))
        return tuple(process_ids)

    def process_image_name(
        self,
        pid: int,
        known_name: Optional[str] = None,
    ) -> Optional[str]:
        if self._image_name_reader is not None:
            return self._image_name_reader(pid, known_name)
        if known_name is not None:
            return known_name
        proc_name = Path("/proc") / str(pid) / "comm"
        if proc_name.is_file():
            try:
                return proc_name.read_text(encoding="utf-8").strip().casefold()
            except (OSError, UnicodeError):
                return None
        return self._ps_process_image_name(pid)

    def process_parent_map(self) -> Dict[int, int]:
        if self._parent_map_reader is not None:
            return self._parent_map_reader()
        proc_root = Path("/proc")
        if not proc_root.is_dir():
            return self._ps_process_parent_map()
        parents: Dict[int, int] = {}
        for candidate in proc_root.iterdir():
            if not candidate.name.isdigit():
                continue
            try:
                contents = (candidate / "stat").read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            closing_parenthesis = contents.rfind(")")
            if closing_parenthesis < 0:
                continue
            fields = contents[closing_parenthesis + 2 :].split()
            if len(fields) < 4:
                continue
            try:
                parents[int(candidate.name)] = int(fields[1])
            except ValueError:
                continue
        return parents

    def _ps_process_ids(self) -> Tuple[int, ...]:
        result = self._run_command(("ps", "-axo", "pid="))
        if not result.succeeded:
            raise OSError(_command_error(result, "ps failed"))
        process_ids: List[int] = []
        for line in result.stdout.splitlines():
            try:
                process_ids.append(int(line.strip()))
            except ValueError:
                continue
        return tuple(process_ids)

    def _ps_process_image_name(self, pid: int) -> Optional[str]:
        result = self._run_command(("ps", "-p", str(pid), "-o", "comm="))
        if not result.succeeded or not result.stdout.strip():
            return None
        return Path(result.stdout.strip()).name.casefold()

    def _ps_process_parent_map(self) -> Dict[int, int]:
        result = self._run_command(("ps", "-axo", "pid=,ppid="))
        if not result.succeeded:
            raise OSError(_command_error(result, "ps failed"))
        parents: Dict[int, int] = {}
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue
            try:
                parents[int(fields[0])] = int(fields[1])
            except ValueError:
                continue
        return parents


class MacOSPlatformAdapter(PlatformAdapter):
    """macOS launcher and ps process adapter."""

    environment = "macOS"

    def launcher_candidates(self, profile: Path) -> Tuple[Path, ...]:
        return (
            profile / "Blasphemous.app" / "Contents" / "MacOS" / "Blasphemous",
            profile / "Blasphemous",
        )

    def identify(self, pid: int, *, strict: bool = False) -> Optional[ProcessIdentity]:
        if self._identity_reader is not None:
            return self._identity_reader(pid, strict=strict)
        return self._ps_process_identity(pid, strict=strict)

    def process_ids(self) -> Tuple[int, ...]:
        if self._ids_reader is not None:
            return self._ids_reader()
        result = self._run_command(("ps", "-axo", "pid="))
        if not result.succeeded:
            raise OSError(_command_error(result, "ps failed"))
        process_ids: List[int] = []
        for line in result.stdout.splitlines():
            try:
                process_ids.append(int(line.strip()))
            except ValueError:
                continue
        return tuple(process_ids)

    def process_image_name(
        self,
        pid: int,
        known_name: Optional[str] = None,
    ) -> Optional[str]:
        if self._image_name_reader is not None:
            return self._image_name_reader(pid, known_name)
        if known_name is not None:
            return known_name
        result = self._run_command(("ps", "-p", str(pid), "-o", "comm="))
        if not result.succeeded or not result.stdout.strip():
            return None
        return Path(result.stdout.strip()).name.casefold()

    def process_parent_map(self) -> Dict[int, int]:
        if self._parent_map_reader is not None:
            return self._parent_map_reader()
        result = self._run_command(("ps", "-axo", "pid=,ppid="))
        if not result.succeeded:
            raise OSError(_command_error(result, "ps failed"))
        parents: Dict[int, int] = {}
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue
            try:
                parents[int(fields[0])] = int(fields[1])
            except ValueError:
                continue
        return parents


def platform_adapter_for(
    environment: str,
    *,
    command_runner: Optional[CommandRunner] = None,
    process_identity: Optional[IdentityReader] = None,
    process_entries: Optional[EntriesReader] = None,
    process_ids: Optional[IdsReader] = None,
    process_image_name: Optional[ImageNameReader] = None,
    process_parent_map: Optional[ParentMapReader] = None,
) -> PlatformAdapter:
    """Return explicit adapter for one supported environment name."""

    adapters = {
        "Windows": WindowsPlatformAdapter,
        "Linux": LinuxPlatformAdapter,
        "macOS": MacOSPlatformAdapter,
    }
    adapter_type = adapters.get(environment)
    if adapter_type is None:
        raise PlatformUnavailableError(
            f"Unsupported operating system or unavailable platform adapter: {environment or 'unknown'}."
        )
    return adapter_type(
        command_runner=command_runner,
        process_identity=process_identity,
        process_entries=process_entries,
        process_ids=process_ids,
        process_image_name=process_image_name,
        process_parent_map=process_parent_map,
    )


__all__ = [
    "MacOSPlatformAdapter",
    "LinuxPlatformAdapter",
    "PlatformAdapter",
    "PlatformUnavailableError",
    "ProcessIdentity",
    "WindowsPlatformAdapter",
    "platform_adapter_for",
]
