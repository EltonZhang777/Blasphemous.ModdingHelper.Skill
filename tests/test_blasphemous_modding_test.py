import hashlib
import importlib.util
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
from pathlib import Path
from unittest import mock


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
            check=False,
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

    def create_project(self, name="Example.csproj", target_name="ExampleMod"):
        project = self.root / name
        project.write_text(
            "<Project><PropertyGroup>"
            f"<TargetName>{target_name}</TargetName>"
            "</PropertyGroup></Project>\n",
            encoding="utf-8",
        )
        return project

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
        sessions = self.temp_root / "blasphemous-modding-test" / "sessions"
        return sorted(sessions.glob("*/manifest.json"))

    def load_cli_module(self):
        module_name = f"blasphemous_modding_test_{id(self)}"
        spec = importlib.util.spec_from_file_location(module_name, SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def write_project_preferences(self, profile):
        preferences = self.root / ".skills" / "blasphemous-modding-helper" / "preferences.md"
        preferences.parent.mkdir(parents=True)
        preferences.write_text(
            f"modding_profile_path: {profile}\n",
            encoding="utf-8",
        )
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
        self.assertIn("status", result.stdout)
        self.assertIn("--dry-run", result.stdout)

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
            "Test session listing: added by later workflow tickets",
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
        profile = self.create_profile()
        self.create_buildable_project()
        self.write_project_preferences(profile)

        result = self.run_cli("run")

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
    def test_build_uses_nearest_solution_root_for_publish(self):
        profile = self.create_profile()
        solution_root = self.root / "solution"
        project = self.create_buildable_project(
            project_directory=solution_root / "mod"
        )
        (solution_root / "BlasphemousMods.sln").write_text(
            "Microsoft Visual Studio Solution File, Format Version 12.00\n",
            encoding="utf-8",
        )
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--dry-run",
            "--project",
            str(project),
        )

        self.assert_success(result)
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
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        (artifact / "localization").mkdir()
        (artifact / "localization" / "strings.txt").write_text(
            "test-localization\n",
            encoding="utf-8",
        )
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--artifact",
            str(artifact),
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
        self.assertIn("Deployed files: 3", result.stdout)

    def test_deployment_records_backups_and_hashes_without_logs(self):
        profile = self.create_profile()
        self.create_project()
        artifact = self.create_package(root=self.root, target_name="known-artifact")
        existing = profile / "Modding" / "plugins" / "Example.dll"
        existing.parent.mkdir()
        existing.write_bytes(b"pre-test-plugin")
        self.write_project_preferences(profile)

        result = self.run_cli(
            "run",
            "--artifact",
            str(artifact),
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

        real_copy2 = module.shutil.copy2
        copy_calls = 0

        def fail_on_third_copy(source, destination, *arguments, **keywords):
            nonlocal copy_calls
            copy_calls += 1
            if copy_calls == 3:
                raise OSError("injected copy failure")
            return real_copy2(source, destination, *arguments, **keywords)

        with module.prepare_artifact(
            project,
            "Debug",
            explicit_artifact=str(artifact),
            cwd=self.root,
        ) as plan:
            with mock.patch.object(module, "_deployment_state_root", return_value=self.temp_root / "sessions"):
                with mock.patch.object(module.shutil, "copy2", side_effect=fail_on_third_copy):
                    with self.assertRaises(module.CliError) as failure:
                        module.deploy_artifact(plan, profile_preflight)

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
