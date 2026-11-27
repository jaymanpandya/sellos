"""Buildings: add, edit, load from a seed list, review and confirm (SOS-P3-04).

A building starts as "Needs review" when the system builds it (a seed list, a file). A person, any Company Admin
or Agent, corrects each field or confirms it. Every correction is saved with who, when and the old value (the
Building DocType does that on every save). Only a Confirmed building reaches the Property Matcher and the market
data roll ups, through `confirmed_buildings`. This module never calls LegiScore: SOS-P3-14 to SOS-P3-16 enrich a
building later.
"""

import csv
import io
import json
import re
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint

from sellos.intel.identifiers import default_country, identifier_fields
from sellos.sellos.doctype.building.building import CONFIRMED, NEEDS_REVIEW

BUILDING = "Building"
CORRECTION = "Building Correction"
MARKET = "Micro Market"
EDITABLE = (
	"building_name",
	"micro_market",
	"project",
	"country",
	"cts_numbers",
	"village",
	"tahsil",
	"district",
	"rera_number",
	"uae_community",
	"dld_number",
	"au_lot",
	"au_plan",
	"platform_building",
)
LIST_FIELDS = [
	"name",
	"building_name",
	"micro_market",
	"project",
	"country",
	"status",
	"source",
	"platform_building",
]
MAX_PAGE = 200
MAX_SEED_ROWS = 2000
MAX_SEED_CHARS = 500_000


def _squash(value) -> str:
	return " ".join(str(value or "").split())


def _cts_rows(value) -> list[dict]:
	"""CTS numbers from a list, or from text split on commas, semicolons and new lines."""
	if isinstance(value, str):
		value = re.split(r"[,;\n]", value)
	return [{"cts_number": _squash(v)} for v in value or [] if _squash(v)]


def _apply(doc, values):
	for key, value in (values or {}).items():
		if key == "cts_numbers":
			doc.set("cts_numbers", _cts_rows(value))
		elif key in EDITABLE:
			doc.set(key, "" if value is None else value)


def save_building(name=None, values=None, reason=None):
	"""Add a building, or correct one. The Building saves a correction for every changed field."""
	if name:
		doc = frappe.get_doc(BUILDING, name)
		doc.flags.market_reason = reason or "Corrected"
	else:
		doc = frappe.get_doc({"doctype": BUILDING, "status": NEEDS_REVIEW, "source": "Manual"})
	_apply(doc, values)
	doc.save()
	return doc


def confirm_building(name):
	"""Mark a building Confirmed, by the person who checked it."""
	doc = frappe.get_doc(BUILDING, name)
	if doc.status != CONFIRMED:
		doc.status = CONFIRMED
		doc.save()
	return doc


def confirmed_buildings(micro_market=None) -> list[dict]:
	"""The buildings the Property Matcher and the market data roll ups may use: Confirmed ones only."""
	filters = {"status": CONFIRMED}
	if micro_market:
		filters["micro_market"] = micro_market
	return frappe.get_all(BUILDING, filters=filters, fields=LIST_FIELDS, order_by="building_name asc")


def building_view(doc) -> dict:
	"""One building as the screens read it, with the identifiers its country shows."""
	row = {k: doc.get(k) or "" for k in LIST_FIELDS}
	for fieldname in EDITABLE:
		if fieldname != "cts_numbers":
			row[fieldname] = doc.get(fieldname) or ""
	row["cts_numbers"] = [r.cts_number for r in doc.get("cts_numbers") or []]
	row["identifier_fields"] = identifier_fields(doc.get("country"))
	row["confirmed_by"] = doc.get("confirmed_by")
	row["confirmed_on"] = doc.get("confirmed_on")
	row["market_history"] = [
		{"micro_market": r.micro_market, "from_on": r.from_on, "to_on": r.to_on, "reason": r.reason}
		for r in doc.get("market_history") or []
	]
	return row


def list_buildings(micro_market=None, status=None, search="", start=0, page_length=50):
	start = max(cint(start), 0)
	page_length = min(max(cint(page_length) or 50, 1), MAX_PAGE)
	filters = {}
	if micro_market:
		filters["micro_market"] = micro_market
	if status in (NEEDS_REVIEW, CONFIRMED):
		filters["status"] = status
	or_filters = None
	search = _squash(search)
	if search:
		like = f"%{search}%"
		or_filters = {"building_name": ["like", like], "rera_number": ["like", like]}
		with_cts = frappe.get_all(
			"Building CTS Number", filters={"cts_number": ["like", like]}, pluck="parent"
		)
		if with_cts:
			or_filters["name"] = ["in", with_cts]
	scalar = sorted(
		{*LIST_FIELDS, *(f for f in EDITABLE if f != "cts_numbers"), "confirmed_by", "confirmed_on"}
	)
	found = frappe.get_list(
		BUILDING,
		filters=filters,
		or_filters=or_filters,
		fields=scalar,
		order_by="building_name asc, name asc",
		start=start,
		page_length=page_length + 1,
	)
	more = len(found) > page_length
	found = found[:page_length]
	names = [r["name"] for r in found]
	cts, history = {}, {}
	if names:
		for r in frappe.get_all(
			"Building CTS Number",
			filters={"parent": ["in", names], "parenttype": BUILDING},
			fields=["parent", "cts_number"],
			order_by="idx asc",
		):
			cts.setdefault(r.parent, []).append(r.cts_number)
		for r in frappe.get_all(
			"Building Market History",
			filters={"parent": ["in", names], "parenttype": BUILDING},
			fields=["parent", "micro_market", "from_on", "to_on", "reason"],
			order_by="idx asc",
		):
			history.setdefault(r.parent, []).append(
				{k: r[k] for k in ("micro_market", "from_on", "to_on", "reason")}
			)
	rows = []
	for r in found:
		row = {k: r.get(k) or "" for k in scalar if k not in ("confirmed_by", "confirmed_on")}
		row["cts_numbers"] = cts.get(r["name"], [])
		row["identifier_fields"] = identifier_fields(r.get("country"))
		row["confirmed_by"] = r.get("confirmed_by")
		row["confirmed_on"] = r.get("confirmed_on")
		row["market_history"] = history.get(r["name"], [])
		rows.append(row)
	return {"rows": rows, "has_more": more}


