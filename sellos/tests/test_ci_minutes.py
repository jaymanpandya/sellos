"""SOS-SETUP-28: CI minutes are a budget. Each job reports the runner minutes it used, the run reports
"runner minutes for this push: N", and the loop says when a red run's jobs never started.

scripts/lib/ci_minutes.py does the counting. These tests run it over a fake `gh` and check that
ci.yml and build-loop.sh use it.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "lib" / "ci_minutes.py"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
LOOP = REPO_ROOT / "scripts" / "build-loop.sh"

sys.path.insert(0, str(SCRIPT.parent))
import ci_minutes

NOW = datetime(2026, 11, 11, 12, 0, 0, tzinfo=UTC)


def job(name, start, end=None, conclusion="success", steps=1, attempt=1):
	return {
		"name": name,
		"started_at": start,
		"completed_at": end,
		"status": "completed" if end else "in_progress",
		"conclusion": conclusion if end else None,
		"steps": [{"name": "s"}] * steps,
		"run_attempt": attempt,
	}


class Counting(unittest.TestCase):
	def test_a_job_is_billed_its_wall_time_rounded_up(self):
		self.assertEqual(
			ci_minutes.job_minutes(job("A", "2026-11-11T11:50:00Z", "2026-11-11T11:59:42Z"), NOW), 10
		)
		self.assertEqual(
			ci_minutes.job_minutes(job("A", "2026-11-11T11:50:00Z", "2026-11-11T11:52:00Z"), NOW), 2
		)

	def test_a_short_job_costs_a_whole_minute(self):
		self.assertEqual(
			ci_minutes.job_minutes(job("A", "2026-11-11T11:59:50Z", "2026-11-11T11:59:52Z"), NOW), 1
		)

	def test_a_running_job_counts_up_to_now(self):
		self.assertEqual(ci_minutes.job_minutes(job("A", "2026-11-11T11:57:30Z"), NOW), 3)

	def test_a_skipped_or_unstarted_job_costs_nothing(self):
		self.assertEqual(ci_minutes.job_minutes(job("A", None, "2026-11-11T11:59:00Z"), NOW), 0)
		skipped = job("A", "2026-11-11T11:59:00Z", "2026-11-11T11:59:00Z", conclusion="skipped")
		self.assertEqual(ci_minutes.job_minutes(skipped, NOW), 0)

	def test_the_push_total_is_the_sum_of_its_jobs(self):
		jobs = [
			job("Server", "2026-11-11T11:50:00Z", "2026-11-11T11:59:42Z"),
			job("UI", "2026-11-11T11:50:00Z", "2026-11-11T11:56:03Z"),
			job("Frontend", "2026-11-11T11:50:00Z", "2026-11-11T11:50:22Z"),
		]
		self.assertEqual(ci_minutes.total_minutes(jobs, NOW), 10 + 7 + 1)

	def test_jobs_that_failed_before_any_step_are_named(self):
		jobs = [
			job("Server", "2026-11-11T11:50:00Z", "2026-11-11T11:50:01Z", conclusion="failure", steps=0),
			job("UI", "2026-11-11T11:50:00Z", "2026-11-11T11:55:00Z", conclusion="failure"),
			job("Frontend", "2026-11-11T11:50:00Z", "2026-11-11T11:50:22Z"),
		]
		self.assertEqual(ci_minutes.never_started(jobs), ["Server"])


FAKE_GH = """#!/usr/bin/env bash
echo "$*" >>"{dir}/calls"
case "$2" in
  *"/actions/runs?head_sha="*) cat "{dir}/runs.json" ;;
  *"/actions/runs/7/jobs"*) cat "{dir}/jobs-7.json" ;;
  *"/actions/runs/8/jobs"*) cat "{dir}/jobs-8.json" ;;
  *) echo "not found" >&2; exit 1 ;;
