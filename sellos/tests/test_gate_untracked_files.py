"""SOS-SETUP-12: the gate marks a task's new files intent-to-add, and nothing downstream breaks.

CI lints and scans every file in the commit. pre-commit --all-files and semgrep ci see only files
git tracks, so scripts/run-tests.sh first runs
	git ls-files --others --exclude-standard -z | xargs -0 git add --intent-to-add
Each case here builds a throwaway repository, adds an untracked new file, runs that exact line
taken from run-tests.sh, and then runs the real guard, the real "changed tests first" lines of the
gate, or the real failure path of the build loop, all read from the scripts themselves.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
RUN_TESTS = (SCRIPTS / "run-tests.sh").read_text(encoding="utf-8")
BUILD_LOOP = (SCRIPTS / "build-loop.sh").read_text(encoding="utf-8")
ITA_LINE = "git ls-files --others --exclude-standard -z | xargs -0 git add --intent-to-add"
TASK = "SOS-X-9"
BLOCK = f"### {TASK}: a task\n- **Status:** In Progress\n"
GIT_ID = ["-c", "user.name=Gate Test", "-c", "user.email=gate@test.invalid"]


def lines_between(text, first, last, after=""):
	"""The lines of a script from the first line containing `first` (past `after`) to the next with `last`."""
	lines = text.splitlines()
	skip = next(i for i, line in enumerate(lines) if after in line) if after else 0
	start = next(i for i in range(skip, len(lines)) if first in lines[i])
	end = next(i for i in range(start, len(lines)) if last in lines[i])
	return "\n".join(line.strip() for line in lines[start : end + 1])


class GateUntrackedFiles(unittest.TestCase):
	def setUp(self):
		self.bench = Path(tempfile.mkdtemp(prefix="sellos-ita-bench-"))
		self.outside = Path(tempfile.mkdtemp(prefix="sellos-ita-block-"))
		self.addCleanup(shutil.rmtree, self.bench, ignore_errors=True)
		self.addCleanup(shutil.rmtree, self.outside, ignore_errors=True)
		self.repo = self.bench / "apps" / "sellos"
		self.repo.mkdir(parents=True)
		self.git("init", "-q")
		self.write("sellos/tests/test_old.py", "class T:\n\tdef test_a(self):\n\t\tself.assertTrue(1)\n")
		self.write("sellos/api.py", "x = 1\n")
		self.write("pyproject.toml", '[project]\nname = "sellos"\n')
		self.git("add", "-A")
		self.git("commit", "-q", "-m", "base")
		self.base = self.git("rev-parse", "HEAD")
		(self.outside / "block.md").write_text(BLOCK, encoding="utf-8")

	def git(self, *args, check=True):
		return subprocess.run(
			["git", *GIT_ID, *args], cwd=self.repo, capture_output=True, text=True, check=check
		).stdout.strip()

	def write(self, rel, text):
		path = self.repo / rel
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(text, encoding="utf-8")

	def bash(self, script, cwd, env=None):
		return subprocess.run(
			["bash", "-c", f"set -euo pipefail\n{script}"],
			cwd=cwd,
			capture_output=True,
			text=True,
			env=env,
		)

	def mark_intent_to_add(self):
		self.assertIn(ITA_LINE, RUN_TESTS, "run-tests.sh no longer marks new files intent-to-add")
		result = self.bash(ITA_LINE, self.repo)
		self.assertEqual(result.returncode, 0, result.stderr)

	def guard(self, name, *args):
		result = subprocess.run(
			[sys.executable, str(SCRIPTS / name), *args], cwd=self.repo, capture_output=True, text=True
		)
		return result.returncode, result.stdout + result.stderr

	def test_new_file_becomes_visible_to_tracked_file_tools(self):
		self.write("sellos/new_module.py", "y = 2\n")
		self.assertNotIn("sellos/new_module.py", self.git("ls-files"))
		self.mark_intent_to_add()
		# pre-commit --all-files and semgrep ci both take their file list from git ls-files.
		self.assertIn("sellos/new_module.py", self.git("ls-files").splitlines())
		self.assertEqual(self.git("diff", "--cached", "--numstat"), "", "content must not be staged")

	def test_no_untracked_files_is_a_no_op(self):
		self.mark_intent_to_add()
		self.assertEqual(self.git("status", "--porcelain"), "")

	def test_gate_files_guard_blocks_a_new_protected_file(self):
		self.write("scripts/check_new_rule.py", "print('x')\n")
		self.mark_intent_to_add()
		code, out = self.guard("check_gate_files.py", self.base, str(self.outside / "block.md"))
		self.assertEqual(code, 1, out)
		self.assertIn("scripts/check_new_rule.py", out)

	def test_gate_files_guard_passes_a_new_ordinary_file(self):
		self.write("sellos/new_module.py", "y = 2\n")
		self.mark_intent_to_add()
		code, out = self.guard("check_gate_files.py", self.base, str(self.outside / "block.md"))
		self.assertEqual(code, 0, out)

	def test_assertion_ratchet_passes_a_new_test_file(self):
		self.write("sellos/tests/test_new.py", "class T:\n\tdef test_b(self):\n\t\tself.assertTrue(1)\n")
		self.mark_intent_to_add()
		code, out = self.guard("check_assertion_ratchet.py", self.base)
		self.assertEqual(code, 0, out)

	def test_assertion_ratchet_still_catches_a_drop_next_to_a_new_file(self):
		self.write("sellos/tests/test_new.py", "class T:\n\tdef test_b(self):\n\t\tself.assertTrue(1)\n")
		self.write("sellos/tests/test_old.py", "class T:\n\tdef test_a(self):\n\t\tpass\n")
		self.mark_intent_to_add()
		code, out = self.guard("check_assertion_ratchet.py", self.base)
		self.assertEqual(code, 1, out)
		self.assertIn("sellos/tests/test_old.py: assertions dropped from 1 to 0", out)

	def test_assertion_ratchet_still_catches_a_deleted_test(self):
		(self.repo / "sellos/tests/test_old.py").unlink()
		self.write("sellos/tests/test_new.py", "class T:\n\tdef test_b(self):\n\t\tself.assertTrue(1)\n")
		self.mark_intent_to_add()
		code, out = self.guard("check_assertion_ratchet.py", self.base)
		self.assertEqual(code, 1, out)
		self.assertIn("sellos/tests/test_old.py: deleted", out)

	def test_task_evidence_finds_a_new_test_file(self):
		self.write(
			"sellos/tests/test_new.py",
			f'"""{TASK}: covered."""\nclass T:\n\tdef test_b(self):\n\t\tself.assertTrue(1)\n',
		)
		self.mark_intent_to_add()
		code, out = self.guard("check_task_evidence.py", TASK, self.base, str(self.outside / "block.md"))
		self.assertEqual(code, 0, out)
		self.assertIn("sellos/tests/test_new.py", out)

	def test_task_evidence_still_fails_without_a_named_test(self):
		self.write("sellos/tests/test_new.py", "class T:\n\tdef test_b(self):\n\t\tself.assertTrue(1)\n")
		self.mark_intent_to_add()
		code, out = self.guard("check_task_evidence.py", TASK, self.base, str(self.outside / "block.md"))
		self.assertEqual(code, 1, out)

	def test_changed_tests_first_finds_new_test_and_spec(self):
		self.write("sellos/tests/test_new.py", "class T:\n\tdef test_b(self):\n\t\tself.assertTrue(1)\n")
		self.write("cypress/integration/crm/new_page.cy.js", "it('x', () => { expect(1).to.eq(1); });\n")
		self.write("sellos/tests/test_old.py", "class T:\n\tdef test_a(self):\n\t\tself.assertTrue(2)\n")
		self.mark_intent_to_add()
		step = lines_between(RUN_TESTS, 'CHANGED="$(git -C "apps/$APP"', 'CHANGED_SPECS="$(')
		result = self.bash(
			f'APP=sellos\n{step}\nprintf "PY:%s\\n" $CHANGED_PY\nprintf "SPEC:%s\\n" $CHANGED_SPECS',
			self.bench,
		)
		self.assertEqual(result.returncode, 0, result.stderr)
		found = set(result.stdout.splitlines())
		self.assertIn("PY:sellos/tests/test_new.py", found)
		self.assertIn("PY:sellos/tests/test_old.py", found)
		self.assertIn("SPEC:cypress/integration/crm/new_page.cy.js", found)

	def assert_clean_at_base(self):
		self.assertEqual(self.git("rev-parse", "HEAD"), self.base)
		self.assertEqual(self.git("status", "--porcelain", "--ignored"), "", "a stray file or index entry")
		self.assertEqual(
			sorted(self.git("ls-files").splitlines()),
			["pyproject.toml", "sellos/api.py", "sellos/tests/test_old.py"],
		)
		self.assertFalse((self.repo / "sellos/tests/test_new.py").exists())
		self.assertFalse((self.repo / "sellos/scratch").exists())

	def run_failure_path(self):
		# The gate-failed branch of the build loop, from the salvage commit to the clean.
		step = lines_between(
			BUILD_LOOP,
			'SALVAGE_BRANCH="failed/${TASK_ID}',
			'git reset --hard "$PRE_TASK_SHA"',
			after='TAIL="$(tail',
		)
		self.assertIn("git add -A", step)
		self.assertIn("git clean -fd", step)
		# SOS-SETUP-34: the loop commits through loop_commit, so the step runs with the real function.
		helper = lines_between(BUILD_LOOP, "loop_commit() {", 'git commit "${args[@]}"') + "\n}"
		self.assertIn("lib/commit_message.py", helper)
		step = f"{helper}\n{step}"
		env = {
			"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
			"HOME": str(self.outside),
			"SCRIPT_DIR": str(SCRIPTS),
			"TASK_ID": TASK,
			"PRE_TASK_SHA": self.base,
			"GIT_AUTHOR_NAME": "Gate Test",
			"GIT_AUTHOR_EMAIL": "gate@test.invalid",
			"GIT_COMMITTER_NAME": "Gate Test",
			"GIT_COMMITTER_EMAIL": "gate@test.invalid",
		}
		result = self.bash(step, self.repo, env=env)
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

	def add_task_work(self):
		self.write("sellos/tests/test_new.py", "class T:\n\tdef test_b(self):\n\t\tself.assertTrue(1)\n")
		self.write("sellos/scratch/notes.txt", "scratch\n")
		self.write("sellos/api.py", "x = 2\n")
		self.mark_intent_to_add()

	def test_failure_path_leaves_nothing_behind(self):
		self.add_task_work()
		self.run_failure_path()
		self.assert_clean_at_base()
		salvage = self.git("branch", "--list", f"failed/{TASK}-*", "--format=%(refname:short)")
		self.assertTrue(salvage, "the attempt was not saved on a failed/ branch")
		self.assertIn("sellos/tests/test_new.py", self.git("ls-tree", "-r", "--name-only", salvage))

	def test_failure_path_is_clean_even_if_the_salvage_commit_fails(self):
		self.add_task_work()
		hook = self.repo / ".git" / "hooks" / "pre-commit"
		hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
		hook.chmod(0o755)
		self.run_failure_path()
		self.assert_clean_at_base()


if __name__ == "__main__":
	unittest.main()
