"""SOS-SETUP-27: the local gate and CI's UI job apply one flaky policy, from one script.

CI run 42925739766 (0259aac, SOS-P1-08) failed the UI job on crm/consent_warning.cy.js, a spec the
local gate had passed. The gate reruns a failed spec once and CI ran Cypress once, so one flake
stopped the loop. scripts/lib/ui_flaky.sh now holds the policy, scripts/run-tests.sh sources it and
.github/workflows/ci.yml runs it:

* a failed spec is rerun once, alone; a rerun that passes is logged FLAKY and the run passes,
* a spec in the flaky log three times fails the run,
* the flaky specs of the run go in the job summary.

These tests drive the script over a fake bench, and check that neither the gate nor CI runs Cypress
any other way.
"""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "lib"
UI_FLAKY_SH = LIB / "ui_flaky.sh"
UI_FLAKY_PY = LIB / "ui_flaky.py"
GATE = REPO_ROOT / "scripts" / "run-tests.sh"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def results_box(spec, failing, colour=False):
	"""The results box Cypress prints after each spec, cut down. CI's has colour codes in it."""
	if colour:
		n = f"\x1b[{31 if failing else 32}m{failing}\x1b[39m"
		return (
			f"\x1b[90m  │\x1b[39m \x1b[90mFailing:\x1b[39m      {n}          \x1b[90m│\x1b[39m\n"
			f"\x1b[90m  │\x1b[39m \x1b[90mSpec Ran:\x1b[39m     \x1b[31m\x1b[31m{spec}\x1b[31m\x1b[39m"
			"        \x1b[90m│\x1b[39m\n"
		)
	return f"  │ Failing:      {failing}          │\n  │ Spec Ran:     {spec}        │\n"


# What run 42925739766 printed for its first two specs, colour codes and all.
CI_RUN = results_box("crm/consent_warning.cy.js", 1, colour=True) + results_box(
	"crm/leads_by_role.cy.js", 0, colour=True
)
ONE_FAILS = results_box("crm/a.cy.js", 0) + results_box("crm/b.cy.js", 1) + results_box("crm/c.cy.js", 0)
TWO_FAIL = results_box("crm/a.cy.js", 2) + results_box("crm/b.cy.js", 1)
ALL_PASS = results_box("crm/a.cy.js", 0) + results_box("crm/b.cy.js", 0)
CRASH = "Cypress could not verify that this server is running\n"

FAKE_BENCH = """\
#!/usr/bin/env bash
echo "$*" >>"{dir}/calls"
case "$*" in *clear-cache*) exit 0 ;; esac
n=$(( $(cat "{dir}/count" 2>/dev/null || echo 0) + 1 ))
echo "$n" >"{dir}/count"
cat "{dir}/out-$n.txt"
exit "$(cat "{dir}/code-$n")"
"""


def flaky_py(*args):
	return subprocess.run(["python3", str(UI_FLAKY_PY), *args], capture_output=True, text=True, check=False)


class CypressLog(unittest.TestCase):
	def parse(self, text):
		with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f:
			f.write(text)
		try:
			return flaky_py("failed-specs", f.name).stdout.split()
		finally:
			Path(f.name).unlink()

	def test_the_coloured_ci_log_names_only_the_failing_spec(self):
		self.assertEqual(self.parse(CI_RUN), ["crm/consent_warning.cy.js"])

	def test_plain_logs_name_each_failing_spec_once_in_order(self):
		self.assertEqual(self.parse(ONE_FAILS), ["crm/b.cy.js"])
		self.assertEqual(self.parse(TWO_FAIL + TWO_FAIL), ["crm/a.cy.js", "crm/b.cy.js"])
		self.assertEqual(self.parse(ALL_PASS), [])
		self.assertEqual(self.parse(CRASH), [])


