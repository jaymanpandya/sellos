"""SOS-SETUP-20: the BuildOS and SellOS loops run at the same time and share one bench gate lock.

The lock helper lives outside both repositories, at ~/iespl-baseline/bench-gate-lock.sh (or the path in
SELLOS_GATE_LOCK_HELPER), so these tests skip where it is not installed, as on CI. Every test uses a
fake lock directory in a throwaway folder, never the real /tmp/iespl-bench-heavy.lock.d.

* The helper, under macOS's bash 3.2: a free lock is taken and released, a held lock makes a waiter
  wait and then exit 3, a dead or too old holder is stolen with a warning, the lock is released when
  its holder fails or is killed, a long wait is notified once, and only the holder can release it.
* The real scripts/run-tests.sh: it takes the lock around its heavy segment, records the wait in its
  log, waits while another gate holds the lock, steals from a dead holder, releases the lock when it
  fails or is killed, and exits 3 when the helper is missing.
"""

import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from sellos.tests import test_loop_environment_failures as loop_env

HELPER = Path(
	os.environ.get("SELLOS_GATE_LOCK_HELPER") or Path.home() / "iespl-baseline" / "bench-gate-lock.sh"
)
BASH32 = "/bin/bash" if Path("/bin/bash").exists() else "bash"


def needs_helper(cls):
	return unittest.skipUnless(HELPER.is_file(), f"the bench gate lock helper is not installed at {HELPER}")(
		cls
	)


def live_process():
	return subprocess.Popen(["sleep", "300"])


def dead_pid():
	proc = subprocess.Popen(["true"])
	proc.wait()
	return proc.pid


def hold(lock_dir, owner, pid, start=None):
	lock_dir.mkdir(parents=True)
	(lock_dir / "owner").write_text(f"{owner}\n", encoding="utf-8")
	(lock_dir / "pid").write_text(f"{pid}\n", encoding="utf-8")
	(lock_dir / "start").write_text(f"{int(start or time.time())}\n", encoding="utf-8")


def wait_for(predicate, seconds=30):
	end = time.time() + seconds
	while time.time() < end:
		if predicate():
			return True
		time.sleep(0.2)
	return False


