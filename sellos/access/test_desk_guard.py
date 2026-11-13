# P0.10 customer roles are redirected away from the desk.
import unittest
from typing import ClassVar

from sellos.access.desk_guard import is_blocked
from sellos.access.roles import ensure_roles


class TestDeskGuard(unittest.TestCase):
	def test_customer_roles_are_blocked_from_the_desk(self):
		for role in ("Company Admin", "Agent", "Client", "Channel Partner", "Sales Manager"):
			self.assertTrue(is_blocked("a@x.com", ["All", f"SellOS {role}"], "/app/user"), role)
			self.assertTrue(is_blocked("a@x.com", [f"SellOS {role}"], "/app"), role)
			self.assertTrue(is_blocked("a@x.com", [f"SellOS {role}"], "/desk/user"), role)
			self.assertTrue(is_blocked("a@x.com", [f"SellOS {role}"], "/desk"), role)

	def test_other_paths_are_not_blocked(self):
		for path in ("/sellos", "/api/method/ping", "/application", "/login"):
			self.assertFalse(is_blocked("a@x.com", ["SellOS Agent"], path), path)

	def test_only_the_platform_admin_keeps_the_desk(self):
		self.assertFalse(is_blocked("p@x.com", ["SellOS Platform Admin"], "/app/user"))
		self.assertFalse(is_blocked("p@x.com", ["SellOS Platform Admin"], "/desk"))
		self.assertFalse(is_blocked("Administrator", ["System Manager"], "/desk"))

	def test_system_manager_and_users_with_no_sellos_role_are_blocked(self):
		self.assertTrue(is_blocked("s@x.com", ["SellOS Agent", "System Manager"], "/app"))
		self.assertTrue(is_blocked("s@x.com", ["System Manager"], "/desk"))
		self.assertTrue(is_blocked("u@x.com", ["Desk User"], "/app"))

	def test_a_guest_is_left_to_the_login_page(self):
		self.assertFalse(is_blocked("Guest", [], "/app"))


class TestDeskGuardRequests(unittest.TestCase):
	"""Real requests through the Frappe app, one user per SellOS role (P0.10)."""

	ROLES: ClassVar[dict[str, bool]] = {
		"SellOS Platform Admin": False,
		"SellOS Company Admin": True,
		"SellOS Agent": True,
		"SellOS Client": True,
		"SellOS Channel Partner": True,
		"SellOS Sales Manager": True,
	}
	PASSWORD = "Zx9!qwerty_long_p010"

	@classmethod
	def setUpClass(cls):
		import frappe

		ensure_roles()
		cls.users = {}
		for i, role in enumerate(cls.ROLES):
			email = f"p010_role_{i}@example.com"
			if not frappe.db.exists("User", email):
				user = frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": "P010",
						"send_welcome_email": 0,
						"new_password": cls.PASSWORD,
					}
				)
				user.append("roles", {"role": role})
				user.insert()
			cls.users[role] = email
		frappe.db.commit()  # the requests below run in their own transactions  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		import frappe

		frappe.set_user("Administrator")  # the requests above switch the session user
		for email in cls.users.values():
			frappe.delete_doc("User", email, force=True)
		frappe.db.commit()  # removes the committed test users  # nosemgrep

	def test_each_role_signs_in_to_the_app_and_customer_roles_cannot_open_the_desk(self):
		import frappe
		from frappe.app import application
		from werkzeug.test import Client
		from werkzeug.wrappers import Response

		for role, blocked in self.ROLES.items():
			client = Client(application, Response)
			headers = {"Host": frappe.local.site}
			login = client.post(
				"/api/method/login",
				data={"usr": self.users[role], "pwd": self.PASSWORD},
				headers=headers,
			)
			self.assertEqual(login.status_code, 200, role)
			self.assertEqual(login.json.get("home_page", "").lstrip("/"), "sellos", role)
			self.assertEqual(client.get("/sellos", headers=headers).status_code, 200, role)
			desk = client.get("/desk/user", headers=headers)
			if blocked:
				self.assertEqual(desk.status_code, 302, role)
				self.assertEqual(desk.headers.get("Location"), "/sellos", role)
			else:
				self.assertNotEqual(desk.headers.get("Location"), "/sellos", role)
