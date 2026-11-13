"""SOS-SETUP-34: no commit the loop makes ever holds a CI skip marker.

On 13 November 2026 the message of 5e46d53 named "[skip ci]" in passing, GitHub skipped CI on it, and
CI ran again only on the next push. scripts/lib/commit_message.py takes every marker out, and every
commit in scripts/build-loop.sh goes through loop_commit, which calls it. The last test runs the real
loop in the sandbox of test_loop_environment_failures.py with an agent whose summary holds markers.
"""

import importlib.util
import re
import subprocess
import unittest
from pathlib import Path

from sellos.tests import test_loop_environment_failures as loop_env

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "lib" / "commit_message.py"
LOOP = REPO_ROOT / "scripts" / "build-loop.sh"

_spec = importlib.util.spec_from_file_location("commit_message", SCRIPT)
commit_message = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(commit_message)

MARKERS = (
	"[skip ci]",
	"[ci skip]",
	"[SKIP CI]",
	"[Skip-CI]",
	"[ci_skip]",
	"[ no ci ]",
	"[skip actions]",
	"[actions skip]",
	"[skip checks]",
	"skip-checks: true",
	"skip-checks:true",
	"Skip_Checks = true",
	"***NO_CI***",
)
# What GitHub looks for, case-insensitively, after the markers are gone.
LEFT_OVER = re.compile(
	r"\[\s*(skip|ci|no|actions)[\s_-]*(ci|skip|actions|checks)\s*\]|skip[\s_-]*checks|no_ci", re.I
)
AGENT_WITH_MARKERS = """#!/usr/bin/env bash
echo call >>"$FAKE_DIR/claude_calls"
echo "work $(wc -l <"$FAKE_DIR/claude_calls" | tr -d ' ')" >>sellos/work.py
echo "IMPLEMENTATION_READY: built it [skip ci] and [ci skip], skip-checks: true, ***NO_CI*** done"
"""
# CI is green: one run for the commit, and watching it succeeds.
GREEN_GH = """#!/usr/bin/env bash
[ "$1 $2" = "run list" ] && echo 101
exit 0
"""


class TheMarkersAreTakenOut(unittest.TestCase):
	def test_every_marker_in_any_case_is_removed(self):
		for marker in MARKERS:
			with self.subTest(marker=marker):
				out = commit_message.clean(f"SOS-P1-07: Buyer pipeline {marker}\n\nThe body {marker} ends.\n")
				self.assertIsNone(LEFT_OVER.search(out), out)
				self.assertTrue(out.startswith("SOS-P1-07: Buyer pipeline"), out)
				self.assertIn("The body", out)
				self.assertIn("ends.", out)

	def test_a_trailer_line_of_only_a_marker_is_dropped(self):
		out = commit_message.clean("SOS-X-1: a task\n\nbody\n\nskip-checks: true\n")
		self.assertEqual(out, "SOS-X-1: a task\n\nbody\n")

	def test_a_clean_message_is_left_as_it_is(self):
		text = "SOS-X-1: a task\n\nSkipped the CI minutes question; checks pass.\n"
		self.assertEqual(commit_message.clean(text), text)

	def test_the_command_line_cleans_stdin_and_a_file(self):
		out = subprocess.run(
			["python3", str(SCRIPT), "clean"],
			input="SOS-LOOP: ledger [skip ci]\n",
			capture_output=True,
			text=True,
			check=True,
		).stdout
		self.assertEqual(out, "SOS-LOOP: ledger\n")
		with self.subTest("clean-file"):
			import tempfile

			with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as f:
				f.write("SOS-X-1: t\n\nsummary [ci skip]\n")
			self.addCleanup(Path(f.name).unlink)
			subprocess.run(["python3", str(SCRIPT), "clean-file", f.name], check=True)
			self.assertEqual(Path(f.name).read_text(), "SOS-X-1: t\n\nsummary\n")


class EveryLoopCommitGoesThroughIt(unittest.TestCase):
	def test_the_loop_has_no_bare_git_commit_and_no_marker(self):
		text = LOOP.read_text(encoding="utf-8")
		code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
		helper = code.split("loop_commit() {", 1)[1].split("\n}\n", 1)[0]
		outside = code.replace(helper, "")
		self.assertNotRegex(
			outside, r"git( -C \S+)? commit ", "a commit that does not go through loop_commit"
		)
		self.assertGreaterEqual(outside.count("loop_commit "), 11)
		self.assertIn('lib/commit_message.py" clean', helper)
		self.assertIn('lib/commit_message.py" clean-file', helper)
		self.assertIsNone(LEFT_OVER.search(code), "the loop writes a skip marker itself")


class TheLoopStripsTheAgentsMarkers(loop_env.LoopSandbox):
	def test_a_summary_with_markers_is_committed_without_them(self):
		self.serve(302)
		self.write(self.bin / "claude", AGENT_WITH_MARKERS, 0o755)
		self.write(self.bin / "gh", GREEN_GH, 0o755)
		code = self.run_loop([0])
		self.assertEqual(code, 0, self.out)
		messages = self.git("log", "--format=%B", f"{self.base}..HEAD")
		self.assertIn(f"{loop_env.TASK}: ", messages)
		self.assertIn("built it", messages, self.out)
		self.assertIsNone(LEFT_OVER.search(messages), messages)
