"""SOS-LOOP: a rejected (non fast forward) push does not stop the loop.

Runs scripts/lib/push_retry.sh, the file scripts/build-loop.sh sources, against real git repositories
(a bare remote and two clones). Another session pushes to 1.0 while the "loop" clone has a commit
of its own: the push is rejected, the lib rebases and pushes again. A real conflict aborts the rebase,
leaves the repository clean and names the files. Nothing is ever forced.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "scripts" / "lib" / "push_retry.sh"
LOOP = Path(__file__).resolve().parents[2] / "scripts" / "build-loop.sh"


def run(cwd, *args, check=True):
	return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)


class LoopPushRebase(unittest.TestCase):
	def setUp(self):
		tmp = tempfile.TemporaryDirectory()
		self.addCleanup(tmp.cleanup)
		root = Path(tmp.name)
		self.remote = root / "remote.git"
		run(root, "git", "init", "--bare", "-b", "1.0", str(self.remote))
		self.loop = root / "loop"
		self.other = root / "other"
		run(root, "git", "clone", str(self.remote), str(self.loop))
		for repo in (self.loop,):
			self.configure(repo)
		self.commit(self.loop, "TASKS.md", "tasks\n", "base")
		self.commit(self.loop, "a.txt", "a\n", "a")
		run(self.loop, "git", "push", "-u", "origin", "1.0")
		run(root, "git", "clone", str(self.remote), str(self.other))
		self.configure(self.other)

	def configure(self, repo):
		run(repo, "git", "config", "user.email", "t@example.com")
		run(repo, "git", "config", "user.name", "t")
		run(repo, "git", "config", "commit.gpgsign", "false")

	def commit(self, repo, name, text, message):
		(repo / name).write_text(text)
		run(repo, "git", "add", name)
		run(repo, "git", "commit", "-m", message)

	def push_with_retry(self, rebases=3):
		script = f'BRANCH=1.0; SELLOS_PUSH_REBASE_ATTEMPTS={rebases}; source "{LIB}"; push_with_retry; rc=$?; printf "ERR=%s\\n" "$PUSH_ERROR"; exit $rc'
		return run(self.loop, "bash", "-c", script, check=False)

	def test_a_rejected_push_is_rebased_and_pushed(self):
		self.commit(self.other, "TASKS.md", "tasks\nstatus\n", "interactive docs commit")
		run(self.other, "git", "push", "origin", "1.0")
		self.commit(self.loop, "b.txt", "b\n", "SOS-X: task")
		result = self.push_with_retry()
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		self.assertIn("Rebase attempt 1 of 3", result.stdout)
		self.assertEqual(
			run(self.loop, "git", "rev-parse", "HEAD").stdout,
			run(self.remote, "git", "rev-parse", "1.0").stdout,
		)
		log = run(self.remote, "git", "log", "--format=%s", "1.0").stdout.split("\n")
		self.assertIn("interactive docs commit", log)
		self.assertIn("SOS-X: task", log)

	def test_a_dirty_tree_is_autostashed(self):
		self.commit(self.other, "other.txt", "o\n", "interactive commit")
		run(self.other, "git", "push", "origin", "1.0")
		self.commit(self.loop, "b.txt", "b\n", "SOS-X: task")
		(self.loop / "a.txt").write_text("changed locally\n")
		result = self.push_with_retry()
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		self.assertEqual((self.loop / "a.txt").read_text(), "changed locally\n")

	def test_a_real_conflict_aborts_the_rebase_and_names_the_files(self):
		self.commit(self.other, "TASKS.md", "other side\n", "interactive edit")
		run(self.other, "git", "push", "origin", "1.0")
		self.commit(self.loop, "TASKS.md", "loop side\n", "SOS-X: task")
		head = run(self.loop, "git", "rev-parse", "HEAD").stdout
		remote_head = run(self.remote, "git", "rev-parse", "1.0").stdout
		result = self.push_with_retry()
		self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
		self.assertIn("Conflicted files: TASKS.md", result.stdout)
		self.assertEqual(run(self.loop, "git", "status", "--porcelain").stdout, "")
		self.assertFalse((self.loop / ".git" / "rebase-merge").exists())
		self.assertFalse((self.loop / ".git" / "rebase-apply").exists())
		self.assertEqual(run(self.loop, "git", "rev-parse", "HEAD").stdout, head)
		self.assertEqual(run(self.remote, "git", "rev-parse", "1.0").stdout, remote_head)

	def test_it_gives_up_after_three_rebase_attempts_and_never_forces(self):
		self.commit(self.other, "o.txt", "o\n", "interactive commit")
		run(self.other, "git", "push", "origin", "1.0")
		self.commit(self.loop, "b.txt", "b\n", "SOS-X: task")
		# A hook on the remote that rejects every push, so each attempt is rejected again.
		hook = self.remote / "hooks" / "pre-receive"
		hook.write_text("#!/bin/sh\necho '! [remote rejected] 1.0 -> 1.0 (non-fast-forward)' >&2\nexit 1\n")
		hook.chmod(0o755)
		result = self.push_with_retry()
		self.assertEqual(result.returncode, 1, result.stdout)
		self.assertIn("Rebase attempt 3 of 3", result.stdout)
		self.assertNotIn("Rebase attempt 4", result.stdout)
		self.assertNotIn("--force", LIB.read_text())

	def test_the_loop_sources_the_lib_and_has_no_force_push(self):
		text = LOOP.read_text()
		self.assertIn('source "$SCRIPT_DIR/lib/push_retry.sh"', text)
		self.assertNotIn("push --force", text)
		self.assertNotIn("push -f", text)
		lib = LIB.read_text()
		self.assertIn("git pull --rebase --autostash origin", lib)
		self.assertIn("git rebase --abort", lib)


if __name__ == "__main__":
	unittest.main()
