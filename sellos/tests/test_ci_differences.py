"""SOS-SETUP-33: CI calls the gate's own scripts, and every remaining difference is written down.

The real scripts/lib/backend_suite.sh runs here with a stub bench, and the workflows are read to
check that no step keeps its own copy of a command the gate's scripts hold.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
LINT = (REPO_ROOT / ".github/workflows/linter.yml").read_text(encoding="utf-8")
DOC = REPO_ROOT / "docs" / "CI_DIFFERENCES.md"


def run_lines(text):
	"""The shell lines of a workflow, comments left out."""
	return re.sub(r"(?m)^\s*#.*$", "", text)


class TestCiCallsTheGateScripts(unittest.TestCase):
	def test_no_workflow_keeps_its_own_copy_of_a_gate_command(self):
		for text in (CI, LINT):
			body = run_lines(text)
			self.assertNotIn("npm ci", body)
			self.assertNotIn("prepare_clean_site", body)
			self.assertNotIn("semgrep ci", body)
			self.assertNotIn("pre-commit/action", body)
			self.assertNotRegex(body, r"bench --site \S+ run-tests")

	def test_each_shared_script_is_called(self):
		self.assertEqual(CI.count("scripts/build-web-app.sh"), 3)
		self.assertEqual(CI.count("scripts/lib/prepare_test_site.sh"), 2)
		self.assertIn("scripts/lib/backend_suite.sh", CI)
		self.assertIn("scripts/lib/ui_flaky.sh", CI)
		self.assertIn("bash scripts/check-guards.sh --all", LINT)
		gate = (REPO_ROOT / "scripts/run-tests.sh").read_text(encoding="utf-8")
		for script in (
			"scripts/build-web-app.sh",
			"scripts/lib/prepare_test_site.sh",
			"scripts/check-guards.sh",
		):
			self.assertIn(script, gate)

	def test_semgrep_is_pinned_in_one_place(self):
		pins = (REPO_ROOT / "scripts/lib/semgrep.env").read_text(encoding="utf-8")
		self.assertRegex(pins, r"(?m)^SEMGREP_VERSION=\d+\.\d+\.\d+$")
		self.assertRegex(pins, r"(?m)^SEMGREP_RULES_SHA=[0-9a-f]{40}$")
		self.assertIn("source scripts/lib/semgrep.env", LINT)
		self.assertIn('"semgrep==$SEMGREP_VERSION"', LINT)
		self.assertIn('"$SEMGREP_RULES_SHA"', LINT)
		make = (REPO_ROOT / "scripts/make-baseline.sh").read_text(encoding="utf-8")
		self.assertIn('"semgrep==$SEMGREP_VERSION"', make)

	def test_the_differences_doc_and_the_rehearsal_exist(self):
		doc = DOC.read_text(encoding="utf-8")
		self.assertIn("## What still differs, and why", doc)
		self.assertGreaterEqual(len(re.findall(r"(?m)^\| \d+ \|", doc)), 10)
		rehearsal = REPO_ROOT / "scripts" / "ci-rehearsal.sh"
		self.assertTrue(rehearsal.stat().st_mode & 0o111)
		self.assertIn("git clone", rehearsal.read_text(encoding="utf-8"))


class TestBackendSuite(unittest.TestCase):
	def run_suite(self, bench_body):
		with tempfile.TemporaryDirectory() as folder:
			bin_dir = Path(folder, "bin")
			bin_dir.mkdir()
			bench = bin_dir / "bench"
			bench.write_text(f"#!/usr/bin/env bash\n{bench_body}\n", encoding="utf-8")
			bench.chmod(0o755)
			result = subprocess.run(
				["bash", str(REPO_ROOT / "scripts/lib/backend_suite.sh"), f"{folder}/logs/backend.log"],
				capture_output=True,
				text=True,
				env={
					"PATH": f"{bin_dir}:/usr/bin:/bin:/opt/homebrew/bin",
					"SITE": "test_site",
					"APP": "sellos",
				},
				timeout=60,
			)
		return result.returncode, result.stdout + result.stderr

	def test_a_passing_suite_passes_with_its_batches_reported(self):
		code, out = self.run_suite(
			'echo "Running 3 unit tests for sellos"; echo "Ran 3 tests in 0.1s"; echo OK'
		)
		self.assertEqual(code, 0, out)
		self.assertIn("Exit code of the test command: 0", out)

	def test_a_failing_batch_fails_whatever_the_last_line_says(self):
		code, out = self.run_suite(
			'echo "Running 2 unit tests for sellos"; echo "Ran 2 tests"; echo "FAILED (failures=1)"; '
			'echo "Running 5 integration tests for sellos"; echo "Ran 5 tests"; echo OK; exit 1'
		)
		self.assertEqual(code, 1, out)
		self.assertIn("FAILED (failures=1)", out)
