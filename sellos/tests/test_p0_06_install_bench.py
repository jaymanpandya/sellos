"""SOS-P0-06: deploy/install-bench.sh, in dry run only.

Covers the dry run output (the pinned Frappe version, dns_multitenant on, the nginx step, SellOS
installed from 1.0, no command run), the version check against ci.yml, and the refusals for a folder
that already holds a bench, ~/iespl-bench included.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "deploy" / "install-bench.sh"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def run_script(*args, home=None, cwd=None):
	env = {"PATH": "/usr/bin:/bin", "HOME": home or tempfile.gettempdir()}
	return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, cwd=cwd)


class TestInstallBench(unittest.TestCase):
	def setUp(self):
		tmp = tempfile.TemporaryDirectory()
		self.addCleanup(tmp.cleanup)
		self.tmp = Path(tmp.name).resolve()

	def dry_run(self, target=None):
		return run_script("--dry-run", "--bench-dir", str(target or self.tmp / "fresh"), home=str(self.tmp))

	def test_dry_run_prints_every_step_and_runs_none(self):
		target = self.tmp / "fresh"
		result = self.dry_run(target)
		self.assertEqual(result.returncode, 0, result.stderr)
		commands = [line[2:] for line in result.stdout.splitlines() if line.startswith("+ ")]
		self.assertTrue(any(c.startswith("bench init") for c in commands))
		self.assertIn("bench config dns_multitenant on", commands)
		self.assertTrue(any(c.startswith("bench setup nginx") for c in commands))
		self.assertTrue(any(c.startswith("bench get-app sellos") and "--branch 1.0" in c for c in commands))
		self.assertFalse(target.exists(), "a dry run must create nothing")

	def test_dry_run_pins_the_frappe_version(self):
		result = self.dry_run()
		self.assertRegex(result.stdout, r"bench init --frappe-branch version-16 ")

	def test_pinned_version_matches_ci(self):
		script = SCRIPT.read_text(encoding="utf-8")
		pins = re.findall(r'^FRAPPE_BRANCH="([^"]+)"$', script, re.M)
		self.assertEqual(len(pins), 1, "the Frappe version is pinned in one place")
		self.assertRegex(pins[0], r"^version-16$")
		ci_branches = set(re.findall(r"--frappe-branch[ =](\S+)", CI.read_text(encoding="utf-8")))
		self.assertEqual(ci_branches, {pins[0]})
		# Every use of the branch in the script goes through the variable.
		self.assertEqual(len(re.findall(r"version-\d+", script)), 1)

	def test_refuses_a_folder_that_holds_a_bench(self):
		for marker in ("sites/apps.txt", "apps/frappe/x", "sites/common_site_config.json"):
			with self.subTest(marker=marker):
				target = self.tmp / marker.replace("/", "_")
				(target / marker).parent.mkdir(parents=True)
				(target / marker).write_text("x")
				result = self.dry_run(target)
				self.assertEqual(result.returncode, 2)
				self.assertIn("already holds a bench", result.stderr)
				self.assertNotIn("+ ", result.stdout, "no command may print before the refusal")

	def test_refuses_the_shared_bench_folder(self):
		(self.tmp / "iespl-bench").mkdir()
		for given in (str(self.tmp / "iespl-bench"), "~/iespl-bench", "iespl-bench/../iespl-bench"):
			with self.subTest(given=given):
				result = run_script("--dry-run", "--bench-dir", given, home=str(self.tmp), cwd=self.tmp)
				self.assertEqual(result.returncode, 2)
				self.assertIn("shared development bench", result.stderr)
				self.assertNotIn("+ ", result.stdout)

	def test_refuses_the_shared_bench_even_when_it_does_not_exist_yet(self):
		result = run_script("--dry-run", "--bench-dir", "~/iespl-bench", home=str(self.tmp))
		self.assertEqual(result.returncode, 2)
		self.assertIn("shared development bench", result.stderr)

	def test_unknown_option_is_refused(self):
		self.assertEqual(run_script("--nope").returncode, 2)
