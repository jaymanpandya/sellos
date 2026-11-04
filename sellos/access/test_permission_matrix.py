# P1.05 every whitelisted sellos method is called as every role, as an outsider and as a guest.
import importlib
import pkgutil
import unittest

import frappe
from frappe.app import application
from frappe.tests.utils import whitelist_for_tests
from werkzeug.test import Client
from werkzeug.wrappers import Response

import sellos
from sellos.access.matrix import MATRIX
from sellos.access.registry import declared_methods, sellos_api, undeclared_whitelisted_methods
from sellos.access.roles import (
	AGENT,
	CHANNEL_PARTNER,
	CLIENT,
	COMPANY_ADMIN,
	PLATFORM_ADMIN,
	ROLES,
	ensure_roles,
)

PASSWORD = "Zx9!qwerty_long_p105"
OUTSIDER = "outsider"  # a user from another company: signed in, but holds no role on this site
SECRET = "p105-secret-company-data"


def import_all_sellos_modules():
	"""Import every non-test module, so every `@sellos_api` runs and fills the registry."""
	for module in pkgutil.walk_packages(sellos.__path__, "sellos."):
		last = module.name.rsplit(".", 1)[-1]
		if last.startswith("test_") or ".patches." in module.name or last == "matrix":
			continue
		importlib.import_module(module.name)


def production_methods(registry):
	return {path: roles for path, roles in registry.items() if ".test_" not in path}


def matrix_problems(matrix, registry, undeclared):
	"""Every way the matrix and the declarations can disagree. Empty means all is covered."""
	problems = []
	for path in sorted(registry):
		if path not in matrix:
			problems.append(f"{path} is declared but has no matrix entry")
		elif matrix[path] != registry[path]:
			problems.append(f"{path} matrix roles {sorted(matrix[path])} differ from {sorted(registry[path])}")
	problems += [f"{path} is in the matrix but not declared" for path in sorted(set(matrix) - set(registry))]
	problems += [f"{path} is whitelisted with no declaration" for path in undeclared]
	return problems


@sellos_api(COMPANY_ADMIN, PLATFORM_ADMIN)
def _matrix_probe():
	return SECRET


@whitelist_for_tests()
def _matrix_probe_open():
	return SECRET


class TestMatrixCoverage(unittest.TestCase):
	def test_every_production_method_is_in_the_matrix(self):
		import_all_sellos_modules()
		undeclared = [p for p in undeclared_whitelisted_methods() if ".test_" not in p]
		problems = matrix_problems(MATRIX, production_methods(declared_methods()), undeclared)
		self.assertEqual(problems, [], "\n".join(problems))

	def test_a_new_method_with_no_matrix_entry_is_reported(self):
		registry = {"sellos.x.new_method": frozenset({AGENT})}
		self.assertEqual(
			matrix_problems({}, registry, []), ["sellos.x.new_method is declared but has no matrix entry"]
		)

	def test_a_deliberately_open_method_is_reported(self):
		problems = matrix_problems({}, {}, undeclared_whitelisted_methods())
		self.assertIn(f"{__name__}._matrix_probe_open is whitelisted with no declaration", problems)

	def test_disagreeing_roles_are_reported(self):
		path = "sellos.x.m"
		problems = matrix_problems({path: frozenset({AGENT})}, {path: frozenset({CLIENT})}, [])
		self.assertEqual(len(problems), 1)
		self.assertIn("differ", problems[0])

	def test_a_stale_matrix_entry_is_reported(self):
		self.assertEqual(
			matrix_problems({"sellos.x.gone": frozenset({AGENT})}, {}, []),
			["sellos.x.gone is in the matrix but not declared"],
		)


class TestMatrixCalls(unittest.TestCase):
	"""Real requests through the Frappe app. The probe method stands in for production methods."""

	@classmethod
	def setUpClass(cls):
		ensure_roles()
		cls.users = {}
		for i, role in enumerate([*ROLES, OUTSIDER]):
			email = f"p105_user_{i}@example.com"
			if not frappe.db.exists("User", email):
				user = frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": "P105",
						"send_welcome_email": 0,
						"new_password": PASSWORD,
					}
				)
				if role != OUTSIDER:
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

	def _call(self, who, method):
		client = Client(application, Response)
		headers = {"Host": frappe.local.site}
		if who != "guest":
			client.post(
				"/api/method/login", data={"usr": self.users[who], "pwd": PASSWORD}, headers=headers
			)
		return client.post(f"/api/method/{method}", headers=headers)

	def test_every_role_outsider_and_guest_gets_the_declared_answer(self):
		method = f"{__name__}._matrix_probe"
		allowed = declared_methods()[method]
		for who in [*ROLES, OUTSIDER, "guest"]:
			response = self._call(who, method)
			if who in allowed:
				self.assertEqual(response.status_code, 200, who)
				self.assertIn(SECRET, response.get_data(as_text=True), who)
			else:
				self.assertEqual(response.status_code, 403 if who != "guest" else response.status_code, who)
				self.assertNotEqual(response.status_code, 200, who)
				self.assertNotIn(SECRET, response.get_data(as_text=True), who)

	def test_the_open_method_is_denied_to_everyone(self):
		method = f"{__name__}._matrix_probe_open"
		for who in [*ROLES, OUTSIDER, "guest"]:
			response = self._call(who, method)
			self.assertNotEqual(response.status_code, 200, who)
			self.assertNotIn(SECRET, response.get_data(as_text=True), who)
