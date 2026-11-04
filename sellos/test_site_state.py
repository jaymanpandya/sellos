import os

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.password import check_password

from sellos.testing.users import PASSWORD, TEST_USERS, create_test_users


class TestSiteState(IntegrationTestCase):
	"""Checks that the site really is in the state the code assumes."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_test_users()

	def test_app_is_installed(self):
		self.assertIn("sellos", frappe.get_installed_apps())

	def test_page_renderer_hook_is_registered(self):
		self.assertIn("sellos.spa.SellOSPage", frappe.get_hooks("page_renderer"))

	def test_built_frontend_exists(self):
		path = os.path.join(frappe.get_app_path("sellos"), "www", "sellos.html")
		self.assertTrue(os.path.isfile(path), "Run yarn build in frontend/")
		with open(path, encoding="utf-8") as f:  # nosemgrep: fixed path inside the app
			self.assertIn('id="app"', f.read())

	def test_every_test_user_exists_and_can_log_in(self):
		for key, spec in TEST_USERS.items():
			with self.subTest(user=key):
				self.assertTrue(frappe.db.exists("User", spec["email"]), f"{spec['email']} is missing")
				self.assertEqual(check_password(spec["email"], PASSWORD), spec["email"])
				roles = frappe.get_roles(spec["email"])
				for role in spec["roles"]:
					self.assertIn(role, roles)

	def test_every_sellos_role_has_a_test_user(self):
		roles = frappe.get_all("Role", filters={"name": ["like", "SellOS %"]}, pluck="name")
		covered = {role for spec in TEST_USERS.values() for role in spec["roles"]}
		self.assertEqual(sorted(set(roles) - covered), [], "Add a test user for each new role")
