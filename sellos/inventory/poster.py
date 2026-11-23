"""A Facebook poster's name and number on a draft listing (SOS-P3-12, decided by Jayman, question 7).

They are kept only on the draft Listing. The number is stored at permission level 1 (Company Admin) and
shown to everyone else masked, like a lead's phone. When the draft is rejected, published or archived, both
are deleted, and so is any copy in the change history.
"""

import json

import frappe

from sellos.crm.base import mask_phone

FIELDS = ("poster_name", "poster_phone", "poster_phone_masked")


def apply(doc) -> None:
	"""Called from Listing.validate: mask the number, or delete the details when the draft is over."""
	if doc.get("rejected") or doc.get("published") or doc.get("archived"):
		if any(doc.get(f) for f in FIELDS):
			doc.flags.poster_cleared = True
		for field in FIELDS:
			doc.set(field, None)
		if doc.get("rejected") and not doc.get("rejected_on"):
			doc.rejected_on = frappe.utils.now_datetime()
		return
	doc.poster_name = " ".join((doc.poster_name or "").split())
	doc.poster_phone_masked = mask_phone(doc.poster_phone)


def scrub_history(doc) -> None:
	"""Called from Listing.on_change after the details were deleted: take them out of the Version rows."""
	if not doc.flags.get("poster_cleared"):
		return
	for name in frappe.get_all(
		"Version", filters={"ref_doctype": doc.doctype, "docname": doc.name}, pluck="name"
	):
		data = json.loads(frappe.db.get_value("Version", name, "data") or "{}")
		for key in ("changed", "added", "removed"):
			data[key] = [row for row in data.get(key, []) if str(row[0]).split(".")[0] not in FIELDS]
		if any(data.get(k) for k in data):
			frappe.db.set_value("Version", name, "data", json.dumps(data), update_modified=False)
		else:
			frappe.db.delete("Version", {"name": name})
