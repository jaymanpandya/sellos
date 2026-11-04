# P1.04 every API method declares its roles, and a method with no declaration is denied.
import unittest

import frappe
from werkzeug.test import Client
from werkzeug.wrappers import Response

from sellos.access.registry import (
	declared_methods,
	is_refused,
	method_from_path,
	sellos_api,
	undeclared_whitelisted_methods,
)
from sellos.access.roles import AGENT, COMPANY_ADMIN, ensure_roles


@sellos_api(COMPANY_ADMIN)
def _declared_for_company_admin():
	return "ok"


@frappe.whitelist()
def _whitelisted_without_declaration():
	return "should never run over HTTP"


MODULE = __name__


class TestRegistryUnits(unittest.TestCase):
	def test_a_declaration_needs_at_least_one_role(self):
		with self.assertRaises(ValueError):
			sellos_api()

	def test_the_declaration_is_recorded(self):
		self.assertEqual(
			declared_methods()[f"{MODULE}._declared_for_company_admin"], frozenset({COMPANY_ADMIN})
		)

	def test_undeclared_whitelisted_methods_are_found(self):
		self.assertIn(f"{MODULE}._whitelisted_without_declaration", undeclared_whitelisted_methods())
		self.assertNotIn(f"{MODULE}._declared_for_company_admin", undeclared_whitelisted_methods())

	def test_only_sellos_methods_without_a_declaration_are_refused(self):
		self.assertTrue(is_refused("sellos.anything.new_method"))
		self.assertFalse(is_refused(f"{MODULE}._declared_for_company_admin"))
		self.assertFalse(is_refused("frappe.auth.get_logged_user"))
		self.assertFalse(is_refused(None))

	def test_method_names_are_read_from_both_api_versions(self):
		self.assertEqual(method_from_path("/api/method/sellos.a.b"), "sellos.a.b")
		self.assertEqual(method_from_path("/api/v2/method/sellos.a.b"), "sellos.a.b")
		self.assertIsNone(method_from_path("/app/user"))


class TestRegistryRequests(unittest.TestCase):
	PASSWORD = "Zx9!qwerty_long_p104"

	@classmethod
	def setUpClass(cls):
		ensure_roles()
		cls.users = {}
		for i, role in enumerate((COMPANY_ADMIN, AGENT)):
			email = f"p104_role_{i}@example.com"
			if not frappe.db.exists("User", email):
				user = frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": "P104",
						"send_welcome_email": 0,
						"new_password": cls.PASSWORD,
					}
				)
				user.append("roles", {"role": role})
				user.insert()
			cls.users[role] = email
		frappe.db.commit()  # the requests run in their own transactions  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for email in cls.users.values():
			frappe.delete_doc("User", email, force=True)
		frappe.db.commit()  # removes the committed test users  # nosemgrep

	def _call(self, role, method):
		from frappe.app import application

		client = Client(application, Response)
		headers = {"Host": frappe.local.site}
		client.post(
			"/api/method/login", data={"usr": self.users[role], "pwd": self.PASSWORD}, headers=headers
		)
		return client.post(f"/api/method/{method}", headers=headers)

	def test_the_declared_role_can_call_and_another_role_cannot(self):
		method = f"{MODULE}._declared_for_company_admin"
		self.assertEqual(self._call(COMPANY_ADMIN, method).status_code, 200)
		self.assertEqual(self._call(AGENT, method).status_code, 403)

	def test_a_method_with_no_declaration_is_denied_to_every_role(self):
		method = f"{MODULE}._whitelisted_without_declaration"
		for role in (COMPANY_ADMIN, AGENT):
			self.assertEqual(self._call(role, method).status_code, 403, role)