class RerunPolicy(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-uiflaky-"))
		(self.dir / "bin").mkdir()
		bench = self.dir / "bin" / "bench"
		bench.write_text(FAKE_BENCH.format(dir=self.dir), encoding="utf-8")
		bench.chmod(0o755)
		self.flaky_log = self.dir / "baseline" / "sellos-flaky.log"
		self.summary = self.dir / "summary.md"

	def tearDown(self):
		for p in sorted(self.dir.rglob("*"), reverse=True):
			p.rmdir() if p.is_dir() else p.unlink()
		self.dir.rmdir()

	def run_suite(self, *runs, spec=None, history=(), summary=True):
		"""Run ui_flaky.sh over a fake bench whose nth Cypress run prints runs[n-1] and exits with its code."""
		for n, (output, code) in enumerate(runs, start=1):
			(self.dir / f"out-{n}.txt").write_text(output, encoding="utf-8")
			(self.dir / f"code-{n}").write_text(str(code), encoding="utf-8")
		if history:
			self.flaky_log.parent.mkdir(parents=True, exist_ok=True)
			self.flaky_log.write_text("".join(f"2026-11-0{i + 1} {s}\n" for i, s in enumerate(history)))
		env = {
			**os.environ,
			"PATH": f"{self.dir / 'bin'}:{os.environ['PATH']}",
			"SITE": "test_site",
			"APP": "sellos",
			"SELLOS_FLAKY_LOG": str(self.flaky_log),
		}
		env.pop("GITHUB_STEP_SUMMARY", None)
		if summary:
			env["GITHUB_STEP_SUMMARY"] = str(self.summary)
		args = ["bash", str(UI_FLAKY_SH), str(self.dir / "cypress.log")] + ([spec] if spec else [])
		result = subprocess.run(args, capture_output=True, text=True, check=False, env=env, cwd=self.dir)
		calls_file = self.dir / "calls"
		calls = calls_file.read_text().splitlines() if calls_file.exists() else []
		return result, calls

	def summary_text(self):
		return self.summary.read_text() if self.summary.exists() else ""

	def flaky_entries(self):
		return self.flaky_log.read_text().splitlines() if self.flaky_log.exists() else []

	def test_a_passing_suite_runs_once_and_says_no_spec_was_flaky(self):
		result, calls = self.run_suite((ALL_PASS, 0))
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		self.assertEqual(calls, ["--site test_site run-ui-tests sellos --headless"])
		self.assertIn("None: every spec passed on its first run.", self.summary_text())
		self.assertEqual(self.flaky_entries(), [])

	def test_a_failed_spec_is_rerun_once_alone_and_a_pass_is_flaky(self):
		result, calls = self.run_suite((ONE_FAILS, 1), (ALL_PASS, 0))
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		self.assertEqual(
			calls,
			[
				"--site test_site run-ui-tests sellos --headless",
				"--site test_site clear-cache",
				"--site test_site run-ui-tests sellos --headless --spec cypress/integration/crm/b.cy.js",
			],
		)
		self.assertIn("FLAKY (passed on rerun): crm/b.cy.js", result.stdout)
		self.assertEqual(len(self.flaky_entries()), 1)
		self.assertRegex(self.flaky_entries()[0], r"^\d{4}-\d{2}-\d{2} crm/b\.cy\.js$")
		self.assertIn("### Flaky Cypress specs", self.summary_text())
		self.assertIn("| `crm/b.cy.js` | 1 |", self.summary_text())

	def test_the_ci_failure_of_run_42925739766_is_rerun_and_passes(self):
		result, calls = self.run_suite((CI_RUN, 1), (ALL_PASS, 0))
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		self.assertEqual(
			calls[-1],
			"--site test_site run-ui-tests sellos --headless --spec cypress/integration/crm/consent_warning.cy.js",
		)
		self.assertIn("FLAKY (passed on rerun): crm/consent_warning.cy.js", result.stdout)

	def test_a_rerun_that_fails_again_fails_the_run(self):
		result, calls = self.run_suite((ONE_FAILS, 1), (ONE_FAILS, 1))
		self.assertEqual(result.returncode, 1)
		self.assertIn("FAILED AGAIN: crm/b.cy.js", result.stdout)
		self.assertEqual(self.flaky_entries(), [])
		self.assertEqual(len([c for c in calls if "run-ui-tests" in c]), 2)

	def test_each_failed_spec_is_rerun_alone_and_one_failing_again_fails_the_run(self):
		result, calls = self.run_suite((TWO_FAIL, 1), (ALL_PASS, 0), (TWO_FAIL, 1))
		self.assertEqual(result.returncode, 1)
		self.assertIn("FLAKY (passed on rerun): crm/a.cy.js", result.stdout)
		self.assertIn("FAILED AGAIN: crm/b.cy.js", result.stdout)
		reruns = [c for c in calls if "--spec" in c]
		self.assertEqual(
			reruns,
			[
				"--site test_site run-ui-tests sellos --headless --spec cypress/integration/crm/a.cy.js",
				"--site test_site run-ui-tests sellos --headless --spec cypress/integration/crm/b.cy.js",
			],
		)

	def test_the_third_flaky_run_of_a_spec_fails_the_run(self):
		history = ("crm/b.cy.js", "crm/b.cy.js")
		result, _ = self.run_suite((ONE_FAILS, 1), (ALL_PASS, 0), history=history)
		self.assertEqual(result.returncode, 1)
		self.assertIn("FLAKY (passed on rerun): crm/b.cy.js", result.stdout)
		self.assertIn("FLAKY too often, fix these specs: crm/b.cy.js (3 times)", result.stdout)
		self.assertIn("| `crm/b.cy.js` | 3 |", self.summary_text())
		self.assertIn("FLAKY too often", self.summary_text())

	def test_a_spec_flaky_three_times_before_fails_even_a_clean_run(self):
		result, _ = self.run_suite((ALL_PASS, 0), history=("crm/a.cy.js",) * 3)
		self.assertEqual(result.returncode, 1)
		self.assertIn("FLAKY too often, fix these specs: crm/a.cy.js (3 times)", result.stdout)

	def test_two_flaky_runs_of_one_spec_still_pass(self):
		result, _ = self.run_suite((ONE_FAILS, 1), (ALL_PASS, 0), history=("crm/b.cy.js", "crm/a.cy.js"))
		self.assertEqual(result.returncode, 0, result.stdout)

	def test_a_failure_no_spec_can_be_named_for_is_not_rerun(self):
		result, calls = self.run_suite((CRASH, 1))
		self.assertEqual(result.returncode, 1)
		self.assertIn("UI tests failed (0 specs identified), not rerunning", result.stdout)
		self.assertEqual(len(calls), 1)

	def test_more_than_five_failed_specs_are_not_rerun(self):
		many = "".join(results_box(f"crm/s{i}.cy.js", 1) for i in range(6))
		result, calls = self.run_suite((many, 1))
		self.assertEqual(result.returncode, 1)
		self.assertIn("UI tests failed (6 specs identified), not rerunning", result.stdout)
		self.assertEqual(len(calls), 1)

	def test_one_spec_is_run_and_rerun_by_its_own_path(self):
		result, calls = self.run_suite((CRASH, 1), (ALL_PASS, 0), spec="crm/x.cy.js")
		self.assertEqual(result.returncode, 0, result.stdout)
		self.assertEqual(
			[c for c in calls if "run-ui-tests" in c],
			["--site test_site run-ui-tests sellos --headless --spec cypress/integration/crm/x.cy.js"] * 2,
		)
		self.assertIn("FLAKY (passed on rerun): crm/x.cy.js", result.stdout)

	def test_without_a_job_summary_nothing_is_written_for_one(self):
		result, _ = self.run_suite((ONE_FAILS, 1), (ALL_PASS, 0), summary=False)
		self.assertEqual(result.returncode, 0, result.stdout)
		self.assertFalse(self.summary.exists())

	def test_the_cypress_output_reaches_the_log_file(self):
		self.run_suite((ONE_FAILS, 1), (ALL_PASS, 0))
		self.assertIn("crm/b.cy.js", (self.dir / "cypress.log").read_text())


class OnePolicyForGateAndCi(unittest.TestCase):
	def test_the_gate_runs_cypress_only_through_the_shared_script(self):
		gate = GATE.read_text(encoding="utf-8")
		self.assertIn('source "$REPO_DIR/scripts/lib/ui_flaky.sh"', gate)
		self.assertNotIn("run-ui-tests", re.sub(r"(?m)^\s*#.*$", "", gate))
		# The whole suite through the rerun policy. SOS-SETUP-33: a changed spec runs 5 times through
		# scripts/lib/flake_check.sh, with no rerun, so a flaky changed spec fails.
		self.assertGreaterEqual(gate.count("sellos_ui_suite "), 1)
		self.assertIn("printf 'spec\\t%s\\t%s\\n' \"$spec\"", gate)
		self.assertIn("export SELLOS_FLAKY_LIMIT=3", gate)
		self.assertIn("export SELLOS_MAX_RERUN=5", gate)

	def test_ci_runs_cypress_only_through_the_shared_script_with_the_gate_limits(self):
		ci = CI.read_text(encoding="utf-8")
		self.assertIn('bash "$GITHUB_WORKSPACE/scripts/lib/ui_flaky.sh"', ci)
		self.assertNotIn("run-ui-tests", re.sub(r"(?m)^\s*#.*$", "", ci))
		self.assertIn("SELLOS_FLAKY_LIMIT: 3", ci)
		self.assertIn("SELLOS_MAX_RERUN: 5", ci)

	def test_ci_keeps_its_flaky_log_between_runs(self):
		ci = CI.read_text(encoding="utf-8")
		self.assertIn("actions/cache/restore@", ci)
		self.assertIn("actions/cache/save@", ci)
		self.assertIn("restore-keys: |\n            sellos-flaky-", ci)
		self.assertIn("if: always() && steps.cypress.outcome != 'skipped'", ci)


if __name__ == "__main__":
	unittest.main()
