"""SOS-SETUP-17: scripts/check_site_set.py fails a gate run that touched another app's site.

Each case makes a throwaway bench with site folders, takes the real snapshot, changes the bench the
way a bad test would, and runs the real compare. SOS-SETUP-18 added the tenant db_name check and the
database list, which these tests give it through SELLOS_CHECK_DATABASES_FILE instead of a server.
"""

import json
import os
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
		self.dbs = self.bench / "databases.txt"
		self.databases("information_schema", "mysql", "_buildos_test", "pamaa_test", "sellos_test")
		self.assertEqual(self.check("snapshot")[0], 0)

	def databases(self, *names):
		self.dbs.write_text("\n".join(names) + "\n", encoding="utf-8")

	def site(self, name, config=None):
		path = self.bench / "sites" / name
		path.mkdir(parents=True, exist_ok=True)
		(path / "site_config.json").write_text(json.dumps(config or {"db_name": name}), encoding="utf-8")

	def check(self, action):
		env = {
			k: v
			for k, v in os.environ.items()
			if not k.startswith(("SELLOS_DB_PROVISIONER_", "SELLOS_CHECK_"))
		}
		result = subprocess.run(
			[sys.executable, str(CHECK), action, str(self.bench), str(self.snapshot)],
			capture_output=True,
			text=True,
			env={**env, "SELLOS_CHECK_DATABASES_FILE": str(self.dbs)},
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

	def test_tenant_with_its_own_database_made_and_dropped_passes(self):
		self.site("sellos_tenant_a1.localhost", {"db_name": "sellos_tenant_a1"})
		self.databases("information_schema", "mysql", "_buildos_test", "pamaa_test", "sellos_test")
		shutil.rmtree(self.bench / "sites" / "sellos_tenant_a1.localhost")
		code, out = self.check("compare")
		self.assertEqual(code, 0, out)

	def test_a_tenant_site_with_another_database_name_fails(self):
		for db_name in (
			"sellos_tenant_b2",
			"_abc123",
			"sellos_tenant_a1.localhost",
			None,
			"sellos_tenant_a1" + "x" * 60,
		):
			with self.subTest(db_name=db_name):
				name = "sellos_tenant_a1.localhost"
				self.site(name, {"db_name": db_name} if db_name else {"x": 1})
				code, out = self.check("compare")
				self.assertEqual(code, 1, out)
				self.assertIn(f"{name} has db_name", out)
				shutil.rmtree(self.bench / "sites" / name)

	def test_a_tenant_database_left_behind_fails(self):
		self.databases(
			"information_schema", "mysql", "_buildos_test", "pamaa_test", "sellos_test", "sellos_tenant_a1"
		)
		code, out = self.check("compare")
		self.assertEqual(code, 1, out)
		self.assertIn("Database sellos_tenant_a1 was created by this run", out)

	def test_another_database_created_or_dropped_fails(self):
		self.databases("information_schema", "mysql", "pamaa_test", "sellos_test", "_c0ffee")
		code, out = self.check("compare")
		self.assertEqual(code, 1, out)
		self.assertIn("Database _buildos_test was removed", out)
		self.assertIn("Database _c0ffee was created", out)

	def test_without_a_password_the_databases_are_not_checked(self):
		env = {
			k: v
			for k, v in os.environ.items()
			if not k.startswith(("SELLOS_DB_PROVISIONER_", "SELLOS_CHECK_"))
		}
		result = subprocess.run(
			[sys.executable, str(CHECK), "snapshot", str(self.bench), str(self.snapshot)],
			capture_output=True,
			text=True,
			env=env,
		)
		self.assertEqual(result.returncode, 0, result.stdout)
		self.assertIn("databases are not checked", result.stdout)

	def test_an_account_that_cannot_list_databases_is_an_environment_problem(self):
		fake_bin = self.bench / "bin"
		fake_bin.mkdir()
		client = fake_bin / "mariadb"
		client.write_text(
			'#!/usr/bin/env bash\necho "ERROR 1045 (28000): Access denied for user" >&2\nexit 1\n'
		)
		client.chmod(0o755)
		env = {
			k: v
			for k, v in os.environ.items()
			if not k.startswith(("SELLOS_DB_PROVISIONER_", "SELLOS_CHECK_"))
		}
		env.update(PATH=f"{fake_bin}:{os.environ['PATH']}", SELLOS_DB_PROVISIONER_PASSWORD="pw-9f1d")
		result = subprocess.run(
			[sys.executable, str(CHECK), "snapshot", str(self.bench), str(self.snapshot)],
			capture_output=True,
			text=True,
			env=env,
		)
		self.assertEqual(result.returncode, 3, result.stdout)
		self.assertIn("Access denied", result.stdout)
		self.assertNotIn("pw-9f1d", result.stdout + result.stderr)


if __name__ == "__main__":
	unittest.main()
