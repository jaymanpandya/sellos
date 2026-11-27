"""Micro markets, buildings and the building review in the web app (SOS-P3-04).

A Company Admin adds, renames, splits, merges and archives micro markets, loads them and a seed list of buildings,
and edits buildings. A Company Admin or an Agent reviews: corrects a building's fields and confirms it. A Sales
Manager reads. A Client, a Channel Partner and the Platform Admin see none of a company's buildings. Every record
is saved through its DocType, so its checks and the DocType permissions run on every call. Nothing is deleted. The
Platform Admin loads the platform master on the control site only.
"""

import frappe
from frappe import _
from frappe.utils import cint

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, PLATFORM_ADMIN, SALES_MANAGER
from sellos.intel import buildings, markets, platform_master
from sellos.intel.identifiers import default_country, profiles

READERS = (COMPANY_ADMIN, AGENT, SALES_MANAGER)
REVIEWERS = (COMPANY_ADMIN, AGENT)


def _market_row(doc) -> dict:
	return {
		"name": doc.name,
		"market_name": doc.market_name,
		"country": doc.country,
		"parent_area": doc.parent_area,
		"status": doc.status,
		"boundary": doc.boundary or "",
		"split_from": doc.split_from,
		"merged_into": doc.merged_into,
		"buildings": frappe.db.count("Building", {"micro_market": doc.name}),
		"history": [
			{
				"changed_on": h.changed_on,
				"changed_by": h.changed_by,
				"change": h.change_kind,
				"detail": h.detail,
			}
			for h in doc.get("history") or []
		],
	}


@sellos_api(*READERS)
def list_micro_markets(include_archived=0):
	filters = {} if cint(include_archived) else {"status": "Active"}
	names = frappe.get_list("Micro Market", filters=filters, order_by="market_name asc", pluck="name")
	return {
		"markets": [_market_row(frappe.get_doc("Micro Market", n)) for n in names],
		"default_country": default_country(),
	}


@sellos_api(COMPANY_ADMIN, methods=["POST"])
def save_micro_market(name=None, values=None):
	return _market_row(markets.save_market(name, values))


@sellos_api(COMPANY_ADMIN, methods=["POST"])
def split_micro_market(name, first, second, assignments=None):
	parts = markets.split_market(name, first, second, assignments)
	return [_market_row(p) for p in parts]


@sellos_api(COMPANY_ADMIN, methods=["POST"])
def merge_micro_markets(keep, merge):
	return _market_row(markets.merge_markets(keep, merge))


@sellos_api(COMPANY_ADMIN, methods=["POST"])
def set_micro_market_archived(name, archived=1):
	return _market_row(markets.set_archived(name, archived))


@sellos_api(COMPANY_ADMIN, methods=["POST"])
def load_micro_markets(text=None):
	"""Load micro markets and their boundaries from a file's text, or the shipped sample when none is given."""
	return markets.load_markets(text)


@sellos_api(*READERS)
def list_buildings(micro_market=None, status=None, search="", start=0, page_length=50):
	result = buildings.list_buildings(micro_market, status, search, start, page_length)
	result["identifier_profiles"] = profiles()
	return result


@sellos_api(*READERS)
def get_building(name):
	doc = frappe.get_doc("Building", name)
	doc.check_permission("read")
	return {**buildings.building_view(doc), "corrections": buildings.corrections_of(name)}


@sellos_api(COMPANY_ADMIN, methods=["POST"])
def save_building(name=None, values=None):
	"""Add a building, or edit one. A building added by hand starts as Needs review."""
	return buildings.building_view(buildings.save_building(name, values))


@sellos_api(*REVIEWERS, methods=["POST"])
def correct_building(name, values):
	"""A reviewer corrects fields of an existing building. Each change is saved with who, when and the old value."""
	if not name:
		frappe.throw(_("Choose a building."))
	values = dict(values or {})
	if COMPANY_ADMIN not in frappe.get_roles():
		values.pop("platform_building", None)  # linking to the platform master is an admin's call
	return buildings.building_view(buildings.save_building(name, values))


@sellos_api(*REVIEWERS, methods=["POST"])
def confirm_building(name):
	return buildings.building_view(buildings.confirm_building(name))


@sellos_api(COMPANY_ADMIN, methods=["POST"])
def load_building_seed_list(text, micro_market=None, country=None):
	"""Create a building, Needs review, for each name of a CSV or a list of building and project names."""
	return buildings.load_seed_list(text, micro_market, country)


@sellos_api(PLATFORM_ADMIN, methods=["POST"])
def load_platform_master(text=None):
	"""Seed the platform master of buildings on the control site, from a file or the shipped sample."""
	return platform_master.load_platform_master(text)
