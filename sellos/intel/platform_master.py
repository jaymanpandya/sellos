"""The platform master of buildings (SOS-P3-04), on the control site only.

The Platform Admin seeds it from a file (the corridor sample, or a real one from SOS-P3-04A) and curates it.
A company building is linked to a platform building by the `platform_building` id on its own record, and company
sites receive building level figures only, through a role checked API (SOS-P3-12 keeps parties' names here).
A building a company adds that is not on the master stays the company's own, with no market data until it is linked.
"""

import json
from pathlib import Path

import frappe
from frappe import _

from sellos.intel.markets import MAX_FILE_CHARS, SAMPLE_FILE
from sellos.provisioning.control import is_control_site

PLATFORM = "Platform Building"
FIELDS = ("village", "tahsil", "district", "country")


def _squash(value) -> str:
	return " ".join(str(value or "").split())


def load_platform_master(text=None):
	"""Add the buildings of a file to the master, or the shipped sample when no text is given. A building already
	there (the same RERA number, or the same name, area and country) is left as it is."""
	if not is_control_site():
		frappe.throw(_("The platform master is kept on the control site."), frappe.PermissionError)
	text = Path(SAMPLE_FILE).read_text(encoding="utf-8") if text in (None, "") else text
	if len(text) > MAX_FILE_CHARS:
		frappe.throw(_("The file is too large."))
	try:
		data = json.loads(text)
	except ValueError:
		frappe.throw(_("The file is not valid JSON."))
	rows = data.get("buildings") if isinstance(data, dict) else None
	if not isinstance(rows, list):
		frappe.throw(_("The file needs a list called buildings."))
	created = skipped = 0
	for row in rows:
		name, area = _squash(row.get("name")), _squash(row.get("market"))
		rera = _squash(row.get("rera")).replace(" ", "").upper()
		same = {"building_name": name, "area_name": area, "country": row.get("country") or ""}
		if frappe.db.exists(PLATFORM, same) or (rera and frappe.db.exists(PLATFORM, {"rera_number": rera})):
			skipped += 1
			continue
		frappe.get_doc(
			{
				"doctype": PLATFORM,
				**same,
				"cts_numbers": "\n".join(_squash(c) for c in row.get("cts") or []),
				"rera_number": rera,
				"source": "Sample file" if not text else "File",
				**{k: row.get(k) for k in FIELDS if k != "country"},
			}
		).insert()
		created += 1
	return {"created": created, "skipped": skipped}
