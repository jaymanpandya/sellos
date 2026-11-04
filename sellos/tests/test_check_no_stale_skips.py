"""SOS-SETUP-16: scripts/check_no_stale_skips.py fails a skipped spec whose task is done.

Each case writes a small TASKS.md and spec folder to a throwaway directory and runs the real check
against it. The last case runs it on the repository itself. test_check_gate_files checks the gate protects it.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPO_ROOT / "scripts" / "check_no_stale_skips.py"
TASKS = """# Tasks

### SOS-P1-01: Done already
- **Status:** Complete

### SOS-P1-02: Not built yet
- **Status:** Not Started
"""
LIVE = 'context("SOS-P1-01: live", () => {\n\tit("works", () => {\n\t\texpect(1).to.equal(1);\n\t});\n});\n'


def skipped(task_id, kind="context"):
	comment = f"// {task_id} removes this skip.\n" if task_id else "// no task named here\n"
	return f'{comment}{kind}.skip("a contract", () => {{\n\tit("x", () => {{\n\t\texpect(1).to.equal(1);\n\t}});\n}});\n'


class TestCheckNoStaleSkips(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-skips-"))
		self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
		(self.dir / "TASKS.md").write_text(TASKS, encoding="utf-8")
		self.specs = self.dir / "cypress" / "integration"
		(self.specs / "area").mkdir(parents=True)
		(self.specs / "area" / "live.cy.js").write_text(LIVE, encoding="utf-8")

	def run_check(self, *args, cwd=None):
		cwd = cwd or self.dir
		result = subprocess.run([sys.executable, str(CHECK), *args], cwd=cwd, capture_output=True, text=True)
		return result.returncode, result.stdout

	def write_spec(self, text):
		(self.specs / "area" / "contract.cy.js").write_text(text, encoding="utf-8")

	def test_no_skips_passes(self):
		code, out = self.run_check()
		self.assertEqual(code, 0, out)

	def test_skip_for_a_task_not_started_passes(self):
		self.write_spec(skipped("SOS-P1-02"))
		code, out = self.run_check()
		self.assertEqual(code, 0, out)

	def test_skip_for_a_complete_task_fails(self):
		for kind in ("context", "describe", "it"):
			with self.subTest(kind=kind):
				self.write_spec(skipped("SOS-P1-01", kind))
				code, out = self.run_check()
				self.assertEqual(code, 1, out)
				self.assertIn("contract.cy.js:2", out)
				self.assertIn("SOS-P1-01 is Complete", out)

	def test_skip_naming_no_task_fails(self):
		self.write_spec(skipped(None))
		code, out = self.run_check()
		self.assertEqual(code, 1, out)
		self.assertIn("names no task", out)

	def test_skip_for_an_unknown_task_fails(self):
		self.write_spec(skipped("SOS-P9-99"))
		code, out = self.run_check()
		self.assertEqual(code, 1, out)
		self.assertIn("SOS-P9-99 is not a task", out)

	def test_skip_for_the_task_being_finished_fails(self):
		self.write_spec(skipped("SOS-P1-02"))
		code, out = self.run_check("--current", "SOS-P1-02")
		self.assertEqual(code, 1, out)
		self.assertIn("SOS-P1-02 is the task being finished", out)
		code, out = self.run_check("--current", "SOS-P1-03")
		self.assertEqual(code, 0, out)

	def test_task_id_on_the_skip_line_counts(self):
		self.write_spec('context.skip("SOS-P1-01: a contract", () => {});\n')
		code, out = self.run_check()
		self.assertEqual(code, 1, out)
		self.assertIn("SOS-P1-01 is Complete", out)

	def test_comment_above_a_blank_line_does_not_count(self):
		self.write_spec('// SOS-P1-02 removes this skip.\n\ncontext.skip("a contract", () => {});\n')
		code, out = self.run_check()
		self.assertEqual(code, 1, out)
		self.assertIn("names no task", out)

	def test_the_repository_passes(self):
		code, out = self.run_check(cwd=REPO_ROOT)
		self.assertEqual(code, 0, out)


if __name__ == "__main__":
	unittest.main()
