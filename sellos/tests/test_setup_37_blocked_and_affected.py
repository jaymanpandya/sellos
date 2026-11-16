"""SOS-SETUP-37: a Blocked task does not idle the loop, and the gate finds the specs a task breaks early.

On 14 November 2026 SOS-P1-20 turned the lead form's Source field into a required select and updated
only the spec that typed into it. Two older specs made a lead through the same form without choosing
a source. They failed only in the whole Cypress suite at the end of the gate, three gate runs in a
row, the task was Blocked at 12:55 IST, and the loop then stood idle for two days with eligible work
left (docs/STOPS.md, "task broke older specs").

* scripts/lib/affected_specs.py lists the specs that use a test id in a changed frontend file or name
  a changed Python function, and the gate runs each once before the changed tests and their repeats.
* The repair prompt starts with those specs and which of them failed, and both prompts tell the agent
  to grep cypress/ for a control or test id it changes.
* A Blocked task sends its notice, records its row (idle 0.0) in the Blocked commit, and the loop
  picks the next eligible task. Two Blocked in a row stop it.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from sellos.tests import test_loop_environment_failures as loop_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
AFFECTED = SCRIPTS / "lib" / "affected_specs.py"
LOOP = SCRIPTS / "build-loop.sh"
GATE = SCRIPTS / "run-tests.sh"
GIT_ENV = {**os.environ, **loop_env.GIT_ENV}

FORM_BEFORE = """<template>
	<form data-testid="sellos-lead-form">
		<input data-testid="sellos-lead-form-name" />
		<input data-testid="sellos-lead-form-source" />
		<button data-testid="sellos-lead-form-save">Save</button>
	</form>
</template>
"""
FORM_AFTER = """<template>
	<form data-testid="sellos-lead-form">
		<input data-testid="sellos-lead-form-name" />
		<select data-testid="sellos-lead-form-source-picker" required></select>
		<button data-testid="sellos-lead-form-save">Save</button>
	</form>
</template>
"""
API_BEFORE = """import frappe


@frappe.whitelist()
def save_lead(values=None):
	return values


@frappe.whitelist()
def list_leads():
	return []
"""
API_AFTER = """import frappe


@frappe.whitelist()
def save_lead(values=None):
	if not (values or {}).get("source"):
		frappe.throw("Choose a source")
	return values


@frappe.whitelist()
def list_leads():
	return []
