import hashlib
import importlib.util
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from xml.sax.saxutils import escape


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "blasphemous-modding-helper"
    / "scripts"
    / "blasphemous_modding_test.py"
)


class BlasphemousModdingTestCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.environment = os.environ.copy()
        for variable in (
            "HOME",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
            "MSYSTEM",
            "WSL_DISTRO_NAME",
            "WSL_INTEROP",
            "STEAM_COMPAT_DATA_PATH",
            "STEAM_COMPAT_CLIENT_INSTALL_PATH",
            "PROTON",
            "WINEPREFIX",
            "WINEDLLOVERRIDES",
        ):
            self.environment.pop(variable, None)
        self.environment["HOME"] = str(self.home)
        self.environment["USERPROFILE"] = str(self.home)
        self.temp_root = self.root / "temp"
        self.temp_root.mkdir()
        for variable in ("TMP", "TEMP", "TMPDIR"):
            self.environment[variable] = str(self.temp_root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *arguments, cwd=None, environment=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=str(cwd or self.root),
            env=environment or self.environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def run_module_cli(self, module, *arguments, session=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(module.Path, "cwd", return_value=self.root.resolve()):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                returncode = module.main(arguments, session=session)
        return SimpleNamespace(
            returncode=returncode,
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
        )

    def create_profile(self, name="profile"):
        profile = self.root / name
        (profile / "Modding").mkdir(parents=True)
        (profile / "BepInEx" / "core").mkdir(parents=True)
        (profile / "BepInEx" / "core" / "BepInEx.dll").write_bytes(b"BepInEx")
        launcher = self.launcher_path(profile)
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_bytes(b"launcher")
        if platform.system() != "Windows":
            launcher.chmod(0o755)
        return profile

    def launcher_path(self, profile):
        if platform.system() == "Windows":
            return profile / "Blasphemous.exe"
        if platform.system() == "Linux":
            return profile / "Blasphemous.x86_64"
        return profile / "Blasphemous.app" / "Contents" / "MacOS" / "Blasphemous"

    def create_project(
        self,
        name="Example.csproj",
        target_name="ExampleMod",
        assembly_name=None,
        project_directory=None,
    ):
        assembly_property = (
            f"<AssemblyName>{assembly_name}</AssemblyName>"
            if assembly_name is not None
            else ""
        )
        project = (project_directory or self.root) / name
        project.parent.mkdir(parents=True, exist_ok=True)
        project.write_text(
            "<Project><PropertyGroup>"
            f"<TargetName>{target_name}</TargetName>{assembly_property}"
            "</PropertyGroup></Project>\n",
            encoding="utf-8",
        )
        return project

    def create_classic_solution(self, solution, *projects):
        solution.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "Microsoft Visual Studio Solution File, Format Version 12.00",
            "# Visual Studio Version 17",
        ]
        for index, project in enumerate(projects, start=1):
            relative_project = self.solution_project_path(solution, project)
            guid = f"{index:032X}"
            lines.extend(
                (
                    f'Project("{{{guid}}}") = "{project.stem}", '
                    f'"{relative_project}", "{{{guid}}}"',
                    "EndProject",
                )
            )
        solution.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return solution

    def create_xml_solution(self, solution, *projects):
        solution.parent.mkdir(parents=True, exist_ok=True)
        project_nodes = []
        for project in projects:
            relative_project = self.solution_project_path(solution, project)
            project_nodes.append(
                f'  <Project Path="{escape(relative_project)}" />'
            )
        solution.write_text(
            "<Solution>\n"
            + "\n".join(project_nodes)
            + "\n</Solution>\n",
            encoding="utf-8",
        )
        return solution

    def solution_project_path(self, solution, project):
        return os.path.relpath(project, solution.parent).replace(os.sep, "/")

    def create_buildable_project(
        self,
        name="Example.csproj",
        target_name="ExampleMod",
        project_directory=None,
    ):
        project = (project_directory or self.root) / name
        project.parent.mkdir(parents=True, exist_ok=True)
        project.write_text(
            "<Project DefaultTargets=\"Build\">\n"
            "  <PropertyGroup>\n"
            f"    <TargetName>{target_name}</TargetName>\n"
            "  </PropertyGroup>\n"
            "  <Target Name=\"Build\">\n"
            f"    <MakeDir Directories=\"$(SolutionDir)publish/{target_name}/plugins\" />\n"
            f"    <MakeDir Directories=\"$(SolutionDir)publish/{target_name}/data\" />\n"
            f"    <WriteLinesToFile File=\"$(SolutionDir)publish/{target_name}/plugins/Example.dll\" Lines=\"plugin\" Overwrite=\"true\" />\n"
            f"    <WriteLinesToFile File=\"$(SolutionDir)publish/{target_name}/data/build-configuration.txt\" Lines=\"$(Configuration)\" Overwrite=\"true\" />\n"
            "  </Target>\n"
            "</Project>\n",
            encoding="utf-8",
        )
        return project

    def create_failing_project(self, name="Example.csproj", target_name="ExampleMod"):
        project = self.root / name
        project.write_text(
            "<Project DefaultTargets=\"Build\">\n"
            "  <PropertyGroup>\n"
            f"    <TargetName>{target_name}</TargetName>\n"
            "  </PropertyGroup>\n"
            "  <Target Name=\"Build\">\n"
            "    <Error Text=\"intentional build failure\" />\n"
            "  </Target>\n"
            "</Project>\n",
            encoding="utf-8",
        )
        return project

    def create_empty_build_project(self, name="Example.csproj", target_name="ExampleMod"):
        project = self.root / name
        project.write_text(
            "<Project DefaultTargets=\"Build\">\n"
            "  <PropertyGroup>\n"
            f"    <TargetName>{target_name}</TargetName>\n"
            "  </PropertyGroup>\n"
            "  <Target Name=\"Build\" />\n"
            "</Project>\n",
            encoding="utf-8",
        )
        return project

    def create_package(self, target_name="ExampleMod", root=None):
        package_root = (root or self.root / "publish") / target_name
        (package_root / "plugins").mkdir(parents=True, exist_ok=True)
        (package_root / "data").mkdir(exist_ok=True)
        (package_root / "plugins" / "Example.dll").write_bytes(b"plugin")
        (package_root / "data" / "settings.json").write_text(
            "{}\n",
            encoding="utf-8",
        )
        return package_root

    def deployment_manifests(self):
        roots = (
            self.temp_root / "blasphemous-modding-test" / "sessions",
            self.temp_root / "sessions",
        )
        return sorted(
            manifest
            for sessions in roots
            for manifest in sessions.glob("*/manifest.json")
        )

    def load_cli_module(self):
        module_name = f"blasphemous_modding_test_{id(self)}"
        spec = importlib.util.spec_from_file_location(module_name, SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def create_session(self, module, process_adapter=None, file_adapter=None):
        return module.TestSession(
            state_root=self.temp_root / "sessions",
            process_adapter=process_adapter,
            file_adapter=file_adapter,
        )

    def create_launched_session(
        self,
        prelaunch_bepinex_log=None,
        project_kwargs=None,
        tracked_child_pids=(),
    ):
        module = self.load_cli_module()
        profile = self.create_profile()
        launcher = profile / "custom-launcher"
        launcher.write_bytes(b"launcher")
        if os.name != "nt":
            launcher.chmod(0o755)
        project = self.create_project(**(project_kwargs or {}))
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        if prelaunch_bepinex_log is not None:
            (profile / "BepInEx" / "LogOutput.log").write_text(
                prelaunch_bepinex_log,
                encoding="utf-8",
            )
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(
            profile,
            environment,
            explicit_launcher=launcher.name,
        )
        process = mock.Mock()
        process.pid = 1234
        process.poll.return_value = None
        identity = module.ProcessIdentity(
            process.pid,
            "start-token",
            launcher.resolve(),
        )
        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        tracked_children = tuple(
            module.ProcessIdentity(
                child_pid,
                f"child-start-token-{child_pid}",
                identity.executable,
            )
            for child_pid in tracked_child_pids
        )
        process_adapter.snapshot_tree.return_value = (
            identity,
            *tracked_children,
        )
        session = self.create_session(module, process_adapter)

        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        session.launch(deployment, profile_preflight)
        return module, session, deployment, profile_preflight, process, identity

    def live_process_double(self, module, launcher, pid=4321):
        process = mock.Mock()
        process.pid = pid
        process.poll.return_value = None
        identity = module.ProcessIdentity(
            pid,
            f"start-token-{pid}",
            launcher.resolve(),
        )
        return process, identity

    def write_project_preferences(self, profile, unity_log_dir=None):
        preferences = self.root / ".skills" / "blasphemous-modding-helper" / "preferences.md"
        preferences.parent.mkdir(parents=True, exist_ok=True)
        values = [f"modding_profile_path: {profile}"]
        if unity_log_dir is not None:
            values.append(f"unity_log_dir: {unity_log_dir}")
        preferences.write_text("\n".join(values) + "\n", encoding="utf-8")
        return preferences

    def write_user_preferences(self, profile):
        preferences = self.home / ".skills" / "blasphemous-modding-helper" / "preferences.md"
        preferences.parent.mkdir(parents=True)
        preferences.write_text(
            f"modding_profile_path: {profile}\n",
            encoding="utf-8",
        )
        return preferences

    def snapshot(self):
        return sorted(
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
        )

    def assert_success(self, result):
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout={result.stdout}\nstderr={result.stderr}",
        )

    def test_help_exposes_run_status_and_dry_run(self):
        result = self.run_cli("--help")

        self.assert_success(result)
        self.assertIn("run", result.stdout)
        self.assertIn("logs", result.stdout)
        self.assertIn("stop", result.stdout)
        self.assertIn("clean", result.stdout)
        self.assertIn("status", result.stdout)
        self.assertIn("--dry-run", result.stdout)

    def test_dry_run_preserves_unicode_and_space_paths_with_non_utf8_console(self):
        profile = self.create_profile(name="配置 文件")
        project = self.create_project(name="项目 工程.csproj", target_name="包 名")
        artifact = self.create_package(
            root=self.root / "发布 目录",
            target_name="包 名",
        )
        self.write_project_preferences(profile)
        environment = self.environment.copy()
        environment["PYTHONIOENCODING"] = "ascii"

        result = self.run_cli(
            "run",
            "--dry-run",
            "--project",
            str(project),
            "--artifact",
            str(artifact),
            "--launcher",
            str(self.launcher_path(profile)),
            environment=environment,
        )

        self.assert_success(result)
        for path in (project, profile, artifact):
            self.assertIn(str(path), result.stdout)
        self.assertNotIn("�", result.stdout)
        self.assertIn(str(profile), result.stderr)
        self.assertNotIn("�", result.stderr)

    def test_build_error_preserves_unicode_project_path_and_exit_category(self):
        module = self.load_cli_module()
        profile = self.create_profile(name="配置 文件")
        project = self.create_project(name="项目 工程.csproj", target_name="包 名")
        self.write_project_preferences(profile)
        build_result = SimpleNamespace(
            returncode=1,
            stdout=f"build output for {project}",
            stderr=f"build error for {project}",
        )

        with mock.patch.object(
            module.subprocess,
            "run",
            return_value=build_result,
        ) as run:
            result = self.run_module_cli(
                module,
                "run",
                "--dry-run",
                "--project",
                str(project),
            )

        self.assertEqual(result.returncode, 20)
        self.assertIn(str(project), result.stderr)
        self.assertNotIn("�", result.stderr)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_unicode_space_paths_survive_complete_lifecycle_and_bad_log_bytes(self):
        module = self.load_cli_module()
        profile = self.create_profile(name="游戏 配置")
        project = self.create_project(name="模组 工程.csproj", target_name="包 名")
        artifact = self.create_package(
            root=self.root / "构建 输出",
            target_name="包 名",
        )
        unity_log_dir = self.root / "统一 日志"
        unity_log_dir.mkdir()
        self.write_project_preferences(profile, unity_log_dir)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)
        process, identity = self.live_process_double(
            module,
            self.launcher_path(profile),
        )
        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        process_adapter.snapshot_tree.return_value = (identity,)
        session = self.create_session(module, process_adapter)

        run_result = self.run_module_cli(
            module,
            "run",
            "--project",
            str(project),
            "--artifact",
            str(artifact),
            session=session,
        )
        self.assert_success(run_result)
        session_id = run_result.stdout.split("Deployment session: ", 1)[1].splitlines()[0]

        bepinex_log = profile_preflight.bepinex_root / "LogOutput.log"
        bepinex_log.write_bytes(
            b"[Info : BepInEx] Chainloader initialized\n"
            b"[Info : BepInEx] Loading ["
            + "包 名 1.0.0".encode("utf-8")
            + b"]\ninvalid byte: \xff; profile: "
            + str(profile).encode("utf-8")
            + b"\n"
        )
        (unity_log_dir / "output_log.txt").write_text(
            "Unity log for 配置 文件\n",
            encoding="utf-8",
        )

        logs_result = self.run_module_cli(
            module,
            "logs",
            session_id,
            "--project",
            str(project),
            "--unity-log-dir",
            str(unity_log_dir),
            session=session,
        )
        process_adapter.is_alive.return_value = False
        status_result = self.run_module_cli(
            module,
            "status",
            "--project",
            str(project),
            session=session,
        )
        stop_result = self.run_module_cli(
            module,
            "stop",
            session_id,
            session=session,
        )
        clean_result = self.run_module_cli(
            module,
            "clean",
            session_id,
            "--project",
            str(project),
            session=session,
        )

        self.assert_success(run_result)
        self.assertIn(str(project), run_result.stdout)
        self.assertIn(str(profile), run_result.stdout)
        self.assertIn(str(artifact), run_result.stdout)
        self.assert_success(logs_result)
        self.assertIn("Startup state: mod_loaded", logs_result.stdout)
        self.assertIn(str(profile), logs_result.stdout)
        self.assertIn(str(unity_log_dir), logs_result.stdout)
        self.assertIn("invalid byte: �", logs_result.stdout)
        self.assert_success(status_result)
        self.assertIn(str(project), status_result.stdout)
        self.assertIn(str(profile), status_result.stdout)
        self.assert_success(stop_result)
        self.assertIn("Stop state: exited", stop_result.stdout)
        self.assert_success(clean_result)
        self.assertIn("Clean state: cleaned", clean_result.stdout)
    def test_root_help_contains_canonical_agent_workflow_examples(self):
        result = self.run_cli("--help")

        self.assert_success(result)
        for example in (
            "blasphemous-modding-test run --project <PROJECT.csproj> --profile <PROFILE> --startup-timeout 60",
            "blasphemous-modding-test logs SESSION_ID",
            "blasphemous-modding-test stop SESSION_ID --force",
            "blasphemous-modding-test clean SESSION_ID",
            "blasphemous-modding-test status",
        ):
            self.assertIn(example, result.stdout)

    def test_command_help_lists_only_valid_options_and_context(self):
        expectations = {
            "run": {
                "present": (
                    "--project PATH",
                    "--profile PATH",
                    "--launcher PATH",
                    "--unity-log-dir PATH",
                    "--configuration {Debug,Release}",
                    "--artifact PATH",
                    "--dry-run",
                    "--startup-timeout SECONDS",
                    "Context:",
                ),
                "absent": ("--force", "--full", "--remove-new-files"),
            },
            "logs": {
                "present": (
                    "SESSION_ID",
                    "--project PATH",
                    "--profile PATH",
                    "--launcher PATH",
                    "--unity-log-dir PATH",
                    "--full",
                    "Context:",
                ),
                "absent": ("--configuration", "--artifact", "--dry-run", "--force", "--remove-new-files"),
            },
            "stop": {
                "present": (
                    "SESSION_ID",
                    "--force",
                    "tracked process tree",
                    "No context or profile overrides are accepted.",
                ),
                "absent": (
                    "--project",
                    "--profile",
                    "--launcher",
                    "--unity-log-dir",
                    "--configuration",
                    "--artifact",
                    "--dry-run",
                    "--full",
                    "--remove-new-files",
                ),
            },
            "clean": {
                "present": (
                    "SESSION_ID",
                    "--project PATH",
                    "--profile PATH",
                    "--launcher PATH",
                    "--unity-log-dir PATH",
                    "--remove-new-files",
                    "Context:",
                ),
                "absent": ("--configuration", "--artifact", "--dry-run", "--force", "--full"),
            },
            "status": {
                "present": (
                    "--project PATH",
                    "--profile PATH",
                    "--launcher PATH",
                    "--unity-log-dir PATH",
                    "read-only",
                    "Context:",
                ),
                "absent": (
                    "SESSION_ID",
                    "--configuration",
                    "--artifact",
                    "--dry-run",
                    "--force",
                    "--full",
                    "--remove-new-files",
                ),
            },
        }

        for command, command_expectations in expectations.items():
            with self.subTest(command=command):
                result = self.run_cli(command, "--help")
                self.assert_success(result)
                for expected in command_expectations["present"]:
                    self.assertIn(expected, result.stdout)
                for unexpected in command_expectations["absent"]:
                    self.assertNotIn(unexpected, result.stdout)

    def test_parser_accepts_each_command_contract(self):
        module = self.load_cli_module()
        parser = module.build_parser()
        invocations = (
            (
                "run",
                "--project",
                "Mod.csproj",
                "--profile",
                "PROFILE",
                "--launcher",
                "launcher",
                "--unity-log-dir",
                "UNITY_LOGS",
                "--configuration",
                "Release",
                "--artifact",
                "PACKAGE",
                "--dry-run",
                "--startup-timeout",
                "5",
            ),
            (
                "logs",
                "SESSION_ID",
                "--project",
                "Mod.csproj",
                "--profile",
                "PROFILE",
                "--launcher",
                "launcher",
                "--unity-log-dir",
                "UNITY_LOGS",
                "--full",
            ),
            ("stop", "SESSION_ID", "--force"),
            (
                "clean",
                "SESSION_ID",
                "--project",
                "Mod.csproj",
                "--profile",
                "PROFILE",
                "--launcher",
                "launcher",
                "--unity-log-dir",
                "UNITY_LOGS",
                "--remove-new-files",
            ),
            (
                "status",
                "--project",
                "Mod.csproj",
                "--profile",
                "PROFILE",
                "--launcher",
                "launcher",
                "--unity-log-dir",
                "UNITY_LOGS",
            ),
        )

        for invocation in invocations:
            with self.subTest(invocation=invocation):
                args = parser.parse_args(invocation)
                self.assertEqual(args.command, invocation[0])

    def test_parser_rejects_misplaced_command_options(self):
        module = self.load_cli_module()
        parser = module.build_parser()
        invalid_invocations = (
            ("stop", "SESSION_ID", "--project", "Mod.csproj"),
            ("stop", "SESSION_ID", "--profile", "PROFILE"),
            ("stop", "SESSION_ID", "--launcher", "launcher"),
            ("stop", "SESSION_ID", "--unity-log-dir", "UNITY_LOGS"),
            ("run", "--full"),
            ("logs", "SESSION_ID", "--dry-run"),
            ("clean", "SESSION_ID", "--full"),
            ("status", "--remove-new-files"),
            ("--profile", "PROFILE", "status"),
        )

        for invocation in invalid_invocations:
            with self.subTest(invocation=invocation):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as failure:
                        parser.parse_args(invocation)
                self.assertEqual(failure.exception.code, 2)

    def test_dispatch_command_routes_through_injected_session(self):
        module = self.load_cli_module()
        args = module.build_parser().parse_args(["status"])
        session = mock.Mock(spec=module.TestSession)

        with mock.patch.object(module, "status_command", return_value=17) as command:
            result = module.dispatch_command(args, session=session)

        self.assertEqual(result, 17)
        command.assert_called_once_with(args, session)

    def test_logs_help_exposes_full_output(self):
        result = self.run_cli("logs", "--help")

        self.assert_success(result)
        self.assertIn("SESSION_ID", result.stdout)
        self.assertIn("--full", result.stdout)

    def test_logs_reports_bounded_current_evidence_without_persisting_logs(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        unity_log_dir = self.root / "unity-logs"
        unity_log_dir.mkdir()
        self.write_project_preferences(profile_preflight.profile, unity_log_dir)
        bepinex_log = profile_preflight.bepinex_root / "LogOutput.log"
        bepinex_log.write_text(
            "".join(f"old-{index}\n" for index in range(205))
            + "[Info : BepInEx] Chainloader initialized\n"
            + "[Info : BepInEx] Loading [ExampleMod 1.0.0]\n"
            + "tail-bepinex\n",
            encoding="utf-8",
        )
        unity_log = unity_log_dir / "output_log.txt"
        unity_log.write_text("unity-start\nunity-tail\n", encoding="utf-8")
        before = self.snapshot()

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)
        self.assertIn("Ready state: ready", result.stdout)
        self.assertIn("Mod-loaded state: loaded", result.stdout)
        self.assertIn("tail-bepinex", result.stdout)
        self.assertIn("unity-tail", result.stdout)
        self.assertNotIn("old-0", result.stdout)
        self.assertEqual(before, self.snapshot())
        manifest_text = deployment.state_path.read_text(encoding="utf-8")
        self.assertNotIn("old-0", manifest_text)
        self.assertNotIn("unity-tail", manifest_text)
        self.assertFalse(
            any(
                path.suffix.lower() == ".log"
                for path in deployment.state_path.parent.rglob("*")
            )
        )

    def test_logs_reports_bounded_hits_with_source_path_provenance(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        bepinex_log = profile_preflight.bepinex_root / "LogOutput.log"
        bepinex_log.write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            + "".join(
                f"[Info : BepInEx] Loading [ExampleMod {index}.0.0]\n"
                for index in range(25)
            ),
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        hits = payload["evidence"]["hits"]
        self.assertEqual(len(hits), module.MAX_EVIDENCE_HITS)
        self.assertEqual(hits[0]["source"], "BepInEx")
        self.assertEqual(hits[0]["path"], str(bepinex_log.resolve()))
        self.assertEqual(hits[0]["line"], 2)
        self.assertEqual(hits[-1]["line"], module.MAX_EVIDENCE_HITS + 1)
        self.assertIn(f"BepInEx:{hits[0]['line']}", result.stdout)
        self.assertIn(str(bepinex_log.resolve()), result.stdout)

    def test_logs_detects_early_current_hit_outside_bounded_tail(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        bepinex_log = profile_preflight.bepinex_root / "LogOutput.log"
        bepinex_log.write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : BepInEx] Loading [ExampleMod 1.0.0]\n"
            + "".join(f"noise-{index}\n" for index in range(250)),
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)
        self.assertIn("BepInEx:2", result.stdout)
        self.assertNotIn("noise-0", result.stdout)

    def test_logs_marks_same_size_content_rewrite_as_current(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            prelaunch_bepinex_log="stale-entry" * 20,
        )
        bepinex_log = profile_preflight.bepinex_root / "LogOutput.log"
        current_prefix = (
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : BepInEx] Loading [ExampleMod 1.0.0]\n"
        )
        baseline = json.loads(
            deployment.state_path.read_text(encoding="utf-8")
        )["process"]["log_baseline"]["bepinex"]
        newline_translation = (
            current_prefix.count("\n") if os.linesep == "\r\n" else 0
        )
        current = current_prefix + "x" * (
            int(baseline["size"]) - len(current_prefix) - newline_translation
        )
        bepinex_log.write_text(current, encoding="utf-8")
        os.utime(
            bepinex_log,
            ns=(int(baseline["mtime_ns"]), int(baseline["mtime_ns"])),
        )
        current_stat = bepinex_log.stat()
        self.assertEqual(current_stat.st_size, baseline["size"])
        self.assertEqual(current_stat.st_mtime_ns, baseline["mtime_ns"])

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("BepInEx log status: current", result.stdout)
        self.assertIn("Startup state: mod_loaded", result.stdout)
        self.assertNotIn("not current", result.stderr)

    def test_logs_full_output_includes_the_complete_current_log(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        unity_log_dir = self.root / "unity-logs"
        unity_log_dir.mkdir()
        self.write_project_preferences(profile_preflight.profile, unity_log_dir)
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "first-bepinex\n[Info : BepInEx] Chainloader initialized\n"
            "[Info : BepInEx] Loading [ExampleMod 1.0.0]\n",
            encoding="utf-8",
        )
        (unity_log_dir / "output_log.txt").write_text(
            "first-unity\nunity-tail\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            "--full",
            session=session,
        )

        self.assert_success(result)
        self.assertIn("first-bepinex", result.stdout)
        self.assertIn("first-unity", result.stdout)

    def test_logs_requires_current_chainloader_evidence_for_ready_and_mod_loaded(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        unity_log_dir = self.root / "unity-logs"
        unity_log_dir.mkdir()
        self.write_project_preferences(profile_preflight.profile, unity_log_dir)
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n",
            encoding="utf-8",
        )
        (unity_log_dir / "output_log.txt").write_text(
            "unity-start\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: ready", result.stdout)
        self.assertIn("Ready state: ready", result.stdout)
        self.assertIn("Mod-loaded state: not-loaded", result.stdout)

    def test_logs_recognizes_structured_moddingapi_registration_for_runtime_alias(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={
                "target_name": "PackageFolder",
                "assembly_name": "RuntimeMod",
            }
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : ModdingAPI] Registered Mod: RuntimeMod\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["target_name"], "PackageFolder")
        self.assertEqual(
            payload["runtime_aliases"],
            ["PackageFolder", "RuntimeMod", "Example"],
        )
        self.assertEqual(payload["evidence"]["hits"][0]["reason"], "ModdingAPI registration")

    def test_logs_recognizes_registering_moddingapi_record(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={"target_name": "Blasphemous.Modlist"}
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : ModdingAPI] Registering mod: Blasphemous.Modlist\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)

    def test_logs_recognizes_mod_loader_id_and_bepinex_display_name(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={
                "name": "ModList.csproj",
                "target_name": "ModList",
                "assembly_name": "Blasphemous.ModList",
            }
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info   :   BepInEx] Loading [Mod List 0.1.0]\n"
            "[Message:   BepInEx] Chainloader startup complete\n"
            "[Message:Mod Loader] Registering mod: Blasphemous.ModList (0.1.0)\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)
        self.assertIn("mod_id=Blasphemous.ModList", result.stdout)
        self.assertIn("mod_name=Mod List", result.stdout)
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        id_hit = next(
            hit
            for hit in payload["evidence"]["hits"]
            if hit["mod_id"] == "Blasphemous.ModList"
        )
        display_hit = next(
            hit
            for hit in payload["evidence"]["hits"]
            if hit["mod_name"] == "Mod List"
        )
        self.assertEqual(id_hit["reason"], "Mod Loader registration")
        self.assertEqual(display_hit["kind"], "context")
        self.assertIsNone(display_hit["mod_id"])

    def test_bepinex_display_name_does_not_become_canonical_id(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={"target_name": "Blasphemous.ModList"}
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Message:Mod Loader] Chainloader startup complete\n"
            "[Info : BepInEx] Loading [Mod List 0.1.0]\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: ready", result.stdout)
        self.assertIn("Mod-loaded state: not-loaded", result.stdout)
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        display_hit = next(
            hit
            for hit in payload["evidence"]["hits"]
            if hit["mod_name"] == "Mod List"
        )
        self.assertIsNone(display_hit["mod_id"])

    def test_logs_recognizes_registered_mod_loader_record(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={"target_name": "Blasphemous.ModList"}
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Message:Mod Loader] Chainloader startup complete\n"
            '[Message:Mod Loader] Registered Mod = "Blasphemous.ModList" (0.1.0)\n',
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)
        self.assertIn("mod_id=Blasphemous.ModList", result.stdout)

    def test_logs_rejects_similar_mod_loader_id(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={"target_name": "Blasphemous.ModList"}
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Message:Mod Loader] Chainloader startup complete\n"
            "[Message:Mod Loader] Registering mod: Blasphemous.ModListExtra (0.1.0)\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: ready", result.stdout)
        self.assertIn("Mod-loaded state: not-loaded", result.stdout)
        self.assertNotIn("mod_id=Blasphemous.ModListExtra", result.stdout)

    def test_logs_recognizes_standard_bepinex_loading_record(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={
                "name": "RuntimeProject.csproj",
                "target_name": "PackageFolder",
            }
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : BepInEx] Loading [RuntimeProject 1.0.0]\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)

    def test_logs_recognizes_standard_bepinex_loaded_record(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={
                "name": "RuntimeProject.csproj",
                "target_name": "PackageFolder",
            }
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : BepInEx] Loaded [RuntimeProject 1.0.0]\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)

    def test_logs_rejects_paths_errors_and_unstructured_target_text(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={"assembly_name": "RuntimeMod"}
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : BepInEx] Loading plugin from C:/mods/RuntimeMod.dll\n"
            "[Error : BepInEx] RuntimeMod failed to load\n"
            "RuntimeMod loaded successfully\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: ready", result.stdout)
        self.assertIn("Mod-loaded state: not-loaded", result.stdout)

    def test_registration_without_current_bepinex_readiness_does_not_load_mod(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={"assembly_name": "RuntimeMod"}
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : ModdingAPI] Registered Mod: RuntimeMod\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: launched", result.stdout)
        self.assertIn("Mod-loaded state: not-loaded", result.stdout)

    def test_target_error_before_registration_does_not_promote_to_loaded(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={"assembly_name": "RuntimeMod"}
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Error : BepInEx] RuntimeMod failed to load\n"
            "[Info : ModdingAPI] Registered Mod: RuntimeMod\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: ready", result.stdout)
        self.assertIn("Mod-loaded state: not-loaded", result.stdout)

    def test_target_error_after_registration_does_not_demote_loaded_state(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={"assembly_name": "RuntimeMod"}
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : ModdingAPI] Registered Mod: RuntimeMod\n"
            "[Error : BepInEx] RuntimeMod failed after registration\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)
        self.assertIn('"kind": "error"', deployment.state_path.read_text(encoding="utf-8"))

    def test_target_error_after_many_registrations_remains_visible(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            project_kwargs={"assembly_name": "RuntimeMod"}
        )
        registration_lines = "".join(
            "[Info : ModdingAPI] Registered Mod: RuntimeMod\n"
            for _ in range(module.MAX_EVIDENCE_HITS + 1)
        )
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            + registration_lines
            + "[Error : BepInEx] RuntimeMod failed after registration\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: mod_loaded", result.stdout)
        self.assertIn("RuntimeMod failed after registration", result.stdout)
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertTrue(any(hit["kind"] == "error" for hit in payload["evidence"]["hits"]))

    def test_timeout_rechecks_evidence_at_deadline(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        not_loaded = module.EvidenceReport("ready", True, False, False, (), ())
        loaded = module.EvidenceReport(
            "mod_loaded",
            True,
            True,
            False,
            (),
            (),
            (module.EvidenceHit("BepInEx", 2, "ModdingAPI registration", "registered"),),
        )

        with mock.patch.object(
            module,
            "collect_log_evidence",
            side_effect=(not_loaded, loaded),
        ) as collect:
            with mock.patch.object(module.time, "monotonic", side_effect=(0.0, 1.0)):
                result = session.wait_for_startup_evidence(
                    deployment.state_path,
                    profile_preflight,
                    module.Preferences("project", self.root / "preferences.md", {"modding_profile_path": str(profile_preflight.profile)}),
                    "Windows",
                    0.0,
                )

        self.assertEqual(result.state, "mod_loaded")
        self.assertEqual(collect.call_count, 2)

    def test_logs_ignores_prelaunch_bepinex_evidence_as_stale(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : BepInEx] Loading [ExampleMod 1.0.0]\n"
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Startup state: launched", result.stdout)
        self.assertIn("Ready state: not-ready", result.stdout)
        self.assertIn("not current", result.stderr)

    def test_missing_unity_log_warns_with_preference_update_handoff(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        missing_unity_dir = self.root / "missing-unity-logs"
        preferences = self.write_project_preferences(profile_preflight.profile, missing_unity_dir)
        (profile_preflight.bepinex_root / "LogOutput.log").write_text(
            "[Info : BepInEx] Chainloader initialized\n"
            "[Info : BepInEx] Loading [ExampleMod 1.0.0]\n",
            encoding="utf-8",
        )

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Warning", result.stderr)
        self.assertIn("unity_log_dir", result.stderr)
        self.assertIn(str(preferences), result.stderr)
        self.assertIn("Startup state: mod_loaded", result.stdout)

    def test_missing_bepinex_log_persists_missing_source_before_failure(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        bepinex_log = profile_preflight.bepinex_root / "LogOutput.log"
        self.assertFalse(bepinex_log.exists())

        result = self.run_module_cli(
            module,
            "logs",
            deployment.session_id,
            session=session,
        )

        self.assertEqual(result.returncode, module.EXIT_LOGS)
        self.assertIn("BepInEx log status: missing", result.stdout)
        self.assertIn("current BepInEx log is unavailable", result.stderr)
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["evidence"]["state"], "launched")
        self.assertFalse(payload["evidence"]["sources"]["BepInEx"]["exists"])

    def test_run_reports_launched_ready_and_mod_loaded_as_distinct_states(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        unity_log_dir = self.root / "unity-logs"
        unity_log_dir.mkdir()
        self.write_project_preferences(profile, unity_log_dir)
        process, identity = self.live_process_double(module, self.launcher_path(profile))

        def start_process(*arguments, **keywords):
            (profile / "BepInEx" / "LogOutput.log").write_text(
                "[Info : BepInEx] Chainloader initialized\n"
                "[Info : BepInEx] Loading [ExampleMod 1.0.0]\n",
                encoding="utf-8",
            )
            (unity_log_dir / "output_log.txt").write_text(
                "unity-start\n",
                encoding="utf-8",
            )
            return process

        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.side_effect = start_process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        session = self.create_session(module, process_adapter)
        result = self.run_module_cli(
            module,
            "run",
            "--artifact",
            str(artifact),
            "--startup-timeout",
            "0.1",
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Launch state: launched", result.stdout)
        self.assertIn("Ready state: ready", result.stdout)
        self.assertIn("Mod-loaded state: loaded", result.stdout)
        self.assertIn("Startup state: mod_loaded", result.stdout)

    def test_startup_timeout_preserves_process_and_session_for_diagnosis(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        process, identity = self.live_process_double(module, self.launcher_path(profile))

        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        session = self.create_session(module, process_adapter)
        result = self.run_module_cli(
            module,
            "run",
            "--artifact",
            str(artifact),
            "--startup-timeout",
            "0",
            session=session,
        )

        self.assertEqual(result.returncode, 60)
        self.assertIn("Startup state: timeout", result.stdout)
        self.assertIn("remain available", result.stderr)
        process_adapter.terminate_tree.assert_not_called()
        manifests = self.deployment_manifests()
        self.assertEqual(len(manifests), 1)
        payload = json.loads(manifests[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "launched")
        self.assertEqual(payload["evidence"]["state"], "timeout")

    def test_stop_help_exposes_session_and_force(self):
        result = self.run_cli("stop", "--help")

        self.assert_success(result)
        self.assertIn("SESSION_ID", result.stdout)
        self.assertIn("--force", result.stdout)

    def test_launch_records_live_profile_process(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        launcher = profile / "custom-launcher"
        launcher.write_bytes(b"launcher")
        if os.name != "nt":
            launcher.chmod(0o755)
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(
            profile,
            environment,
            explicit_launcher=launcher.name,
        )
        process = mock.Mock()
        process.pid = 1234
        process.poll.return_value = None
        identity = module.ProcessIdentity(
            process.pid,
            "start-token",
            launcher.resolve(),
        )

        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        session = self.create_session(module, process_adapter)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        launch = session.launch(deployment, profile_preflight)

        self.assertEqual(launch.session_id, deployment.session_id)
        self.assertEqual(launch.pid, process.pid)
        process_adapter.start.assert_called_once_with(
            launcher.resolve(),
            profile.resolve(),
        )
        payload = json.loads(
            deployment.state_path.read_text(encoding="utf-8")
        )
        self.assertEqual(payload["process"]["state"], "launched")
        self.assertEqual(payload["process"]["pid"], process.pid)
        self.assertEqual(payload["process"]["start_token"], "start-token")

    def test_test_session_launch_uses_public_process_lifecycle_seam(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        process = mock.Mock()
        process.pid = 1234
        process.poll.return_value = None
        identity = module.ProcessIdentity(
            process.pid,
            "start-token",
            self.launcher_path(profile).resolve(),
        )
        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        session = module.TestSession(
            state_root=self.temp_root / "sessions",
            process_adapter=process_adapter,
        )
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(
            profile,
            environment,
        )

        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        launch = session.launch(deployment, profile_preflight)

        self.assertEqual(launch.pid, process.pid)
        process_adapter.start.assert_called_once_with(
            profile_preflight.launcher,
            profile_preflight.profile,
        )
        process_adapter.identify.assert_called_once_with(process.pid, strict=True)
        process_adapter.wait_for_alive.assert_called_once_with(
            identity,
            timeout=module.LAUNCH_GRACE_PERIOD_SECONDS,
        )

    def test_launch_race_refuses_conflict_without_mutating_session_state(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        launcher = profile / "custom-launcher"
        launcher.write_bytes(b"launcher")
        if os.name != "nt":
            launcher.chmod(0o755)
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(
            profile,
            environment,
            explicit_launcher=launcher.name,
        )
        conflict = module.ProcessIdentity(4321, "other-token", launcher.resolve())

        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.side_effect = [None, conflict]
        process_adapter.start.return_value = mock.Mock()
        session = self.create_session(module, process_adapter)
        self.assertIsNone(session.find_conflict(profile_preflight.launcher))
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        manifest_before_launch = json.loads(
            deployment.state_path.read_text(encoding="utf-8")
        )
        with self.assertRaises(module.CliError) as failure:
            session.launch(deployment, profile_preflight)

        self.assertEqual(failure.exception.code, 50)
        self.assertIn("already running", str(failure.exception))
        process_adapter.start.assert_not_called()
        self.assertEqual(
            json.loads(deployment.state_path.read_text(encoding="utf-8")),
            manifest_before_launch,
        )

    def test_launch_does_not_report_exited_process_as_launched(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        launcher = profile / "custom-launcher"
        launcher.write_bytes(b"launcher")
        if os.name != "nt":
            launcher.chmod(0o755)
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(
            profile,
            environment,
            explicit_launcher=launcher.name,
        )
        process = mock.Mock()
        process.pid = 1234
        process.poll.return_value = 7

        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        session = self.create_session(module, process_adapter)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        with self.assertRaises(module.CliError) as failure:
            session.launch(deployment, profile_preflight)

        self.assertEqual(failure.exception.code, 50)
        self.assertIn("exited", str(failure.exception))
        payload = json.loads(
            deployment.state_path.read_text(encoding="utf-8")
        )
        self.assertEqual(payload["process"]["state"], "exited")

    def test_launch_race_records_process_that_exits_before_identity_inspection(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        process, identity = self.live_process_double(
            module,
            self.launcher_path(profile),
        )
        process.poll.side_effect = [None, 7]
        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = None
        session = self.create_session(module, process_adapter)

        result = self.run_module_cli(
            module,
            "run",
            "--artifact",
            str(artifact),
            session=session,
        )

        self.assertEqual(result.returncode, module.EXIT_LAUNCH)
        self.assertIn("exited", result.stderr)
        payload = json.loads(self.deployment_manifests()[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "exited")
        self.assertEqual(payload["process"]["exit_code"], 7)
        process.terminate.assert_not_called()

    def test_launch_persists_safely_tracked_child_identities(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            tracked_child_pids=(1235,)
        )

        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))

        self.assertEqual(
            payload["process"]["children"],
            [
                {
                    "executable": str(identity.executable),
                    "pid": 1235,
                    "start_token": "child-start-token-1235",
                }
            ],
        )

    def test_stop_terminates_tracked_process_and_is_idempotent(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        session.process_adapter.is_alive.return_value = True
        session.process_adapter.snapshot_tree.return_value = (identity,)
        session.process_adapter.wait_for_exit.return_value = True
        result = session.stop(deployment.session_id, force=True)

        self.assertEqual(result.session_id, deployment.session_id)
        self.assertEqual(result.state, "stopped")
        session.process_adapter.terminate_tree.assert_called_once_with(
            identity,
            force=True,
        )
        payload = json.loads(
            deployment.state_path.read_text(encoding="utf-8")
        )
        self.assertEqual(payload["process"]["state"], "stopped")

        repeated = session.stop(deployment.session_id)
        self.assertEqual(repeated.state, "stopped")
        self.assertEqual(session.process_adapter.terminate_tree.call_count, 1)

    def test_stop_and_clean_are_idempotent_when_session_state_is_gone(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        self.write_project_preferences(profile)
        missing_session = "a" * 32

        session = self.create_session(module)
        stopped = self.run_module_cli(module, "stop", missing_session, session=session)
        cleaned = self.run_module_cli(module, "clean", missing_session, session=session)

        self.assert_success(stopped)
        self.assertIn("Stop state: gone", stopped.stdout)
        self.assert_success(cleaned)
        self.assertIn("Clean state: already-gone", cleaned.stdout)
        self.assertIn("already gone", cleaned.stderr)

    def test_stop_marks_an_already_exited_process_without_termination(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        session.process_adapter.is_alive.return_value = False
        result = session.stop(deployment.session_id)

        self.assertEqual(result.state, "exited")
        session.process_adapter.terminate_tree.assert_not_called()
        payload = json.loads(
            deployment.state_path.read_text(encoding="utf-8")
        )
        self.assertEqual(payload["process"]["state"], "exited")

    def test_windows_taskkill_not_found_race_records_exited(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        session.process_adapter = module.ProcessAdapter()
        observed_identities = iter(
            (identity, identity, identity, None, None)
        )

        with mock.patch.object(module.os, "name", "nt"):
            with mock.patch.object(
                module,
                "_windows_process_entries",
                return_value=(),
            ):
                with mock.patch.object(
                    module,
                    "_process_identity",
                    side_effect=lambda pid, strict=False: next(observed_identities),
                ):
                    with mock.patch.object(
                        module.subprocess,
                        "run",
                        return_value=SimpleNamespace(
                            returncode=1281,
                            stdout="",
                            stderr="The process was not found.",
                        ),
                    ) as taskkill:
                        result = session.stop(deployment.session_id)

        self.assertEqual(result.state, "exited")
        taskkill.assert_called_once_with(
            ["taskkill", "/PID", str(identity.pid), "/T"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "exited")
        cleaned = session.clean(deployment.session_id)
        self.assertEqual(cleaned.state, "cleaned")

    def test_windows_taskkill_race_refuses_reused_pid(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        session.process_adapter = module.ProcessAdapter()
        reused = module.ProcessIdentity(
            identity.pid,
            "reused-start-token",
            identity.executable,
        )
        observed_identities = iter(
            (identity, identity, identity, reused)
        )

        with mock.patch.object(module.os, "name", "nt"):
            with mock.patch.object(
                module,
                "_windows_process_entries",
                return_value=(),
            ):
                with mock.patch.object(
                    module,
                    "_process_identity",
                    side_effect=lambda pid, strict=False: next(observed_identities),
                ):
                    with mock.patch.object(
                        module.subprocess,
                        "run",
                        return_value=SimpleNamespace(
                            returncode=1281,
                            stdout="",
                            stderr="The process was not found.",
                        ),
                    ) as taskkill:
                        with self.assertRaises(module.CliError) as failure:
                            session.stop(deployment.session_id)

        self.assertEqual(failure.exception.code, module.EXIT_CLEAN)
        self.assertIn("changed", str(failure.exception))
        taskkill.assert_called_once()
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "launched")

    def test_windows_process_adapter_does_not_report_exited_process_as_live(self):
        import ctypes
        from ctypes import wintypes

        module = self.load_cli_module()
        kernel32 = SimpleNamespace(
            OpenProcess=mock.Mock(return_value=1234),
            GetProcessTimes=mock.Mock(),
            QueryFullProcessImageNameW=mock.Mock(),
            CloseHandle=mock.Mock(return_value=1),
        )

        def fill_process_times(handle, creation, exit_time, kernel, user):
            creation_value = ctypes.cast(
                creation,
                ctypes.POINTER(wintypes.FILETIME),
            ).contents
            exit_value = ctypes.cast(
                exit_time,
                ctypes.POINTER(wintypes.FILETIME),
            ).contents
            creation_value.dwHighDateTime = 0x12
            creation_value.dwLowDateTime = 0x34
            exit_value.dwHighDateTime = 0
            exit_value.dwLowDateTime = 1
            return 1

        kernel32.GetProcessTimes.side_effect = fill_process_times
        with mock.patch.object(module.os, "name", "nt"):
            with mock.patch.object(ctypes, "WinDLL", return_value=kernel32):
                identity = module.ProcessAdapter().identify(1234, strict=True)

        self.assertIsNone(identity)
        self.assertEqual(
            kernel32.OpenProcess.argtypes,
            [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
        )
        self.assertEqual(kernel32.OpenProcess.restype, wintypes.HANDLE)
        self.assertEqual(kernel32.GetProcessTimes.restype, wintypes.BOOL)

    def test_status_derives_live_process_observation_without_mutating_state(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        session.process_adapter.is_alive.return_value = False
        before = deployment.state_path.read_text(encoding="utf-8")

        result = self.run_module_cli(
            module,
            "status",
            session=session,
        )

        self.assert_success(result)
        self.assertIn("process=exited", result.stdout)
        session.process_adapter.is_alive.assert_called_once_with(identity)
        self.assertEqual(
            deployment.state_path.read_text(encoding="utf-8"),
            before,
        )

    def test_stop_does_not_declare_exit_until_every_tracked_child_is_gone(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            tracked_child_pids=(1235,)
        )
        child = module.ProcessIdentity(
            identity.pid + 1,
            "child-start-token",
            identity.executable,
        )
        session.process_adapter.is_alive.return_value = True
        session.process_adapter.terminate_tree.return_value = False
        session.process_adapter.wait_for_exit.side_effect = [True, False]

        with self.assertRaises(module.CliError) as failure:
            session.stop(deployment.session_id)

        self.assertEqual(failure.exception.code, module.EXIT_CLEAN)
        self.assertIn("child process", str(failure.exception))
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "launched")

    def test_stop_refuses_when_root_exited_but_tracked_child_is_live(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            tracked_child_pids=(1235,)
        )
        session.process_adapter.is_alive.side_effect = [False, True]

        with self.assertRaises(module.CliError) as failure:
            session.stop(deployment.session_id)

        self.assertEqual(failure.exception.code, module.EXIT_CLEAN)
        self.assertIn("child", str(failure.exception).casefold())
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "launched")

    def test_stop_records_exited_after_root_and_all_tracked_children_are_gone(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            tracked_child_pids=(1235,)
        )
        session.process_adapter.is_alive.side_effect = [False, False, False]

        result = session.stop(deployment.session_id)

        self.assertEqual(result.state, "exited")
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "exited")
        self.assertEqual(session.clean(deployment.session_id).state, "cleaned")

    def test_stop_refuses_when_root_exited_but_tracked_child_pid_was_reused(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            tracked_child_pids=(1235,)
        )
        session.process_adapter.is_alive.side_effect = [
            False,
            module.CliError(
                module.EXIT_CLEAN,
                "stop/clean",
                "Tracked process ID 1235 was reused by another process; refusing to stop it.",
            ),
        ]

        with self.assertRaises(module.CliError) as failure:
            session.stop(deployment.session_id)

        self.assertEqual(failure.exception.code, module.EXIT_CLEAN)
        self.assertIn("reused", str(failure.exception))
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "launched")

    def test_stop_refuses_when_root_exited_without_persisted_child_identities(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        del payload["process"]["children"]
        deployment.state_path.write_text(json.dumps(payload), encoding="utf-8")
        session.process_adapter.is_alive.return_value = False

        with self.assertRaises(module.CliError) as failure:
            session.stop(deployment.session_id)

        self.assertEqual(failure.exception.code, module.EXIT_CLEAN)
        self.assertIn("child", str(failure.exception).casefold())
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "launched")

    def test_clean_refuses_when_root_exited_but_tracked_child_is_uninspectable(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session(
            tracked_child_pids=(1235,)
        )
        session.process_adapter.is_alive.side_effect = [
            False,
            module.CliError(
                module.EXIT_CLEAN,
                "stop/clean",
                "Tracked child process ID 1235 could not be inspected; refusing to clean it.",
            ),
        ]

        result = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            session=session,
        )

        self.assertEqual(result.returncode, module.EXIT_CLEAN)
        self.assertIn("could not be inspected", result.stderr)
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "launched")

    def test_stop_refuses_an_uninspectable_live_process(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        session.process_adapter = module.ProcessAdapter()

        with mock.patch.object(
            module,
            "_process_identity",
            side_effect=PermissionError(5, "access denied"),
        ):
            with self.assertRaises(module.CliError) as failure:
                session.stop(deployment.session_id)

        self.assertEqual(failure.exception.code, module.EXIT_CLEAN)
        self.assertIn("refusing", str(failure.exception))
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "launched")

    def test_stop_refuses_a_reused_pid_without_termination(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()

        session.process_adapter.is_alive.side_effect = module.CliError(
            module.EXIT_CLEAN,
            "stop/clean",
            f"Tracked process ID {identity.pid} was reused by another process; refusing to stop it.",
        )
        with self.assertRaises(module.CliError) as failure:
            session.stop(deployment.session_id)

        self.assertEqual(failure.exception.code, 70)
        self.assertIn("reused", str(failure.exception))
        session.process_adapter.terminate_tree.assert_not_called()
        payload = json.loads(
            deployment.state_path.read_text(encoding="utf-8")
        )
        self.assertEqual(payload["process"]["state"], "launched")

    def test_dry_run_resolves_project_and_profile_without_mutation(self):
        profile = self.create_profile()
        project = self.create_project()
        package_root = self.create_package()
        self.write_project_preferences(profile)
        before = self.snapshot()

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
        )

        self.assert_success(result)
        self.assertIn(f"Project: {project}", result.stdout)
        self.assertIn(f"Modding profile: {profile}", result.stdout)
        self.assertIn(f"Launcher: {self.launcher_path(profile)}", result.stdout)
        self.assertIn(f"Package root: {package_root}", result.stdout)
        self.assertIn("Configuration: Debug", result.stdout)
        self.assertIn(
            "Dry run: no profile files copied; no process launched.",
            result.stdout,
        )
        self.assertEqual(before, self.snapshot())

    def test_status_is_read_only_and_reports_profile_state(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        before = self.snapshot()

        result = self.run_cli("status")

        self.assert_success(result)
        self.assertIn(f"Modding profile: {profile}", result.stdout)
        self.assertIn(
            "Test sessions (newest first):",
            result.stdout,
        )
        self.assertEqual(before, self.snapshot())

    def test_project_scope_overrides_user_scope(self):
        project_profile = self.create_profile("project-profile")
        user_profile = self.create_profile("user-profile")
        self.create_project()
        package_root = self.create_package()
        self.write_user_preferences(user_profile)
        project_preferences = self.write_project_preferences(project_profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
        )

        self.assert_success(result)
        self.assertIn(f"Preferences: project ({project_preferences})", result.stdout)
        self.assertIn(f"Modding profile: {project_profile}", result.stdout)
        self.assertNotIn(f"Modding profile: {user_profile}", result.stdout)

    def test_explicit_profile_overrides_project_preference(self):
        preferred_profile = self.root / "missing-profile"
        explicit_profile = self.create_profile("explicit-profile")
        self.create_project()
        package_root = self.create_package()
        self.write_project_preferences(preferred_profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
            "--profile",
            str(explicit_profile),
        )

        self.assert_success(result)
        self.assertIn(f"Modding profile: {explicit_profile}", result.stdout)

    def test_configured_source_path_is_validated_before_build_or_dry_run(self):
        profile = self.create_profile()
        self.create_project()
        package_root = self.create_package()
        preferences = self.write_project_preferences(profile)
        preferences.write_text(
            preferences.read_text(encoding="utf-8")
            + f"lightweight_source_code_path: {self.root / 'missing-source'}\n",
            encoding="utf-8",
        )

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
        )

        self.assertEqual(result.returncode, 10)
        self.assertIn("lightweight_source_code_path", result.stderr)
        self.assertIn("does not exist", result.stderr)

    def test_missing_preferences_returns_profile_preference_error(self):
        self.create_project()

        result = self.run_cli("run", "--dry-run")

        self.assertEqual(result.returncode, 10)
        self.assertIn("preferences.md", result.stderr)

    def test_no_project_returns_usage_configuration_error(self):
        profile = self.create_profile()
        self.write_project_preferences(profile)

        result = self.run_cli("run", "--dry-run")

        self.assertEqual(result.returncode, 2)
        self.assertIn("No .csproj project was found", result.stderr)

    def test_multiple_projects_require_explicit_selection(self):
        profile = self.create_profile()
        self.write_project_preferences(profile)
        first = self.create_project("First.csproj")
        second = self.create_project("Second.csproj")
        package_root = self.create_package()

        ambiguous = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
        )
        selected = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
            "--project",
            str(second),
        )

        self.assertEqual(ambiguous.returncode, 2)
        self.assertIn(first.name, ambiguous.stderr)
        self.assertIn(second.name, ambiguous.stderr)
        self.assert_success(selected)
        self.assertIn(f"Project: {second}", selected.stdout)

    def test_missing_profile_children_are_rejected_without_creation(self):
        profile = self.root / "incomplete-profile"
        profile.mkdir()
        self.create_project()
        package_root = self.create_package()
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
        )

        self.assertEqual(result.returncode, 10)
        self.assertIn("Modding", result.stderr)
        self.assertFalse((profile / "Modding").exists())
        self.assertFalse((profile / "BepInEx").exists())

    def test_missing_launcher_is_rejected_without_mutation(self):
        profile = self.root / "profile-without-launcher"
        (profile / "Modding").mkdir(parents=True)
        (profile / "BepInEx" / "core").mkdir(parents=True)
        (profile / "BepInEx" / "core" / "BepInEx.dll").write_bytes(b"BepInEx")
        self.create_project()
        package_root = self.create_package()
        self.write_project_preferences(profile)
        before = self.snapshot()

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
        )

        self.assertEqual(result.returncode, 10)
        self.assertIn("launcher", result.stderr.lower())
        self.assertEqual(before, self.snapshot())

    def test_empty_bepinex_directory_is_not_an_installation(self):
        profile = self.root / "profile-without-bepinex-core"
        (profile / "Modding").mkdir(parents=True)
        (profile / "BepInEx").mkdir()
        launcher = self.launcher_path(profile)
        launcher.write_bytes(b"launcher")
        if platform.system() != "Windows":
            launcher.chmod(0o755)
        self.create_project()
        self.write_project_preferences(profile)

        result = self.run_cli("run", "--dry-run")

        self.assertEqual(result.returncode, 10)
        self.assertIn("BepInEx core assembly", result.stderr)

    def test_explicit_launcher_can_be_relative_to_the_profile(self):
        profile = self.create_profile()
        custom_launcher = profile / "custom-launcher"
        custom_launcher.write_bytes(b"launcher")
        if os.name != "nt":
            custom_launcher.chmod(0o755)
        self.create_project()
        package_root = self.create_package()
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
            "--launcher",
            custom_launcher.name,
        )

        self.assert_success(result)
        self.assertIn(f"Launcher: {custom_launcher}", result.stdout)
        self.assertIn("Warning: Using explicit launcher override", result.stderr)

    def test_default_launcher_symlink_cannot_escape_the_profile(self):
        profile = self.create_profile()
        launcher = self.launcher_path(profile)
        launcher.unlink()
        external_launcher = self.root / launcher.name
        external_launcher.parent.mkdir(parents=True, exist_ok=True)
        external_launcher.write_bytes(b"external-launcher")
        if os.name != "nt":
            external_launcher.chmod(0o755)
        try:
            os.symlink(external_launcher, launcher)
        except OSError as error:
            self.skipTest(f"symbolic links unavailable: {error}")
        self.create_project()
        package_root = self.create_package()
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(package_root),
        )

        self.assertEqual(result.returncode, 10)
        self.assertIn("No known game launcher", result.stderr)

    def test_invalid_preferences_encoding_returns_profile_preference_error(self):
        preferences = self.root / ".skills" / "blasphemous-modding-helper" / "preferences.md"
        preferences.parent.mkdir(parents=True)
        preferences.write_bytes(b"modding_profile_path: \xff\n")

        result = self.run_cli("status")

        self.assertEqual(result.returncode, 10)
        self.assertIn("Could not read preferences.md", result.stderr)

    def test_compatibility_shell_is_rejected(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        environment = self.environment.copy()
        environment["MSYSTEM"] = "MINGW64"

        result = self.run_cli(
            "run",
            "--dry-run",
            environment=environment,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported", result.stderr.lower())

    def test_stop_rejects_compatibility_shell(self):
        environment = self.environment.copy()
        environment["MSYSTEM"] = "MINGW64"

        result = self.run_cli(
            "stop",
            "00000000000000000000000000000000",
            environment=environment,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported", result.stderr.lower())

    def test_proton_environment_is_rejected(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        environment = self.environment.copy()
        environment["STEAM_COMPAT_DATA_PATH"] = str(self.root / "compatdata")

        result = self.run_cli(
            "run",
            "--dry-run",
            environment=environment,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Proton", result.stderr)

    def test_classic_solution_membership_selects_matching_solution_root(self):
        profile = self.create_profile()
        solution_root = self.root / "solution"
        project = self.create_project(
            project_directory=solution_root / "src" / "mod"
        )
        unrelated_solution = self.create_classic_solution(
            solution_root / "src" / "unrelated.sln",
            self.root / "other.csproj",
        )
        target_solution = self.create_classic_solution(
            solution_root / "BlasphemousMods.sln",
            project,
        )
        package = self.create_package(root=self.root)
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--project",
            str(project),
            "--artifact",
            str(package),
        )

        self.assert_success(result)
        self.assertIn(f"Solution: {target_solution}", result.stdout)
        self.assertNotIn(f"Solution: {unrelated_solution}", result.stdout)
        self.assertIn(f"Solution root: {solution_root}", result.stdout)
        self.assertIn(f"Publish directory: {solution_root / 'publish'}", result.stdout)

    def test_xml_solution_membership_selects_solution_root(self):
        profile = self.create_profile()
        solution_root = self.root / "xml-solution"
        project = self.create_project(
            project_directory=solution_root / "mods" / "xml"
        )
        target_solution = self.create_xml_solution(
            solution_root / "BlasphemousMods.slnx",
            project,
        )
        package = self.create_package(root=self.root)
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--project",
            str(project),
            "--artifact",
            str(package),
        )

        self.assert_success(result)
        self.assertIn(f"Solution: {target_solution}", result.stdout)
        self.assertIn(f"Solution root: {solution_root}", result.stdout)
        self.assertIn(f"SolutionDir: {solution_root}{os.sep}", result.stdout)
        self.assertIn(f"Publish directory: {solution_root / 'publish'}", result.stdout)

    def test_unrelated_solutions_use_project_directory_fallback(self):
        profile = self.create_profile()
        project = self.create_project(project_directory=self.root / "mods")
        self.create_classic_solution(
            self.root / "Unrelated.sln",
            self.root / "other.csproj",
        )
        package = self.create_package(root=self.root)
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--project",
            str(project),
            "--artifact",
            str(package),
        )

        self.assert_success(result)
        self.assertIn("Solution: project directory fallback", result.stdout)
        self.assertIn(f"Solution root: {project.parent}", result.stdout)
        self.assertIn(f"SolutionDir: {project.parent}{os.sep}", result.stdout)
        self.assertIn(f"Publish directory: {project.parent / 'publish'}", result.stdout)

    def test_multiple_matching_solutions_fail_explicitly(self):
        profile = self.create_profile()
        project = self.create_project()
        self.create_classic_solution(self.root / "First.sln", project)
        self.create_xml_solution(self.root / "Second.slnx", project)
        package = self.create_package(root=self.root)
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--project",
            str(project),
            "--artifact",
            str(package),
        )

        self.assertEqual(result.returncode, 20)
        self.assertIn("Multiple solutions", result.stderr)

    def test_duplicate_project_membership_fails_explicitly(self):
        profile = self.create_profile()
        project = self.create_project()
        self.create_classic_solution(self.root / "Duplicate.sln", project, project)
        package = self.create_package(root=self.root)
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--project",
            str(project),
            "--artifact",
            str(package),
        )

        self.assertEqual(result.returncode, 20)
        self.assertIn("listed multiple times", result.stderr)

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required")
    def test_default_build_uses_debug_and_reports_the_package_plan(self):
        profile = self.create_profile()
        self.create_buildable_project()
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
        )

        self.assert_success(result)
        self.assertIn("Configuration: Debug", result.stdout)
        self.assertIn("Solution: project directory fallback", result.stdout)
        self.assertIn(f"Solution root: {self.root}", result.stdout)
        self.assertIn(f"SolutionDir: {self.root}{os.sep}", result.stdout)
        self.assertIn(
            f"Package root: {self.root / 'publish' / 'ExampleMod'}",
            result.stdout,
        )
        self.assertEqual(
            (self.root / "publish" / "ExampleMod" / "data" / "build-configuration.txt").read_text(
                encoding="utf-8"
            ),
            "Debug\n",
        )

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required")
    def test_default_build_deploys_the_validated_package(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        self.create_buildable_project()
        self.write_project_preferences(profile)
        process, identity = self.live_process_double(module, self.launcher_path(profile))
        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        session = self.create_session(module, process_adapter)
        result = self.run_module_cli(module, "run", session=session)

        self.assert_success(result)
        self.assertEqual(
            (profile / "Modding" / "plugins" / "Example.dll").read_text(
                encoding="utf-8"
            ),
            "plugin\n",
        )
        self.assertEqual(
            (profile / "Modding" / "data" / "build-configuration.txt").read_text(
                encoding="utf-8"
            ),
            "Debug\n",
        )
        self.assertIn("Deployment state: deployed", result.stdout)

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required")
    def test_release_requires_explicit_configuration(self):
        profile = self.create_profile()
        self.create_buildable_project()
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--configuration",
            "Release",
        )

        self.assert_success(result)
        self.assertIn("Configuration: Release", result.stdout)
        self.assertEqual(
            (self.root / "publish" / "ExampleMod" / "data" / "build-configuration.txt").read_text(
                encoding="utf-8"
            ),
            "Release\n",
        )

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required")
    def test_build_uses_matching_solution_root_for_publish(self):
        profile = self.create_profile()
        solution_root = self.root / "solution"
        project = self.create_buildable_project(
            project_directory=solution_root / "mod"
        )
        solution = self.create_classic_solution(
            solution_root / "BlasphemousMods.sln",
            project,
        )
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--project",
            str(project),
        )

        self.assert_success(result)
        self.assertIn(f"Solution: {solution}", result.stdout)
        self.assertIn(f"Solution root: {solution_root}", result.stdout)
        self.assertIn(f"SolutionDir: {solution_root}{os.sep}", result.stdout)
        package_root = solution_root / "publish" / "ExampleMod"
        self.assertIn(f"Publish directory: {solution_root / 'publish'}", result.stdout)
        self.assertIn(f"Package root: {package_root}", result.stdout)
        self.assertEqual(
            (package_root / "data" / "build-configuration.txt").read_text(
                encoding="utf-8"
            ),
            "Debug\n",
        )

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required")
    def test_build_uses_xml_solution_root_for_publish(self):
        profile = self.create_profile()
        solution_root = self.root / "xml-solution"
        project = self.create_buildable_project(
            project_directory=solution_root / "mod"
        )
        solution = self.create_xml_solution(
            solution_root / "BlasphemousMods.slnx",
            project,
        )
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--project",
            str(project),
        )

        self.assert_success(result)
        self.assertIn(f"Solution: {solution}", result.stdout)
        self.assertIn(f"Solution root: {solution_root}", result.stdout)
        self.assertIn(f"SolutionDir: {solution_root}{os.sep}", result.stdout)
        package_root = solution_root / "publish" / "ExampleMod"
        self.assertIn(f"Publish directory: {solution_root / 'publish'}", result.stdout)
        self.assertIn(f"Package root: {package_root}", result.stdout)
        self.assertEqual(
            (package_root / "data" / "build-configuration.txt").read_text(
                encoding="utf-8"
            ),
            "Debug\n",
        )

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required")
    def test_build_failure_returns_build_error_before_artifact_validation(self):
        profile = self.create_profile()
        self.create_failing_project()
        self.write_project_preferences(profile)

        result = self.run_cli("run", "--dry-run")

        self.assertEqual(result.returncode, 20)
        self.assertIn("Build failed", result.stderr)
        self.assertFalse((self.root / "publish").exists())

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required")
    def test_missing_package_root_returns_artifact_error(self):
        profile = self.create_profile()
        self.create_empty_build_project()
        self.write_project_preferences(profile)

        result = self.run_cli("run", "--dry-run")

        self.assertEqual(result.returncode, 30)
        self.assertIn("Package root does not exist", result.stderr)

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK required")
    def test_empty_package_returns_artifact_error(self):
        profile = self.create_profile()
        self.create_empty_build_project()
        (self.root / "publish" / "ExampleMod").mkdir(parents=True)
        self.write_project_preferences(profile)

        result = self.run_cli("run", "--dry-run")

        self.assertEqual(result.returncode, 30)
        self.assertIn("package contains no files", result.stderr.lower())

    def test_explicit_directory_artifact_skips_build(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        artifact = self.root / "known-artifact"
        self.create_package(root=self.root, target_name="known-artifact")

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(artifact),
        )

        self.assert_success(result)
        self.assertIn(f"Artifact: {artifact}", result.stdout)

    def test_run_deploys_artifact_relative_to_selected_modding_root(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        (artifact / "localization").mkdir()
        (artifact / "localization" / "strings.txt").write_text(
            "test-localization\n",
            encoding="utf-8",
        )
        self.write_project_preferences(profile)
        process, identity = self.live_process_double(module, self.launcher_path(profile))
        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        session = self.create_session(module, process_adapter)
        result = self.run_module_cli(
            module,
            "run",
            "--artifact",
            str(artifact),
            session=session,
        )

        self.assert_success(result)
        for relative_path in (
            Path("plugins/Example.dll"),
            Path("data/settings.json"),
            Path("localization/strings.txt"),
        ):
            self.assertEqual(
                (artifact / relative_path).read_bytes(),
                (profile / "Modding" / relative_path).read_bytes(),
            )
        self.assertFalse((profile / "plugins").exists())
        self.assertIn("Deployment session:", result.stdout)
        self.assertIn("Launch state: launched", result.stdout)
        self.assertIn("Process ID: 4321", result.stdout)
        self.assertIn("Deployed files: 3", result.stdout)

    def test_launcher_command_string_is_rejected(self):
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(artifact),
            "--launcher",
            f"{self.launcher_path(profile)} --flag",
        )

        self.assertEqual(result.returncode, 10)
        self.assertIn("does not exist", result.stderr)

    def test_deployment_records_backups_and_hashes_without_logs(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "plugins" / "Example.dll"
        existing.parent.mkdir()
        existing.write_bytes(b"pre-test-plugin")
        self.write_project_preferences(profile)
        process, identity = self.live_process_double(module, self.launcher_path(profile))
        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        session = self.create_session(module, process_adapter)
        result = self.run_module_cli(
            module,
            "run",
            "--artifact",
            str(artifact),
            session=session,
        )

        self.assert_success(result)
        manifests = self.deployment_manifests()
        self.assertEqual(len(manifests), 1)
        manifest = manifests[0]
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "deployed")
        self.assertEqual(payload["planned_directories"], ["data"])
        self.assertEqual(payload["created_directories"], ["data"])
        records = {
            record["relative_path"]: record
            for record in payload["files"]
        }

        overwritten = records["plugins/Example.dll"]
        self.assertTrue(overwritten["existed"])
        self.assertTrue(overwritten["backup_created"])
        self.assertEqual(
            (manifest.parent / overwritten["backup_path"]).read_bytes(),
            b"pre-test-plugin",
        )
        self.assertEqual(
            overwritten["deployed_sha256"],
            hashlib.sha256((artifact / "plugins/Example.dll").read_bytes()).hexdigest(),
        )

        new_file = records["data/settings.json"]
        self.assertFalse(new_file["existed"])
        self.assertIsNone(new_file["backup_path"])
        self.assertTrue(new_file["deployed_sha256"])
        self.assertNotIn("LogOutput.log", manifest.read_text(encoding="utf-8"))

    def test_repeated_runs_archive_previous_session_and_status_is_newest_first(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        process, identity = self.live_process_double(
            module,
            self.launcher_path(profile),
        )
        process_adapter = mock.Mock(spec=module.ProcessAdapter)
        process_adapter.find_conflict.return_value = None
        process_adapter.start.return_value = process
        process_adapter.identify.return_value = identity
        process_adapter.wait_for_alive.return_value = (True, identity)
        process_adapter.is_alive.return_value = False
        session = self.create_session(module, process_adapter)
        first = self.run_module_cli(
            module,
            "run",
            "--artifact",
            str(artifact),
            session=session,
        )
        second = self.run_module_cli(
            module,
            "run",
            "--artifact",
            str(artifact),
            session=session,
        )
        status = self.run_module_cli(module, "status", session=session)

        self.assert_success(first)
        self.assert_success(second)
        first_id = first.stdout.split("Deployment session: ", 1)[1].splitlines()[0]
        second_id = second.stdout.split("Deployment session: ", 1)[1].splitlines()[0]
        self.assertNotEqual(first_id, second_id)
        self.assertIn("archived", second.stderr.casefold())
        self.assertIn(first_id, second.stderr)
        self.assert_success(status)
        self.assertLess(status.stdout.index(second_id), status.stdout.index(first_id))
        self.assertIn(f"{second_id}: active", status.stdout)
        self.assertIn(f"{first_id}: archived", status.stdout)

    def test_archive_failure_rolls_back_the_new_deployment(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "plugins" / "Example.dll"
        existing.parent.mkdir()
        existing.write_bytes(b"pre-test-plugin")
        self.write_project_preferences(profile)
        failure = module.CliError(40, "deployment", "archive state failed")
        session = self.create_session(module)
        with mock.patch.object(session, "archive_previous", side_effect=failure):
            result = self.run_module_cli(
                module,
                "run",
                "--artifact",
                str(artifact),
                session=session,
            )

        self.assertEqual(result.returncode, 40)
        self.assertIn("rolled back safely", result.stderr)
        self.assertEqual(existing.read_bytes(), b"pre-test-plugin")
        self.assertFalse(profile.joinpath("Modding", "data").exists())

    def test_clean_restores_overwritten_files_and_keeps_new_files(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "plugins" / "Example.dll"
        existing.parent.mkdir()
        existing.write_bytes(b"pre-test-plugin")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)
        session = self.create_session(module)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        result = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            session=session,
        )
        repeated = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Clean state: cleaned", result.stdout)
        self.assert_success(repeated)
        self.assertIn("Clean state: already-cleaned", repeated.stdout)
        self.assertIn(
            "restored plugins/Example.dll: restored previous file",
            repeated.stdout,
        )
        self.assertEqual(existing.read_bytes(), b"pre-test-plugin")
        self.assertEqual(
            (profile / "Modding" / "data" / "settings.json").read_text(
                encoding="utf-8"
            ),
            "{}\n",
        )
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["cleanup_state"], "cleaned")

    def test_clean_reports_package_relative_file_outcomes_and_post_clean_status(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "plugins" / "Example.dll"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"pre-test-plugin")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)
        session = self.create_session(module)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)

        result = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            session=session,
        )

        self.assert_success(result)
        self.assertIn("Cleanup files:", result.stdout)
        self.assertIn(
            "restored plugins/Example.dll: restored previous file",
            result.stdout,
        )
        self.assertIn(
            "retained data/settings.json: retained new file by default",
            result.stdout,
        )
        self.assertNotIn(str(profile), result.stdout)

        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(
            payload["cleanup_outcomes"],
            [
                {
                    "action": "retained",
                    "reason": "retained new file by default",
                    "relative_path": "data/settings.json",
                },
                {
                    "action": "restored",
                    "reason": "restored previous file",
                    "relative_path": "plugins/Example.dll",
                },
            ],
        )

        status = self.run_module_cli(module, "status", session=session)

        self.assert_success(status)
        self.assertIn("deployment=deployed (history)", status.stdout)
        self.assertIn("cleanup=cleaned (complete)", status.stdout)
        self.assertIn("process=not-launched (observation)", status.stdout)

    def test_clean_reports_each_protected_file_with_package_relative_reason(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "plugins" / "Example.dll"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"pre-test-plugin")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)
        session = self.create_session(module)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        existing.write_bytes(b"user-change-during-test")
        new_file = profile / "Modding" / "data" / "settings.json"
        new_file.write_text("user-settings\n", encoding="utf-8")

        result = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            "--remove-new-files",
            session=session,
        )

        self.assertEqual(result.returncode, module.EXIT_CLEAN)
        self.assertIn(
            "protected plugins/Example.dll: overwritten deployment target changed during testing",
            result.stderr,
        )
        self.assertIn(
            "protected data/settings.json: new deployment target changed during testing",
            result.stderr,
        )
        self.assertNotIn(str(profile), result.stderr)
        self.assertEqual(existing.read_bytes(), b"user-change-during-test")
        self.assertEqual(new_file.read_text(encoding="utf-8"), "user-settings\n")
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["cleanup_state"], "pending")
        self.assertEqual(
            [outcome["action"] for outcome in payload["cleanup_outcomes"]],
            ["protected", "protected"],
        )

    def test_clean_marks_an_already_exited_process_before_cleanup(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        session.process_adapter.is_alive.return_value = False

        result = session.clean(deployment.session_id)

        self.assertEqual(result.state, "cleaned")
        session.process_adapter.terminate_tree.assert_not_called()
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["process"]["state"], "exited")

    def test_clean_uses_injected_file_adapter_for_restore_and_remove(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "plugins" / "Example.dll"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"pre-test-plugin")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)
        file_adapter = mock.Mock(spec=module.FileAdapter)
        adapter_events = set()

        def copy_with_event(source, destination):
            adapter_events.add("copy")
            shutil.copy2(source, destination)

        def remove_with_event(destination):
            adapter_events.add("remove")
            destination.unlink()

        file_adapter.copy.side_effect = copy_with_event
        file_adapter.remove.side_effect = remove_with_event
        session = self.create_session(module)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        session.file_adapter = file_adapter

        result = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            "--remove-new-files",
            session=session,
        )

        self.assert_success(result)
        self.assertEqual(adapter_events, {"copy", "remove"})
        self.assertEqual(existing.read_bytes(), b"pre-test-plugin")
        self.assertFalse((profile / "Modding" / "data" / "settings.json").exists())

    def test_clean_protects_an_overwritten_file_changed_during_testing(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "plugins" / "Example.dll"
        existing.parent.mkdir()
        existing.write_bytes(b"pre-test-plugin")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)
        session = self.create_session(module)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        existing.write_bytes(b"user-change-during-test")
        result = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            session=session,
        )

        self.assertEqual(result.returncode, 70)
        self.assertIn("changed", result.stderr.casefold())
        self.assertIn("protected", result.stderr.casefold())
        self.assertEqual(existing.read_bytes(), b"user-change-during-test")
        payload = json.loads(deployment.state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("cleanup_state", "pending"), "pending")

    def test_clean_removes_new_files_only_after_explicit_approval(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)
        session = self.create_session(module)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        default_clean = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            session=session,
        )
        self.assert_success(default_clean)
        self.assertTrue(profile.joinpath("Modding", "data", "settings.json").is_file())
        approved_clean = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            "--remove-new-files",
            session=session,
        )

        self.assert_success(approved_clean)
        self.assertIn("Removed new files", approved_clean.stdout)
        self.assertIn(
            "removed data/settings.json: removed new file with explicit approval",
            approved_clean.stdout,
        )
        self.assertFalse(profile.joinpath("Modding", "data", "settings.json").exists())

    def test_clean_protects_a_new_file_changed_during_testing_when_removal_is_approved(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)
        session = self.create_session(module)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            deployment = session.deploy(plan, profile_preflight)
        new_file = profile / "Modding" / "data" / "settings.json"
        new_file.write_text("user-settings\n", encoding="utf-8")
        result = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            "--remove-new-files",
            session=session,
        )

        self.assertEqual(result.returncode, 70)
        self.assertIn("protected", result.stderr.casefold())
        self.assertEqual(new_file.read_text(encoding="utf-8"), "user-settings\n")

    def test_clean_rejects_an_older_session_until_the_newer_session_is_cleaned(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "plugins" / "Example.dll"
        existing.parent.mkdir()
        existing.write_bytes(b"pre-test-plugin")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)
        session = self.create_session(module)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            first = session.deploy(plan, profile_preflight)
        (artifact / "plugins" / "Example.dll").write_bytes(b"second-build")
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            second = session.deploy(plan, profile_preflight)

        blocked = self.run_module_cli(
            module,
            "clean",
            first.session_id,
            session=session,
        )
        newest = self.run_module_cli(
            module,
            "clean",
            second.session_id,
            session=session,
        )
        older = self.run_module_cli(
            module,
            "clean",
            first.session_id,
            session=session,
        )

        self.assertEqual(blocked.returncode, 70)
        self.assertIn("newer", blocked.stderr.casefold())
        self.assert_success(newest)
        self.assert_success(older)
        self.assertEqual(existing.read_bytes(), b"pre-test-plugin")

    def test_clean_refuses_while_the_tracked_game_process_is_running(self):
        module, session, deployment, profile_preflight, process, identity = self.create_launched_session()
        session.process_adapter.is_alive.return_value = True
        result = self.run_module_cli(
            module,
            "clean",
            deployment.session_id,
            session=session,
        )

        self.assertEqual(result.returncode, 70)
        self.assertIn("still running", result.stderr.casefold())

    def test_deployment_rejects_hard_linked_destination_without_mutation(self):
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        external_file = self.root / "outside-mod-destination.dll"
        external_file.write_bytes(b"external-content")
        destination = profile / "Modding" / "plugins" / "Example.dll"
        destination.parent.mkdir()
        try:
            os.link(external_file, destination)
        except OSError as error:
            self.skipTest(f"hard links unavailable: {error}")
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--artifact",
            str(artifact),
        )

        self.assertEqual(result.returncode, 40)
        self.assertIn("multiple hard links", result.stderr)
        self.assertEqual(external_file.read_bytes(), b"external-content")
        self.assertEqual(destination.read_bytes(), b"external-content")

    def test_deployment_failure_rolls_back_partial_copy(self):
        module = self.load_cli_module()
        profile = self.create_profile()
        project = self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "data" / "settings.json"
        existing.parent.mkdir()
        existing.write_bytes(b"pre-test-settings")
        self.write_project_preferences(profile)
        environment = {
            "Windows": "Windows",
            "Linux": "Linux",
            "Darwin": "macOS",
        }[platform.system()]
        profile_preflight = module.preflight_profile(profile, environment)

        real_copy2 = shutil.copy2
        copy_calls = 0

        def fail_on_third_copy(source, destination, *arguments, **keywords):
            nonlocal copy_calls
            copy_calls += 1
            if copy_calls == 3:
                raise OSError("injected copy failure")
            return real_copy2(source, destination, *arguments, **keywords)

        file_adapter = mock.Mock(spec=module.FileAdapter)
        file_adapter.copy.side_effect = fail_on_third_copy
        session = self.create_session(module, file_adapter=file_adapter)
        with session.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            with self.assertRaises(module.CliError) as failure:
                session.deploy(plan, profile_preflight)

        self.assertEqual(failure.exception.code, 40)
        self.assertIn("rollback succeeded", str(failure.exception))
        self.assertEqual(existing.read_bytes(), b"pre-test-settings")
        self.assertFalse((profile / "Modding" / "plugins").exists())
        manifests = sorted((self.temp_root / "sessions").glob("*/manifest.json"))
        self.assertEqual(len(manifests), 1)
        payload = json.loads(manifests[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "rolled_back")

    def test_deployment_preflight_rejects_file_parent_without_mutation(self):
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        conflicting_parent = profile / "Modding" / "plugins"
        conflicting_parent.write_bytes(b"not-a-directory")
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--artifact",
            str(artifact),
        )

        self.assertEqual(result.returncode, 40)
        self.assertIn("rollback not required", result.stderr)
        self.assertEqual(conflicting_parent.read_bytes(), b"not-a-directory")
        self.assertFalse((profile / "Modding" / "data").exists())

    def test_explicit_zip_artifact_is_extracted_and_validated(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        archive = self.root / "known-artifact.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("plugins/Example.dll", b"plugin")
            package.writestr("data/settings.json", b"{}")

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(archive),
        )

        self.assert_success(result)
        self.assertIn(f"Artifact: {archive}", result.stdout)
        self.assertIn("Planned files: 2", result.stdout)

    def test_zip_parent_traversal_is_rejected_before_profile_mutation(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("../escape.txt", b"bad")

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(archive),
        )

        self.assertEqual(result.returncode, 30)
        self.assertIn("unsafe", result.stderr.lower())
        self.assertFalse((self.root / "escape.txt").exists())

    def test_zip_absolute_path_is_rejected_before_profile_mutation(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        archive = self.root / "absolute.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("/escape.txt", b"bad")

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(archive),
        )

        self.assertEqual(result.returncode, 30)
        self.assertIn("unsafe", result.stderr.lower())

    def test_zip_case_collision_is_rejected_as_ambiguous(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        archive = self.root / "case-collision.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("plugins/Example.dll", b"first")
            package.writestr("plugins/example.dll", b"second")

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(archive),
        )

        self.assertEqual(result.returncode, 30)
        self.assertIn("ambiguous", result.stderr.lower())

    def test_explicit_directory_symlink_is_rejected(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        package_root = self.create_package(root=self.root, target_name="real-artifact")
        symlink = self.root / "linked-artifact"
        try:
            symlink.symlink_to(package_root, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"directory symlinks unavailable: {error}")

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(symlink),
        )

        self.assertEqual(result.returncode, 30)
        self.assertIn("symlink", result.stderr.lower())

    def test_zip_symlink_entries_are_rejected(self):
        profile = self.create_profile()
        self.create_project()
        self.write_project_preferences(profile)
        archive = self.root / "symlink.zip"
        symlink = zipfile.ZipInfo("plugins/link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr(symlink, "../../outside")

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(archive),
        )

        self.assertEqual(result.returncode, 30)
        self.assertIn("link", result.stderr.lower())

    def test_explicit_missing_artifact_does_not_fallback_to_publish(self):
        profile = self.create_profile()
        self.create_project()
        self.create_package()
        self.write_project_preferences(profile)
        missing = self.root / "missing.zip"

        result = self.run_cli(
            "run",
            "--dry-run",
            "--artifact",
            str(missing),
        )

        self.assertEqual(result.returncode, 30)
        self.assertIn("artifact", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
