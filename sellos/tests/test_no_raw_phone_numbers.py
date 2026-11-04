"""SOS-P1-06: no hand written phone numbers in tests or Cypress specs.

A phone number written by hand is a number that can be invalid, can collide with another test's,
and is real personal data in the repository. Numbers come from sellos.tests.phones, and a Cypress
spec gets its number from the backend fixture that seeds its data.

BuildOS started with 33 files on an allowed list and had to shrink it. SellOS starts with none,
so the list is empty and stays empty.
"""

import re
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
ALLOWED = set()

# +91 followed by digits, or a ten digit national number that starts with 6 to 9, in a string.
RAW = [
	re.compile(r"\+91[\s-]?\d"),
	re.compile(r"""["'`(\s]([6-9]\d{9})["'`)\s,;]"""),
	re.compile(r"\+614\d"),
	re.compile(r"\+9715\d"),
]


def files_to_scan():
	yield from (APP_ROOT / "sellos").rglob("test_*.py")
	yield from (APP_ROOT / "cypress" / "integration").rglob("*.cy.js")


class TestNoRawPhoneNumbers(unittest.TestCase):
	def test_no_test_or_spec_writes_a_phone_number_by_hand(self):
		found = []
		for path in files_to_scan():
			relative = path.relative_to(APP_ROOT).as_posix()
			if relative in ALLOWED or path.name in {"test_no_raw_phone_numbers.py", "test_phones.py"}:
				continue
			for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
				if any(pattern.search(line) for pattern in RAW):
					found.append(f"{relative}:{number}: {line.strip()[:80]}")
		self.assertEqual(found, [], "Use sellos.tests.phones, never a literal number:\n" + "\n".join(found))
