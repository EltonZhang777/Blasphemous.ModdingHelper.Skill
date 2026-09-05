import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "ci" / "compress-docs" / "compress_docs.py"
PYTHON = Path(sys.executable)
TARGET = REPO_ROOT / "skills" / "blasphemous-modding-helper" / "SKILL.md"
sys.path.insert(0, str(SCRIPT.parent))
import compress_docs


FAKE_CODEX = r'''
import json
import os
import re
import sys
from pathlib import Path

log_path = Path(os.environ["FAKE_CODEX_LOG"])
events = []
if log_path.exists():
    events = json.loads(log_path.read_text(encoding="utf-8"))
events.append({"argv": sys.argv[1:], "cwd": os.getcwd()})
log_path.write_text(json.dumps(events), encoding="utf-8")

if sys.argv[1:3] == ["login", "status"]:
    if os.environ.get("FAKE_CODEX_AUTH") == "fail":
        print("Not logged in", file=sys.stderr)
        raise SystemExit(3)
    print("Logged in")
    raise SystemExit(0)

if sys.argv[1:2] == ["exec"]:
    prompt_bytes = sys.stdin.buffer.read()
    events[-1]["prompt_has_frontmatter"] = b"name: blasphemous-modding-helper" in prompt_bytes
    log_path.write_text(json.dumps(events), encoding="utf-8")
    exec_count = sum(event["argv"][:1] == ["exec"] for event in events)
    if os.environ.get("FAKE_CODEX_MODE") == "fail-first" and exec_count == 1:
        print("synthetic first-document failure", file=sys.stderr)
        raise SystemExit(7)
    if os.environ.get("FAKE_CODEX_MODE") == "malformed":
        sys.stdout.write("Here is the compressed document:\n```markdown\n# Wrong\n```\n")
    else:
        marker = re.search(br'<(?:document|candidate)-body bytes="(\d+)">\n', prompt_bytes)
        start = marker.end()
        length = int(marker.group(1))
        body = prompt_bytes[start : start + length]
        if os.environ.get("FAKE_CODEX_MODE") == "compress":
            body = body.replace(b"Original prose.", b"Compressed prose.", 1)
        if os.environ.get("FAKE_CODEX_MODE") == "invalid":
            body = body.replace(b"# Blasphemous modding helper", b"# Wrong", 1)
        sys.stdout.buffer.write(body)
    raise SystemExit(0)

raise SystemExit(4)
'''


class PreviewCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.temp = Path(self.tempdir.name)
        self.fake = self.temp / "fake_codex.py"
        self.fake.write_text(FAKE_CODEX, encoding="utf-8")
        self.log = self.temp / "events.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, *args, selection="skills/blasphemous-modding-helper/SKILL.md", **env_overrides):
        env = os.environ.copy()
        env.update(
            {
                "FAKE_CODEX_LOG": str(self.log),
                "FAKE_CODEX_AUTH": env_overrides.pop("FAKE_CODEX_AUTH", "ok"),
                "FAKE_CODEX_MODE": env_overrides.pop("FAKE_CODEX_MODE", "body"),
            }
        )
        env.update(env_overrides)
        command = [str(PYTHON), str(SCRIPT), "preview"]
        if selection is not None:
            selections = selection if isinstance(selection, (list, tuple)) else [selection]
            for item in selections:
                command.extend(["--file", item])
        command.extend(
            [
                "--codex-executable",
                str(self.fake),
                "--timeout-seconds",
                "5",
                *args,
            ]
        )
        return subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def run_apply(self, run_id, *args):
        return subprocess.run(
            [str(PYTHON), str(SCRIPT), "apply", "--run", run_id, *args],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def preview_test_documents(self, names):
        paths = []
        selections = []
        for name in names:
            path = REPO_ROOT / "skills" / name
            path.write_bytes(b"# Apply test\r\n\r\nOriginal prose.\r\n")
            paths.append(path)
            selections.append(str(path.relative_to(REPO_ROOT)).replace("\\", "/"))
        result = self.run_cli(selection=selections, FAKE_CODEX_MODE="compress")
        summary = self.summary_path(result.stdout)
        manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
        return paths, selections, result, summary, manifest

    def read_events(self):
        return json.loads(self.log.read_text(encoding="utf-8"))

    @staticmethod
    def summary_path(output):
        match = re.search(r"^Summary: (.+)$", output, re.MULTILINE)
        if not match:
            raise AssertionError(output)
        return Path(match.group(1).strip())

    def test_preview_creates_candidate_without_mutating_live_document(self):
        original = TARGET.read_bytes()

        result = self.run_cli()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(TARGET.read_bytes(), original)
        summary = self.summary_path(result.stdout)
        self.assertTrue(summary.is_file())
        self.assertTrue(str(summary).startswith(str(REPO_ROOT / "ci" / "compress-docs" / ".runs")))

        manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "accepted")
        self.assertEqual(manifest["documents"][0]["path"], "skills/blasphemous-modding-helper/SKILL.md")
        self.assertEqual(
            manifest["documents"][0]["source_sha256"],
            hashlib.sha256(original).hexdigest(),
        )
        candidate = summary.parent / "candidate.md"
        self.assertEqual(candidate.read_bytes(), original)

        events = self.read_events()
        self.assertEqual([event["argv"][:2] for event in events], [["login", "status"], ["exec", "--ephemeral"]])
        self.assertNotEqual(events[1]["cwd"], str(REPO_ROOT))
        self.assertIn("--sandbox", events[1]["argv"])
        self.assertIn("read-only", events[1]["argv"])
        self.assertIn("--ask-for-approval", events[1]["argv"])
        self.assertIn("never", events[1]["argv"])
        self.assertIn("--cd", events[1]["argv"])
        self.assertFalse(events[1]["prompt_has_frontmatter"])

        shutil.rmtree(summary.parent)

    def test_authentication_failure_stops_before_exec(self):
        result = self.run_cli(FAKE_CODEX_AUTH="fail")

        self.assertNotEqual(result.returncode, 0)
        summary = self.summary_path(result.stdout)
        manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "preflight_failed")
        self.assertEqual(manifest["documents"][0]["status"], "failed")
        self.assertEqual(len(self.read_events()), 1)

        shutil.rmtree(summary.parent)

    def test_malformed_output_is_rejected_and_live_document_stays_unchanged(self):
        original = TARGET.read_bytes()

        result = self.run_cli(FAKE_CODEX_MODE="malformed")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(TARGET.read_bytes(), original)
        summary = self.summary_path(result.stdout)
        manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "rejected")
        self.assertFalse((summary.parent / "candidate.md").exists())
        self.assertEqual(sum(event["argv"][:1] == ["exec"] for event in self.read_events()), 1)

        shutil.rmtree(summary.parent)

    def test_validation_failure_is_rejected_without_repair(self):
        original = TARGET.read_bytes()

        result = self.run_cli(FAKE_CODEX_MODE="invalid")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(TARGET.read_bytes(), original)
        summary = self.summary_path(result.stdout)
        manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
        document = manifest["documents"][0]
        self.assertEqual(manifest["status"], "rejected")
        self.assertEqual(document["status"], "rejected")
        self.assertEqual(document["validation"]["errors"], ["heading changed (source=11, candidate=11)"])
        self.assertFalse((summary.parent / "candidate.md").exists())
        events = self.read_events()
        self.assertEqual(sum(event["argv"][:1] == ["exec"] for event in events), 1)

        shutil.rmtree(summary.parent)

    def test_preview_without_file_scans_future_skill_and_excludes_non_live_files(self):
        future_dir = REPO_ROOT / "skills" / "compress_docs_future_test"
        future_file = future_dir / "SKILL.md"
        hidden_file = REPO_ROOT / "skills" / "blasphemous-modding-helper" / ".hidden-compress-test.md"
        backup_file = REPO_ROOT / "skills" / "blasphemous-modding-helper" / "SKILL.original.md"
        future_dir.mkdir()
        future_file.write_text("# Future skill\n\nFuture prose.\n", encoding="utf-8")
        hidden_file.write_text("# Hidden\n", encoding="utf-8")
        backup_file.write_text("# Backup\n", encoding="utf-8")
        try:
            expected = sorted(
                str(path.relative_to(REPO_ROOT)).replace("\\", "/")
                for path in REPO_ROOT.joinpath("skills").rglob("*.md")
                if path not in (hidden_file, backup_file)
            )
            result = self.run_cli(selection=None)

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = self.summary_path(result.stdout)
            manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
            paths = [document["path"] for document in manifest["documents"]]
            self.assertEqual(paths, expected)
            self.assertIn("skills/compress_docs_future_test/SKILL.md", paths)
            self.assertNotIn("skills/blasphemous-modding-helper/.hidden-compress-test.md", paths)
            self.assertNotIn("skills/blasphemous-modding-helper/SKILL.original.md", paths)
            self.assertEqual([document["status"] for document in manifest["documents"]], ["accepted"] * len(paths))
            self.assertEqual(sum(event["argv"][:1] == ["exec"] for event in self.read_events()), len(paths))
            self.assertTrue(manifest["git"]["dirty"])
            self.assertTrue(manifest["skipped"])
            self.assertTrue(all((summary.parent / document["candidate"]).is_file() for document in manifest["documents"]))
            shutil.rmtree(summary.parent)
        finally:
            shutil.rmtree(future_dir, ignore_errors=True)
            hidden_file.unlink(missing_ok=True)
            backup_file.unlink(missing_ok=True)

    def test_batch_continues_after_document_process_failure(self):
        selections = [
            "skills/blasphemous-modding-helper/SKILL.md",
            "skills/blasphemous-modding-helper/references/requirement-levels-definitions.md",
        ]

        result = self.run_cli(selection=selections, FAKE_CODEX_MODE="fail-first")

        self.assertNotEqual(result.returncode, 0)
        summary = self.summary_path(result.stdout)
        manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual([document["status"] for document in manifest["documents"]], ["failed", "accepted"])
        self.assertEqual(sum(event["argv"][:1] == ["exec"] for event in self.read_events()), 2)
        self.assertFalse((summary.parent / manifest["documents"][0].get("candidate", "missing")).exists())
        self.assertTrue((summary.parent / manifest["documents"][1]["candidate"]).is_file())

        shutil.rmtree(summary.parent)

    def test_interruption_retains_inspectable_run_without_resuming(self):
        output = io.StringIO()
        environment = {
            "FAKE_CODEX_LOG": str(self.log),
            "FAKE_CODEX_AUTH": "ok",
            "FAKE_CODEX_MODE": "body",
        }
        with mock.patch.dict(os.environ, environment, clear=False):
            with mock.patch.object(compress_docs, "_process_document", side_effect=KeyboardInterrupt):
                with contextlib.redirect_stdout(output):
                    result = compress_docs.preview(
                        REPO_ROOT,
                        ["skills/blasphemous-modding-helper/SKILL.md"],
                        str(self.fake),
                        5,
                    )

        self.assertEqual(result, 130)
        summary = self.summary_path(output.getvalue())
        manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "interrupted")
        self.assertEqual(manifest["documents"][0]["status"], "interrupted")
        self.assertIn("run artifacts were retained", (summary.parent / "diagnostics.log").read_text(encoding="utf-8"))
        self.assertFalse((summary.parent.parent / ".lock").exists())

        shutil.rmtree(summary.parent)

    def test_authentication_failure_precedes_document_decode(self):
        invalid = REPO_ROOT / "skills" / "blasphemous-modding-helper" / "compress_docs_invalid_utf8.md"
        invalid.write_bytes(b"\xff")
        try:
            result = self.run_cli(selection="skills/blasphemous-modding-helper/compress_docs_invalid_utf8.md", FAKE_CODEX_AUTH="fail")

            self.assertNotEqual(result.returncode, 0)
            summary = self.summary_path(result.stdout)
            manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "preflight_failed")
            self.assertEqual(manifest["documents"][0]["status"], "failed")
            self.assertEqual(len(self.read_events()), 1)

            shutil.rmtree(summary.parent)
        finally:
            invalid.unlink(missing_ok=True)

    def test_lock_contention_stops_before_codex(self):
        runs = REPO_ROOT / "ci" / "compress-docs" / ".runs"
        runs.mkdir(parents=True, exist_ok=True)
        lock = runs / ".lock"
        lock.write_text("pid=other\n", encoding="ascii")
        try:
            result = self.run_cli()

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("another compression run is active", result.stderr)
            self.assertFalse(self.log.exists())
        finally:
            lock.unlink(missing_ok=True)

    def test_file_outside_skills_is_rejected_before_codex(self):
        result = subprocess.run(
            [
                str(PYTHON),
                str(SCRIPT),
                "preview",
                "--file",
                "README.md",
                "--codex-executable",
                str(self.fake),
            ],
            cwd=str(REPO_ROOT),
            env={**os.environ, "FAKE_CODEX_LOG": str(self.log)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_apply_requires_explicit_file_or_all_scope(self):
        paths, selections, result, summary, manifest = self.preview_test_documents(["compress_docs_apply_scope_test.md"])
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            apply_result = self.run_apply(manifest["run_id"])
            self.assertNotEqual(apply_result.returncode, 0)
            self.assertEqual(paths[0].read_bytes(), b"# Apply test\r\n\r\nOriginal prose.\r\n")
        finally:
            shutil.rmtree(summary.parent, ignore_errors=True)
            for path in paths:
                path.unlink(missing_ok=True)

    def test_apply_verifies_backup_readback_atomic_write_and_permission(self):
        paths, selections, result, summary, manifest = self.preview_test_documents(["compress_docs_apply_success_test.md"])
        path = paths[0]
        original = path.read_bytes()
        mode = stat.S_IMODE(path.stat().st_mode)
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            apply_result = self.run_apply(manifest["run_id"], "--file", selections[0])
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            updated_manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
            document = updated_manifest["documents"][0]
            candidate = (summary.parent / document["candidate"]).read_bytes()
            backup = summary.parent / document["apply"]["backup"]
            self.assertEqual(document["apply"]["status"], "applied")
            self.assertEqual(path.read_bytes(), candidate)
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
            self.assertIn("## Apply", (summary.parent / "summary.md").read_text(encoding="utf-8"))
            self.assertIn("Status: applied", apply_result.stdout)
            self.assertIn("Summary: ", apply_result.stdout)
        finally:
            shutil.rmtree(summary.parent, ignore_errors=True)
            path.unlink(missing_ok=True)

    def test_apply_rejects_stale_source_before_any_write(self):
        paths, selections, result, summary, manifest = self.preview_test_documents(["compress_docs_apply_stale_test.md"])
        path = paths[0]
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            path.write_bytes(b"# Apply test\r\n\r\nChanged after preview.\r\n")
            apply_result = self.run_apply(manifest["run_id"], "--file", selections[0])
            self.assertNotEqual(apply_result.returncode, 0)
            updated_manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
            document = updated_manifest["documents"][0]
            self.assertEqual(updated_manifest["apply"]["status"], "preflight_failed")
            self.assertEqual(document["apply"]["status"], "rejected")
            self.assertFalse((summary.parent / document["apply"].get("backup", "missing")).exists())
            self.assertEqual(path.read_bytes(), b"# Apply test\r\n\r\nChanged after preview.\r\n")
        finally:
            shutil.rmtree(summary.parent, ignore_errors=True)
            path.unlink(missing_ok=True)

    def test_apply_stops_after_write_failure_and_reports_applied_files(self):
        names = [
            "compress_docs_apply_stop_one_test.md",
            "compress_docs_apply_stop_two_test.md",
            "compress_docs_apply_stop_three_test.md",
        ]
        paths, selections, result, summary, manifest = self.preview_test_documents(names)
        originals = [path.read_bytes() for path in paths]
        replace_count = 0
        real_atomic_replace = compress_docs._atomic_replace

        def fail_on_second_replace(path, data, mode):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("synthetic write failure")
            return real_atomic_replace(path, data, mode)

        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            with mock.patch.object(compress_docs, "_atomic_replace", side_effect=fail_on_second_replace):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    apply_result = compress_docs.apply(REPO_ROOT, manifest["run_id"], selections, False)
            self.assertNotEqual(apply_result, 0)
            updated_manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
            statuses = [document["apply"]["status"] for document in updated_manifest["documents"]]
            self.assertEqual(statuses, ["applied", "failed", "skipped"])
            self.assertNotEqual(paths[0].read_bytes(), originals[0])
            self.assertEqual(paths[1].read_bytes(), originals[1])
            self.assertEqual(paths[2].read_bytes(), originals[2])
            self.assertTrue((summary.parent / updated_manifest["documents"][0]["apply"]["backup"]).is_file())
            self.assertFalse((summary.parent / updated_manifest["documents"][2]["apply"].get("backup", "missing")).exists())
            self.assertIn("completed_with_failures", (summary.parent / "summary.md").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(summary.parent, ignore_errors=True)
            for path in paths:
                path.unlink(missing_ok=True)

    def test_apply_rejects_tampered_candidate_before_write(self):
        paths, selections, result, summary, manifest = self.preview_test_documents(["compress_docs_apply_tamper_test.md"])
        path = paths[0]
        original = path.read_bytes()
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            candidate = summary.parent / manifest["documents"][0]["candidate"]
            candidate.write_bytes(candidate.read_bytes().replace(b"Compressed prose.", b"Tampered prose.", 1))
            apply_result = self.run_apply(manifest["run_id"], "--all")
            self.assertNotEqual(apply_result.returncode, 0)
            updated_manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(updated_manifest["apply"]["status"], "preflight_failed")
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse((summary.parent / updated_manifest["documents"][0]["apply"].get("backup", "missing")).exists())
        finally:
            shutil.rmtree(summary.parent, ignore_errors=True)
            path.unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
