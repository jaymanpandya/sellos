"""SOS-P0-06L: multitenancy on the local bench, tested in the test process.

* test_01 is the provisioner probe and runs first: create sellos_tenant_probe.localhost once and drop
  it once with only the MariaDB provisioner account.
* The name check refuses every site that is not sellos_tenant_<id>.localhost before a command runs.
* Two tenant sites, each with its own data, are switched to with frappe.init and frappe.connect and
  never see each other's records. The suite goes back to the site it started on (sellos_test.localhost
  in the gate, test_site in CI) in a finally block.
* Every tenant site a test makes is dropped by the same code, even when the test fails.
* The provisioner password is in no file under the repository, the tenant site folders, the bench
  logs or the gate's log folder after a create and a drop.

No server is started for a tenant site and no HTTP request is sent to one.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase

from sellos.provisioning import tenant_sites
from sellos.provisioning.credentials import PASSWORD_ENV, get_provisioner_password

REPO_ROOT = Path(__file__).resolve().parents[2]
LEAK_CHECK = REPO_ROOT / "scripts" / "check_no_secret_leak.py"
TOO_LONG = "x" * 51  # sellos_tenant_ + 51 is 65 characters, one over MariaDB's limit


def drop_quietly(tenant_id):
	"""Drop a tenant site a test made, whether or not it got as far as existing."""
	site, _ = tenant_sites.names(tenant_id)
	if site in tenant_sites.list_sites():
		tenant_sites.drop(tenant_id)


class TestAProvisionerProbe(IntegrationTestCase):
	"""SOS-P0-06L: the provisioner account can create and drop a tenant site. Runs first."""

	def test_01_probe_creates_and_drops_with_only_the_provisioner_account(self):
		self.assertNotIn("sellos_tenant_probe.localhost", tenant_sites.list_sites())
		self.assertEqual(tenant_sites.probe(), "sellos_tenant_probe.localhost")
		self.assertNotIn("sellos_tenant_probe.localhost", tenant_sites.list_sites())


class TestTenantNames(unittest.TestCase):
	"""SOS-P0-06L: one function validates a tenant id and gives the site and database names."""

	def test_good_ids_give_matching_site_and_database_names(self):
		self.assertEqual(tenant_sites.names("a1"), ("sellos_tenant_a1.localhost", "sellos_tenant_a1"))
		self.assertEqual(tenant_sites.names("x" * 50)[1], "sellos_tenant_" + "x" * 50)

	def test_other_names_are_refused(self):
		for bad in (
			"test_site",
			"dev_site",
			"pamaa_test.localhost",
			"sellos.localhost",
			"sellos_test.localhost",
			"sellos_tenant_A.localhost",
			"sellos_tenant_a.localhost.evil",
			"../sellos_tenant_a.localhost",
			"sellos_tenant_a.localhost",
			"sellos_tenant_a",
			"A",
			"a_b",
			"",
			None,
			TOO_LONG,
		):
			with self.subTest(bad=bad), self.assertRaises(tenant_sites.TenantNameError):
				tenant_sites.names(bad)

	def test_create_and_drop_refuse_before_any_command_runs(self):
		with mock.patch.object(tenant_sites, "_run_frappe") as run:
			for bad in ("test_site", "sellos_test.localhost", "../a", TOO_LONG, "A"):
				with self.subTest(bad=bad):
					with self.assertRaises(tenant_sites.TenantNameError):
						tenant_sites.create(bad)
					with self.assertRaises(tenant_sites.TenantNameError):
						tenant_sites.drop(bad)
		run.assert_not_called()


class TestTenantIsolation(IntegrationTestCase):
	"""SOS-P0-06L: two tenant sites never see each other's data, switched in process."""

	IDS = ("isoa", "isob")
	TITLES = MappingProxyType({"isoa": "SOS-P0-06L note for A", "isob": "SOS-P0-06L note for B"})

	def setUp(self):
		super().setUp()
		self.addCleanup(self.drop_all)
		for tenant_id in self.IDS:
			tenant_sites.create(tenant_id)

	def drop_all(self):
		for tenant_id in self.IDS:
			drop_quietly(tenant_id)

	def switch(self, site):
		frappe.destroy()
		frappe.init(site=site, sites_path=self.sites_path)
		frappe.connect()
		frappe.set_user("Administrator")

	def titles(self):
		return sorted(frappe.get_all("Note", pluck="title"))

	def db_name(self):
		return frappe.db.sql("select database()")[0][0]

	def admin_password_hash(self):
		rows = frappe.db.sql(
			"select password from `__Auth` where doctype='User' and name='Administrator' and fieldname='password'"
		)
		self.assertEqual(len(rows), 1)
		return rows[0][0]

	def test_each_site_sees_only_its_own_records(self):
		self.sites_path = frappe.local.sites_path
		# Go back to the site the run started on, not a fixed name: CI runs on test_site (SOS-SETUP-24).
		start_site = frappe.local.site
		self.assertFalse(start_site.startswith(tenant_sites.PREFIX), start_site)
		try:
			for tenant_id in self.IDS:
				site, db_name = tenant_sites.names(tenant_id)
				self.switch(site)
				self.assertEqual(frappe.local.conf.db_name, db_name)
				self.assertEqual(self.db_name(), db_name)
				frappe.get_doc(
					{"doctype": "Note", "title": self.TITLES[tenant_id], "content": tenant_id}
				).insert()
				# The write must reach this tenant's own database before the next site is opened.
				frappe.db.commit()  # nosemgrep
			admin_hashes = set()
			for tenant_id in self.IDS:
				site, _ = tenant_sites.names(tenant_id)
				self.switch(site)
				self.assertEqual(self.titles(), [self.TITLES[tenant_id]])
				other = next(i for i in self.IDS if i != tenant_id)
				self.assertFalse(frappe.db.exists("Note", {"title": self.TITLES[other]}))
				admin_hashes.add(self.admin_password_hash())
			# SOS-SETUP-28: a site built from the test template keeps the template's Administrator
			# password unless the launcher sets its own. Each tenant has its own.
			self.assertEqual(len(admin_hashes), len(self.IDS))
		finally:
			self.switch(start_site)
		self.assertEqual(frappe.local.site, start_site)
		self.assertNotIn(self.TITLES["isoa"], self.titles())
		self.assertNotIn(self.TITLES["isob"], self.titles())


