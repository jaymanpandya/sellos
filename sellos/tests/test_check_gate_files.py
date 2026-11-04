"""SOS-SETUP-11: scripts/check_gate_files.py blocks a task from changing what judges it.

Each case builds a throwaway git repository with the real pyproject.toml and a file at every newly
protected path, commits it as the base, makes one change, and runs the real guard against it.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / "scripts" / "check_gate_files.py"
PYPROJECT = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
NEWLY_PROTECTED = [".semgrepignore", ".eslintrc", "scripts/check_no_stale_skips.py"]
ALLOWED_BLOCK = "### SOS-X-1: a task\n- **Status:** In Progress\n- **Gate files:** allowed\n"
PLAIN_BLOCK = "### SOS-X-1: a task\n- **Status:** In Progress\n"


def git(cwd, *args):
	return subprocess.run(
		["git", "-c", "user.name=Gate Test", "-c", "user.email=gate@test.invalid", *args],
		cwd=cwd,
		capture_output=True,
		text=True,
		check=True,
	).stdout.strip()


class TestCheckGateFiles(unittest.TestCase):
	def setUp(self):
		self.repo = Path(tempfile.mkdtemp(prefix="sellos-gate-repo-"))
		self.outside = Path(tempfile.mkdtemp(prefix="sellos-gate-block-"))
		self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
		self.addCleanup(shutil.rmtree, self.outside, ignore_errors=True)
		git(self.repo, "init", "-q")
		(self.repo / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
		for name in NEWLY_PROTECTED:
			(self.repo / name).parent.mkdir(parents=True, exist_ok=True)
			(self.repo / name).write_text("# base\n", encoding="utf-8")
		(self.repo / "app.py").write_text("x = 1\n", encoding="utf-8")
		git(self.repo, "add", "-A")
		git(self.repo, "commit", "-q", "-m", "base")
		self.base = git(self.repo, "rev-parse", "HEAD")

	def run_guard(self, block):
		block_file = self.outside / "block.md"
		block_file.write_text(block, encoding="utf-8")
		result = subprocess.run(
			[sys.executable, str(GUARD), self.base, str(block_file)],
			cwd=self.repo,
			capture_output=True,
			text=True,
		)
		return result.returncode, result.stdout

	def edit_pyproject(self, old, new):
		path = self.repo / "pyproject.toml"
		text = path.read_text(encoding="utf-8")
		self.assertIn(old, text, "the test's anchor text is missing from pyproject.toml")
		path.write_text(text.replace(old, new, 1), encoding="utf-8")

	def test_untouched_passes(self):
		(self.repo / "app.py").write_text("x = 2\n", encoding="utf-8")
		code, out = self.run_guard(PLAIN_BLOCK)
		self.assertEqual(code, 0, out)
		self.assertIn("untouched", out)

	def test_newly_protected_files_blocked_then_allowed(self):
		for name in NEWLY_PROTECTED:
			with self.subTest(file=name):
				(self.repo / name).write_text("# changed by a task\n", encoding="utf-8")
				code, out = self.run_guard(PLAIN_BLOCK)
				self.assertEqual(code, 1, out)
				self.assertIn(name, out)
				code, out = self.run_guard(ALLOWED_BLOCK)
				self.assertEqual(code, 0, out)
				git(self.repo, "checkout", "-q", "--", name)

	def test_deleting_a_protected_file_is_blocked(self):
		(self.repo / ".semgrepignore").unlink()
		code, out = self.run_guard(PLAIN_BLOCK)
		self.assertEqual(code, 1, out)
		self.assertIn(".semgrepignore", out)

	def test_pyproject_dependency_only_passes(self):
		self.edit_pyproject(
			'dependencies = [\n    # "frappe~=16.0.0" # Installed and managed by bench.\n]',
			'dependencies = [\n    # "frappe~=16.0.0" # Installed and managed by bench.\n    "phonenumbers~=9.0",\n]',
		)
		code, out = self.run_guard(PLAIN_BLOCK)
		self.assertEqual(code, 0, out)
		self.assertNotIn("tool.ruff", out)

	def test_ruff_per_file_ignore_change_fails(self):
		self.edit_pyproject(
			'"scripts/lib/tasks.py" = ["UP015"]', '"scripts/lib/tasks.py" = ["UP015", "F841"]'
		)
		code, out = self.run_guard(PLAIN_BLOCK)
		self.assertEqual(code, 1, out)
		self.assertIn("pyproject.toml [tool.ruff]", out)

	def test_ruff_new_per_file_ignore_entry_fails(self):
		self.edit_pyproject(
			"[tool.ruff.lint.per-file-ignores]\n",
			'[tool.ruff.lint.per-file-ignores]\n"sellos/api.py" = ["B"]\n',
		)
		code, out = self.run_guard(PLAIN_BLOCK)
		self.assertEqual(code, 1, out)
		self.assertIn("pyproject.toml [tool.ruff]", out)

	def test_ruff_ignore_change_fails_then_allowed(self):
		self.edit_pyproject('    "E501", # line too long\n', '    "E501", # line too long\n    "B006",\n')
		code, out = self.run_guard(PLAIN_BLOCK)
		self.assertEqual(code, 1, out)
		self.assertIn("pyproject.toml [tool.ruff]", out)
		code, out = self.run_guard(ALLOWED_BLOCK)
		self.assertEqual(code, 0, out)

	def test_ruff_comment_only_passes(self):
		self.edit_pyproject('    "E501", # line too long\n', '    "E501", # lines over 110 characters\n')
		code, out = self.run_guard(PLAIN_BLOCK)
		self.assertEqual(code, 0, out)

	def test_unparseable_pyproject_fails(self):
		(self.repo / "pyproject.toml").write_text(PYPROJECT + "\n[tool.ruff\n", encoding="utf-8")
		code, out = self.run_guard(PLAIN_BLOCK)
		self.assertEqual(code, 1, out)
		self.assertIn("does not parse", out)


if __name__ == "__main__":
	unittest.main()