def corrections_of(building) -> list[dict]:
	frappe.get_doc(BUILDING, building).check_permission("read")
	return frappe.get_all(
		CORRECTION,
		filters={"building": building},
		fields=["fieldname", "old_value", "new_value", "corrected_by", "corrected_on"],
		order_by="corrected_on desc, creation desc",
	)


# ---- the seed list -------------------------------------------------------------------------------------------

_NAME_HEADERS = {"name", "building", "building name", "project", "project name", "building or project"}
_COLUMNS = {
	"cts": "cts_numbers",
	"cts number": "cts_numbers",
	"cts numbers": "cts_numbers",
	"village": "village",
	"tahsil": "tahsil",
	"district": "district",
	"rera": "rera_number",
	"rera number": "rera_number",
	"micro market": "micro_market",
	"country": "country",
}


def parse_seed_list(text) -> list[dict]:
	"""Rows of {name, ...} from a CSV with a header, or from one building or project name a line."""
	text = str(text or "")
	if len(text) > MAX_SEED_CHARS:
		frappe.throw(_("The list is too large."))
	lines = [line for line in text.splitlines() if line.strip()]
	if not lines:
		frappe.throw(_("Add at least one building or project name."))
	first = [_squash(cell).lower() for cell in next(csv.reader([lines[0]]))]
	rows = []
	if any(cell in _NAME_HEADERS for cell in first):
		for record in csv.DictReader(io.StringIO("\n".join(lines))):
			row = {}
			for header, value in record.items():
				key = _squash(header).lower()
				if key in _NAME_HEADERS:
					row["name"] = _squash(value)
				elif key in _COLUMNS:
					row[_COLUMNS[key]] = _squash(value)
			rows.append(row)
	else:
		rows = [{"name": _squash(line)} for line in lines]
	if len(rows) > MAX_SEED_ROWS:
		frappe.throw(_("A list holds at most {0} rows.").format(MAX_SEED_ROWS))
	return rows


def _market_names() -> dict:
	rows = frappe.get_all(MARKET, filters={"status": "Active"}, fields=["name", "market_name", "country"])
	return {(_squash(r.market_name).lower(), r.country): r.name for r in rows}


def _create_needs_review(values, source) -> bool:
	"""Insert one building as Needs review. False when the same RERA number, or the same name in the same
	micro market, is already there."""
	rera = _squash(values.get("rera_number")).replace(" ", "").upper()
	same = {"building_name": values["building_name"], "micro_market": values.get("micro_market") or ""}
	if frappe.db.exists(BUILDING, same) or (rera and frappe.db.exists(BUILDING, {"rera_number": rera})):
		return False
	doc = frappe.get_doc({"doctype": BUILDING, "status": NEEDS_REVIEW, "source": source})
	_apply(doc, values)
	doc.insert()
	return True


def load_seed_list(text, micro_market=None, country=None):
	"""Create a building, status Needs review, for each name of a CSV or a list. A building already there is
	skipped, so the same list twice adds nothing. A row with no name, or one that cannot be saved, is
	counted and the load goes on."""
	rows = parse_seed_list(text)
	by_name = {}
	for (label, _country), name in _market_names().items():
		by_name.setdefault(label, name)  # a name two countries share goes to the first
	created = skipped = 0
	rejected = []
	for index, row in enumerate(rows, start=1):
		if not row.get("name"):
			rejected.append({"row": index, "why": "No name."})
			continue
		values = {k: v for k, v in row.items() if k in EDITABLE and v}
		values["building_name"] = row["name"]
		values["micro_market"] = by_name.get(_squash(row.get("micro_market")).lower()) or micro_market or ""
		values["country"] = row.get("country") or country or ""
		frappe.db.savepoint("seed_row")
		try:
			if _create_needs_review(values, "Seed list"):
				created += 1
			else:
				skipped += 1
		except frappe.ValidationError as e:
			frappe.db.rollback(save_point="seed_row")
			rejected.append({"row": index, "why": _squash(frappe.utils.strip_html(str(e)))[:200]})
	return {"created": created, "skipped": skipped, "rejected": rejected}


def load_sample_buildings(text=None):
	"""Load the buildings of the corridor sample file (or a file of the same shape) as Needs review, under the
	micro markets of the same name. Run `markets.load_markets` first."""
	from sellos.intel.markets import SAMPLE_FILE

	data = json.loads(Path(SAMPLE_FILE).read_text(encoding="utf-8") if not text else text)
	by_name = _market_names()
	created = skipped = 0
	for row in data.get("buildings", []):
		country = row.get("country") or default_country()
		values = {
			"building_name": _squash(row.get("name")),
			"micro_market": by_name.get((_squash(row.get("market")).lower(), country)) or "",
			"country": country,
			"cts_numbers": row.get("cts"),
			"village": row.get("village"),
			"tahsil": row.get("tahsil"),
			"district": row.get("district"),
			"rera_number": row.get("rera"),
		}
		if _create_needs_review(values, "Sample file"):
			created += 1
		else:
			skipped += 1
	return {"created": created, "skipped": skipped}
