import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "ci" / "compress-docs" / "compress_docs.py"
PYTHON = Path(sys.executable)
TARGET = REPO_ROOT / "skills" / "blasphemous-modding-helper" / "SKILL.md"


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
    if os.environ.get("FAKE_CODEX_MODE") == "malformed":
        sys.stdout.write("Here is the compressed document:\n```markdown\n# Wrong\n```\n")
    else:
        marker = re.search(br'<document-body bytes="(\d+)">\n', prompt_bytes)
        start = marker.end()
        length = int(marker.group(1))
        sys.stdout.buffer.write(prompt_bytes[start : start + length])
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
        return subprocess.run(
            [
                str(PYTHON),
                str(SCRIPT),
                "preview",
                "--file",
                selection,
                "--codex-executable",
                str(self.fake),
                "--timeout-seconds",
                "5",
                *args,
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

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

        import shutil

        shutil.rmtree(summary.parent)

    def test_authentication_failure_stops_before_exec(self):
        result = self.run_cli(FAKE_CODEX_AUTH="fail")

        self.assertNotEqual(result.returncode, 0)
        summary = self.summary_path(result.stdout)
        manifest = json.loads((summary.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "preflight_failed")
        self.assertEqual(len(self.read_events()), 1)

        import shutil

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

        import shutil

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
            self.assertEqual(len(self.read_events()), 1)

            import shutil

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


if __name__ == "__main__":
    unittest.main()
