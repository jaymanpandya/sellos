"""SOS-P0-02: the sellos app has the agreed subpackages, each with a one line docstring."""

import importlib
import unittest

SUBPACKAGES = ("access", "telephony", "intel", "inventory", "reports", "scraper", "whatsapp", "billing")


class TestSubpackages(unittest.TestCase):
	"""SOS-P0-02 subpackage skeletons."""

	def test_each_subpackage_imports_with_one_line_docstring(self):
		for name in SUBPACKAGES:
			module = importlib.import_module(f"sellos.{name}")
			doc = (module.__doc__ or "").strip()
			self.assertTrue(doc, f"sellos.{name} has no docstring")
			self.assertEqual(len(doc.splitlines()), 1, f"sellos.{name} docstring is not one line")

	def test_docstrings_name_no_frappe(self):
		for name in SUBPACKAGES:
			module = importlib.import_module(f"sellos.{name}")
			self.assertNotIn("frappe", module.__doc__.lower())
