"""SOS-SETUP-17: scripts/check_ci_parity.py fails when the local bench is not the bench CI builds.

Each case writes a workflow and a throwaway bench (a Frappe checkout, a fake Python and a fake Node)
and runs the real check against them. The last case runs it on the repository's own ci.yml.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPO_ROOT / "scripts" / "check_ci_parity.py"


def workflow(init_line, python="'3.14'", node="24"):
	return (
		"jobs:\n  server:\n    steps:\n      - uses: actions/setup-python@v6\n        with:\n"
		f"          python-version: {python}\n      - uses: actions/setup-node@v6\n        with:\n"
		f"          node-version: {node}\n      - run: |\n          {init_line}\n"
	)


PINNED = 'bench init --frappe-branch version-16 --skip-assets --python "$(which python)" ~/frappe-bench'


class TestCheckCiParity(unittest.TestCase):
	def setUp(self):
		self.root = Path(tempfile.mkdtemp(prefix="sellos-parity-"))
		self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
		self.bench = self.root / "bench"
		self.frappe = self.bench / "apps" / "frappe"
		self.frappe.mkdir(parents=True)
		subprocess.run(["git", "init", "-q", "-b", "version-16"], cwd=self.frappe, check=True)
		self.bin = self.root / "bin"
		self.bin.mkdir()
		self.fake(self.bench / "env" / "bin" / "python", "Python 3.14.7")
		self.fake(self.bin / "node", "v24.22.2")
		self.workflow = self.root / "ci.yml"
		self.workflow.write_text(workflow(PINNED), encoding="utf-8")

	def fake(self, path, version):
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(f"#!/usr/bin/env bash\necho {version}\n", encoding="utf-8")
		path.chmod(0o755)

	def run_check(self, bench=None, workflow_file=None):
		env = {**os.environ, "PATH": f"{self.bin}:{os.environ.get('PATH', '/usr/bin:/bin')}"}
		result = subprocess.run(
			[sys.executable, str(CHECK), str(bench or self.bench), str(workflow_file or self.workflow)],
			capture_output=True,
			text=True,
			env=env,
		)
		return result.returncode, result.stdout

	def test_matching_bench_passes(self):
		code, out = self.run_check()
		self.assertEqual(code, 0, out)

	def test_bench_init_without_a_frappe_branch_fails(self):
		self.workflow.write_text(
			workflow('bench init --skip-assets --python "$(which python)" ~/frappe-bench'), encoding="utf-8"
		)
		code, out = self.run_check()
		self.assertEqual(code, 1, out)
		self.assertIn("names no --frappe-branch", out)

	def test_local_frappe_on_another_branch_fails(self):
		subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/develop"], cwd=self.frappe, check=True)
		code, out = self.run_check()
		self.assertEqual(code, 1, out)
		self.assertIn("CI installs Frappe version-16", out)
		self.assertIn("is on develop", out)

	def test_jobs_on_different_frappe_branches_fail(self):
		text = workflow(PINNED) + "      - run: bench init --frappe-branch develop ~/other\n"
		self.workflow.write_text(text, encoding="utf-8")
		code, out = self.run_check()
		self.assertEqual(code, 1, out)
		self.assertIn("different Frappe branches", out)

	def test_another_python_fails(self):
		self.fake(self.bench / "env" / "bin" / "python", "Python 3.12.3")
		code, out = self.run_check()
		self.assertEqual(code, 1, out)
		self.assertIn("CI uses Python 3.14", out)

	def test_another_node_fails(self):
		self.fake(self.bin / "node", "v20.11.0")
		code, out = self.run_check()
		self.assertEqual(code, 1, out)
		self.assertIn("CI uses Node 24", out)

	def test_the_repository_workflow_pins_frappe(self):
		self.workflow = REPO_ROOT / ".github" / "workflows" / "ci.yml"
		code, out = self.run_check()
		self.assertEqual(code, 0, out)


if __name__ == "__main__":
	unittest.main()
