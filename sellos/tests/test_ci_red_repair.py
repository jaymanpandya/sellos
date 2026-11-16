"""SOS-SETUP-38: a red CI on a head the loop pushed is repaired, and status commits are not pushed alone.

The real scripts/build-loop.sh runs in the throwaway bench of test_loop_environment_failures.py, with a
fake gate, a fake claude, a fake notifier and a fake gh that plays one CI result per wait from
ci_plan: green, red (a failing test and a spec's console error, as CI run 43954312044 showed) or env
(the runner was lost, no test failed).

* Red, then green after the first repair: the agent is given the failing tests and their messages, the
  repair passes the gate, is committed and pushed, CI goes green and the loop carries on.
* Red, and red again after each of two repairs: the loop stops as ci-red with the failures in its notice.
* A fault outside the code: the failed jobs are rerun once, no agent runs, and the loop stops as
  environment when the rerun is red too.
* A commit that changes only TASKS.md or docs/STOPS.md is not pushed at the start; it goes up with the
  next completion push, and a Blocked task's status commit stays local.
Every step sends a Telegram message.
"""

import shutil

from sellos.tests import test_loop_environment_failures as loop_env

TASK = loop_env.TASK
FAKE_GH = """#!/usr/bin/env bash
F="$FAKE_DIR"
case "$1 $2" in
  "run list") echo 101 ;;
  "run watch")
    echo "$(git -C "$ORIGIN" rev-parse 1.0)" >>"$F/ci_heads"
    o="$(head -n 1 "$F/ci_plan")"; tail -n +2 "$F/ci_plan" >"$F/ci_plan.rest"; mv "$F/ci_plan.rest" "$F/ci_plan"
    echo "${o:-green}" >"$F/ci_last"
    [ "${o:-green}" = green ] ;;
  "run view") if [ "$(cat "$F/ci_last")" = env ]; then cat "$F/env.log"; else cat "$F/red.log"; fi ;;
  "run rerun") echo "$*" >>"$F/gh_reruns" ;;
  *) exit 0 ;;
esac
"""
# The prompt is the argument after -p. Each call is kept, so a test can read what the agent was told.
FAKE_CLAUDE = """#!/usr/bin/env bash
echo call >>"$FAKE_DIR/claude_calls"
n="$(wc -l <"$FAKE_DIR/claude_calls" | tr -d ' ')"
printf '%s' "$2" >"$FAKE_DIR/prompt-$n"
echo "work $n" >>sellos/work.py
echo "IMPLEMENTATION_READY: did the work $n"
"""
RED_LOG = (
	"Server\tRun Tests\t2026-11-16T21:00:31.1539521Z  FAIL  test_the_buyer_pipeline_supersedes_the_wizard_stages"
	" (sellos.tests.test_tasks_selection.RealTasksFile.test_the_buyer_pipeline_supersedes_the_wizard_stages)\n"
	"Server\tRun Tests\t2026-11-16T21:00:31.1546484Z AssertionError: 'In Progress' != 'Not Started'\n"
	"Server\tRun Tests\t2026-11-16T21:00:31.1548124Z FAILED (failures=1, skipped=21)\n"
	'UI\tRun the Cypress suite\t2026-11-16T20:58:14.5982764Z     1) "after each" hook for "keeps partners out"\n'
	"UI\tRun the Cypress suite\t2026-11-16T20:58:14.6578721Z       -[ 'list_lead_sources failed Failed to fetch' ]\n"
	"UI\tRun the Cypress suite\t2026-11-16T21:00:28.0000000Z ##[error]Process completed with exit code 1.\n"
)
ENV_LOG = (
	"UI\tRun the Cypress suite\t2026-11-16T20:58:14.0000000Z ##[error]The runner has received a shutdown"
	" signal. This can happen when the runner service is stopped, or a manually started runner is canceled.\n"
)


class CiSandbox(loop_env.LoopSandbox):
	def setUp(self):
		super().setUp()
		shutil.copy2(
			loop_env.SCRIPTS / "lib" / "ci_failures.py", self.repo / "scripts" / "lib" / "ci_failures.py"
		)
		self.write(self.bin / "gh", FAKE_GH, 0o755)
		self.write(self.bin / "claude", FAKE_CLAUDE, 0o755)
		self.write(self.fake / "red.log", RED_LOG)
		self.write(self.fake / "env.log", ENV_LOG)
		self.origin = self.root / "origin.git"
		self.serve(302)

	def run_ci(self, codes, plan):
		self.write(self.fake / "ci_plan", "".join(f"{p}\n" for p in plan))
		env = {"ORIGIN": str(self.origin), "SELLOS_CI_FIRST_WAIT": "0"}
		return self.run_loop(codes, max_runs=1, extra_env=env)

	def notices(self):
		return [n.strip() for n in self.read("notifications").split("----") if n.strip()]

	def origin_log(self):
		return self.git("log", "--format=%s", "origin/1.0").splitlines()

	def ledger(self):
		path = self.repo / "docs" / "STOPS.md"
		return path.read_text(encoding="utf-8") if path.exists() else ""


