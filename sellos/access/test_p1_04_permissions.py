# SOS-P1-04 five roles with a written table, and agents see only their own leads unless shared.
from pathlib import Path

import frappe
import frappe.share
from frappe.tests import IntegrationTestCase

from sellos.access.lead_permissions import has_permission
from sellos.access.matrix import MATRIX
from sellos.access.registry import declared_methods, load_declared_modules, undeclared_whitelisted_methods
from sellos.access.roles import ROLES, ensure_roles
from sellos.testing.users import TEST_USERS, create_test_users

DOC = Path(__file__).resolve().parents[2] / "docs" / "permissions.md"


def _email(key):
	return TEST_USERS[key]["email"]


class TestWrittenPermissionTable(IntegrationTestCase):
	def test_the_table_names_all_five_roles_and_their_code_names(self):
		text = DOC.read_text()
		self.assertEqual(len(ROLES), 5)
		for role in ROLES:
			self.assertIn(f"`{role}`", text, role)

	def test_the_table_lists_every_declared_api_method(self):
		text = DOC.read_text()
		for path in MATRIX:
			self.assertIn(path.rsplit(".", 1)[1], text, path)

	def test_every_declaration_is_in_the_matrix_and_none_is_open(self):
		load_declared_modules()
		declared = {p: r for p, r in declared_methods().items() if p.startswith("sellos.crm")}
		self.assertEqual(declared, {p: r for p, r in MATRIX.items() if p.startswith("sellos.crm")})
		# Probe functions that other test modules whitelist on purpose are not product methods.
		open_methods = [
			m for m in undeclared_whitelisted_methods() if not m.rsplit(".", 2)[-2].startswith("test_")
		]
		self.assertEqual(open_methods, [])


class TestAgentsSeeOnlyTheirOwnLeads(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _lead_owned_by(self, user):
		frappe.set_user(user)
		client = frappe.get_doc(
			{"doctype": "Client", "client_name": "P104 Buyer", "client_type": "Buyer"}
		).insert()
		return frappe.get_doc({"doctype": "Lead", "client": client.name, "source": "Website"}).insert()

	def _visible(self, user):
		frappe.set_user(user)
		try:
			return set(frappe.get_list("Lead", pluck="name"))
		except frappe.PermissionError:
			return set()  # refused outright is also seeing nothing

	def test_an_agent_cannot_see_another_agents_lead_unless_shared(self):
		agent, admin = _email("agent"), _email("company_admin")
		lead = self._lead_owned_by(admin)  # not the agent's, not assigned to them
		self.assertNotIn(lead.name, self._visible(agent))
		frappe.set_user(agent)
		self.assertFalse(has_permission(lead, "read", agent))

		frappe.set_user("Administrator")
		frappe.share.add("Lead", lead.name, agent, read=1)
		self.assertIn(lead.name, self._visible(agent))
		self.assertTrue(has_permission(lead, "read", agent))

	def test_an_agent_sees_a_lead_they_own_and_a_client_sees_none(self):
		own = self._lead_owned_by(_email("agent"))
		self.assertIn(own.name, self._visible(_email("agent")))
		self.assertIn(own.name, self._visible(_email("company_admin")))
		self.assertEqual(self._visible(_email("client")), set())
		self.assertNotIn(own.name, self._visible(_email("platform_admin")))
