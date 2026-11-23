"""Run the normaliser over the raw transaction table (SOS-P3-03).

`normalise_pending` reads Raw Transaction rows on the control site that have no Normalised Transaction yet
(or, with `force`, all of them, to repeat the cleaning after the rules change) and writes one Normalised
Transaction per readable record, named like its raw row. A record with any field it cannot read gets no
Normalised Transaction and is put on the review list (Normaliser Review, status Open, with the fields and
reasons). The raw row is never touched. A later run that can read a reviewed record writes its Normalised
Transaction and marks its review entry Resolved.
"""

import json

import frappe
from frappe.utils import now_datetime

from sellos.intel import normaliser

RAW = "Raw Transaction"
NORMAL = "Normalised Transaction"
REVIEW = "Normaliser Review"
BATCH = 500


def _problem_text(problems) -> str:
	return "\n".join(f"{name}: {reason}" for name, reason in problems)


def _write(doctype, name, values):
	if frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc({"doctype": doctype, "raw_transaction": name, **values}).insert(
			ignore_permissions=True
		)


def normalise_one(name, today=None) -> bool:
	"""Normalise one raw row. True when it was clean, False when it went to the review list."""
	row = frappe.db.get_value(RAW, name, ["source", "source_record_id", "raw_record"], as_dict=True)
	result = normaliser.normalise(json.loads(row.raw_record), today)
	now = now_datetime()
	common = {"source": row.source, "source_record_id": row.source_record_id}
	if result.ok:
		fields = dict(result.fields)
		fields.pop("source_record_id")
		fields["original_fields"] = json.dumps(fields.pop("originals"), sort_keys=True, ensure_ascii=False)
		_write(NORMAL, name, {**common, **fields, "normalised_at": now})
		if frappe.db.exists(REVIEW, name):
			frappe.db.set_value(REVIEW, name, "status", "Resolved")
		return True
	_write(
		REVIEW,
		name,
		{
			**common,
			"status": "Open",
			"problems": _problem_text(result.problems),
			"rules_version": normaliser.RULES_VERSION,
			"checked_at": now,
		},
	)
	return False


def normalise_pending(source=None, force=False, limit=BATCH, today=None) -> dict:
	"""Normalise up to `limit` raw rows not yet done. Returns the counts."""
	filters = {"source": source} if source else {}
	done = set() if force else set(frappe.get_all(NORMAL, pluck="name"))
	open_review = set(frappe.get_all(REVIEW, filters={"status": "Open"}, pluck="name"))
	counts = {"clean": 0, "review": 0}
	for name in frappe.get_all(RAW, filters=filters, pluck="name", order_by="creation asc, name asc"):
		if name in done:
			continue
		if name in open_review and not force and _already_checked(name):
			continue
		counts["clean" if normalise_one(name, today) else "review"] += 1
		if sum(counts.values()) >= limit:
			break
	return counts


def _already_checked(name) -> bool:
	"""An open review entry made under the current rules has nothing new to find."""
	return frappe.db.get_value(REVIEW, name, "rules_version") == normaliser.RULES_VERSION
