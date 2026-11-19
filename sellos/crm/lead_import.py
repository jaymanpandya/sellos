"""Import a bought lead list from a CSV file (SOS-P1-12).

The import maps the file's columns to a client and a lead, merges duplicates, and gives every lead an
honest consent status:

* Unknown: the default. A bought list proves no consent, so no Consent Record is made.
* Registered DND: when the file carries a known do not call result for the row. The result is stored
  only through `consent.record_dnd_result` (SOS-P1-08), the function SOS-P2-10 uses too.

Consent never blocks (Jayman, 10 November 2026). The import sets no flag, stage, archive mark or opt out
that stops a call, an SMS or a WhatsApp message: a do not call result shows an amber warning and
nothing more. The source is the Lead's own `source`, set to Bought list (SOS-P1-20).

Duplicates are merged by `duplicates.find_matches`, the one matching function (SOS-P1-16):
* two rows of the file that share a phone, an overseas phone or an email become one record;
* a row that matches a client already in SellOS is merged into that client. The client keeps what it
  has and gains only what it lacked. If the client already has a live lead no second lead is made, and
  the lead gets a note that the number appeared on the list.

SOS-P4-10C reuses `read_csv` and `suggest_mapping` for its own files.
"""

import csv
import io

import frappe
from frappe import _

from sellos.crm import consent, duplicates
from sellos.crm.base import mask_phone
from sellos.crm.lead_sources import BOUGHT_LIST, normalise

MAX_ROWS = 5000
MAX_CHARS = 3_000_000
SAMPLE_ROWS = 10
INDIA_CODE = "+91"

# The fields a column can be mapped to, and the header names that map to each without being told.
FIELDS = ("name", "phone", "overseas_phone", "email", "city", "notes", "do_not_call")
LABELS = {
	"name": "Name",
	"phone": "Phone",
	"overseas_phone": "Overseas phone",
	"email": "Email",
	"city": "City",
	"notes": "Notes",
	"do_not_call": "Do not call result",
}
ALIASES = {
	"name": ("name", "fullname", "clientname", "customername", "leadname", "contactname", "buyername"),
	"phone": ("phone", "mobile", "mobileno", "mobilenumber", "phonenumber", "contactnumber", "cell"),
	"overseas_phone": ("overseasphone", "internationalphone", "nriphone", "foreignphone"),
	"email": ("email", "emailid", "emailaddress", "mail"),
	"city": ("city", "town", "location"),
	"notes": ("notes", "note", "remarks", "comments", "requirement"),
	"do_not_call": (
		"dnd",
		"dndstatus",
		"dndresult",
		"donotcall",
		"donotcallresult",
		"dnc",
		"dncstatus",
		"ndnc",
		"ndncstatus",
	),
}
# A do not call result, by its normalised text. Anything else is not a known result.
REGISTERED_VALUES = frozenset(
	{"yes", "y", "true", "1", "dnd", "dnc", "ndnc", "registered", "listed", "donotcall", "blocked", "ondnd"}
)
NOT_REGISTERED_VALUES = frozenset(
	{"no", "n", "false", "0", "notregistered", "notdnd", "nondnd", "clear", "clean", "notlisted", "ok"}
)


# --- reading the file ---------------------------------------------------------------------------


def read_csv(text) -> tuple[list[str], list[dict]]:
	"""The header names and the rows (a dict per row, with its line number as `_row`) of a CSV text.

	Comma, semicolon and tab files are read. A byte order mark is dropped, empty lines are skipped."""
	text = str(text or "").lstrip("﻿")
	if len(text) > MAX_CHARS:
		frappe.throw(_("The file is too large. Import at most {0} rows at a time.").format(MAX_ROWS))
	lines = [line for line in text.splitlines() if line.strip()]
	if len(lines) < 2:
		frappe.throw(_("The file needs a header row and at least one row of leads."))
	head = lines[0]
	delimiter = max(",;\t", key=head.count)
	reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
	headers = [h.strip() for h in next(reader)]
	if len(lines) - 1 > MAX_ROWS:
		frappe.throw(_("The file has more than {0} rows. Split it and import the parts.").format(MAX_ROWS))
	rows = []
	for number, values in enumerate(reader, start=2):
		row = {header: (values[i].strip() if i < len(values) else "") for i, header in enumerate(headers)}
		row["_row"] = number
		rows.append(row)
	return headers, rows


def suggest_mapping(headers) -> dict:
	"""{field: header} for each field a header name suggests. A header is used for one field only."""
	mapping, used = {}, set()
	for field in FIELDS:
		for header in headers:
			if header not in used and normalise(header) in ALIASES[field]:
				mapping[field] = header
				used.add(header)
				break
	return mapping


