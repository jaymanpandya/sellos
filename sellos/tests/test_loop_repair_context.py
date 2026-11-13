"""SOS-SETUP-32: the repair agent sees every failing test, and both prompts say how to treat a guard.

On 13 November 2026 SOS-N21A was Blocked after two repair runs. The failure output they got kept
only the last failed backend batch, cut at 150 lines that one traceback's local variables filled, and
its tail began one line after the phone number guard's message, which named the fix. The real
failure_context from scripts/build-loop.sh is run here on a log shaped like that one.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOOP = REPO_ROOT / "scripts" / "build-loop.sh"
EQ = "=" * 70
DASH = "-" * 70


def failed_batch(header, assertion, locals_count=0, message_lines=()):
	lines = [EQ, f" FAIL  {header}", DASH, "Traceback (most recent call last):", '  File "x.py", line 1']
	lines += [f"    local_{n} = {'x' * 100}" for n in range(locals_count)]
	lines += [assertion, *message_lines, "", DASH, "Ran 3 tests in 0.1s", "", "FAILED (failures=1)"]
	return lines


def run_failure_context(log_text):
	script = LOOP.read_text(encoding="utf-8")
	start = script.index("failure_context() {")
	end = script.index("\n}\n", start) + 3
	with tempfile.TemporaryDirectory() as folder:
		Path(folder, "latest.log").write_text(log_text, encoding="utf-8")
		result = subprocess.run(
			["bash", "-c", script[start:end] + f'LOG_DIR="{folder}"; failure_context'],
			capture_output=True,
			text=True,
			check=True,
		)
	return result.stdout


class TestFailureContext(unittest.TestCase):
	def test_every_failed_batch_and_its_message_comes_first(self):
		guard_message = "Use the helper, never a literal:"
		log = failed_batch(
			"test_runs_commands (a.Unit)",
			"AssertionError: {'subprocess'} is not false : keys.py runs commands",
		)
		log += ["unit batch summary"]
		log += failed_batch(
			"test_a_huge_traceback (b.Integration)", "AssertionError: matrix", locals_count=400
		)
		log += failed_batch(
			"test_no_literal (c.Guard)",
			"AssertionError: Lists differ: ['x.py:22'] != []",
			message_lines=[f" : {guard_message}", "x.py:22: LITERAL = 1"],
		)
		log += [f"tail line {n}" for n in range(60)]
		out = run_failure_context("\n".join(log) + "\n")
		first = out.split("--- each failed backend batch")[0]
		for wanted in (
			"test_runs_commands",
			"keys.py runs commands",
			"test_a_huge_traceback",
			"test_no_literal",
		):
			self.assertIn(wanted, first)
		self.assertIn(guard_message, first)
		self.assertIn("x.py:22: LITERAL = 1", first)
		# local variable dumps are left out of the batches, so they cannot crowd out a later failure
		self.assertNotIn("local_399", out)
		self.assertIn("tail line 59", out)


class TestGuardRulesInBothPrompts(unittest.TestCase):
	def test_the_implementation_and_repair_prompts_carry_the_guard_rules(self):
		script = LOOP.read_text(encoding="utf-8")
		self.assertIn('GUARD_RULES="Guards.', script)
		rules = script.split('GUARD_RULES="', 1)[1].split('"\n', 1)[0]
		for words in (
			"read its whole message",
			"names the fix",
			"sellos.tests.phones",
			"Never work around a guard",
			"never disguise",
			"never add to an allowed list",
			"never edit the guard",
			"in every batch",
		):
			self.assertIn(words, rules)
		implementation = script.split('PROMPT="You are implementing', 1)[1].split("Task:\n$TASK_BLOCK", 1)[0]
		repair = script.split('REPAIR_PROMPT="', 1)[1].split("Task:\n$TASK_BLOCK", 1)[0]
		self.assertIn("$GUARD_RULES", implementation)
		self.assertIn("$GUARD_RULES", repair)
