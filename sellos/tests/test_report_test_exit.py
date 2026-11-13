"""SOS-SETUP-24: a passing summary line does not prove the test command passed; the exit code does.

CI run 42830839891 printed "Ran 238 tests ... OK (skipped=18)" and the step failed with exit code 1.
Frappe's run-tests had run two batches: 43 integration tests that ended FAILED (errors=3), then the
other 238, whose OK was printed last. scripts/lib/report_test_exit.sh runs a test command, prints
every batch's summary and the exit code, names the batch that failed, and exits with that code.
The gate and CI run the backend suite through it.
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "scripts" / "lib" / "report_test_exit.sh"

# What Frappe's runner printed in run 42830839891, colour codes and all, cut down.
TWO_BATCHES = """\
Running 43 integration tests for sellos
   \x1b[31m ✖ \x1b[0m test_01_probe_creates_and_drops_with_only_the_provisioner_account
----------------------------------------------------------------------
Ran 43 tests in 2.181s

FAILED (errors=3)
Running 238 unspecified-category tests for sellos
   \x1b[32m ✔ \x1b[0m test_children_follow_the_lead
----------------------------------------------------------------------
Ran 238 tests in 42.549s

OK (skipped=18)
"""


class ReportTestExit(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-exit-"))

	def tearDown(self):
		for p in self.dir.iterdir():
			p.unlink()
		self.dir.rmdir()

	def run_with(self, output, code):
		"""Run the wrapper around a fake runner that prints output and exits with code."""
		(self.dir / "out.txt").write_text(output, encoding="utf-8")
		runner = self.dir / "runner.sh"
		runner.write_text(f'#!/usr/bin/env bash\ncat "{self.dir}/out.txt"\nexit {code}\n', encoding="utf-8")
		runner.chmod(0o755)
		result = subprocess.run(
			["bash", str(WRAPPER), str(runner)], capture_output=True, text=True, timeout=30
		)
		return result.returncode, result.stdout + result.stderr

	def test_the_ci_run_names_the_failed_batch_and_keeps_its_exit_code(self):
		code, out = self.run_with(TWO_BATCHES, 1)
		self.assertEqual(code, 1)
		self.assertIn("=== Exit code of the test command: 1", out)
		self.assertIn("FAILED (errors=3)  <- Running 43 integration tests for sellos", out)
		self.assertIn("    OK (skipped=18)", out)
		self.assertNotIn("tests passed", out, "a batch failed, so the tests did not pass")
		# The runner's own output still passes through.
		self.assertIn("test_01_probe_creates_and_drops_with_only_the_provisioner_account", out)

	def test_every_batch_passing_and_a_nonzero_exit_says_so_and_fails(self):
		code, out = self.run_with("Running 2 integration tests for sellos\nRan 2 tests in 1s\n\nOK\n", 3)
		self.assertEqual(code, 3)
		self.assertIn("tests passed but the runner returned 3", out)

	def test_a_clean_run_passes_and_prints_its_exit_code(self):
		code, out = self.run_with(TWO_BATCHES.replace("FAILED (errors=3)", "OK"), 0)
		self.assertEqual(code, 0)
		self.assertIn("=== Exit code of the test command: 0", out)
		self.assertEqual(len(re.findall(r"^    Ran \d+ tests in", out, re.M)), 2)

	def test_a_run_that_ran_no_tests_fails_even_with_exit_0(self):
		code, out = self.run_with("Starting test run with parameters: tests=('NoSuchTest',)\n", 0)
		self.assertEqual(code, 1)
		self.assertIn("The runner returned 0 but ran no tests.", out)

	def test_a_crash_with_no_summary_keeps_its_exit_code(self):
		code, out = self.run_with("Traceback (most recent call last):\nImportError: boom\n", 4)
		self.assertEqual(code, 4)
		self.assertIn("The runner returned 4 and printed no test summary.", out)

	def test_no_command_is_a_usage_error(self):
		result = subprocess.run(["bash", str(WRAPPER)], capture_output=True, text=True, timeout=30)
		self.assertEqual(result.returncode, 2)
		self.assertIn("usage:", result.stderr)


class TheGateAndCiUseIt(unittest.TestCase):
	def test_ci_runs_the_backend_suite_through_the_wrapper(self):
		ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
		# SOS-SETUP-33: through the gate's run_backend (scripts/lib/backend_suite.sh), which runs the
		# wrapper with the site and app CI gives it.
		self.assertIn('bash "$GITHUB_WORKSPACE/scripts/lib/backend_suite.sh"', ci)
		suite = (REPO_ROOT / "scripts/lib/backend_suite.sh").read_text(encoding="utf-8")
		self.assertIn('export REPORT_TEST_EXIT="$LIB/report_test_exit.sh"', suite)
		self.assertEqual(len(re.findall(r"^\s*bench --site \S+ run-tests\b", ci, re.M)), 0)

	def test_the_gate_runs_every_backend_test_command_through_the_wrapper(self):
		"""Rewritten on purpose by SOS-SETUP-25: the gate's backend commands moved into run_backend
		(scripts/lib/db_conflict.sh), which reruns a module after a database conflict. Every one of
		them, the first run and the rerun, still goes through the wrapper."""
		gate = (REPO_ROOT / "scripts/run-tests.sh").read_text(encoding="utf-8")
		lib = (REPO_ROOT / "scripts/lib/db_conflict.sh").read_text(encoding="utf-8")
		self.assertIn('REPORT_TEST_EXIT="apps/$APP/scripts/lib/report_test_exit.sh"', gate)
		self.assertIn('source "$REPO_DIR/scripts/lib/db_conflict.sh"', gate)
		# The whole suite and each changed module run through run_backend.
		self.assertIn('run_backend "$LOG_DIR/backend-$STAMP-all.log" ||', gate)
		# SOS-SETUP-33: each changed module runs more than once, each run through run_backend.
		# SOS-SETUP-34: the changed modules are listed, then run through the repeat plan.
		self.assertIn('printf \'backend\\t%s\\t%s\\n\' "$mod" "$LOG_DIR/backend-$STAMP-$mod"', gate)
		flake = (REPO_ROOT / "scripts/lib/flake_check.sh").read_text(encoding="utf-8")
		self.assertIn('run_backend "$prefix-run$run.log" --module "$target"', flake)
		# run_backend runs the wrapper for the first run and for the rerun of a failing module.
		self.assertIn('"$REPORT_TEST_EXIT" bench --site "$SITE" run-tests --app "$APP" "$@"', lib)
		self.assertIn('"$REPORT_TEST_EXIT" bench --site "$SITE" run-tests --app "$APP" --module "$mod"', lib)
		bare = [
			line
			for line in (gate + "\n" + lib).splitlines()
			if re.search(r"\bbench --site \S+ run-tests\b", line) and "REPORT_TEST_EXIT" not in line
		]
		self.assertEqual(bare, [])

	def test_the_wrapper_is_executable_and_a_protected_gate_file(self):
		self.assertTrue(os.access(WRAPPER, os.X_OK))
		strategy = (REPO_ROOT / "docs/DEV_STRATEGY.md").read_text(encoding="utf-8")
		self.assertIn("`scripts/lib/*`", strategy)