def _clean_mapping(mapping, headers) -> dict:
	mapping = frappe.parse_json(mapping) if isinstance(mapping, str) else (mapping or {})
	clean = {}
	for field, header in mapping.items():
		if not header:
			continue
		if field not in FIELDS:
			frappe.throw(_("{0} is not a field a column can be mapped to.").format(field))
		if header not in headers:
			frappe.throw(_("The file has no column called {0}.").format(header))
		clean[field] = header
	if "name" not in clean:
		frappe.throw(_("Choose the column that holds the name."))
	if not ({"phone", "overseas_phone", "email"} & set(clean)):
		frappe.throw(_("Choose a column for the phone, the overseas phone or the email."))
	return clean


def dnd_result(value):
	"""True when the text says the number is on the do not call list, False when it says it is not, None
	when the file gives no known result."""
	key = normalise(value)
	if key in REGISTERED_VALUES:
		return True
	if key in NOT_REGISTERED_VALUES:
		return False
	return None


# --- one row, and the merge of rows -------------------------------------------------------------


def _parse_row(row, mapping) -> dict:
	def get(field):
		return (row.get(mapping[field]) or "").strip() if field in mapping else ""

	phone = overseas = ""
	for field in ("phone", "overseas_phone"):
		key = duplicates.normalise_phone(get(field))
		if not key:
			continue
		if key.startswith(INDIA_CODE) and not phone:
			phone = key
		elif not overseas:
			overseas = key
	email = duplicates.normalise_email(get("email"))
	if email and ("@" not in email or " " in email):
		email = ""
	text = get("do_not_call")
	return {
		"rows": [row["_row"]],
		"name": get("name"),
		"phone": phone,
		"overseas_phone": overseas,
		"email": email,
		"city": get("city"),
		"notes": get("notes"),
		"dnd": dnd_result(text),
		"unrecognised_dnd": bool(text) and dnd_result(text) is None,
	}


def _merge_into(base, extra):
	"""Fold a later row of the same person into the first: the first value kept, blanks filled. A known
	registered result is never lost to a later row that says not registered."""
	base["rows"] += extra["rows"]
	for field in ("name", "phone", "overseas_phone", "email", "city", "notes"):
		base[field] = base[field] or extra[field]
	if extra["dnd"] is True or base["dnd"] is None:
		base["dnd"] = extra["dnd"]
	base["unrecognised_dnd"] = base["unrecognised_dnd"] or extra["unrecognised_dnd"]


def _keys(record):
	return {k for k in (record["phone"], record["overseas_phone"], record["email"]) if k}


def _fold_file_duplicates(parsed) -> tuple[list[dict], list[dict]]:
	"""(records, skipped). A row with no name or nothing to reach the person by is skipped with its reason."""
	records, skipped, by_key = [], [], {}
	for record in parsed:
		line = record["rows"][0]
		if not record["name"]:
			skipped.append({"row": line, "reason": _("No name.")})
			continue
		if not _keys(record):
			skipped.append({"row": line, "reason": _("No usable phone number or email.")})
			continue
		home = next((by_key[k] for k in sorted(_keys(record)) if k in by_key), None)
		if home is None:
			records.append(record)
			home = record
		else:
			_merge_into(home, record)
		for key in _keys(record) | _keys(home):
			by_key[key] = home
	return records, skipped


def _existing_client(record):
	"""The live client already in SellOS that this record matches, or None."""
	for match in duplicates.find_matches(record["phone"], record["overseas_phone"], record["email"]):
		if not match["archived"]:
			return match["name"]
	return None


def _live_lead(client):
	rows = frappe.get_all(
		"Lead", filters={"client": client, "archived": 0}, pluck="name", order_by="creation desc", limit=1
	)
	return rows[0] if rows else None


# --- the plan and the import --------------------------------------------------------------------


def build_plan(text, mapping=None) -> dict:
	"""Read the file and decide what the import will do, without writing anything."""
	headers, rows = read_csv(text)
	mapping = _clean_mapping(mapping or suggest_mapping(headers), headers)
	records, skipped = _fold_file_duplicates([_parse_row(r, mapping) for r in rows])
	for record in records:
		record["client"] = _existing_client(record)
		record["lead"] = _live_lead(record["client"]) if record["client"] else None
		record["action"] = "merge" if record["lead"] else ("add lead" if record["client"] else "create")
	return {
		"headers": headers,
		"mapping": mapping,
		"records": records,
		"skipped": skipped,
		"total": len(rows),
	}


def _counts(plan) -> dict:
	records = plan["records"]
	return {
		"rows": plan["total"],
		"new_leads": sum(r["action"] != "merge" for r in records),
		"merged_with_existing": sum(r["action"] != "create" for r in records),
		"merged_in_file": sum(len(r["rows"]) - 1 for r in records),
		"registered_dnd": sum(r["dnd"] is True for r in records),
		"unrecognised_dnd": sum(r["unrecognised_dnd"] for r in records),
		"skipped": len(plan["skipped"]),
	}


