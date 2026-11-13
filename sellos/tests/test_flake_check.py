"""SOS-SETUP-33: every new or changed test runs 5 times in the gate, and one failed run fails it.

The real sellos_flake_check from scripts/lib/flake_check.sh runs here with run_backend and
_sellos_ui_run replaced by stubs that fail on a chosen run, so no bench is needed.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FLAKE = REPO_ROOT / "scripts" / "lib" / "flake_check.sh"
GATE = REPO_ROOT / "scripts" / "run-tests.sh"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

STUBS = """
COUNT_FILE="$WORK/count"
echo 0 >"$COUNT_FILE"
stub_run() {
  local n; n=$(( $(cat "$COUNT_FILE") + 1 )); echo "$n" >"$COUNT_FILE"
  echo "$1 $2 call $n" >>"$WORK/calls"
  [ "$n" = "${FAIL_ON:-0}" ] && return 1
  return 0
}
run_backend() { stub_run backend "$*"; }
_sellos_ui_run() { stub_run spec "$*"; }
"""


def flake_check(kind, target, fail_on=0, runs=None):
	with tempfile.TemporaryDirectory() as work:
		env_runs = f"SELLOS_FLAKE_RUNS={runs}; export SELLOS_FLAKE_RUNS; " if runs is not None else ""
		script = (
			f'WORK="{work}"; FAIL_ON={fail_on}; {env_runs}'
			+ STUBS
			+ f'source "{FLAKE}"; sellos_flake_check {kind} "{target}" "{work}/log"'
		)
		result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
		calls_file = Path(work, "calls")
		calls = calls_file.read_text().splitlines() if calls_file.exists() else []
	return result.returncode, result.stdout + result.stderr, calls


class TestFlakeCheck(unittest.TestCase):
	def test_five_passing_runs_pass(self):
		code, out, calls = flake_check("backend", "sellos.crm.test_crm")
		self.assertEqual(code, 0, out)
		self.assertEqual(len(calls), 5)
		self.assertIn("Flake check: sellos.crm.test_crm passed 5 of 5 runs.", out)
		self.assertIn("--module sellos.crm.test_crm", calls[0])

	def test_a_failure_on_a_later_run_is_a_flaky_failure_with_its_fix(self):
		code, out, calls = flake_check("backend", "sellos.crm.test_crm", fail_on=3)
		self.assertEqual(code, 1, out)
		self.assertEqual(len(calls), 3, "the runs after the failing one are not needed")
		self.assertIn("GUARD FAILED: flake-check", out)
		self.assertIn("passed on run(s) 1 2 and failed on run 3 of 5", out)
		for rule in (
			"no real background jobs",
			"wait on a condition never on time",
			"no shared mutable state",
		):
			self.assertIn(rule, out)
		self.assertIn("END GUARD", out)

	def test_the_fifth_run_counts_too(self):
		code, out, calls = flake_check("spec", "crm/leads.cy.js", fail_on=5)
		self.assertEqual(code, 1, out)
		self.assertEqual(len(calls), 5)
		self.assertTrue(all(call.startswith("spec ") for call in calls), calls)
		self.assertIn("crm/leads.cy.js", calls[0])

	def test_a_failure_on_the_first_run_is_a_plain_failure(self):
		code, out, calls = flake_check("backend", "sellos.crm.test_crm", fail_on=1)
		self.assertEqual(code, 1, out)
		self.assertEqual(len(calls), 1)
		self.assertNotIn("GUARD FAILED", out)

	def test_the_number_of_runs_comes_from_the_variable(self):
		code, out, calls = flake_check("backend", "m", runs=2)
		self.assertEqual(code, 0, out)
		self.assertEqual(len(calls), 2)
		code, out, calls = flake_check("backend", "m", runs="none")
		self.assertEqual(code, 1, out)
		self.assertEqual(calls, [])


class TestTheGateUsesIt(unittest.TestCase):
	def test_changed_modules_and_specs_run_through_the_flake_check(self):
		gate = GATE.read_text(encoding="utf-8")
		self.assertIn('source "$REPO_DIR/scripts/lib/flake_check.sh"', gate)
		self.assertIn('sellos_flake_check backend "$mod"', gate)
		self.assertIn('sellos_flake_check spec "$spec"', gate)
		flake = FLAKE.read_text(encoding="utf-8")
		self.assertIn('runs="${SELLOS_FLAKE_RUNS:-5}"', flake)

	def test_the_test_rules_are_in_claude_md(self):
		text = CLAUDE_MD.read_text(encoding="utf-8")
		self.assertIn("## Test rules", text)
		for rule in (
			"No real background jobs in tests",
			"Wait on conditions, never on time",
			"No shared mutable state",
			"five times",
		):
			self.assertIn(rule, text)
