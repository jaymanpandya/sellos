"""SOS-P0-11: the test site script makes a working site from nothing, in the agreed time, and cleans up.

Test criterion: run it twice in a row and both runs succeed. The runs use the real provisioner account.
"""

import subprocess
import unittest
from pathlib import Path
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase

from sellos.provisioning import site_script, tenant_sites

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "test-site.sh"
TENANT = "p011"


class TestSiteScriptNames(unittest.TestCase):
	"""SOS-P0-11: only sellos_tenant_<id>.localhost sites, through the P0-06L name check."""

	def test_bad_ids_are_refused_before_any_command_runs(self):
		with (
			mock.patch.object(tenant_sites, "_run_frappe") as run,
			mock.patch.object(site_script, "_site_command") as command,
		):
			for bad in ("test_site", "sellos_test.localhost", "../a", "A", ""):
				for fn in (site_script.up, site_script.down, site_script.run):
					with (
						self.subTest(bad=bad, fn=fn.__name__),
						self.assertRaises(tenant_sites.TenantNameError),
					):
						fn(bad)
		run.assert_not_called()
		command.assert_not_called()

	def test_shell_script_refuses_a_bad_id(self):
		for bad in ("test_site", "A", "a.b"):
			result = subprocess.run([str(SCRIPT), "run", bad], capture_output=True, text=True, check=False)
			self.assertEqual(result.returncode, 2, bad)

	def test_run_drops_the_site_when_up_fails(self):
		with (
			mock.patch.object(site_script, "up", side_effect=site_script.SiteScriptError("x")),
			mock.patch.object(site_script, "down") as down,
		):
			with self.assertRaises(site_script.SiteScriptError):
				site_script.run("a1")
		down.assert_called_once_with("a1")

	def test_run_over_the_agreed_time_fails(self):
		with mock.patch.object(site_script, "up", return_value={}), mock.patch.object(site_script, "down"):
			with self.assertRaises(site_script.SiteScriptError):
				site_script.run("a1", budget=-1)


class TestSiteScriptRuns(IntegrationTestCase):
	"""SOS-P0-11: two runs in a row both succeed, and each leaves nothing behind."""

	def tearDown(self):
		site_script.down(TENANT)
		super().tearDown()

	def database_exists(self, db_name):
		return bool(frappe.db.sql("select 1 from information_schema.schemata where schema_name=%s", db_name))

	def test_two_runs_in_a_row_both_work_and_clean_up(self):
		site, db_name = tenant_sites.names(TENANT)
		for _ in range(2):
			info, seconds = site_script.run(TENANT)
			self.assertEqual(info["site"], site)
			self.assertEqual(info["database"], db_name)
			self.assertIn("sellos", info["apps"])
			self.assertEqual(info["admin"], "sos_test_company_admin@example.com")
			self.assertTrue(info["admin_enabled"])
			self.assertIn("SellOS Company Admin", info["admin_roles"])
			self.assertLessEqual(seconds, site_script.TIME_BUDGET_SECONDS)
			self.assertNotIn(site, tenant_sites.list_sites())
			self.assertFalse(self.database_exists(db_name))
