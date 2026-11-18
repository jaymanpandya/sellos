"""SOS-SETUP-42: the local gate is fast by default, and --full is the whole thing.

The fast gate runs the smoke set in place of the whole backend and Cypress suites. These cases read
the scripts, so they hold without a bench: the mode switch exists, the whole suites run only under
--full, every smoke entry points at a real test, the loop's repair path knows the new failure line,
and CI still runs the whole suites through the same scripts on every push.
"""

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_TESTS = (REPO_ROOT / "scripts" / "run-tests.sh").read_text(encoding="utf-8")
BUILD_LOOP = (REPO_ROOT / "scripts" / "build-loop.sh").read_text(encoding="utf-8")
CI = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
SMOKE = REPO_ROOT / "scripts" / "smoke-set.txt"


def smoke_entries():
	for line in SMOKE.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if line and not line.startswith("#"):
			kind, target = line.split(None, 1)
			yield kind, target


class GateFastMode(unittest.TestCase):
	def test_the_script_parses_and_refuses_an_unknown_option(self):
		self.assertEqual(
			subprocess.run(["bash", "-n", str(REPO_ROOT / "scripts/run-tests.sh")]).returncode, 0
		)
		out = subprocess.run(
			["bash", str(REPO_ROOT / "scripts/run-tests.sh"), "--bogus"], capture_output=True, text=True
		)
		self.assertEqual(out.returncode, 2)
		self.assertIn("Usage", out.stderr)

	def test_the_default_is_fast_and_full_is_opt_in(self):
		self.assertIn("GATE_MODE=fast", RUN_TESTS)
		self.assertIn("--full) GATE_MODE=full", RUN_TESTS)
		self.assertIn("SELLOS_GATE_FULL", RUN_TESTS)

	def test_the_whole_suites_run_only_in_full_mode(self):
		full = re.search(r'if \[ "\$GATE_MODE" = full \]; then\n(.*?)\nelse\n', RUN_TESTS, re.S)
		self.assertIsNotNone(full)
		self.assertIn("run_backend", full.group(1))
		self.assertIn("sellos_ui_suite", full.group(1))
		self.assertEqual(RUN_TESTS.count("sellos_ui_suite "), 1)
		self.assertEqual(RUN_TESTS.count('run_backend "$LOG_DIR/backend-$STAMP-all.log"'), 1)

	def test_everything_before_the_whole_suites_is_in_both_modes(self):
		fast_part = RUN_TESTS[: RUN_TESTS.index('if [ "$GATE_MODE" = full ]')]
		for needed in ("check-guards.sh", "affected_specs.py", "sellos_flake_gate", "sellos_reset_test_site"):
			self.assertIn(needed, fast_part)

	def test_every_smoke_entry_is_a_real_test(self):
		entries = list(smoke_entries())
		self.assertGreaterEqual(len(entries), 3)
		for kind, target in entries:
			if kind == "spec":
				self.assertTrue((REPO_ROOT / "cypress/integration" / target).is_file(), target)
			elif kind == "backend":
				self.assertTrue((REPO_ROOT / (target.replace(".", "/") + ".py")).is_file(), target)
			else:
				self.fail(f"unknown kind {kind}")

	def test_the_loop_reads_the_smoke_failure(self):
		self.assertIn("SMOKE TESTS FAILED", RUN_TESTS)
		self.assertGreaterEqual(BUILD_LOOP.count("SMOKE TESTS FAILED"), 2)

	def test_the_loop_runs_the_fast_gate(self):
		for line in BUILD_LOOP.splitlines():
			if 'run-tests.sh"' in line and "SCRIPT_DIR" in line:
				self.assertNotIn("--full", line)

	def test_ci_still_runs_the_whole_suites_on_every_push(self):
		self.assertIn("scripts/lib/backend_suite.sh", CI)
		self.assertIn("scripts/lib/ui_flaky.sh", CI)
		self.assertNotIn("smoke-set", CI)
