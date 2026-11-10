"""SOS-SETUP-21: the read only BuildOS reference copy and the shared bench helpers.

* scripts/refresh-buildos-reference.sh copies a BuildOS working tree without .git, node_modules,
  buildos/public/frontend, buildos/www/buildos.html, logs, *.log, __pycache__ and *.pyc, leaves no
  write bit anywhere in the copy, prints the BuildOS commit it copied, refreshes an existing read only
  copy (excluded and removed files go), and exits 3 when the source is missing.
* scripts/install-shared-helpers.sh installs scripts/shared/bench-gate-lock.sh to
  <baseline>/bench-gate-lock.sh, replacing a different copy.
* The real build loop, at its start and once only: reinstalls a missing or different lock helper with
  a warning, refreshes the reference copy, and stops before any task when the refresh fails.

Every test works in a throwaway folder, never in ~/iespl-baseline or apps/buildos.
"""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from sellos.tests import test_loop_environment_failures as loop_env

REPO_ROOT = Path(__file__).resolve().parents[2]
REFRESH = REPO_ROOT / "scripts" / "refresh-buildos-reference.sh"
INSTALL = REPO_ROOT / "scripts" / "install-shared-helpers.sh"
SHARED_HELPER = REPO_ROOT / "scripts" / "shared" / "bench-gate-lock.sh"
GIT_ENV = loop_env.GIT_ENV

KEPT = [
	"buildos/hooks.py",
	"buildos/public/other.js",
	"buildos/www/other.html",
	"frontend/src/main.js",
	"docs/notes.md",
]
EXCLUDED = [
	".git",
	"node_modules/pkg/index.js",
	"frontend/node_modules/pkg/index.js",
	"buildos/public/frontend/assets/app.js",
	"buildos/www/buildos.html",
	"logs/bench.log",
	"buildos/logs/worker.txt",
	"loop.log",
	"buildos/__pycache__/hooks.cpython-314.pyc",
	"buildos/stray.pyc",
]


def write_bits(root):
	"""Every path under root (root included) that still has a write bit for anyone."""
	found = []
	for path in [root, *root.rglob("*")]:
		if path.lstat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
			found.append(str(path.relative_to(root)))
	return found


class Workspace(unittest.TestCase):
	def setUp(self):
		self.root = Path(tempfile.mkdtemp(prefix="sellos-buildos-ref-"))
		self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
		self.addCleanup(subprocess.run, ["chmod", "-R", "u+w", str(self.root)], check=False)
		self.source = self.root / "bench" / "apps" / "buildos"
		self.reference = self.root / "baseline" / "buildos-reference"
		for rel in KEPT + EXCLUDED[1:]:
			path = self.source / rel
			path.parent.mkdir(parents=True, exist_ok=True)
			path.write_text(f"{rel}\n", encoding="utf-8")
		self.git("init", "-q", "-b", "main")
		# Commit only what a repository would hold, so the working tree is clean.
		(self.source / ".gitignore").write_text(
			"node_modules/\nlogs/\n*.log\n__pycache__/\n*.pyc\nbuildos/public/frontend/\nbuildos/www/buildos.html\n",
			encoding="utf-8",
		)
		self.git("add", "-A")
		self.git("commit", "-q", "-m", "BOS-1: a BuildOS commit")
		self.commit = self.git("rev-parse", "HEAD")

	def git(self, *args):
		return subprocess.run(
			["git", *args],
			cwd=self.source,
			capture_output=True,
			text=True,
			check=True,
			env={**os.environ, **GIT_ENV},
		).stdout.strip()

	def refresh(self, source=None):
		return subprocess.run(
			["bash", str(REFRESH)],
			capture_output=True,
			text=True,
			env={
				**os.environ,
				"SELLOS_BUILDOS_SOURCE": str(source or self.source),
				"SELLOS_BUILDOS_REFERENCE": str(self.reference),
			},
			timeout=120,
		)


class RefreshBuildosReference(Workspace):
	def test_the_copy_keeps_the_source_and_drops_every_exclude(self):
		result = self.refresh()
		self.assertEqual(result.returncode, 0, result.stderr)
		for rel in KEPT:
			self.assertEqual((self.reference / rel).read_text(encoding="utf-8"), f"{rel}\n", rel)
		for rel in EXCLUDED:
			self.assertFalse((self.reference / rel).exists(), f"{rel} was copied")

	def test_the_copy_is_read_only(self):
		self.assertEqual(self.refresh().returncode, 0)
		self.assertEqual(write_bits(self.reference), [])
		if os.geteuid() != 0:
			with self.assertRaises(PermissionError):
				(self.reference / "new.txt").write_text("x", encoding="utf-8")
			with self.assertRaises(PermissionError):
				(self.reference / "buildos/hooks.py").write_text("x", encoding="utf-8")

	def test_it_prints_the_commit_it_copied(self):
		result = self.refresh()
		self.assertIn(f"copied commit {self.commit} (BOS-1: a BuildOS commit)", result.stdout)
		self.assertIn("(read only)", result.stdout)
		self.assertNotIn("uncommitted changes", result.stdout)

	def test_it_says_when_the_working_tree_had_uncommitted_changes(self):
		(self.source / "buildos/hooks.py").write_text("changed\n", encoding="utf-8")
		result = self.refresh()
		self.assertIn(f"copied commit {self.commit}", result.stdout)
		self.assertIn("plus uncommitted changes in the working tree", result.stdout)
		self.assertEqual((self.reference / "buildos/hooks.py").read_text(encoding="utf-8"), "changed\n")

	def test_a_refresh_updates_a_read_only_copy_and_stays_read_only(self):
		self.assertEqual(self.refresh().returncode, 0)
		(self.source / "buildos/hooks.py").write_text("v2\n", encoding="utf-8")
		(self.source / "docs/notes.md").unlink()
		(self.source / "buildos/new.py").write_text("new\n", encoding="utf-8")
		result = self.refresh()
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertEqual((self.reference / "buildos/hooks.py").read_text(encoding="utf-8"), "v2\n")
		self.assertTrue((self.reference / "buildos/new.py").exists())
		self.assertFalse((self.reference / "docs/notes.md").exists(), "a file removed from BuildOS stayed")
		self.assertEqual(write_bits(self.reference), [])

	def test_an_excluded_file_already_in_the_copy_is_removed(self):
		self.reference.mkdir(parents=True)
		(self.reference / "loop.log").write_text("old log\n", encoding="utf-8")
		(self.reference / "node_modules").mkdir()
		self.assertEqual(self.refresh().returncode, 0)
		self.assertFalse((self.reference / "loop.log").exists())
		self.assertFalse((self.reference / "node_modules").exists())

	def test_a_missing_source_exits_3_and_leaves_the_copy_alone(self):
		self.assertEqual(self.refresh().returncode, 0)
		result = self.refresh(source=self.root / "no-such-buildos")
		self.assertEqual(result.returncode, 3)
		self.assertIn("BuildOS source not found", result.stderr)
		self.assertTrue((self.reference / "buildos/hooks.py").exists())
		self.assertEqual(write_bits(self.reference), [])