def preview(text, mapping=None) -> dict:
	"""What importing this file would do: the mapping used, the counts and the first rows, numbers masked."""
	plan = build_plan(text, mapping)
	sample = [
		{
			"rows": ", ".join(str(n) for n in r["rows"]),
			"name": r["name"],
			"phone": mask_phone(r["phone"] or r["overseas_phone"]),
			"email": r["email"],
			"action": r["action"],
			"do_not_call": {True: "Registered", False: "Not registered"}.get(r["dnd"], ""),
		}
		for r in plan["records"][:SAMPLE_ROWS]
	]
	return {
		"headers": plan["headers"],
		"mapping": plan["mapping"],
		"fields": [{"field": f, "label": LABELS[f]} for f in FIELDS],
		"counts": _counts(plan),
		"sample": sample,
		"skipped": plan["skipped"][:50],
	}


def _fill_client(name, record):
	"""A client keeps what it has and gains only what it lacked."""
	client = frappe.get_doc("Client", name)
	changed = False
	for field in ("phone", "overseas_phone", "email", "city"):
		if record[field] and not client.get(field):
			client.set(field, record[field])
			changed = True
	if changed:
		client.flags.ignore_permissions = True
		client.save()


def _new_client(record):
	client = frappe.get_doc(
		{
			"doctype": "Client",
			"client_name": record["name"],
			"client_type": "Buyer",
			"phone": record["phone"] or None,
			"overseas_phone": record["overseas_phone"] or None,
			"email": record["email"] or None,
			"city": record["city"] or None,
		}
	)
	client.check_permission("create")
	client.flags.ignore_permissions = True  # checked above. Needed for the level 1 phone fields.
	return client.insert().name


def _new_lead(client, record, list_name):
	lead = frappe.get_doc(
		{
			"doctype": "Lead",
			"client": client,
			"source": BOUGHT_LIST,
			"campaign": list_name or None,
			"notes": record["notes"] or None,
			"consent_status": consent.UNKNOWN,
		}
	)
	lead.check_permission("create")
	lead.flags.ignore_permissions = True
	return lead.insert().name


def _apply_dnd(lead, dnd):
	"""Store a known result through record_dnd_result. A later list never turns a known registered
	number back to not registered, and a not registered result is not written over an earlier check."""
	if dnd is None:
		return
	row = frappe.db.get_value("Lead", lead, ["dnd_registered", "dnd_checked_on"], as_dict=True)
	if dnd is False and (row.dnd_registered or row.dnd_checked_on):
		return
	consent.record_dnd_result(lead, dnd)


def _import_record(record, list_name):
	"""Make or merge one record. Returns (lead, created, merged_with_existing). The client is looked up
	again here, because a row earlier in this import may have made it."""
	client = record["client"] or _existing_client(record)
	lead = record["lead"] or (_live_lead(client) if client else None)
	if client:
		_fill_client(client, record)
	created = not lead
	if created:
		client = client or _new_client(record)
		lead = _new_lead(client, record, list_name)
	frappe.get_doc("Lead", lead).add_comment(
		"Info",
		_("{0} from the bought list {1}, row {2}.").format(
			_("Imported") if created else _("Appeared again"),
			list_name or _("(unnamed)"),
			", ".join(str(n) for n in record["rows"]),
		),
	)
	_apply_dnd(lead, record["dnd"])
	return lead, created, bool(record["client"])


def import_list(text, mapping=None, list_name=None) -> dict:
	"""Import the file. A row that cannot be saved is reported and left out, and the others go on."""
	plan = build_plan(text, mapping)
	list_name = (list_name or "").strip()[:140]
	skipped = list(plan["skipped"])
	created, merged, done = [], [], []
	for record in plan["records"]:
		frappe.db.savepoint("lead_import_row")
		try:
			lead, was_created, _matched = _import_record(record, list_name)
		except Exception as error:
			frappe.db.rollback(save_point="lead_import_row")
			skipped.append(
				{"row": record["rows"][0], "reason": _("Could not be saved: {0}").format(str(error)[:200])}
			)
			continue
		frappe.db.release_savepoint("lead_import_row")
		done.append(record)
		(created if was_created else merged).append(lead)
	counts = _counts({**plan, "records": done, "skipped": skipped})
	counts["new_leads"] = len(created)
	return {
		"counts": counts,
		"created": created,
		"merged": merged,
		"skipped": sorted(skipped, key=lambda s: s["row"])[:200],
		"source": BOUGHT_LIST,
	}
