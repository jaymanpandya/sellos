# P0.10 customer roles are redirected away from the desk.
import unittest

from sellos.access.desk_guard import is_blocked


class TestDeskGuard(unittest.TestCase):
	def test_customer_roles_are_blocked_from_the_desk(self):
		for role in ("Company Admin", "Agent", "Client", "Channel Partner"):
			self.assertTrue(is_blocked("a@x.com", ["All", f"SellOS {role}"], "/app/user"), role)
			self.assertTrue(is_blocked("a@x.com", [f"SellOS {role}"], "/app"), role)

	def test_other_paths_are_not_blocked(self):
		for path in ("/sellos", "/api/method/ping", "/application", "/login"):
			self.assertFalse(is_blocked("a@x.com", ["SellOS Agent"], path), path)

	def test_platform_admin_and_system_manager_keep_the_desk(self):
		self.assertFalse(is_blocked("p@x.com", ["SellOS Platform Admin"], "/app/user"))
		self.assertFalse(is_blocked("s@x.com", ["SellOS Agent", "System Manager"], "/app"))

	def test_guest_and_users_with_no_sellos_role_are_not_touched(self):
		self.assertFalse(is_blocked("Guest", [], "/app"))
		self.assertFalse(is_blocked("u@x.com", ["Desk User"], "/app"))


class TestDeskGuardRequests(unittest.TestCase):
	"""Real requests through the Frappe app, one user per SellOS role (P0.10)."""

	ROLES = {
		"SellOS Platform Admin": False,
		"SellOS Company Admin": True,
		"SellOS Agent": True,
		"SellOS Client": True,
		"SellOS Channel Partner": True,
	}
	PASSWORD = "Zx9!qwerty_long_p010"

	@classmethod
	def setUpClass(cls):
		import frappe

		cls.users = {}
		for i, role in enumerate(cls.ROLES):
			if not frappe.db.exists("Role", role):
				frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 0}).insert()
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
		frappe.db.commit()  # the requests below run in their own transactions

	@classmethod
	def tearDownClass(cls):
		import frappe

		frappe.set_user("Administrator")  # the requests above switch the session user
		for email in cls.users.values():
			frappe.delete_doc("User", email, force=True)
		for role in cls.ROLES:
			frappe.delete_doc("Role", role, force=True)
		frappe.db.commit()

	def test_each_role_signs_in_to_the_app_and_customer_roles_cannot_open_the_desk(self):
		import frappe
		from werkzeug.test import Client
		from werkzeug.wrappers import Response

		from frappe.app import application

		for role, blocked in self.ROLES.items():
			client = Client(application, Response)
			headers = {"Host": frappe.local.site}
			login = client.post(
				"/api/method/login",
				data={"usr": self.users[role], "pwd": self.PASSWORD},
				headers=headers,
			)
			self.assertEqual(login.status_code, 200, role)
			self.assertEqual(login.json.get("home_page"), "/sellos", role)
			self.assertEqual(client.get("/sellos", headers=headers).status_code, 200, role)
			desk = client.get("/app/user", headers=headers)
			if blocked:
				self.assertEqual(desk.status_code, 302, role)
				self.assertEqual(desk.headers.get("Location"), "/sellos", role)
			else:
				self.assertNotEqual(desk.headers.get("Location"), "/sellos", role)
