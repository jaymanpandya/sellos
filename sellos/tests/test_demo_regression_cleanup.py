"""SOS-LOOP (demo seed, 25 November 2026): the "Regression ..." records are removed from the demo sites only.

remove_regression_records() refuses any site that is not a sellos_tenant_demo<id>.localhost site (this test runs on
sellos_test, so it must refuse and remove nothing). The removal itself, _purge_regression(), takes out the matching
clients with their leads and a developer, keeps a record that something else still links to, and finds
nothing the second time.
"""

import frappe
from frappe.tests import IntegrationTestCase

from sellos.testing import demo

# The tests use a pattern of their own, never the Regression one: sellos_test keeps its Regression records.
LIKE = "Cleanup Probe%"
CLIENT = "Cleanup Probe Buyer"
DEVELOPER = "Cleanup Probe Developer"
LINKED_DEVELOPER = "Cleanup Probe Linked Developer"
PROJECT = "Cleanup Test Project (a real one)"


class TestRegressionCleanup(IntegrationTestCase):
	"""SOS-LOOP demo seed: Regression records out of the demo sites, nothing else touched."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(self._clean)
		self._clean()

	def _clean(self):
		for name in frappe.get_all("Project", {"project_name": PROJECT}, pluck="name"):
			frappe.db.delete("Project", {"name": name})
		for name in (DEVELOPER, LINKED_DEVELOPER):
			frappe.db.delete("Developer", {"name": name})
		for name in frappe.get_all("Client", {"client_name": CLIENT}, pluck="name"):
			frappe.db.delete("Lead", {"client": name})
			frappe.db.delete("Client", {"name": name})

	def _client(self):
		return frappe.get_doc({"doctype": "Client", "client_name": CLIENT, "client_type": "Buyer"}).insert(
			ignore_permissions=True
		)

	def test_a_site_that_is_not_a_demo_site_is_refused_and_nothing_is_removed(self):
		self._client()
		with self.assertRaises(Exception):
			demo.remove_regression_records()
		self.assertTrue(frappe.db.exists("Client", {"client_name": CLIENT}))

	def test_regression_clients_and_developers_are_removed_and_a_second_run_finds_nothing(self):
		self._client()
		frappe.get_doc({"doctype": "Developer", "developer_name": DEVELOPER}).insert(ignore_permissions=True)
		first = demo._purge_regression(LIKE)
		self.assertEqual(first["removed"].get("clients"), 1)
		self.assertEqual(first["removed"].get("Developer"), 1)
		self.assertFalse(frappe.db.exists("Client", {"client_name": CLIENT}))
		self.assertFalse(frappe.db.exists("Developer", DEVELOPER))
		second = demo._purge_regression(LIKE)
		self.assertNotIn("clients", second["removed"])
		self.assertNotIn("Developer", second["removed"])

	def test_a_developer_that_a_real_project_still_uses_is_kept_and_reported(self):
		frappe.get_doc({"doctype": "Developer", "developer_name": LINKED_DEVELOPER}).insert(
			ignore_permissions=True
		)
		frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": PROJECT,
				"developer": LINKED_DEVELOPER,
				"city": "Mumbai",
				"rera_number": "P51800099999",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		result = demo._purge_regression(LIKE)
		self.assertTrue(frappe.db.exists("Developer", LINKED_DEVELOPER))
		self.assertTrue(any(LINKED_DEVELOPER in line for line in result["kept"]))
