"""The list of lead sources (SOS-P1-20).

Every lead has a source from the Lead Source list. A Company Admin extends the list and disables a
source, and a source that a lead uses is never deleted. SOS-P1-09 (Website), SOS-P1-12 (Bought list)
and SOS-P2-08 (Missed call) set their source from the same list, by these constants.
"""

import re

import frappe
from frappe import _

WEBSITE = "Website"
PORTAL = "Portal"
REFERRAL = "Referral"
WALK_IN = "Walk in"
CHANNEL_PARTNER = "Channel partner"
FACEBOOK = "Facebook"
MISSED_CALL = "Missed call"
BOUGHT_LIST = "Bought list"
# A lead that had no source before the list existed gets this one (patch p1_20_lead_sources).
NOT_RECORDED = "Not recorded"

DEFAULT_SOURCES = (WEBSITE, PORTAL, REFERRAL, WALK_IN, CHANNEL_PARTNER, FACEBOOK, MISSED_CALL, BOUGHT_LIST)

# Free text that older leads hold, by its normalised form (see normalise), and the source it means.
ALIASES = {
	"web": WEBSITE,
	"site": WEBSITE,
	"website": WEBSITE,
	"portal": PORTAL,
	"referral": REFERRAL,
	"referred": REFERRAL,
	"reference": REFERRAL,
	"walkin": WALK_IN,
	"walkins": WALK_IN,
	"channelpartner": CHANNEL_PARTNER,
	"partner": CHANNEL_PARTNER,
	"facebook": FACEBOOK,
	"fb": FACEBOOK,
	"missedcall": MISSED_CALL,
	"boughtlist": BOUGHT_LIST,
	"purchasedlist": BOUGHT_LIST,
}
MAX_LENGTH = 140


def normalise(text) -> str:
	"""'Walk-in', 'walk in' and 'WALK_IN' are the same source: lower case letters and digits only."""
	return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def ensure_default_sources() -> list[str]:
	"""Create any of the eight sources that is missing. A disabled source stays disabled. Safe to run again."""
	made = []
	for name in DEFAULT_SOURCES:
		if not frappe.db.exists("Lead Source", name):
			frappe.get_doc({"doctype": "Lead Source", "source_name": name, "enabled": 1}).insert(
				ignore_permissions=True
			)
			made.append(name)
	return made


def ensure_deletable(name) -> None:
	"""Refuse to delete a source a lead uses, or one of the eight the product itself sets."""
	count = frappe.db.count("Lead", {"source": name})
	if count:
		frappe.throw(
			_("{0} is used by {1} lead(s) and cannot be deleted. Disable it instead.").format(name, count),
			frappe.ValidationError,
		)
	if name in DEFAULT_SOURCES:
		frappe.throw(_("{0} is a standard source and cannot be deleted. Disable it instead.").format(name))


def check_usable(lead) -> None:
	"""A lead needs a source from the list, and a new choice must be an enabled one."""
	if not lead.source:
		frappe.throw(_("Choose a source for the lead."), frappe.MandatoryError)
	if lead.is_new() or lead.has_value_changed("source"):
		if not frappe.db.get_value("Lead Source", lead.source, "enabled"):
			frappe.throw(_("The source {0} is disabled. Choose another.").format(lead.source))


def list_sources(include_disabled=False) -> list[dict]:
	filters = {} if include_disabled else {"enabled": 1}
	rows = frappe.get_all(
		"Lead Source", filters=filters, fields=["name", "enabled"], order_by="creation asc, name asc"
	)
	return [{"name": row.name, "enabled": int(row.enabled)} for row in rows]


def _known_sources() -> dict[str, str]:
	return {normalise(name): name for name in frappe.get_all("Lead Source", pluck="name")}


def _new_source(text, known, created) -> str:
	name = " ".join(str(text).split())[:MAX_LENGTH].strip()
	frappe.get_doc({"doctype": "Lead Source", "source_name": name, "enabled": 1}).insert(
		ignore_permissions=True
	)
	known[normalise(name)] = name
	created.append(name)
	return name


def _target(raw, known, created) -> str:
	key = normalise(raw)
	if not key:
		return known.get(normalise(NOT_RECORDED)) or _new_source(NOT_RECORDED, known, created)
	return known.get(key) or ALIASES.get(key) or _new_source(raw, known, created)


def map_free_text_sources() -> dict:
	"""Give every lead a source from the list (SOS-P1-20). The patch calls this, and running it again
	changes nothing.

	A value that names a source (ignoring case, spaces and dashes) or one of its usual spellings maps to
	it. A value no source matches becomes a new source. A lead with no value gets Not recorded. Only the
	source column is written, so a lead keeps its modified time.
	Returns {"mapped": {old: new}, "created": [sources made], "leads": rows changed}.
	"""
	ensure_default_sources()
	known = _known_sources()
	mapped, created, changed = {}, [], 0
	for raw in frappe.db.sql("select distinct source from `tabLead`", pluck=True):
		if raw and raw in known.values():
			continue  # already a source, written exactly
		target = _target(raw, known, created)
		mapped[raw or ""] = target
		if raw:
			changed += frappe.db.sql(
				"select count(*) from `tabLead` where binary source = binary %s", (raw,)
			)[0][0]
			frappe.db.sql("update `tabLead` set source = %s where binary source = binary %s", (target, raw))
		else:
			blank = "select count(*) from `tabLead` where source is null or source = ''"
			changed += frappe.db.sql(blank)[0][0]
			frappe.db.sql("update `tabLead` set source = %s where source is null or source = ''", (target,))
	return {"mapped": mapped, "created": created, "leads": changed}
