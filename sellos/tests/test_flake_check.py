"""SOS-SETUP-33 and SOS-SETUP-34: every new or changed test runs more than once in the gate, and one
failed run fails it. SOS-SETUP-34: 5 runs under 60 seconds, 3 under 3 minutes, 2 above, and the
repeats of one gate capped at 10 minutes.

The real sellos_flake_check from scripts/lib/flake_check.sh runs here with run_backend and
_sellos_ui_run replaced by stubs that fail on a chosen run, so no bench is needed.
"""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FLAKE = REPO_ROOT / "scripts" / "lib" / "flake_check.sh"
GATE = REPO_ROOT / "scripts" / "run-tests.sh"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
PLAN_PY = REPO_ROOT / "scripts" / "lib" / "flake_plan.py"

_spec = importlib.util.spec_from_file_location("flake_plan", PLAN_PY)
flake_plan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(flake_plan)

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
		# SOS-SETUP-34: every changed module and spec is listed, then one repeat plan runs them all.
		self.assertIn('>>"$FLAKE_TARGETS"', gate)
		self.assertIn('sellos_flake_gate "$FLAKE_TARGETS" || exit 1', gate)
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


# SOS-SETUP-34: a fake clock. Each stub run moves it on by the seconds the target's line in
# $WORK/durations gives (target seconds), so a 4 minute module takes no real time.
CLOCK_STUBS = """
CLOCK="$WORK/clock"
echo 1000 >"$CLOCK"
COUNT_FILE="$WORK/count"
echo 0 >"$COUNT_FILE"
stub_run() {
  local n target secs
  n=$(( $(cat "$COUNT_FILE") + 1 )); echo "$n" >"$COUNT_FILE"
  target="${*: -1}"
  echo "$target" >>"$WORK/calls"
  # A third column is the time of every run after the target's first.
  if grep -qx "$target" "$WORK/seen" 2>/dev/null; then
    secs="$(awk -v t="$target" '$1 == t { print ($3 != "" ? $3 : $2) }' "$WORK/durations")"
  else
    secs="$(awk -v t="$target" '$1 == t { print $2 }' "$WORK/durations")"
    echo "$target" >>"$WORK/seen"
  fi
  echo $(( $(cat "$CLOCK") + ${secs:-0} )) >"$CLOCK"
  [ "$n" = "${FAIL_ON:-0}" ] && return 1
  return 0
}
run_backend() { stub_run "$@"; }
_sellos_ui_run() { stub_run "$@"; }
"""


def flake_gate(targets, fail_on=0, cap=None, runs=None, later=None):
	"""targets: [(kind, target, seconds per run)]; later: {target: seconds of each run after the first}.
	Returns (exit code, output, [target per run])."""
	later = later or {}
	with tempfile.TemporaryDirectory() as work:
		Path(work, "durations").write_text(
			"".join(f"{target} {seconds} {later.get(target, '')}\n" for _, target, seconds in targets),
			encoding="utf-8",
		)
		Path(work, "targets").write_text(
			"".join(f"{kind}\t{target}\t{work}/log-{i}\n" for i, (kind, target, _) in enumerate(targets)),
			encoding="utf-8",
		)
		env = ""
		if cap is not None:
			env += f"export SELLOS_FLAKE_CAP_SECONDS={cap}; "
		if runs is not None:
			env += f"export SELLOS_FLAKE_RUNS={runs}; "
		script = (
			f'WORK="{work}"; FAIL_ON={fail_on}; {env}'
			+ CLOCK_STUBS
			+ f'source "{FLAKE}"; _sellos_flake_now() {{ cat "$CLOCK"; }}; '
			+ f'sellos_flake_gate "{work}/targets"'
		)
		result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
		calls_file = Path(work, "calls")
		calls = calls_file.read_text().splitlines() if calls_file.exists() else []
	return result.returncode, result.stdout + result.stderr, calls


