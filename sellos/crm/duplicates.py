"""Find the client a person already is, and merge two clients (SOS-P1-16).

`find_matches` is the one matching function. The screens (through `sellos.crm.api.find_duplicates`),
the website endpoint (SOS-P1-09) and the bought list import (SOS-P1-12) all call it, so a number is
matched the same way everywhere. It matches on the phone, the overseas phone and the email.

A phone number is normalised to its country code and digits: an Indian number with or without
spaces, +91, 91, 0091 or a leading 0 becomes +91 and ten digits. Normalised numbers are stored in
`Client.phone_key` and `Client.overseas_phone_key`, at permission level 1 like the numbers
themselves, so a match is an indexed lookup and never reads a number the viewer may not see.
"""

import frappe
from frappe import _

# What a match reports as the reason, in the order the screens show them.
PHONE, OVERSEAS_PHONE, EMAIL = "phone", "overseas_phone", "email"
# Fields a merge copies to the kept client when it has none of its own.
FILLED_FROM_MERGED = ("phone", "overseas_phone", "email", "city", "country_of_residence")


def normalise_phone(value) -> str:
	"""'+91' and ten digits for an Indian number, '+' and digits for any other, '' when unusable.

	A number with no country code and ten digits is Indian, as is one with a leading 0 and ten
	digits or the code 91 in front. Anything with a plus keeps its own country code."""
	text = str(value or "").strip()
	digits = "".join(ch for ch in text if ch.isdigit())
	if not digits:
		return ""
	if text.startswith("+"):
		pass
	elif digits.startswith("00"):
		digits = digits[2:]
	elif len(digits) == 10:
		digits = "91" + digits
	elif len(digits) == 11 and digits.startswith("0"):
		digits = "91" + digits[1:]
	elif len(digits) < 11:
		return ""
	return "+" + digits if len(digits) >= 8 else ""


def normalise_email(value) -> str:
	return str(value or "").strip().lower()


def find_matches(phone=None, overseas_phone=None, email=None, exclude=None) -> list[dict]:
	"""Every client that shares a phone number, an overseas phone or an email with what is given.

	Each number given is compared with both stored numbers, so a number typed in the wrong box still
	matches. Returns [{"name", "matched_on": [...], "archived"}], best match first. It ignores the
	caller's permissions on purpose: the caller decides what to show (`sellos.crm.api.find_duplicates`
	shows only what the viewer's role allows). `exclude` is a client to leave out (the one being edited)."""
	keys = {key for key in (normalise_phone(phone), normalise_phone(overseas_phone)) if key}
	address = normalise_email(email)
	conditions = []
	if keys:
		conditions.append(["phone_key", "in", sorted(keys)])
		conditions.append(["overseas_phone_key", "in", sorted(keys)])
	if address:
		conditions.append(["email", "=", address])
	if not conditions:
		return []
	rows = frappe.get_all(
		"Client",
		or_filters=conditions,
		fields=["name", "phone_key", "overseas_phone_key", "email", "archived", "creation"],
		order_by="creation asc",
	)
	found = []
	for row in rows:
		if exclude and row.name == exclude:
			continue
		reasons = []
		if row.phone_key in keys:
			reasons.append(PHONE)
		if row.overseas_phone_key in keys:
			reasons.append(OVERSEAS_PHONE)
		if address and normalise_email(row.email) == address:
			reasons.append(EMAIL)
		if reasons:
			found.append({"name": row.name, "matched_on": reasons, "archived": row.archived})
	return sorted(found, key=lambda m: (-len(m["matched_on"]), m["archived"]))


def merge_clients(keep: str, merged: str) -> dict:
	"""Move every lead of `merged` to `keep`, then archive `merged`. Nothing is deleted.

	The leads keep their activities, tasks, site visits and consent records, because those belong to
	the lead. Each lead is saved, so its change history shows the move. The kept client gets the
	details it lacked (a phone, an email) from the merged one. The merge is logged as a comment on
	both clients, and the merged client points at the kept one in `merged_into`. The caller checks
	who may merge."""
	if keep == merged:
		frappe.throw(_("Choose two different clients to merge."))
	keeper = frappe.get_doc("Client", keep)
	gone = frappe.get_doc("Client", merged)
	if keeper.merged_into:
		frappe.throw(_("{0} was merged into {1} and cannot be kept.").format(keep, keeper.merged_into))
	if gone.merged_into:
		frappe.throw(_("{0} was already merged into {1}.").format(merged, gone.merged_into))

	leads = frappe.get_all("Lead", filters={"client": merged}, pluck="name", order_by="creation asc")
	for name in leads:
		lead = frappe.get_doc("Lead", name)
		lead.client = keep
		lead.flags.ignore_permissions = True
		lead.save(ignore_version=False)  # the history always shows the move

	for field in FILLED_FROM_MERGED:
		if not keeper.get(field) and gone.get(field):
			keeper.set(field, gone.get(field))
	keeper.flags.ignore_permissions = True
	keeper.save(ignore_version=False)

	gone.merged_into = keep
	gone.archived = 1
	gone.flags.ignore_permissions = True
	gone.save(ignore_version=False)

	by = frappe.session.user
	keeper.add_comment(
		"Info", _("{0} merged client {1} into this one. {2} lead(s) moved.").format(by, merged, len(leads))
	)
	gone.add_comment(
		"Info", _("{0} merged this client into {1}. {2} lead(s) moved.").format(by, keep, len(leads))
	)
	return {"kept": keep, "merged": merged, "leads_moved": leads}