class InstallSharedHelpers(unittest.TestCase):
	def setUp(self):
		self.baseline = Path(tempfile.mkdtemp(prefix="sellos-baseline-"))
		self.addCleanup(shutil.rmtree, self.baseline, ignore_errors=True)
		self.target = self.baseline / "bench-gate-lock.sh"

	def install(self):
		return subprocess.run(
			["bash", str(INSTALL)],
			capture_output=True,
			text=True,
			env={**os.environ, "SELLOS_BASELINE_DIR": str(self.baseline)},
			check=True,
		)

	def test_it_installs_the_repository_copy(self):
		result = self.install()
		self.assertEqual(self.target.read_bytes(), SHARED_HELPER.read_bytes())
		self.assertTrue(os.access(self.target, os.X_OK))
		self.assertIn(f"Installed {self.target}", result.stdout)

	def test_it_replaces_a_different_copy_and_leaves_no_temporary_file(self):
		self.target.write_text("an old helper\n", encoding="utf-8")
		self.install()
		self.assertEqual(self.target.read_bytes(), SHARED_HELPER.read_bytes())
		self.assertEqual(sorted(p.name for p in self.baseline.iterdir()), ["bench-gate-lock.sh"])

	def test_it_makes_the_baseline_folder(self):
		shutil.rmtree(self.baseline)
		self.install()
		self.assertEqual(self.target.read_bytes(), SHARED_HELPER.read_bytes())


class LoopStart(loop_env.LoopSandbox):
	"""The real build loop: what it does once at its start, before it picks a task."""

	def setUp(self):
		super().setUp()
		self.installed = self.root / "iespl-baseline" / "bench-gate-lock.sh"
		self.reference = self.root / "buildos-reference"
		# A pause makes the loop stop right after its start steps, before any pick.
		(self.root / "loop.pause").write_text("paused\n", encoding="utf-8")

	def test_a_different_installed_helper_is_reinstalled_with_a_warning(self):
		self.serve(302)
		self.write(self.installed, "an old helper\n")
		self.run_loop([0])
		self.assertIn(
			"is missing or differs from scripts/shared/bench-gate-lock.sh. Reinstalling it", self.out
		)
		self.assertEqual(self.installed.read_bytes(), SHARED_HELPER.read_bytes())

	def test_a_missing_installed_helper_is_installed(self):
		self.serve(302)
		self.run_loop([0])
		self.assertIn("Reinstalling it", self.out)
		self.assertEqual(self.installed.read_bytes(), SHARED_HELPER.read_bytes())

	def test_a_matching_helper_is_left_alone(self):
		self.serve(302)
		self.write(self.installed, SHARED_HELPER.read_text(encoding="utf-8"))
		self.run_loop([0])
		self.assertNotIn("Reinstalling it", self.out)

	def test_the_reference_copy_is_refreshed_once_at_start(self):
		self.serve(302)
		self.run_loop([0])
		self.assertEqual(self.out.count("BuildOS reference: copied commit"), 1, self.out)
		self.assertTrue((self.reference / "buildos/hooks.py").exists())
		self.assertEqual(write_bits(self.reference), [])
		self.assertIn("Paused for regression", self.out)
		loop = (loop_env.SCRIPTS / "build-loop.sh").read_text(encoding="utf-8")
		self.assertLess(
			loop.index('"$SCRIPT_DIR/refresh-buildos-reference.sh"'), loop.index("while true; do")
		)
		self.assertEqual(loop.count('refresh-buildos-reference.sh"'), 1)

	def test_a_failed_refresh_stops_before_any_task(self):
		self.serve(302)
		(self.root / "loop.pause").unlink()
		shutil.rmtree(self.bench / "apps" / "buildos")
		code = self.run_loop([0])
		self.assertEqual(code, 3, self.out)
		self.assertEqual(self.calls("claude_calls"), 0)
		self.assertEqual(self.status(), "Not Started")
		self.assertIn("BuildOS reference copy could not be refreshed", self.read("notifications"))


if __name__ == "__main__":
	unittest.main()
