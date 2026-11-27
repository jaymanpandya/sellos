"""Micro markets: add, rename, split, merge, archive and load from a file (SOS-P3-04).

A micro market is a DocType, a named area with a country, a city or region, an optional GeoJSON boundary and a
status. A company's micro market is a grouping of its own buildings, so it can change freely without touching
another company or the platform master. Nothing is deleted: a split, a merge and an archive keep the old market,
and every building keeps the list of the markets it belonged to. No market name, city or country is in this
code: they come from the file or from the person.
"""

import json
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint

MARKET = "Micro Market"
BUILDING = "Building"
SAMPLE_FILE = Path(__file__).parent / "fixtures" / "corridor_bandra_andheri.json"
EDITABLE = ("market_name", "country", "parent_area", "boundary")
MAX_FILE_CHARS = 2_000_000


def _squash(value) -> str:
	return " ".join(str(value or "").split())


def get_market(name) -> "frappe.model.document.Document":
	if not name or not frappe.db.exists(MARKET, name):
		frappe.throw(_("Choose a micro market."), frappe.DoesNotExistError)
	return frappe.get_doc(MARKET, name)


def save_market(name=None, values=None):
	"""Add a micro market, or edit one (rename, move to another city, change its boundary). Not its status."""
	values = {k: v for k, v in (values or {}).items() if k in EDITABLE}
	if name:
		doc = get_market(name)
		if doc.status != "Active":
			frappe.throw(_("Restore the micro market before editing it."))
		doc.update(values)
	else:
		doc = frappe.get_doc({"doctype": MARKET, "status": "Active", **values})
	doc.save()
	return doc


def buildings_of(market) -> list[str]:
	return frappe.get_all(BUILDING, filters={"micro_market": market}, pluck="name", order_by="creation asc")


def move_building(building, market, reason):
	doc = frappe.get_doc(BUILDING, building)
	doc.micro_market = market
	doc.flags.market_reason = reason
	doc.save()


def split_market(name, first, second, assignments):
	"""Split one market into two. `first` and `second` are the new markets' values; `assignments` gives each
	building of the market 0 (first) or 1 (second). The old market is archived and kept in the history."""
	old = get_market(name)
	if old.status != "Active":
		frappe.throw(_("Only an active micro market can be split."))
	members = buildings_of(old.name)
	assignments = {str(k): cint(v) for k, v in (assignments or {}).items()}
	if set(assignments) != set(members) or any(v not in (0, 1) for v in assignments.values()):
		frappe.throw(_("Give every building of the micro market to the first or the second part."))
	for part in (first, second):
		if not _squash((part or {}).get("market_name")):
			frappe.throw(_("Name both parts."))
	if _squash(first["market_name"]).lower() == _squash(second["market_name"]).lower():
		frappe.throw(_("The two parts need different names."))
	# The old market gives its name up before a part may take it.
	old.status = "Archived"
	old.flags.history_kind = "Split"
	old.flags.history_detail = f"{_squash(first['market_name'])} and {_squash(second['market_name'])}"
	old.save()
	parts = []
	for part in (first, second):
		values = {k: part.get(k) for k in EDITABLE if part.get(k) not in (None, "")}
		values.setdefault("country", old.country)
		values.setdefault("parent_area", old.parent_area)
		doc = frappe.get_doc({"doctype": MARKET, "status": "Active", "split_from": old.name, **values})
		doc.save()
		parts.append(doc)
	for building, side in assignments.items():
		move_building(building, parts[side].name, "Split")
	return parts


def merge_markets(keep, merge):
	"""Merge `merge` into `keep`: its buildings move to `keep` and it is archived, pointing at `keep`."""
	if keep == merge:
		frappe.throw(_("Choose two different micro markets."))
	target, source = get_market(keep), get_market(merge)
	if target.status != "Active" or source.status != "Active":
		frappe.throw(_("Only active micro markets can be merged."))
	for building in buildings_of(source.name):
		move_building(building, target.name, "Merged")
	source.status = "Archived"
	source.merged_into = target.name
	source.flags.history_kind = "Merged"
	source.flags.history_detail = f"into {target.market_name}"
	source.save()
	return target


def set_archived(name, archived):
	"""Archive a micro market, or restore it. An archive is refused while buildings still belong to it."""
	doc = get_market(name)
	if cint(archived):
		if doc.status == "Archived":
			return doc
		if buildings_of(doc.name):
			frappe.throw(_("Move or merge the buildings of this micro market first."))
		doc.status = "Archived"
	else:
		doc.status = "Active"
	doc.save()
	return doc


def load_markets(text=None):
	"""Load micro markets and their boundaries from a JSON file's text, or the shipped sample when none is
	given. Existing markets of the same name and country are updated, never doubled. Returns the counts."""
	text = Path(SAMPLE_FILE).read_text(encoding="utf-8") if text in (None, "") else text
	if len(text) > MAX_FILE_CHARS:
		frappe.throw(_("The file is too large."))
	try:
		data = json.loads(text)
	except ValueError:
		frappe.throw(_("The file is not valid JSON."))
	rows = data.get("markets") if isinstance(data, dict) else None
	if not isinstance(rows, list):
		frappe.throw(_("The file needs a list called markets."))
	created = updated = 0
	for row in rows:
		if not isinstance(row, dict):
			frappe.throw(_("Each micro market in the file needs a name, a country and a city or region."))
		values = {
			"market_name": row.get("name"),
			"country": row.get("country"),
			"parent_area": row.get("parent"),
			"boundary": json.dumps(row["boundary"]) if row.get("boundary") else "",
		}
		existing = frappe.db.get_value(
			MARKET,
			{"market_name": _squash(values["market_name"]), "country": values["country"], "status": "Active"},
			"name",
		)
		save_market(existing, values)
		created, updated = (created, updated + 1) if existing else (created + 1, updated)
	return {"created": created, "updated": updated}
