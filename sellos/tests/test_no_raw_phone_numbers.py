"""SOS-P1-06: no hand written phone numbers in tests or Cypress specs.

A phone number written by hand is a number that can be invalid, can collide with another test's,
and is real personal data in the repository. Numbers come from sellos.tests.phones, and a Cypress
spec gets its number from the backend fixture that seeds its data.

BuildOS started with 33 files on an allowed list and had to shrink it. SellOS starts with none,
so the list is empty and stays empty.

SOS-SETUP-33: the scan lives in sellos.testing.guards, which scripts/check-guards.sh runs in a
second without a database, so the agent sees it before the gate does.
"""

import unittest

from sellos.testing import guards


class TestNoRawPhoneNumbers(unittest.TestCase):
	def test_no_test_or_spec_writes_a_phone_number_by_hand(self):
		found = guards.raw_phone_numbers()
		self.assertEqual(found, [], guards.message("phones", found))

	def test_the_allowed_list_is_empty(self):
		self.assertEqual(guards.ALLOWED_PHONE_FILES, frozenset())