@needs_helper
class Helper(unittest.TestCase):
	def setUp(self):
		self.root = Path(tempfile.mkdtemp(prefix="sellos-gate-lock-"))
		self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
		self.lock = self.root / "heavy.lock.d"
		self.env = {
			**os.environ,
			"BENCH_GATE_LOCK_DIR": str(self.lock),
			"BENCH_GATE_POLL": "1",
		}

	def bash(self, script, extra_env=None, timeout=60):
		return subprocess.run(
			[BASH32, "-c", f'source "{HELPER}"\n{script}'],
			capture_output=True,
			text=True,
			env={**self.env, **(extra_env or {})},
			timeout=timeout,
		)

	def holder(self):
		proc = live_process()
		self.addCleanup(proc.wait)
		self.addCleanup(proc.kill)
		return proc

	def test_a_free_lock_is_taken_and_released(self):
		result = self.bash(
			'bench_gate_acquire "SellOS gate" 10\n'
			'cat "$BENCH_GATE_LOCK_DIR/owner"; cat "$BENCH_GATE_LOCK_DIR/pid"\n'
			'echo "waited=$BENCH_GATE_WAITED"\n'
			"bench_gate_release\n"
			'[ -d "$BENCH_GATE_LOCK_DIR" ] && echo still-held || echo gone\n'
		)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("SellOS gate\n", result.stdout)
		self.assertIn("waited=0", result.stdout)
		self.assertIn("gone", result.stdout)
		self.assertNotIn("still-held", result.stdout)

	def test_a_held_lock_makes_the_waiter_wait_then_exit_3(self):
		proc = self.holder()
		hold(self.lock, "BuildOS gate", proc.pid)
		result = self.bash("bench_gate_acquire 'SellOS gate' 3\necho acquired")
		self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
		self.assertIn(f"Waiting for BuildOS gate (pid {proc.pid}, running 0m)", result.stdout)
		self.assertIn("Gave up waiting for the bench gate lock", result.stderr)
		self.assertNotIn("acquired", result.stdout)
		self.assertEqual((self.lock / "owner").read_text(encoding="utf-8"), "BuildOS gate\n")

	def test_the_waiter_takes_the_lock_once_it_is_released(self):
		proc = self.holder()
		hold(self.lock, "BuildOS gate", proc.pid)
		waiter = subprocess.Popen(
			[BASH32, "-c", f'source "{HELPER}"\nbench_gate_acquire "SellOS gate" 60\necho acquired'],
			stdout=subprocess.PIPE,
			text=True,
			env=self.env,
		)
		time.sleep(2)
		self.assertIsNone(waiter.poll(), "the waiter did not wait")
		shutil.rmtree(self.lock)
		out, _ = waiter.communicate(timeout=30)
		self.assertEqual(waiter.returncode, 0)
		self.assertIn("Waiting for BuildOS gate", out)
		self.assertIn("acquired", out)

	def test_a_dead_holder_is_stolen_with_a_warning(self):
		hold(self.lock, "BuildOS gate", dead_pid())
		result = self.bash("bench_gate_acquire 'SellOS gate' 10\ncat \"$BENCH_GATE_LOCK_DIR/owner\"")
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("WARNING: stealing a stale bench gate lock from BuildOS gate", result.stderr)
		self.assertIn("SellOS gate", result.stdout)

	def test_a_holder_older_than_two_hours_is_stolen(self):
		proc = self.holder()
		hold(self.lock, "BuildOS gate", proc.pid, start=time.time() - 2 * 3600 - 60)
		result = self.bash("bench_gate_acquire 'SellOS gate' 10\ncat \"$BENCH_GATE_LOCK_DIR/owner\"")
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("WARNING: stealing a stale bench gate lock", result.stderr)
		self.assertIn("SellOS gate", result.stdout)

	def test_the_lock_is_released_when_the_holder_fails(self):
		result = self.bash("set -e\nbench_gate_acquire 'SellOS gate' 10\nfalse\necho not-reached")
		self.assertEqual(result.returncode, 1)
		self.assertNotIn("not-reached", result.stdout)
		self.assertFalse(self.lock.exists())

	def test_the_lock_is_released_when_the_holder_is_killed(self):
		for sig, code in ((signal.SIGTERM, 143), (signal.SIGINT, 130)):
			with self.subTest(sig=sig):
				proc = subprocess.Popen(
					[
						BASH32,
						"-c",
						f'source "{HELPER}"\nbench_gate_acquire "SellOS gate" 10\nwhile true; do sleep 1; done',
					],
					stdout=subprocess.DEVNULL,
					env=self.env,
				)
				self.assertTrue(wait_for(lambda: (self.lock / "start").exists()), "the lock was not taken")
				proc.send_signal(sig)
				self.assertEqual(proc.wait(timeout=30), code)
				self.assertFalse(self.lock.exists())

	def test_a_long_wait_is_notified_once(self):
		proc = self.holder()
		hold(self.lock, "BuildOS gate", proc.pid)
		notes = self.root / "notes"
		notify = self.root / "notify.sh"
		notify.write_text(f'#!/bin/bash\necho "$1" >>"{notes}"\n', encoding="utf-8")
		notify.chmod(0o755)
		result = self.bash(
			"bench_gate_acquire 'SellOS gate' 4",
			{"BENCH_GATE_NOTIFY": str(notify), "BENCH_GATE_NOTIFY_AFTER": "1"},
		)
		self.assertEqual(result.returncode, 3)
		lines = notes.read_text(encoding="utf-8").splitlines()
		self.assertEqual(len(lines), 1, lines)
		self.assertIn("SellOS gate has waited", lines[0])
		self.assertIn("held by BuildOS gate", lines[0])

	def test_only_the_holder_releases(self):
		proc = self.holder()
		hold(self.lock, "BuildOS gate", proc.pid)
		result = self.bash("bench_gate_release")
		self.assertEqual(result.returncode, 0)
		self.assertTrue(self.lock.exists())

	def test_the_helper_is_bash_3_2_compatible(self):
		version = subprocess.run([BASH32, "--version"], capture_output=True, text=True).stdout
		if "version 3.2" not in version:
			self.skipTest("no bash 3.2 on this machine")
		result = subprocess.run([BASH32, "-n", str(HELPER)], capture_output=True, text=True)
		self.assertEqual(result.returncode, 0, result.stderr)


