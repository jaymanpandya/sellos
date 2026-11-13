# P1.04 the six roles exist (the Sales Manager since SOS-SETUP-35) and only the Platform Admin may use the desk.
import unittest

import frappe

from sellos.access.roles import ROLES, ensure_roles


class TestRoles(unittest.TestCase):
	def test_six_roles_exist_after_install(self):
		ensure_roles()
		self.assertEqual(len(ROLES), 6)
		self.assertIn("SellOS Sales Manager", ROLES)
		for role in ROLES:
			self.assertTrue(frappe.db.exists("Role", role), role)

	def test_only_the_platform_admin_may_use_the_desk(self):
		ensure_roles()
		for role, desk_access in ROLES.items():
			self.assertEqual(frappe.db.get_value("Role", role, "desk_access"), desk_access, role)
		self.assertEqual([r for r, d in ROLES.items() if d], ["SellOS Platform Admin"])

	def test_ensure_roles_can_run_twice(self):
		ensure_roles()
		ensure_roles()
		self.assertEqual(frappe.db.count("Role", {"name": ["in", list(ROLES)]}), 6)

	def test_every_role_lands_in_the_web_app_after_sign_in(self):
		"""SOS-SETUP-35: a new role (the Sales Manager) must be in hooks.role_home_page, or its users land on /me."""
		from sellos import hooks

		self.assertEqual(set(hooks.role_home_page), set(ROLES))
		self.assertEqual(set(hooks.role_home_page.values()), {"sellos"})
