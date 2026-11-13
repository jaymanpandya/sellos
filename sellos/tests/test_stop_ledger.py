"""SOS-SETUP-33: every stop of the loop is in docs/STOPS.md, with the hours since the last one.

scripts/lib/stops.py is tested on its own, then the real scripts/build-loop.sh is run in the
throwaway repository of test_loop_environment_failures.py and made to stop.
"""

import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sellos.tests import test_loop_environment_failures as loop_env

REPO_ROOT = Path(__file__).resolve().parents[2]
STOPS = REPO_ROOT / "scripts" / "lib" / "stops.py"


def stops(*args, cwd=None):
	return subprocess.run(
		["python3", str(STOPS), *map(str, args)], capture_output=True, text=True, check=True, cwd=cwd
	).stdout.strip()


def git(repo, *args):
	return subprocess.run(
		["git", "-c", "user.name=Ledger Test", "-c", "user.email=ledger@test.invalid", *args],
		cwd=repo,
		capture_output=True,
		text=True,
		check=True,
	).stdout.strip()


class TestStopsScript(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-stops-"))
		self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(self.dir)]))
		self.file = self.dir / "STOPS.md"

	def test_a_stop_is_a_row_with_every_column(self):
		self.assertEqual(stops("since", self.file), "never")
		stops("record", self.file, "SOS-P1-07", "blocked", "the gate failed | twice", "42")
		text = self.file.read_text()
		self.assertIn(
			"| Time (UTC) | Task | Category | Cause | Attempt lost (min) | Idle until restart (h) |", text
		)
		row = text.strip().splitlines()[-1]
		self.assertRegex(
			row,
			r"^\| \d{4}-\d\d-\d\d \d\d:\d\d \| SOS-P1-07 \| blocked \| the gate failed / twice \| 42 \|  \|$",
		)
		self.assertEqual(stops("since", self.file), "0.0")

	def test_the_restart_fills_the_idle_time_once(self):
		stops("record", self.file, "-", "start", "gh is not signed in", "0")
		earlier = (datetime.now(UTC) - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
		self.file.write_text(self.file.read_text().replace(datetime.now(UTC).strftime("%Y-%m-%d"), "X", 0))
		text = self.file.read_text()
		last = text.strip().splitlines()[-1]
		self.file.write_text(text.replace(last, "| " + earlier + last[18:]))
		stops("restarted", self.file)
		self.assertTrue(self.file.read_text().strip().endswith("| 3.0 |"), self.file.read_text())
		stops("restarted", self.file)
		self.assertTrue(self.file.read_text().strip().endswith("| 3.0 |"))

	def test_the_streak_counts_finished_tasks_since_the_last_unplanned_stop(self):
		repo = self.dir / "repo"
		repo.mkdir()
		git(repo, "init", "-q")
		stops("record", self.file, "SOS-A-1", "blocked", "old", "5")
		older = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
		text = self.file.read_text()
		last = text.strip().splitlines()[-1]
		self.file.write_text(text.replace(last, "| " + older + last[18:]))
		for subject in (
			"SOS-A-2: mark In Progress",
			"SOS-A-2: Build the thing",
			"SOS-SETUP-40: a human change",
			"SOS-LOOP: the last stop and the restart, in docs/STOPS.md",
			"SOS-A-3: Build the other thing",
		):
			git(repo, "commit", "-q", "--allow-empty", "-m", subject)
		stops("record", self.file, "-", "paused", "regression", "0")
		self.assertEqual(stops("streak", self.file, repo), "2")
		summary = stops("summary", self.file, repo)
		self.assertIn("2 task(s) finished since the last unplanned stop (8 more for the exit test)", summary)


class LoopRecordsItsStops(loop_env.LoopSandbox):
	def ledger(self):
		path = self.repo / "docs" / "STOPS.md"
		return path.read_text(encoding="utf-8") if path.exists() else ""

	def test_a_blocked_task_is_recorded_with_its_task_and_the_hours_are_printed(self):
		self.serve(302)
		self.run_loop([1], max_runs=1)
		self.assertEqual(self.status(), "Blocked", self.out)
		self.assertRegex(
			self.ledger(), rf"\| {loop_env.TASK} \| blocked \| the gate still failed after 1 gate run"
		)
		self.assertIn("Stop recorded in docs/STOPS.md: blocked", self.out)
		self.assertIn("hours since the last stop", self.out)

	def test_a_pause_is_recorded_and_the_next_start_commits_it_with_the_idle_time(self):
		self.serve(302)
		pause = self.root / "loop.pause"
		pause.write_text("paused\n")
		env = {"SELLOS_PAUSE_FILE": str(pause)}
		self.run_loop([0], extra_env=env)
		self.assertRegex(self.ledger(), r"\| - \| paused \| the regression pause file exists \| 0 \|  \|")
		self.assertEqual(self.git("rev-parse", "HEAD"), self.base, "a stop commits nothing")
		self.run_loop([0], extra_env=env)
		self.assertEqual(
			self.git("log", "-1", "--format=%s"),
			"SOS-LOOP: the last stop and the restart, in docs/STOPS.md [skip ci]",
		)
		rows = [line for line in self.ledger().splitlines() if line.startswith("| 20")]
		self.assertEqual(len(rows), 2)
		self.assertRegex(rows[0], r"\| \d+\.\d \|$", "the restart filled in the idle time")


class TheExitTest(unittest.TestCase):
	def test_dev_strategy_states_the_exit_test(self):
		text = (REPO_ROOT / "docs" / "DEV_STRATEGY.md").read_text(encoding="utf-8")
		self.assertIn("ten consecutive tasks without a stop", text)
		self.assertIn("docs/STOPS.md", text)