"""
SPECS = {
	# uses the save button through the helper: a new required field breaks it
	"crm/by_role.cy.js": 'cy.getByTestId("lead-form-name").type("A");\ncy.getByTestId("lead-form-save").click();\n',
	# uses the source id the task renamed, by its full name
	"crm/source.cy.js": 'cy.get("[data-testid=sellos-lead-form-source]").type("Web");\n',
	# intercepts the changed API method
	"crm/intercepts.cy.js": 'cy.intercept("**/sellos.crm.api.save_lead*").as("save");\n',
	# names only the unchanged method in the same file
	"crm/list_only.cy.js": 'cy.intercept("**/sellos.crm.api.list_leads*").as("list");\n',
	# uses nothing the task changed
	"smoke/shell.cy.js": 'cy.getByTestId("app-shell").should("be.visible");\n',
	# a longer id that only starts with a changed one
	"crm/prefix.cy.js": 'cy.getByTestId("lead-form-name-hint").should("exist");\n',
	# the spec the task changed itself
	"crm/own.cy.js": 'cy.getByTestId("lead-form-source-picker").select("Website");\n',
}


class AffectedSpecs(unittest.TestCase):
	def setUp(self):
		self.app = Path(tempfile.mkdtemp(prefix="sellos-affected-"))
		self.addCleanup(subprocess.run, ["rm", "-rf", str(self.app)], check=False)
		self.write("frontend/src/pages/LeadsPage.vue", FORM_BEFORE)
		self.write("sellos/crm/api.py", API_BEFORE)
		for spec, text in SPECS.items():
			self.write(f"cypress/integration/{spec}", text)
		self.git("init", "-q", "-b", "1.0")
		self.git("add", "-A")
		self.git("commit", "-q", "-m", "base")
		self.write("frontend/src/pages/LeadsPage.vue", FORM_AFTER)
		self.write("sellos/crm/api.py", API_AFTER)
		self.write("cypress/integration/crm/own.cy.js", SPECS["crm/own.cy.js"] + "// changed\n")

	def write(self, rel, text):
		path = self.app / rel
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(text, encoding="utf-8")

	def git(self, *args):
		subprocess.run(["git", "-C", str(self.app), *args], check=True, capture_output=True, env=GIT_ENV)

	def affected(self, *changed):
		result = subprocess.run(
			["python3", str(AFFECTED), str(self.app), "HEAD", *changed],
			capture_output=True,
			text=True,
			check=True,
		)
		return dict(line.split("\t", 1) for line in result.stdout.splitlines())

	def test_a_spec_using_any_test_id_of_a_changed_screen_is_affected(self):
		found = self.affected("frontend/src/pages/LeadsPage.vue")
		self.assertIn("crm/by_role.cy.js", found)
		self.assertIn("lead-form-save", found["crm/by_role.cy.js"])

	def test_an_id_the_task_removed_or_renamed_still_counts(self):
		found = self.affected("frontend/src/pages/LeadsPage.vue")
		self.assertIn("crm/source.cy.js", found)
		self.assertIn("lead-form-source", found["crm/source.cy.js"])

	def test_a_spec_naming_a_changed_api_method_is_affected_and_an_unchanged_one_is_not(self):
		found = self.affected("sellos/crm/api.py")
		self.assertEqual(set(found), {"crm/intercepts.cy.js"})
		self.assertIn("calls sellos.crm.api.save_lead", found["crm/intercepts.cy.js"])

	def test_specs_using_nothing_changed_and_the_tasks_own_specs_are_left_out(self):
		found = self.affected(
			"frontend/src/pages/LeadsPage.vue", "sellos/crm/api.py", "cypress/integration/crm/own.cy.js"
		)
		self.assertEqual(set(found), {"crm/by_role.cy.js", "crm/source.cy.js", "crm/intercepts.cy.js"})

	def test_a_new_python_file_counts_every_function_in_it(self):
		self.write("sellos/tests/ui_fixtures.py", "def seed_gate_leads():\n\treturn {}\n")
		self.write(
			"cypress/integration/crm/seeds.cy.js", 'cy.bench("sellos.tests.ui_fixtures.seed_gate_leads");\n'
		)
		found = self.affected("sellos/tests/ui_fixtures.py")
		self.assertEqual(set(found), {"crm/seeds.cy.js"})

	def test_nothing_changed_lists_nothing(self):
		self.assertEqual(self.affected(), {})

	def test_the_14_november_change_would_have_been_caught(self):
		"""The real SOS-P1-20 attempt, kept on its failed branch, lists both specs it broke."""
		branch = "failed/SOS-P1-20-20261114-125557"
		probe = subprocess.run(
			["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", "-q", branch],
			capture_output=True,
			text=True,
		)
		if probe.returncode != 0:
			self.skipTest(f"{branch} is not in this clone (CI fetches only 1.0)")
		work = Path(tempfile.mkdtemp(prefix="sellos-p120-"))
		self.addCleanup(subprocess.run, ["rm", "-rf", str(work)], check=False)
		subprocess.run(
			["git", "-C", str(REPO_ROOT), "worktree", "add", "-q", "--detach", str(work / "wt"), branch],
			check=True,
			capture_output=True,
		)
		self.addCleanup(
			subprocess.run,
			["git", "-C", str(REPO_ROOT), "worktree", "remove", "--force", str(work / "wt")],
			check=False,
			capture_output=True,
		)
		base = "e78f90f"
		changed = subprocess.run(
			["git", "-C", str(work / "wt"), "diff", "--name-only", base, "HEAD"],
			capture_output=True,
			text=True,
			check=True,
		).stdout.split()
		result = subprocess.run(
			["python3", str(AFFECTED), str(work / "wt"), base, *changed],
			capture_output=True,
			text=True,
			check=True,
		)
		specs = {line.split("\t", 1)[0] for line in result.stdout.splitlines()}
		self.assertIn("crm/leads_by_role.cy.js", specs)
		self.assertIn("crm/duplicate_warning.cy.js", specs)


class TheGateRunsThemFirst(unittest.TestCase):
	def test_the_affected_specs_run_before_the_changed_tests_and_their_repeats(self):
		gate = GATE.read_text(encoding="utf-8")
		self.assertIn("scripts/lib/affected_specs.py", gate)
		self.assertLess(gate.index("affected_specs.py"), gate.index('sellos_flake_gate "$FLAKE_TARGETS"'))
		self.assertIn('AFFECTED_FILE="$LOG_DIR/affected-specs.txt"', gate)
		self.assertIn("AFFECTED SPEC FAILED: $spec", gate)

	def test_the_site_is_reset_after_affected_specs_ran(self):
		gate = GATE.read_text(encoding="utf-8")
		self.assertIn('if grep -q \'^spec\' "$FLAKE_TARGETS" || [ -n "${AFFECTED_RAN:-}" ]; then', gate)


def run_affected_context(rows):
	script = LOOP.read_text(encoding="utf-8")
	start = script.index("affected_context() {")
	end = script.index("\n}\n", start) + 3
	with tempfile.TemporaryDirectory() as folder:
		if rows is not None:
			Path(folder, "affected-specs.txt").write_text(rows, encoding="utf-8")
		return subprocess.run(
			["bash", "-c", script[start:end] + f'LOG_DIR="{folder}"; affected_context'],
			capture_output=True,
			text=True,
			check=True,
		).stdout


class TheRepairPromptNamesThem(unittest.TestCase):
	def test_the_failed_affected_specs_open_the_repair_prompt(self):
		out = run_affected_context(
			"PASSED\tfrontend/leads_screen.cy.js\ttest ids lead-row\n"
			"FAILED\tcrm/leads_by_role.cy.js\ttest ids lead-form-save\n"
		)
		self.assertIn("frontend/leads_screen.cy.js", out)
		self.assertIn(
			"These failed, so this task broke them:\n  crm/leads_by_role.cy.js (test ids lead-form-save)", out
		)
		self.assertIn("grep cypress/", out)
		self.assertIn("Never weaken or delete an assertion", out)

	def test_all_passed_names_them_without_a_failure(self):
		out = run_affected_context("PASSED\tcrm/a.cy.js\ttest ids x\n")
		self.assertIn("PASSED: crm/a.cy.js", out)
		self.assertNotIn("These failed", out)

	def test_no_affected_specs_adds_nothing(self):
		self.assertEqual(run_affected_context(None), "")

	def test_both_prompts_tell_the_agent_to_update_every_user_of_what_it_changes(self):
		script = LOOP.read_text(encoding="utf-8")
		implementation = script.split('PROMPT="You are implementing', 1)[1].split("Task:\n$TASK_BLOCK", 1)[0]
		repair = script.split('REPAIR_PROMPT="', 1)[1].split("Task:\n$TASK_BLOCK", 1)[0]
		for prompt in (implementation, repair):
			self.assertIn("When you change a control or a test id", prompt)
			self.assertIn("grep cypress/ for it and update every spec that uses it", prompt)
		self.assertTrue(repair.startswith("$(repair_head)$(affected_context)"), repair[:80])


TASKS_FOUR = """# Tasks

