import re
import unittest

from sellos.tests import phones


class TestPhones(unittest.TestCase):
	"""SOS-P1-06: the fake phone number helpers."""

	def test_indian_mobiles_have_the_right_shape(self):
		for seed in range(1, 40):
			self.assertRegex(phones.in_mobile(seed), r"^\+91[6-9]\d{9}$")

	def test_australian_and_uae_mobiles_have_the_right_shape(self):
		for seed in range(1, 40):
			self.assertRegex(phones.au_mobile(seed), r"^\+614\d{8}$")
			self.assertRegex(phones.ae_mobile(seed), r"^\+9715\d{8}$")

	def test_the_same_seed_gives_the_same_number_and_other_seeds_differ(self):
		self.assertEqual(phones.in_mobile(5), phones.in_mobile(5))
		self.assertEqual(len({phones.in_mobile(seed) for seed in range(1, 200)}), 199)

	def test_a_near_number_differs_only_in_the_last_digit(self):
		for seed in range(1, 20):
			base, near = phones.in_mobile(seed), phones.near_in_mobile(seed)
			self.assertNotEqual(base, near)
			self.assertEqual(base[:-1], near[:-1])

	def test_forms_lists_every_way_a_number_can_appear(self):
		number = phones.in_mobile(3)
		forms = phones.forms(number)
		self.assertIn(number, forms)
		self.assertIn(number.lstrip("+"), forms)
		self.assertTrue(any(re.fullmatch(r"[6-9]\d{9}", form) for form in forms))
		self.assertEqual(len(set(forms)), len(forms))