class ARedCiIsRepaired(CiSandbox):
	def test_red_then_green_after_one_repair_carries_on(self):
		code = self.run_ci([0, 0], ["red", "green"])
		self.assertEqual(code, 0, self.out)
		self.assertEqual(self.status(), "Complete", self.out)
		self.assertEqual(self.calls("claude_calls"), 2, "the task's agent, then one repair")
		prompt = self.read("prompt-2")
		self.assertIn("CI repair attempt 1 of 2", prompt)
		self.assertIn("FAIL  test_the_buyer_pipeline_supersedes_the_wizard_stages", prompt)
		self.assertIn("AssertionError: 'In Progress' != 'Not Started'", prompt)
		self.assertIn('1) "after each" hook for "keeps partners out"', prompt)
		self.assertIn("-[ 'list_lead_sources failed Failed to fetch' ]", prompt)
		self.assertIn("never raise a limit", prompt)
		self.assertEqual(self.calls("gate_calls"), 2, "the task's gate, then the repair's")
		self.assertTrue(
			self.origin_log()[0].startswith("SOS-LOOP: repair of the red CI on "), self.origin_log()
		)
		self.assertEqual(self.git("rev-parse", "HEAD"), self.git("rev-parse", "origin/1.0"))
		notices = "\n".join(self.notices())
		self.assertIn("Repair attempt 1 of 2. Failing:", notices)
		self.assertIn("passed the gate and is pushed as", notices)
		self.assertIn("after repair attempt 1. Going on.", notices)
		self.assertNotIn("| ci-red |", self.ledger())
		self.assertIn("Stop recorded in docs/STOPS.md: no-work", self.out)

	def test_red_after_two_repairs_stops_with_the_failures(self):
		code = self.run_ci([0, 0, 0], ["red", "red", "red"])
		self.assertEqual(code, 0, self.out)
		self.assertEqual(self.calls("claude_calls"), 3, "the task's agent, then two repairs")
		self.assertIn("CI repair attempt 2 of 2", self.read("prompt-3"))
		self.assertEqual(self.calls("ci_heads"), 3, "CI was awaited on the task and on each repair")
		repairs = [s for s in self.origin_log() if s.startswith("SOS-LOOP: repair of the red CI")]
		self.assertEqual(len(repairs), 2, self.origin_log())
		last = self.notices()[-1]
		self.assertIn("CI is still red on the commit for SOS-X-1", last)
		self.assertIn("after 2 repair attempt(s). Stopping, nothing new started.", last)
		self.assertIn("AssertionError: 'In Progress' != 'Not Started'", last)
		self.assertRegex(
			self.ledger(), r"\| SOS-X-1 \| ci-red \| CI still red on [0-9a-f]+ .*after 2 repair attempt"
		)
		self.assertIn("Stop recorded in docs/STOPS.md: ci-red, SOS-X-1", self.out)

	def test_a_fault_outside_the_code_is_rerun_once_then_stops(self):
		code = self.run_ci([0], ["env", "env"])
		self.assertEqual(code, 0, self.out)
		self.assertEqual(self.calls("claude_calls"), 1, "no repair agent runs for the environment")
		self.assertEqual(self.calls("gate_calls"), 1)
		self.assertEqual(self.read("gh_reruns").splitlines(), ["run rerun 101 --failed"])
		notices = "\n".join(self.notices())
		self.assertIn(
			"the cause is outside the code: ##[error]The runner has received a shutdown signal", notices
		)
		self.assertIn("Rerunning the failed jobs once.", notices)
		self.assertIn("still red on the commit for SOS-X-1", self.notices()[-1])
		self.assertIn("after one rerun", self.notices()[-1])
		self.assertRegex(
			self.ledger(), r"\| SOS-X-1 \| environment \| CI red on [0-9a-f]+ .*still red after one rerun"
		)


class StatusCommitsAreNotPushedAlone(CiSandbox):
	def mark_in_progress_locally(self):
		self.write(self.repo / "TASKS.md", loop_env.TASKS_MD.replace("Not Started", "In Progress"))
		self.git("add", "TASKS.md")
		self.git("commit", "-q", "-m", f"{TASK}: mark In Progress")

	def test_a_status_commit_waits_for_the_completion_push(self):
		self.mark_in_progress_locally()
		code = self.run_ci([0], ["green"])
		self.assertEqual(code, 0, self.out)
		self.assertIn("Not pushing them alone", self.out)
		self.assertEqual(self.calls("ci_heads"), 1, "CI was awaited once, on the completion push only")
		self.assertEqual(self.read("ci_heads").strip(), self.git("rev-parse", "HEAD"))
		self.assertEqual(self.origin_log()[:2], [f"{TASK}: a task", f"{TASK}: mark In Progress"])

	def test_a_blocked_tasks_status_commit_stays_local(self):
		code = self.run_ci([1], [])
		self.assertEqual(code, 0, self.out)
		self.assertEqual(self.status(), "Blocked", self.out)
		self.assertEqual(self.git("rev-parse", "origin/1.0"), self.base, "a status commit was pushed")
		# The next start finds only status commits ahead and still pushes nothing.
		self.run_ci([], [])
		self.assertIn("Not pushing them alone", self.out)
		self.assertEqual(self.git("rev-parse", "origin/1.0"), self.base)
		self.assertEqual(self.calls("ci_heads"), 0, "CI never ran on a status commit")
