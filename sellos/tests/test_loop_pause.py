"""SOS-SETUP-19: regression is a scheduled pause, not a gate.

scripts/pause-loop.sh creates the pause file and scripts/resume-loop.sh removes it. Before picking each
task the real scripts/build-loop.sh checks for the file. If it exists the loop picks nothing, changes
no status, starts no agent, notifies "Paused for regression" and stops.
"""

import os
import shutil
import subprocess

from sellos.tests import test_loop_environment_failures as loop_env

SCRIPTS = loop_env.SCRIPTS


class LoopPause(loop_env.LoopSandbox):
	def setUp(self):
		super().setUp()
		self.pause_file = self.root / "loop.pause"
		for name in ("pause-loop.sh", "resume-loop.sh"):
			shutil.copy2(SCRIPTS / name, self.repo / "scripts" / name)

	def switch(self, name):
		return subprocess.run(
			["bash", str(self.repo / "scripts" / name)],
			capture_output=True,
			text=True,
			env={**os.environ, "SELLOS_PAUSE_FILE": str(self.pause_file)},
			check=True,
		)

	def test_the_pause_scripts_create_and_remove_the_file(self):
		self.switch("pause-loop.sh")
		self.assertTrue(self.pause_file.exists())
		self.switch("resume-loop.sh")
		self.assertFalse(self.pause_file.exists())
		self.switch("resume-loop.sh")
		self.assertFalse(self.pause_file.exists())

	def test_the_scripts_default_to_the_tmp_pause_file(self):
		for name in ("pause-loop.sh", "resume-loop.sh", "build-loop.sh"):
			text = (SCRIPTS / name).read_text(encoding="utf-8")
			self.assertIn('"${SELLOS_PAUSE_FILE:-/tmp/sellos-loop.pause}"', text, name)

	def test_a_paused_loop_picks_nothing_and_says_so(self):
		self.serve(302)
		self.switch("pause-loop.sh")
		code = self.run_loop([0])
		self.assertEqual(code, 0, self.out)
		self.assertEqual(self.status(), "Not Started")
		self.assertEqual(self.calls("claude_calls"), 0)
		self.assertEqual(self.calls("gate_calls"), 0)
		self.assertEqual(self.git("rev-parse", "HEAD"), self.base)
		self.assertIn("Paused for regression", self.read("notifications"))

	def test_a_resumed_loop_picks_the_task(self):
		self.serve(302)
		self.switch("pause-loop.sh")
		self.switch("resume-loop.sh")
		# One failing gate run ends the loop quickly; a passing one would wait for CI.
		self.run_loop([1], max_runs=1)
		self.assertEqual(self.calls("claude_calls"), 1, self.out)
		self.assertEqual(self.calls("gate_calls"), 1, self.out)
		self.assertNotIn("Paused for regression", self.read("notifications"))
