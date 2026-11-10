# P1.06B phone numbers do not leak: the change history, the form loader, and the log of full numbers shown.
import json

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access import field_history
from sellos.access.roles import ensure_roles
from sellos.crm import api
from sellos.crm.base import mask_phone
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

OLD = phones.in_mobile(41)
NEW = phones.near_in_mobile(41)
LOG_METHOD = "Full phone number shown"


def as_user(key):
	frappe.set_user(TEST_USERS[key]["email"])


def loaded_history(name, loader="getdoc"):
	"""The text of the change history the loader sends the current user for a client."""
	frappe.local.response = frappe._dict({"docs": []})  # as a request starts
	if loader == "getdoc":
		field_history.getdoc("Client", name)
	else:
		field_history.get_docinfo(doctype="Client", name=name)
	return json.dumps(frappe.response["docinfo"]["versions"], default=str)


class TestPhoneLeaks(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		as_user("company_admin")
		client = api.save_client(values={"client_name": "Leak Probe", "client_type": "Buyer", "phone": OLD})
		api.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": email("agent")})
		# Frappe does not keep a history while tests run unless asked, so ask.
		doc = frappe.get_doc("Client", client["name"])
		doc.phone = NEW
		doc.flags.ignore_permissions = True
		doc.save(ignore_version=False)
		self.client_name = client["name"]
		frappe.db.delete("Access Log", {"method": LOG_METHOD})

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.response = frappe._dict()
		frappe.db.rollback()

	def test_the_history_holds_the_full_number_in_the_database(self):
		frappe.set_user("Administrator")
		raw = json.dumps(frappe.get_all("Version", filters={"docname": self.client_name}, pluck="data"))
		self.assertIn(NEW, raw)  # not vacuous: there is something to hide

	def test_an_agent_gets_no_full_number_from_the_history(self):
		as_user("agent")
		for loader in ("getdoc", "get_docinfo"):
			text = loaded_history(self.client_name, loader)
			for number in (OLD, NEW):
				for form in phones.forms(number):
					self.assertNotIn(form, text, loader)
			self.assertIn("phone_masked", text)  # the masked change is still shown

	def test_a_company_admin_sees_the_history_unchanged(self):
		as_user("company_admin")
		for loader in ("getdoc", "get_docinfo"):
			text = loaded_history(self.client_name, loader)
			self.assertIn(NEW, text, loader)
			self.assertIn(OLD, text, loader)

	def test_without_fields_removes_only_the_hidden_changes(self):
		data = json.dumps({"changed": [["phone", "a", "b"], ["city", "x", "y"]], "added": [], "removed": []})
		out = json.loads(field_history.without_fields(data, {"phone"}))
		self.assertEqual(out["changed"], [["city", "x", "y"]])
		self.assertEqual(field_history.without_fields("not json", {"phone"}), "not json")

	def test_the_phone_fields_are_the_unreadable_ones_for_an_agent_and_not_for_a_company_admin(self):
		as_user("agent")
		self.assertTrue({"phone", "overseas_phone"} <= field_history.unreadable_fields("Client"))
		as_user("company_admin")
		self.assertFalse({"phone", "overseas_phone"} & field_history.unreadable_fields("Client"))

	def test_the_api_masks_for_an_agent_and_a_partner_and_shows_full_to_a_company_admin(self):
		for key in ("agent", "channel_partner"):
			as_user(key)
			try:
				view = api.client_view(frappe.get_doc("Client", self.client_name))
			except frappe.PermissionError:
				continue  # a partner who sees no such client has nothing to leak
			self.assertEqual(view["phone"], mask_phone(NEW))
			self.assertNotIn(NEW[-9:], view["phone"])
		as_user("company_admin")
		self.assertEqual(api.client_view(frappe.get_doc("Client", self.client_name))["phone"], NEW)

	def test_showing_a_full_number_to_a_company_admin_is_logged_without_the_number(self):
		as_user("company_admin")
		frappe.db.delete("Access Log", {"method": LOG_METHOD})
		api.list_clients()
		rows = frappe.get_all("Access Log", filters={"method": LOG_METHOD}, fields=["user", "filters"])
		self.assertEqual(len(rows), 1, "one row per call")
		self.assertEqual(rows[0].user, email("company_admin"))
		self.assertIn(self.client_name, rows[0].filters)
		self.assertNotIn(NEW, rows[0].filters)

	def test_a_masked_view_is_not_logged(self):
		as_user("agent")
		frappe.db.delete("Access Log", {"method": LOG_METHOD})
		api.list_clients()
		self.assertEqual(frappe.db.count("Access Log", {"method": LOG_METHOD}), 0)


def email(key):
	return TEST_USERS[key]["email"]
