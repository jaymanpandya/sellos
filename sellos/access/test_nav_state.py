"""SOS-LOOP design system pass: the sidebar's open and closed sections are kept per person on the server.

Each person reads and writes only their own value; unknown section keys are dropped; every role may call both
methods (the permission matrix, sellos/access/matrix.py, says which roles).
"""

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access import preferences
from sellos.access.matrix import MATRIX


class TestNavState(IntegrationTestCase):
	"""SOS-LOOP design system pass: sidebar state per person."""

	def setUp(self):
		self.user = "Administrator"
		self.addCleanup(frappe.defaults.clear_default, preferences.DEFAULT_KEY, parent=self.user)
		frappe.set_user(self.user)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_nothing_is_closed_until_a_person_closes_a_section(self):
		self.assertEqual(preferences.get_nav_state(), {"closed": []})

	def test_a_closed_section_is_remembered_and_unknown_keys_are_dropped(self):
		saved = preferences.set_nav_state(["money", "bogus", "sales"])
		self.assertEqual(saved, {"closed": ["sales", "money"]})
		self.assertEqual(preferences.get_nav_state(), {"closed": ["sales", "money"]})
		self.assertEqual(preferences.set_nav_state([]), {"closed": []})

	def test_a_json_string_is_read_as_a_list(self):
		self.assertEqual(preferences.set_nav_state('["company"]'), {"closed": ["company"]})

	def test_every_role_may_call_both_methods(self):
		self.assertEqual(len(MATRIX["sellos.access.preferences.get_nav_state"]), 6)
		self.assertEqual(
			MATRIX["sellos.access.preferences.get_nav_state"],
			MATRIX["sellos.access.preferences.set_nav_state"],
		)