@needs_helper
class GateTakesTheLock(loop_env.GateSandbox):
	"""The real scripts/run-tests.sh with the real helper and a fake lock directory."""

	def setUp(self):
		super().setUp()
		self.gate_lock_helper = HELPER
		self.lock = self.root / "bench-gate.lock.d"

	def holder(self):
		proc = live_process()
		self.addCleanup(proc.wait)
		self.addCleanup(proc.kill)
		return proc

	def test_a_free_lock_is_taken_recorded_and_released_when_the_gate_fails(self):
		self.serve(302)
		self.resolves()
		self.assertEqual(self.run_gate(), 1, self.out)
		self.assertIn("Bench gate lock taken by SellOS gate", self.out)
		self.assertIn("Bench gate lock wait: 0s", self.out)
		self.assertIn("fake bench failed", self.out)
		self.assertFalse(self.lock.exists(), "the failed gate left the lock behind")
		log = next(self.logs.glob("run-*.log")).read_text(encoding="utf-8")
		self.assertIn("Bench gate lock wait: 0s", log)

	def test_the_build_runs_before_the_lock(self):
		self.serve(302)
		self.resolves()
		self.run_gate()
		self.assertLess(self.out.index("--- Building web app"), self.out.index("--- Bench gate lock"))
		self.assertLess(self.out.index("--- Bench gate lock"), self.out.index("fake bench failed"))

	def test_a_held_lock_makes_the_gate_wait(self):
		self.serve(302)
		self.resolves()
		proc = self.holder()
		hold(self.lock, "BuildOS gate", proc.pid)
		self.assertEqual(self.run_gate({"SELLOS_GATE_LOCK_MAX_WAIT": "3"}), 3, self.out)
		self.assertIn(f"Waiting for BuildOS gate (pid {proc.pid}", self.out)
		self.assertIn("Gave up waiting for the bench gate lock", self.out)
		self.assertNotIn("fake bench failed", self.out, "the restore ran without the lock")
		self.assertEqual((self.lock / "owner").read_text(encoding="utf-8"), "BuildOS gate\n")

	def test_a_dead_holder_is_stolen(self):
		self.serve(302)
		self.resolves()
		hold(self.lock, "BuildOS gate", dead_pid())
		self.assertEqual(self.run_gate(), 1, self.out)
		self.assertIn("WARNING: stealing a stale bench gate lock from BuildOS gate", self.out)
		self.assertIn("fake bench failed", self.out)
		self.assertFalse(self.lock.exists())

	def test_the_lock_is_released_when_the_gate_is_killed(self):
		self.serve(302)
		self.resolves()
		self.write(self.bin / "bench", "#!/usr/bin/env bash\nsleep 30\n", 0o755)
		site = self.bench / "sites" / "sellos_test.localhost"
		site.mkdir(parents=True, exist_ok=True)
		shutil.copy2(self.bench / "sites" / loop_env.SITE / "site_config.json", site / "site_config.json")
		env = {
			**self.env(),
			"SELLOS_TEST_SITE": "sellos_test.localhost",
			"SELLOS_BASELINE_DIR": str(self.baseline),
			"SELLOS_GATE_LOCK_HELPER": str(HELPER),
		}
		gate = subprocess.Popen(
			["bash", str(self.repo / "scripts/run-tests.sh")],
			cwd=self.repo,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			env=env,
			start_new_session=True,
		)
		self.addCleanup(lambda: gate.poll() is None and os.killpg(gate.pid, signal.SIGKILL))
		self.assertTrue(wait_for(lambda: (self.lock / "start").exists(), 60), "the gate never took the lock")
		os.killpg(gate.pid, signal.SIGTERM)
		gate.wait(timeout=60)
		self.assertTrue(wait_for(lambda: not self.lock.exists(), 30), "the killed gate left the lock behind")

	def test_a_missing_helper_exits_3(self):
		self.serve(302)
		self.resolves()
		self.gate_lock_helper = self.root / "no-such-helper.sh"
		self.assertEqual(self.run_gate(), 3, self.out)
		self.assertIn("The bench gate lock helper is missing", self.out)
		self.assertNotIn("fake bench failed", self.out)
