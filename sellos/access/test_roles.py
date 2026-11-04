# P1.04 the five roles exist and only the Platform Admin may use the desk.
import unittest

import frappe

from sellos.access.roles import ROLES, ensure_roles


class TestRoles(unittest.TestCase):
	def test_five_roles_exist_after_install(self):
		ensure_roles()
		self.assertEqual(len(ROLES), 5)
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
		self.assertEqual(frappe.db.count("Role", {"name": ["in", list(ROLES)]}), 5)
