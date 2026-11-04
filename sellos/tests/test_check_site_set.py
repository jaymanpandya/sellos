"""SOS-SETUP-17: scripts/check_site_set.py fails a gate run that touched another app's site.

Each case makes a throwaway bench with site folders, takes the real snapshot, changes the bench the
way a bad test would, and runs the real compare.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK = REPO_ROOT / "scripts" / "check_site_set.py"
EXISTING = ["test_site", "dev_site", "pamaa_test.localhost", "sellos.localhost", "sellos_test.localhost"]


class TestCheckSiteSet(unittest.TestCase):
	def setUp(self):
		self.bench = Path(tempfile.mkdtemp(prefix="sellos-sites-"))
		self.addCleanup(shutil.rmtree, self.bench, ignore_errors=True)
		for name in EXISTING:
			self.site(name)
		(self.bench / "sites" / "assets").mkdir()
		(self.bench / "sites" / "common_site_config.json").write_text("{}", encoding="utf-8")
		self.snapshot = self.bench / "snapshot.json"
		self.assertEqual(self.check("snapshot")[0], 0)

	def site(self, name, config=None):
		path = self.bench / "sites" / name
		path.mkdir(parents=True, exist_ok=True)
		(path / "site_config.json").write_text(json.dumps(config or {"db_name": name}), encoding="utf-8")

	def check(self, action):
		result = subprocess.run(
			[sys.executable, str(CHECK), action, str(self.bench), str(self.snapshot)],
			capture_output=True,
			text=True,
		)
		return result.returncode, result.stdout

	def test_untouched_bench_passes(self):
		code, out = self.check("compare")
		self.assertEqual(code, 0, out)

	def test_gate_site_may_change(self):
		self.site("sellos_test.localhost", {"db_name": "sellos_test", "allow_tests": 1})
		code, out = self.check("compare")
		self.assertEqual(code, 0, out)

	def test_tenant_made_and_dropped_passes(self):
		self.site("sellos_tenant_a1.localhost")
		shutil.rmtree(self.bench / "sites" / "sellos_tenant_a1.localhost")
		code, out = self.check("compare")
		self.assertEqual(code, 0, out)

	def test_tenant_left_behind_fails(self):
		self.site("sellos_tenant_a1.localhost")
		code, out = self.check("compare")
		self.assertEqual(code, 1, out)
		self.assertIn("sellos_tenant_a1.localhost was created by this run", out)

	def test_other_app_site_removed_fails(self):
		shutil.rmtree(self.bench / "sites" / "test_site")
		code, out = self.check("compare")
		self.assertEqual(code, 1, out)
		self.assertIn("test_site was removed", out)

	def test_other_app_site_config_changed_fails(self):
		self.site("pamaa_test.localhost", {"db_name": "pamaa_test", "maintenance_mode": 1})
		code, out = self.check("compare")
		self.assertEqual(code, 1, out)
		self.assertIn("pamaa_test.localhost/site_config.json changed", out)

	def test_a_site_with_another_name_fails(self):
		for name in (
			"sellos_tenant_a1",
			"tenant_a1.localhost",
			"sellos_tenant_A1.localhost",
			"sellos2.localhost",
		):
			with self.subTest(name=name):
				self.site(name)
				code, out = self.check("compare")
				self.assertEqual(code, 1, out)
				self.assertIn(f"{name} was created", out)
				shutil.rmtree(self.bench / "sites" / name)


if __name__ == "__main__":
	unittest.main()