class TestRepeatsShrinkAsATestGetsSlower(unittest.TestCase):
	"""SOS-SETUP-34: 5 runs under 60 seconds, 3 under 3 minutes, 2 above, repeats capped at 600s."""

	def test_the_tiers_and_their_edges(self):
		for seconds, runs in ((0, 5), (59, 5), (60, 3), (179, 3), (180, 2), (900, 2)):
			with self.subTest(seconds=seconds):
				self.assertEqual(flake_plan.runs_for(seconds), runs)
		self.assertEqual(flake_plan.runs_for(10, most=2), 2, "SELLOS_FLAKE_RUNS lowers a tier")
		self.assertEqual(flake_plan.runs_for(200, most=4), 2, "and never raises one")

	def test_a_fast_a_medium_and_a_slow_module_get_5_3_and_2_runs(self):
		code, out, calls = flake_gate(
			[("backend", "fast", 10), ("backend", "medium", 90), ("backend", "slow", 200)]
		)
		self.assertEqual(code, 0, out)
		self.assertEqual([calls.count(t) for t in ("fast", "medium", "slow")], [5, 3, 2], out)
		self.assertEqual(calls[:3], ["fast", "medium", "slow"], "every test runs once before any repeat")
		self.assertIn("fast: first run 10s, 5 run(s) in all, 40s more", out)
		self.assertIn("medium: first run 90s, 3 run(s) in all, 180s more", out)
		self.assertIn("slow: first run 200s, 2 run(s) in all, 200s more", out)
		self.assertIn("Planned repeat time: 420s of 600s.", out)
		self.assertIn("the repeats took 420s of 600s", out)

	def test_the_plan_is_printed_before_the_first_run_and_before_any_repeat(self):
		code, out, _calls = flake_gate([("backend", "a", 5), ("spec", "crm/b.cy.js", 5)])
		self.assertEqual(code, 0, out)
		self.assertLess(
			out.index("=== Repeat plan: 2 changed test(s): a crm/b.cy.js"), out.index("a, run 1 ---")
		)
		self.assertLess(out.index("Planned repeat time"), out.index("run 2 of"))

	def test_the_repeats_never_take_more_than_ten_minutes(self):
		# Four 4 minute modules want 4 repeats (960s); the cap lets two have theirs.
		targets = [("backend", f"slow{i}", 240) for i in range(4)]
		code, out, calls = flake_gate(targets)
		self.assertEqual(code, 0, out)
		self.assertEqual([calls.count(f"slow{i}") for i in range(4)], [2, 2, 1, 1], out)
		self.assertIn("wanted 2, cut to fit the 600s cap", out)
		self.assertIn("the repeats took 480s of 600s", out)

	def test_every_test_gets_a_first_repeat_before_any_gets_a_second(self):
		runs, wanted, spent = flake_plan.plan([("a", 100), ("b", 100), ("c", 100)], cap_seconds=400)
		self.assertEqual(wanted, [3, 3, 3])
		self.assertEqual(runs, [3, 2, 2])
		self.assertLessEqual(spent, 400)

	def test_a_test_slower_than_the_cap_runs_once_and_says_why(self):
		code, out, calls = flake_gate([("backend", "huge", 700)])
		self.assertEqual(code, 0, out)
		self.assertEqual(calls, ["huge"])
		self.assertIn(
			"huge: first run 700s, 1 run(s) in all, 0s more (wanted 2, cut to fit the 600s cap)", out
		)

	def test_a_repeat_that_runs_long_is_not_followed_past_the_cap(self):
		# The first run took 50s, so 5 runs (200s of repeats) were planned; the repeats take 250s each.
		code, out, calls = flake_gate([("backend", "a", 50)], later={"a": 250})
		self.assertEqual(code, 0, out)
		self.assertEqual(len(calls), 3, out)
		self.assertIn("Repeat cap: a stops after run 3 of 5", out)
		self.assertIn("a passed 3 of 3 runs", out)
		self.assertIn("the repeats took 500s of 600s", out)
		plan_runs, _wanted, _spent = flake_plan.plan([("a", 1)], cap_seconds=0)
		self.assertEqual(plan_runs, [1])

	def test_a_flaky_repeat_still_fails_with_the_changed_test_line(self):
		code, out, calls = flake_gate([("backend", "a", 1), ("spec", "crm/b.cy.js", 1)], fail_on=4)
		self.assertEqual(code, 1, out)
		self.assertEqual(len(calls), 4)
		self.assertIn("GUARD FAILED: flake-check", out)
		self.assertIn("a passed on run(s) 1 2 and failed on run 3 of 5", out)
		self.assertIn("CHANGED TEST FAILED: a", out)

	def test_a_first_run_failure_of_a_spec_is_a_plain_changed_spec_failure(self):
		code, out, calls = flake_gate([("backend", "a", 1), ("spec", "crm/b.cy.js", 1)], fail_on=2)
		self.assertEqual(code, 1, out)
		self.assertEqual(calls, ["a", "crm/b.cy.js"])
		self.assertIn("CHANGED SPEC FAILED: crm/b.cy.js", out)
		self.assertNotIn("GUARD FAILED", out)

	def test_no_changed_test_runs_nothing(self):
		code, out, calls = flake_gate([])
		self.assertEqual(code, 0, out)
		self.assertEqual(calls, [])
		self.assertIn("Repeat plan: no changed test.", out)
