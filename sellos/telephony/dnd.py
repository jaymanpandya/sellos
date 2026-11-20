"""The do not call list (SOS-P2-10): import it, check a number against it, flag the lead.

A listed number gives the lead the consent status Registered DND, and nothing more. The status is stored
only through `consent.record_dnd_result` (SOS-P1-08), the function SOS-P1-12 uses too. No field is added
to Lead. Consent never blocks (Jayman, 10 November 2026): a listed number shows an amber warning on the
lead, the caller queue and the call log, and the call proceeds. Only the one consent function may refuse,
and only when Consent enforcement is On. The rules are for India.
"""

import re

import frappe
from frappe import _
from frappe.utils import now_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.crm import consent

DOCTYPE = "Do Not Call Number"
MAX_ROWS = 5000
MAX_CHARS = 1_000_000
_NATIONAL = re.compile(r"^[6-9]\d{9}$")
_CELLS = re.compile(r"[,;\t]")


def normalise(value) -> str | None:
	"""An Indian mobile number as +91 and ten digits, or None when it is not one."""
	digits = re.sub(r"\D", "", str(value or ""))
	if len(digits) == 12 and digits.startswith("91"):
		digits = digits[2:]
	elif len(digits) == 11 and digits.startswith("0"):
		digits = digits[1:]
	return f"+91{digits}" if _NATIONAL.match(digits) else None


def _variants(number) -> list[str]:
	national = number[-10:]
	return [number, f"91{national}", national, f"0{national}"]


def parse_numbers(text) -> tuple[list[str], int]:
	"""The numbers in a text (one a line, or a CSV with the number in any column), and the count of lines
	that held no valid Indian mobile number. A header line is not counted."""
	text = str(text or "").lstrip("﻿")
	if len(text) > MAX_CHARS:
		frappe.throw(_("The file is too large. Import at most {0} numbers at a time.").format(MAX_ROWS))
	numbers, skipped, seen = [], 0, set()
	lines = [line for line in text.splitlines() if line.strip()]
	if len(lines) > MAX_ROWS + 1:
		frappe.throw(_("The list has more than {0} numbers. Split it and import the parts.").format(MAX_ROWS))
	for index, line in enumerate(lines):
		found = [n for n in (normalise(cell) for cell in _CELLS.split(line)) if n]
		if not found:
			if not (index == 0 and not re.search(r"\d", line)):
				skipped += 1
			continue
		for number in found:
			if number not in seen:
				seen.add(number)
				numbers.append(number)
	return numbers, skipped


def is_listed(number) -> bool:
	normal = normalise(number)
	return bool(normal and frappe.db.exists(DOCTYPE, normal))


def lead_number(lead) -> str | None:
	client = frappe.db.get_value("Lead", lead, "client")
	return normalise(frappe.db.get_value("Client", client, "phone")) if client else None


def apply_to_lead(lead) -> bool:
	"""Check the lead's number against the list. A listed number gives the lead Registered DND. Returns
	True when the number is listed. Safe to run again, and it never refuses anything."""
	number = lead_number(lead)
	if not number or not is_listed(number):
		return False
	if not frappe.db.get_value("Lead", lead, "dnd_registered"):
		consent.record_dnd_result(lead, True)
	return True


def apply_numbers(numbers) -> int:
	"""Flag every lead whose client's phone is one of `numbers`. Returns how many leads were newly flagged."""
	flagged = 0
	for start in range(0, len(numbers), 200):
		variants = [v for n in numbers[start : start + 200] for v in _variants(n)]
		clients = frappe.get_all("Client", filters={"phone": ["in", variants]}, pluck="name")
		if not clients:
			continue
		leads = frappe.get_all("Lead", filters={"client": ["in", clients], "dnd_registered": 0}, pluck="name")
		for lead in leads:
			consent.record_dnd_result(lead, True)
			flagged += 1
	return flagged


@sellos_api(COMPANY_ADMIN)
def import_do_not_call_list(text, source=None):
	"""Add the numbers of a do not call list (SOS-P2-10). Leads with a listed number become Registered DND.
	Returns how many numbers were added, were already listed or were skipped, and how many leads were flagged."""
	numbers, skipped = parse_numbers(text)
	if not numbers:
		frappe.throw(_("The list has no valid Indian mobile numbers (+91 and ten digits)."))
	existing = set()
	for start in range(0, len(numbers), 500):
		existing.update(
			frappe.get_all(DOCTYPE, filters={"name": ["in", numbers[start : start + 500]]}, pluck="name")
		)
	added = 0
	for number in numbers:
		if number in existing:
			continue
		frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"number": number,
				"source": (source or "").strip()[:140],
				"imported_on": now_datetime(),
				"imported_by": frappe.session.user,
			}
		).insert(ignore_permissions=True)
		added += 1
	flagged = apply_numbers(numbers)
	return {
		"added": added,
		"already_listed": len(existing),
		"skipped": skipped,
		"leads_flagged": flagged,
		"total": frappe.db.count(DOCTYPE),
	}


@sellos_api(COMPANY_ADMIN)
def do_not_call_summary():
	"""How many numbers the list holds."""
	return {"total": frappe.db.count(DOCTYPE)}