esac
"""


class Script(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-minutes-"))
		gh = self.dir / "gh"
		gh.write_text(FAKE_GH.format(dir=self.dir), encoding="utf-8")
		gh.chmod(0o755)
		self.summary = self.dir / "summary.md"
		(self.dir / "runs.json").write_text(json.dumps({"workflow_runs": [{"id": 7}, {"id": 8}]}))
		(self.dir / "jobs-7.json").write_text(
			json.dumps(
				{
					"jobs": [
						job("Server", "2026-11-11T11:50:00Z", "2026-11-11T11:59:42Z", attempt=2),
						job("UI", "2026-11-11T11:50:00Z", "2026-11-11T11:56:03Z", attempt=2),
						job("UI", "2026-11-11T10:00:00Z", "2026-11-11T10:04:10Z", attempt=1),
					]
				}
			)
		)
		(self.dir / "jobs-8.json").write_text(
			json.dumps({"jobs": [job("Frappe Linter", "2026-11-11T11:50:00Z", "2026-11-11T11:50:33Z")]})
		)

	def tearDown(self):
		for p in self.dir.iterdir():
			p.unlink()
		self.dir.rmdir()

	def run_script(self, *args, run_id="7"):
		env = {
			**os.environ,
			"PATH": f"{self.dir}:{os.environ['PATH']}",
			"GITHUB_REPOSITORY": "owner/sellos",
			"GITHUB_RUN_ID": run_id,
			"GITHUB_RUN_ATTEMPT": "2",
			"GITHUB_SHA": "abc123",
			"GITHUB_STEP_SUMMARY": str(self.summary),
		}
		return subprocess.run(
			["python3", str(SCRIPT), *args], capture_output=True, text=True, env=env, check=False
		)

	def summary_text(self):
		return self.summary.read_text() if self.summary.exists() else ""

	def test_a_job_writes_its_own_minutes_of_this_attempt_to_its_summary(self):
		result = self.run_script("job", "UI")
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("**UI: 7 runner minutes**", self.summary_text())  # not the first attempt's 5

	def test_the_push_line_counts_every_job_of_every_run_on_the_commit(self):
		result = self.run_script("push")
		self.assertEqual(result.returncode, 0, result.stderr)
		# Server 10, UI 7, the earlier UI attempt 5, the Linters job 1.
		self.assertIn("runner minutes for this push: 23", self.summary_text())
		self.assertIn("| Frappe Linter | 1 |", self.summary_text())
		self.assertIn("head_sha=abc123", (self.dir / "calls").read_text())

	def test_an_api_failure_is_reported_and_never_fails_the_job(self):
		result = self.run_script("job", "UI", run_id="99")
		self.assertEqual(result.returncode, 0)
		self.assertIn("UI: runner minutes could not be read", self.summary_text())

	def test_never_started_prints_only_jobs_with_no_steps(self):
		(self.dir / "jobs-7.json").write_text(
			json.dumps(
				{
					"jobs": [
						job("Server", "2026-11-11T11:50:00Z", "2026-11-11T11:50:01Z", "failure", steps=0),
						job("UI", "2026-11-11T11:50:00Z", "2026-11-11T11:50:01Z", "failure", steps=0),
					]
				}
			)
		)
		self.assertEqual(self.run_script("never-started", "7").stdout.strip(), "Server, UI")
		(self.dir / "jobs-7.json").write_text(
			json.dumps({"jobs": [job("UI", "2026-11-11T11:50:00Z", "2026-11-11T11:55:00Z", "failure")]})
		)
		self.assertEqual(self.run_script("never-started", "7").stdout, "")


class Wiring(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.ci = CI.read_text(encoding="utf-8")

	def test_every_job_reports_its_minutes(self):
		for name in ("Frontend", "Server", "UI"):
			self.assertRegex(self.ci, rf"scripts/lib/ci_minutes\.py\"? job {name}\n")
		self.assertEqual(self.ci.count("- name: Runner minutes (SOS-SETUP-28)\n        if: always()"), 3)

	def test_the_last_job_reports_the_push_whatever_the_others_did(self):
		block = self.ci[self.ci.index("\n  minutes:\n") :]
		self.assertIn("needs: [frontend, tests, ui]", block)
		self.assertIn("if: always()", block)
		self.assertIn("python3 scripts/lib/ci_minutes.py push", block)

	def test_the_token_may_read_actions(self):
		self.assertRegex(self.ci, r"(?m)^permissions:\n  contents: read\n  actions: read\n")

	def test_the_bench_is_cached_in_server_and_ui_without_the_app(self):
		self.assertEqual(
			self.ci.count(
				"uses: actions/cache/restore@v4\n        with:\n          path: |\n            /home/runner/frappe-bench\n            !/home/runner/frappe-bench/apps/sellos"
			),
			2,
		)
		self.assertEqual(
			len(
				re.findall(
					r"if \[ \"\$\{\{ steps\.bench-cache\.outputs\.cache-hit \}\}\" != \"true\" \]", self.ci
				)
			),
			2,
		)

	def test_the_loop_names_a_run_whose_jobs_never_started(self):
		loop = LOOP.read_text(encoding="utf-8")
		self.assertIn('ci_minutes.py" never-started "$id"', loop)
		self.assertEqual(loop.count("${CI_RED_REASON:+ $CI_RED_REASON}"), 2)