### SOS-X-1: first
- **Status:** Not Started
- **Dependencies:** None

### SOS-X-3: needs the first
- **Status:** Not Started
- **Dependencies:** SOS-X-1

### SOS-X-2: second
- **Status:** Not Started
- **Dependencies:** None

### SOS-X-4: fourth
- **Status:** Not Started
- **Dependencies:** None
"""
# gh for a loop that completes a task: one CI run on the commit, and it is green.
FAKE_GH_GREEN = """#!/usr/bin/env bash
case "$1 $2" in
  "run list") echo 101 ;;
  *) exit 0 ;;
esac
"""


class ABlockedTaskDoesNotIdleTheLoop(loop_env.LoopSandbox):
	def setUp(self):
		super().setUp()
		self.write(self.repo / "TASKS.md", TASKS_FOUR)
		self.git("add", "TASKS.md")
		self.git("commit", "-q", "-m", "SOS-X-0 four tasks")
		self.git("push", "-q", "origin", "1.0")
		self.serve(302)

	def statuses(self):
		import re

		text = (self.repo / "TASKS.md").read_text(encoding="utf-8")
		return dict(re.findall(r"^### (SOS-X-\d+):.*?\*\*Status:\*\* *(.*?)$", text, re.M | re.S))

	def notices(self):
		return [n.strip() for n in self.read("notifications").split("----") if n.strip()]

	def test_the_next_eligible_task_is_picked_and_two_blocked_in_a_row_stop(self):
		code = self.run_loop([1, 1], max_runs=1)
		self.assertEqual(code, 0, self.out)
		self.assertEqual(
			self.statuses(),
			{"SOS-X-1": "Blocked", "SOS-X-3": "Not Started", "SOS-X-2": "Blocked", "SOS-X-4": "Not Started"},
			self.out,
		)
		self.assertEqual(self.calls("claude_calls"), 2, "the second task was not started")
		first, second = self.notices()[:2]
		self.assertIn("SOS-X-1 failed tests", first)
		self.assertIn("Going on with the next eligible task", first)
		self.assertIn("SOS-X-1: holds up 1 task(s): SOS-X-3", first)
		self.assertIn("SOS-X-2 failed tests", second)
		self.assertIn("Two tasks Blocked in a row, so the loop stops.", second)
		ledger = (self.repo / "docs" / "STOPS.md").read_text(encoding="utf-8")
		self.assertRegex(
			ledger,
			r"\| SOS-X-1 \| blocked \| the gate still failed .*the loop went on to the next task \| \d+ \| 0\.0 \|",
		)
		self.assertRegex(
			ledger, r"\| SOS-X-2 \| blocked \| two tasks Blocked in a row \(SOS-X-1, then SOS-X-2\)"
		)
		# The first row went into SOS-X-1's Blocked commit, so the next task's tree was clean.
		blocked_commit = self.git("log", "--format=%H", "--grep=^SOS-X-1: tests failed, marking Blocked")
		self.assertTrue(blocked_commit, self.git("log", "--oneline"))
		self.assertIn("docs/STOPS.md", self.git("show", "--name-only", "--format=", blocked_commit))
		self.assertIn("Stop recorded in docs/STOPS.md: blocked, SOS-X-2", self.out)

	def test_a_completed_task_between_two_blocked_ones_keeps_the_loop_going(self):
		self.write(self.bin / "gh", FAKE_GH_GREEN, 0o755)
		code = self.run_loop([1, 0, 1], max_runs=1)
		self.assertEqual(code, 0, self.out)
		self.assertEqual(
			self.statuses(),
			{"SOS-X-1": "Blocked", "SOS-X-3": "Not Started", "SOS-X-2": "Complete", "SOS-X-4": "Blocked"},
			self.out,
		)
		self.assertNotIn("Two tasks Blocked in a row", self.read("notifications"))
		self.assertIn("Stop recorded in docs/STOPS.md: no-work", self.out)


if __name__ == "__main__":
	unittest.main()
