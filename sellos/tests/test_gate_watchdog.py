"""SOS-SETUP-39: a hung or frozen gate is impossible to miss and impossible to leave stuck.

On 17 November 2026 the gate held the bench lock for 5 hours after the Mac slept on battery power. Every
test here uses fakes: fake commands that hang, fake Cypress processes, fake pmset output, a fake gate.

a. hard timeouts: the helper, the limits inside the gate, and the loop's rerun-once-then-stop rule
b. the stall watchdog: no new line in the log for the stall limit is a timeout too
d. leftover Cypress and headless Chrome processes: only SellOS's own are killed
c. power: the warning text, and caffeinate in "sellos up"
e. status names the gate's real log path
"""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from sellos.tests import test_loop_environment_failures as loop_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
WATCH = SCRIPTS / "lib" / "gate_watch.py"
SELLOS = SCRIPTS / "sellos"


def alive(pid):
	try:
		os.kill(pid, 0)
	except ProcessLookupError:
		return False
	return True


def wait_dead(pid, seconds=10):
	end = time.time() + seconds
	while time.time() < end:
		if not alive(pid):
			return True
		time.sleep(0.1)
	return False


def wait_for_file(path, seconds=10):
	end = time.time() + seconds
	while time.time() < end:
		if path.exists() and path.read_text().strip():
			return path.read_text().strip()
		time.sleep(0.1)
	raise AssertionError(f"{path} was never written")


