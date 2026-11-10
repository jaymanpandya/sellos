# SOS-P1-06A the CRM works on a fresh company site, for the right roles, and refuses the others.
import json
import subprocess
import sys
import tempfile

import frappe
from frappe.app import application
from frappe.tests import IntegrationTestCase
from werkzeug.test import Client
from werkzeug.wrappers import Response

from sellos.access import registry
from sellos.access.matrix import MATRIX
from sellos.config.company_site import configure_company_site
from sellos.testing.users import PASSWORD, TEST_USERS, create_test_users
from sellos.tests import ui_fixtures
from sellos.tests.phones import forms

FRESH_PROCESS = """
import sys
import sellos.access.registry as registry

assert "sellos.crm.api" not in sys.modules, "the CRM module was imported before the guard ran"
assert not registry.is_refused("sellos.crm.api.list_leads"), "a declared method was refused"
assert registry.is_refused("sellos.crm.api.not_declared"), "an undeclared method was allowed"
assert registry.is_refused("sellos.access.registry.guard_api"), "an unlisted method was allowed"
assert "sellos.crm.api" in sys.modules
print("ok")
"""


class TestGuardInAFreshProcess(IntegrationTestCase):
	"""SOS-P1-06A: the registry is complete in a process that imported no API module (the cause of the 403s)."""

	def test_a_declared_method_is_not_refused_and_an_undeclared_one_is(self):
		result = subprocess.run(
			[sys.executable, "-c", FRESH_PROCESS],
			capture_output=True,
			text=True,
			cwd=tempfile.gettempdir(),
			check=False,
		)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("ok", result.stdout)

	def test_every_method_in_the_matrix_is_declared_after_loading(self):
		registry.load_declared_modules()
		for path in MATRIX:
			self.assertIn(path, registry.declared_methods(), path)
			self.assertFalse(registry.is_refused(path), path)


class TestCrmOverHttp(IntegrationTestCase):
	"""SOS-P1-06A: real requests, as the permission matrix says: Company Admin and Agent in, the others refused."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		configure_company_site()
		create_test_users()
		frappe.db.commit()  # the requests run in their own transactions  # nosemgrep

	def call(self, role, method, data=None):
		client = Client(application, Response)
		headers = {"Host": frappe.local.site}
		spec = TEST_USERS[role]
		client.post("/api/method/login", data={"usr": spec["email"], "pwd": PASSWORD}, headers=headers)
		return client.post(f"/api/method/sellos.crm.api.{method}", data=data or {}, headers=headers)

	def test_list_leads_and_save_client_work_for_company_admin_and_agent(self):
		for role in ("company_admin", "agent"):
			self.assertEqual(self.call(role, "list_leads").status_code, 200, role)
			values = json.dumps({"client_name": f"P106A {role}", "client_type": "Buyer"})
			response = self.call(role, "save_client", {"values": values})
			self.assertEqual(response.status_code, 200, f"{role}: {response.get_data(as_text=True)}")
		frappe.db.rollback()

	def test_roles_with_no_crm_access_are_refused(self):
		for role in ("client", "platform_admin", "basic"):
			self.assertEqual(self.call(role, "list_leads").status_code, 403, role)
			self.assertEqual(self.call(role, "save_client").status_code, 403, role)

	def test_an_undeclared_sellos_method_is_still_refused_for_every_role(self):
		for role in ("company_admin", "agent"):
			response = self.call(role, "not_declared")
			self.assertEqual(response.status_code, 403, role)


class TestCompanySiteSetup(IntegrationTestCase):
	"""SOS-P1-06A: a fresh company site is configured by the same code provisioning uses."""

	def tearDown(self):
		frappe.db.rollback()

	def test_it_makes_the_roles_and_a_company_name_and_is_safe_to_run_again(self):
		configure_company_site()
		first = configure_company_site()
		self.assertTrue(first["company_name"])
		for role in ("SellOS Company Admin", "SellOS Agent", "SellOS Client", "SellOS Channel Partner"):
			self.assertTrue(frappe.db.exists("Role", role), role)
		self.assertEqual(configure_company_site("Other Realty")["company_name"], "Other Realty")

	def test_the_test_site_setup_calls_it(self):
		ui_fixtures._configure_company_site()
		self.assertTrue(frappe.get_doc("SellOS Settings").company_name)


class TestFixtures(IntegrationTestCase):
	"""SOS-P1-06A: the agent leads and client fixtures read back as their docstrings say."""

	def setUp(self):
		frappe.set_user("Administrator")
		ui_fixtures.remove_seeded_leads()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		ui_fixtures.remove_seeded_leads()  # the fixtures commit, so a rollback does not undo them

	def test_seed_agent_leads_gives_the_agent_one_lead_and_hides_the_others(self):
		seeded = ui_fixtures.seed_agent_leads()
		self.assertEqual(len(seeded["others"]), 2)
		frappe.set_user(TEST_USERS["agent"]["email"])
		from sellos.crm import api

		seen = [lead["client_name"] for lead in api.list_leads()]
		self.assertIn(seeded["own"], seen)
		for other in seeded["others"]:
			self.assertNotIn(other, seen)

	def test_remove_seeded_leads_removes_everything_the_seeds_made_and_says_so(self):
		"""SOS-SETUP-24: the specs that seed call this in their after hook, and cy.bench reads its JSON."""
		ui_fixtures.seed_agent_leads()
		ui_fixtures.seed_client_with_phone(seed=21)
		self.assertEqual(ui_fixtures.remove_seeded_leads(), {"clients": 4, "leads": 4})
		self.assertEqual(ui_fixtures.remove_seeded_leads(), {"clients": 0, "leads": 0})
		frappe.set_user(TEST_USERS["agent"]["email"])
		from sellos.crm import api

		self.assertFalse([r for r in api.list_leads() if r["client_name"].startswith("Gate ")])

	def test_seed_client_with_phone_keeps_the_old_and_new_number_in_the_history(self):
		# Frappe skips change history while tests run, so run the fixture the way bench execute does.
		in_test, frappe.in_test = frappe.in_test, False
		try:
			seeded = ui_fixtures.seed_client_with_phone(seed=21)
		finally:
			frappe.in_test = in_test
		client = frappe.get_doc("Client", seeded["client"])
		self.assertEqual(client.client_name, seeded["client_name"])
		self.assertEqual(frappe.get_doc("Lead", seeded["lead"]).client, seeded["client"])
		self.assertEqual(len(seeded["phone_forms"]), 8)
		self.assertEqual(seeded["phone_forms"][0], client.phone)
		versions = " ".join(
			frappe.get_all(
				"Version", filters={"ref_doctype": "Client", "docname": seeded["client"]}, pluck="data"
			)
		)
		for number in (seeded["phone_forms"][0], seeded["phone_forms"][4]):
			self.assertIn(number, versions)
		self.assertEqual(seeded["phone_forms"][:4], forms(client.phone))

	def test_set_company_branding_sets_and_clears_the_logo(self):
		self.assertEqual(
			ui_fixtures.set_company_branding("Logo Realty", "/files/x.png")["logo"], "/files/x.png"
		)
		self.assertEqual(ui_fixtures.set_company_branding(logo="")["logo"], "")