class TestTenantCleanup(IntegrationTestCase):
	"""SOS-P0-06L: a tenant site is dropped, database included, even when the test fails."""

	def test_site_and_database_are_dropped_after_a_failing_body(self):
		site, db_name = tenant_sites.names("cleanup1")
		try:
			tenant_sites.create("cleanup1")
			self.assertIn(site, tenant_sites.list_sites())
			raise RuntimeError("the test body failed")
		except RuntimeError:
			pass
		finally:
			drop_quietly("cleanup1")
		self.assertNotIn(site, tenant_sites.list_sites())
		self.assertFalse(self.database_exists(db_name))

	def database_exists(self, db_name):
		return bool(frappe.db.sql("select 1 from information_schema.schemata where schema_name=%s", db_name))


class TestTenantPasswordNeverWritten(IntegrationTestCase):
	"""SOS-P0-06L: after a create and a drop the password is in no file of the places the gate checks."""

	def test_password_is_in_no_file_after_a_create_and_a_drop(self):
		password = get_provisioner_password()
		self.addCleanup(drop_quietly, "leak1")
		tenant_sites.create("leak1")
		tenant_sites.drop("leak1")
		bench = tenant_sites.bench_dir()
		paths = [
			REPO_ROOT,
			bench / "logs",
			bench / "sites" / "common_site_config.json",
			bench / "archived",
			Path(os.environ.get("SELLOS_LOG_DIR") or "/tmp/sellos-test-logs"),
			*sorted((bench / "sites").glob("sellos_tenant_*")),
		]
		result = subprocess.run(
			[sys.executable, str(LEAK_CHECK), *[str(path) for path in paths]],
			env={**os.environ, PASSWORD_ENV: password},
			capture_output=True,
			text=True,
			check=False,
		)
		self.assertEqual(result.returncode, 0, result.stdout.replace(password, "[password]"))