class Folder(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-watch-"))
		self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
		self.pids = []
		self.addCleanup(self.kill_all)

	def kill_all(self):
		for pid in self.pids:
			try:
				os.kill(pid, signal.SIGKILL)
			except (ProcessLookupError, PermissionError):
				pass

	def watch(self, *args, env=None, timeout=60):
		result = subprocess.run(
			[sys.executable, str(WATCH), *args],
			capture_output=True,
			text=True,
			timeout=timeout,
			env={**os.environ, **(env or {})},
		)
		return result.returncode, result.stdout + result.stderr


class TimeoutAndStall(Folder):
	def hanging_command(self):
		"""bash starts a sleeping grandchild and waits for it. The grandchild's pid goes to a file."""
		pidfile = self.dir / "grandchild.pid"
		return pidfile, ["bash", "-c", f"sleep 300 & echo $! >{pidfile}; wait"]

	def test_a_command_past_its_timeout_is_killed_with_its_whole_tree(self):
		pidfile, command = self.hanging_command()
		fault = self.dir / "fault.txt"
		code, out = self.watch(
			"run", "--label", "the fake gate", "--timeout", "2", "--poll", "0.2",
			"--fault-file", str(fault), "--", *command,
		)  # fmt: skip
		self.assertEqual(code, 124, out)
		self.assertIn("GATE TIMEOUT", out)
		grandchild = int(pidfile.read_text())
		self.pids.append(grandchild)
		self.assertTrue(wait_dead(grandchild), "the command's child is still running")
		self.assertIn("gate timeout: the fake gate ran longer than its limit", fault.read_text())

	def test_a_command_that_finishes_keeps_its_status_and_output(self):
		code, out = self.watch("run", "--timeout", "30", "--", "bash", "-c", "echo hello; exit 7")
		self.assertEqual(code, 7, out)
		self.assertIn("hello", out)
		self.assertNotIn("GATE TIMEOUT", out)

	def test_a_stalled_log_kills_the_tree_and_a_live_log_does_not(self):
		log = self.dir / "loop.log"
		log.write_text("start\n")
		pidfile, command = self.hanging_command()
		fault = self.dir / "fault.txt"
		code, out = self.watch(
			"run", "--label", "the fake gate", "--timeout", "600", "--stall", "2", "--stall-file", str(log),
			"--poll", "0.2", "--fault-file", str(fault), "--", *command,
		)  # fmt: skip
		self.assertEqual(code, 125, out)
		self.pids.append(int(pidfile.read_text()))
		self.assertTrue(wait_dead(self.pids[-1]))
		self.assertIn("wrote nothing", fault.read_text())
		# The same stall limit does not fire while the command keeps writing.
		writer = f"for i in 1 2 3 4 5 6; do echo line >>{log}; sleep 0.5; done"
		code, out = self.watch(
			"run", "--timeout", "600", "--stall", "2", "--stall-file", str(log), "--poll", "0.2",
			"--", "bash", "-c", writer,
		)  # fmt: skip
		self.assertEqual(code, 0, out)

	def test_the_bench_lock_of_a_killed_gate_is_released(self):
		lock = self.dir / "bench.lock.d"
		script = f"mkdir {lock}; echo $$ >{lock}/pid; echo gate >{lock}/owner; sleep 300"
		code, out = self.watch(
			"run", "--timeout", "2", "--poll", "0.2", "--", "bash", "-c", script,
			env={"BENCH_GATE_LOCK_DIR": str(lock)},
		)  # fmt: skip
		self.assertEqual(code, 124, out)
		self.assertFalse(lock.exists(), "the lock is still held")
		self.assertIn("Released the bench gate lock", out)

	def test_a_lock_held_by_a_live_process_that_is_not_ours_stays(self):
		lock = self.dir / "bench.lock.d"
		other = subprocess.Popen(["sleep", "300"])
		self.pids.append(other.pid)
		lock.mkdir()
		(lock / "pid").write_text(f"{other.pid}\n")
		code, out = self.watch(
			"run", "--timeout", "1", "--poll", "0.2", "--", "sleep", "300",
			env={"BENCH_GATE_LOCK_DIR": str(lock)},
		)  # fmt: skip
		self.assertEqual(code, 124, out)
		self.assertTrue(lock.exists(), "another gate's lock was released")

	def test_a_term_to_the_watch_kills_the_tree(self):
		pidfile, command = self.hanging_command()
		proc = subprocess.Popen(
			[sys.executable, str(WATCH), "run", "--timeout", "600", "--poll", "0.2", "--", *command]
		)
		self.pids.append(proc.pid)
		grandchild = int(wait_for_file(pidfile))
		self.pids.append(grandchild)
		proc.send_signal(signal.SIGTERM)
		self.assertEqual(proc.wait(timeout=20), 143)
		self.assertTrue(wait_dead(grandchild), "sellos stop --now would leave the gate running")


class LimitsInsideTheGate(Folder):
	"""scripts/lib/gate_limits.sh, ui_flaky.sh and db_conflict.sh with a fake bench that hangs."""

	def setUp(self):
		super().setUp()
		self.bin = self.dir / "bin"
		self.bin.mkdir()
		self.fault = self.dir / "fault.txt"
		self.env = {
			**os.environ,
			"PATH": f"{self.bin}:{os.environ['PATH']}",
			"SITE": "test.localhost",
			"APP": "sellos",
			"SELLOS_GATE_FAULT_FILE": str(self.fault),
			"SELLOS_GATE_LIMITS": "1",
		}

	def fake(self, name, body):
		path = self.bin / name
		path.write_text(f"#!/usr/bin/env bash\n{body}\n")
		path.chmod(0o755)

	def bash(self, script, **env):
		result = subprocess.run(
			["bash", "-c", script],
			capture_output=True,
			text=True,
			timeout=60,
			env={**self.env, **env},
		)
		return result.returncode, result.stdout + result.stderr

	def test_a_hung_spec_ends_the_gate_with_status_4(self):
		self.fake("bench", "sleep 300")
		code, out = self.bash(
			f"source {SCRIPTS}/lib/ui_flaky.sh; _sellos_ui_run {self.dir}/ui.log crm/a.cy.js; echo STILL-RUNNING",
			SELLOS_SPEC_TIMEOUT="2",
		)
		self.assertEqual(code, 4, out)
		self.assertNotIn("STILL-RUNNING", out)
		self.assertIn("GATE TIMEOUT", out)
		self.assertIn("the Cypress spec crm/a.cy.js", self.fault.read_text())

	def test_a_hung_whole_suite_has_its_own_limit(self):
		self.fake("bench", "sleep 300")
		code, out = self.bash(
			f"source {SCRIPTS}/lib/ui_flaky.sh; _sellos_ui_run {self.dir}/ui.log; echo STILL-RUNNING",
			SELLOS_UI_SUITE_TIMEOUT="2",
		)
		self.assertEqual(code, 4, out)
		self.assertIn("the whole Cypress suite", self.fault.read_text())

	def test_a_hung_backend_suite_ends_the_gate_with_status_4(self):
		self.fake("bench", "sleep 300")
		self.fake("report", 'exec "$@"')
		code, out = self.bash(
			f"export REPORT_TEST_EXIT={self.bin}/report DB_CONFLICT=/nonexistent;"
			f" source {SCRIPTS}/lib/db_conflict.sh; run_backend {self.dir}/b.log; echo STILL-RUNNING",
			SELLOS_BACKEND_TIMEOUT="2",
		)
		self.assertEqual(code, 4, out)
		self.assertNotIn("STILL-RUNNING", out)
		self.assertIn("the backend tests", self.fault.read_text())

	def test_a_spec_inside_its_limit_passes_through(self):
		self.fake("bench", 'echo "ran $*"')
		code, out = self.bash(
			f"source {SCRIPTS}/lib/ui_flaky.sh; _sellos_ui_run {self.dir}/ui.log crm/a.cy.js; echo status=$?",
			SELLOS_SPEC_TIMEOUT="30",
		)
		self.assertEqual(code, 0, out)
		self.assertIn("status=0", out)
		self.assertIn("--spec cypress/integration/crm/a.cy.js", out)

	def test_without_the_gate_the_limits_are_off(self):
		"""CI sources the same libraries and must run the commands as it always did."""
		self.fake("bench", 'echo "ran $*"; exit 5')
		env = {k: v for k, v in self.env.items() if k != "SELLOS_GATE_LIMITS"}
		result = subprocess.run(
			["bash", "-c", f"source {SCRIPTS}/lib/ui_flaky.sh; _sellos_ui_run {self.dir}/ui.log crm/a.cy.js; echo status=$?"],
			capture_output=True, text=True, timeout=60, env=env,
		)  # fmt: skip
		self.assertIn("status=5", result.stdout)
		self.assertNotIn("GATE TIMEOUT", result.stdout)

	def test_the_limits_are_measured_not_guessed(self):
		"""The gate's limits sit well above its measured times (docs/STOPS.md) and well below 5 hours."""
		ui = (SCRIPTS / "lib" / "ui_flaky.sh").read_text()
		db = (SCRIPTS / "lib" / "db_conflict.sh").read_text()
		loop = (SCRIPTS / "build-loop.sh").read_text()
		self.assertIn("SELLOS_SPEC_TIMEOUT:-900", ui)
		self.assertIn("SELLOS_UI_SUITE_TIMEOUT:-2700", ui)
		self.assertIn("SELLOS_BACKEND_TIMEOUT:-2700", db)
		self.assertIn("SELLOS_GATE_TIMEOUT:-9000", loop)
		self.assertIn("SELLOS_STALL_TIMEOUT:-900", loop)


class Leftovers(Folder):
	"""Only SellOS's own Cypress and headless Chrome processes are killed."""

	def setUp(self):
		super().setUp()
		self.tag = f"test-{uuid.uuid4().hex}"

	def start(self, name, *args, tag=None):
		"""A fake process named `name`, started so that its parent is gone (adopted by launchd)."""
		# Run by Python, not /bin/sh: macOS hides the environment of Apple's own binaries, but not of
		# Cypress, Electron and Chrome, which is what the cleanup looks at.
		script = self.dir / f"{name}.py"
		script.write_text(
			"import os, sys, time\nopen(sys.argv[1], 'w').write(str(os.getpid()))\nwhile True: time.sleep(1)\n"
		)
		pidfile = self.dir / f"{name}.pid"
		pidfile.unlink(missing_ok=True)
		env = {k: v for k, v in os.environ.items() if k != "SELLOS_GATE_TAG"}
		if tag:
			env["SELLOS_GATE_TAG"] = tag
		subprocess.run(
			[
				"bash",
				"-c",
				f'"{sys.executable}" "{script}" "{pidfile}" {" ".join(args)} >/dev/null 2>&1 & disown',
			],
			env=env,
			check=True,
		)
		pid = int(wait_for_file(pidfile))
		self.pids.append(pid)
		return pid

	def cleanup(self, tag=None):
		return self.watch("cleanup", "--tag", tag or self.tag)

	def test_only_sellos_own_cypress_and_headless_chrome_are_killed(self):
		ours_cypress = self.start("cypress-run", tag=self.tag)
		ours_chrome = self.start("fake-chrome", "--headless=new", tag=self.tag)
		buildos_cypress = self.start("cypress-run-buildos", tag=None)
		other_tag = self.start("cypress-run-pamaa", tag=f"test-{uuid.uuid4().hex}")
		browser = self.start("fake-chrome-windowed", tag=self.tag)
		bystander = self.start("some-server", tag=self.tag)
		code, out = self.cleanup()
		self.assertEqual(code, 0, out)
		self.assertTrue(wait_dead(ours_cypress), "SellOS's Cypress was left behind")
		self.assertTrue(wait_dead(ours_chrome), "SellOS's headless Chrome was left behind")
		for pid, what in (
			(buildos_cypress, "BuildOS's Cypress, which has no SellOS tag"),
			(other_tag, "a Cypress with another tag"),
			(browser, "a Chrome that is not headless"),
			(bystander, "a tagged process that is not Cypress or Chrome"),
		):
			self.assertTrue(alive(pid), f"{what} was killed")
		self.assertIn("Killing a leftover of SellOS's own", out)

	def test_nothing_is_killed_without_a_tag(self):
		code, out = self.watch("cleanup")
		self.assertNotEqual(code, 0, out)
		code, out = self.watch("cleanup", "--tag", "")
		self.assertNotEqual(code, 0, out)

	def test_a_run_with_nothing_to_clean_is_quiet(self):
		code, out = self.cleanup()
		self.assertEqual(code, 0, out)
		self.assertNotIn("Killing", out)


class Power(Folder):
	def pmset(self, text, *args):
		path = self.dir / "pmset.txt"
		path.write_text(text)
		return self.watch("power", *args, env={"SELLOS_PMSET_FILE": str(path)})

	def test_battery_power_is_a_warning(self):
		code, out = self.pmset(
			"Now drawing from 'Battery Power'\n -InternalBattery-0\t62%; discharging\n", "--warn"
		)
		self.assertEqual(code, 1, out)
		self.assertIn("on battery power, 62%", out)

	def test_below_30_percent_is_a_warning_even_on_ac(self):
		code, out = self.pmset("Now drawing from 'AC Power'\n -InternalBattery-0\t17%; charging\n", "--warn")
		self.assertEqual(code, 1, out)
		self.assertIn("on AC power, 17%", out)

	def test_ac_power_above_30_percent_is_fine(self):
		code, out = self.pmset("Now drawing from 'AC Power'\n -InternalBattery-0\t85%; charged\n", "--warn")
		self.assertEqual(code, 0, out)

	def test_a_mac_with_no_battery_is_fine(self):
		code, out = self.pmset("Now drawing from 'AC Power'\n", "--warn")
		self.assertEqual(code, 0, out)

	def test_without_warn_it_only_reports(self):
		code, out = self.pmset("Now drawing from 'Battery Power'\n -InternalBattery-0\t10%\n")
		self.assertEqual(code, 0, out)

	def test_sellos_up_starts_the_loop_under_caffeinate(self):
		text = SELLOS.read_text()
		self.assertIn("-i -m -s", text)
		self.assertIn("caffeinate", text)
		self.assertIn('SELLOS_LOOP_LOG="$LOOP_LOG"', text)
		self.assertIn('lib/gate_watch.py" power --warn', text)


class LoopGateTimeouts(loop_env.LoopSandbox):
	"""The real build loop with a fake gate: a timeout is rerun once, then the loop stops."""

	def setUp(self):
		super().setUp()
		self.serve(302)

	def stops(self):
		return (self.repo / "docs" / "STOPS.md").read_text()

	def assert_no_repair(self):
		self.assertEqual(self.calls("claude_calls"), 1, "a repair run was started")
		self.assertEqual(self.status(), "In Progress")
		self.assertEqual(self.git("branch", "--list", "failed/*"), "", "the task was reset")

	def test_two_timeouts_in_a_row_stop_the_loop_after_one_rerun(self):
		code = self.run_loop([4, 4], max_runs=3)
		self.assertEqual(code, 3, self.out)
		self.assertEqual(self.calls("gate_calls"), 2, "the gate runs once more, and only once")
		self.assert_no_repair()
		notes = self.read("notifications")
		self.assertIn("GATE TIMEOUT. ", notes)
		self.assertIn("GATE TIMEOUT again", notes)
		self.assertIn("| gate timeout |", self.stops())
		self.assertNotIn("failed tests", notes)

	def test_one_timeout_then_a_pass_goes_on(self):
		code = self.run_loop([4, 1], max_runs=1)
		self.assertEqual(self.calls("gate_calls"), 2, self.out)
		self.assertNotIn("GATE TIMEOUT again", self.read("notifications"))
		self.assertIn("GATE TIMEOUT. ", self.read("notifications"))
		self.assertNotIn("| gate timeout |", self.stops())
		self.assertNotEqual(code, 99)

	def test_a_gate_that_hangs_is_killed_by_the_loop_and_rerun_once(self):
		hang = (
			'#!/usr/bin/env bash\necho run >>"$FAKE_DIR/gate_calls"\n'
			'sleep 300 & echo $! >>"$FAKE_DIR/hung_pids"\nwait\n'
		)
		self.write(self.repo / "scripts/run-tests.sh", hang, 0o755)
		code = self.run_loop([0], extra_env={"SELLOS_GATE_TIMEOUT": "2"})
		self.assertEqual(code, 3, self.out)
		self.assertEqual(self.calls("gate_calls"), 2)
		for pid in self.read("hung_pids").split():
			self.pids_to_check = int(pid)
			self.assertTrue(wait_dead(int(pid)), "the hung gate's child is still running")
		self.assert_no_repair()
		self.assertIn("| gate timeout |", self.stops())
		self.assertIn("ran longer than its limit", self.read("notifications"))

	def test_a_silent_loop_log_is_a_stall(self):
		hang = (
			'#!/usr/bin/env bash\necho run >>"$FAKE_DIR/gate_calls"\n'
			'sleep 300 & echo $! >>"$FAKE_DIR/hung_pids"\nwait\n'
		)
		self.write(self.repo / "scripts/run-tests.sh", hang, 0o755)
		log = self.root / "loop.log"
		log.write_text("the loop started\n")
		code = self.run_loop(
			[0],
			extra_env={
				"SELLOS_STALL_TIMEOUT": "2",
				"SELLOS_LOOP_LOG": str(log),
				"SELLOS_GATE_TIMEOUT": "600",
			},
		)
		self.assertEqual(code, 3, self.out)
		self.assertEqual(self.calls("gate_calls"), 2)
		self.assertIn("wrote nothing", self.read("notifications"))
		self.assertIn("| gate timeout |", self.stops())

	def test_the_bench_lock_of_a_killed_gate_is_released_before_the_rerun(self):
		lock = self.root / "bench-gate.lock.d"
		hang = (
			'#!/usr/bin/env bash\necho run >>"$FAKE_DIR/gate_calls"\n'
			f"mkdir -p {lock}; echo $$ >{lock}/pid\n"
			"sleep 300\n"
		)
		self.write(self.repo / "scripts/run-tests.sh", hang, 0o755)
		code = self.run_loop([0], extra_env={"SELLOS_GATE_TIMEOUT": "2"})
		self.assertEqual(code, 3, self.out)
		self.assertFalse(lock.exists(), "the bench lock was left held")

	def test_a_battery_warning_goes_to_telegram_at_each_task_start(self):
		self.write(
			self.fake / "pmset.txt",
			"Now drawing from 'Battery Power'\n -InternalBattery-0\t17%; discharging\n",
		)
		self.run_loop([4, 4], max_runs=1)
		self.assertIn(
			f"starting {loop_env.TASK} with the Mac on battery power, 17%", self.read("notifications")
		)

	def test_no_warning_on_ac_power(self):
		self.run_loop([4, 4], max_runs=1)
		self.assertNotIn("with the Mac on", self.read("notifications"))

	def test_the_loop_cleans_up_before_the_gate_and_after_the_stop(self):
		self.run_loop([4, 4], max_runs=1)
		self.assertGreaterEqual(self.out.count("leftover Cypress and Chrome processes (before the gate)"), 2)
		self.assertIn("(after the stop)", self.out)


class StatusNamesTheGateLog(Folder):
	def test_status_shows_the_real_log_path_and_when_it_was_written(self):
		logs = self.dir / "logs"
		logs.mkdir()
		real = logs / "run-20261117-081711.log"
		real.write_text("--- Preflight ---\n")
		(logs / "latest.log").symlink_to(real)
		tasks = self.dir / "TASKS.md"
		tasks.write_text("### SOS-A-1: one\n- **Status:** Not Started\n")
		result = subprocess.run(
			[str(SELLOS), "status"],
			capture_output=True,
			text=True,
			timeout=90,
			env={
				**os.environ,
				"SELLOS_LOG_DIR": str(logs),
				"SELLOS_LOOP_LOCK": str(self.dir / "lock"),
				"SELLOS_LOOP_LOG": str(self.dir / "loop.log"),
				"SELLOS_TASKS_FILE": str(tasks),
			},
		)
		out = result.stdout + result.stderr
		self.assertIn("== Gate log", out)
		self.assertIn(str(real), out)
		self.assertIn("last written 0 min ago", out)

	def test_the_gate_points_latest_log_at_its_log_from_the_first_line(self):
		text = (SCRIPTS / "run-tests.sh").read_text()
		start = text.index('ln -sf "$LOG_FILE" "$LOG_DIR/latest.log"')
		self.assertLess(start, text.index('echo "=== SellOS test run'))
		self.assertNotIn('rm -f "$LOG_DIR/latest.log"', text)


if __name__ == "__main__":
	unittest.main()
