"""Match buyers to inventory (SOS-P7-08).

From a lead, SellOS lists the published listings and the Available units that suit what the buyer wants
(SOS-P1-15), scored 0 to 100. From a unit or a listing it lists the leads it suits that the user may see.

The score has four parts, each worked out from 0 to 100 on its own and shown with its reason:

* Budget: 100 inside the lead's budget range. Each percent over the top of the range costs 4 points, each
  percent under the bottom costs 1 point (a cheaper home is a smaller problem than a dearer one). A unit's price
  is its base price plus floor rise from the price list in force (SOS-P7-07); a listing's is its asking price,
  or its unit's price when the asking price is empty. No price known scores 0.
* Configuration: 100 for a wanted configuration, 60 half a bedroom away (2 BHK against 2.5 BHK), 30 one
  bedroom away, else 0. "4 BHK and above" accepts four bedrooms or more.
* Locality: 100 for a preferred locality, 70 when one contains the other, else 0.
* Property type: 100 for the type wanted, 60 between Villa and Independent house, else 0.

A part the lead did not give (no budget, no configuration, no locality, no type) is left out, and a part that
makes no sense for the home (configuration of a plot, shop or office) is left out too. The total is the
weighted average of the parts that remain, using the four company weights (25 each by default), so a lead
that gave only a budget is scored on the budget alone. Nothing is saved: the score is worked out on each call.

A unit that is not Available (or is archived) and a listing that is not published (or is archived, or whose
unit or property is not Available) is never suggested.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, flt

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.crm import api as crm_api
from sellos.crm.requirements import REQUIREMENT_FIELDS, requirements_view, split_values
from sellos.inventory import pricing
from sellos.inventory.base import AVAILABLE

SETTINGS = "SellOS Settings"
READERS = (COMPANY_ADMIN, AGENT, SALES_MANAGER)
PARTS = ("budget", "configuration", "locality", "property_type")
LABELS = {
	"budget": "Budget",
	"configuration": "Configuration",
	"locality": "Locality",
	"property_type": "Property type",
}
WEIGHT_FIELDS = {part: f"match_weight_{part}" for part in PARTS}
DEFAULT_WEIGHT = 25
MAX_WEIGHT = 100
OVER_BUDGET_POINTS = 4  # per percent over the top of the budget
UNDER_BUDGET_POINTS = 1  # per percent under the bottom of the budget
MAX_RESULTS = 50
NO_CONFIGURATION = ("Plot", "Shop", "Office")
SIMILAR_TYPES = {frozenset({"Villa", "Independent house"})}
UNIT_TYPE = "Apartment"  # a unit is a flat in a project


# --- the settings ---------------------------------------------------------------------------------


def weights() -> dict[str, int]:
	"""The four company weights. Settings never saved (nothing, or all zero) are 25 each."""
	result = {}
	for part, field in WEIGHT_FIELDS.items():
		# Read the stored row: get_single_value answers 0 for a setting never saved, and 0 is a real weight.
		value = frappe.db.get_value("Singles", {"doctype": SETTINGS, "field": field}, "value", order_by=None)
		result[part] = None if value in (None, "") else cint(value)
	if not any(result.values()):
		# Never saved: saving the settings form stores a blank Int as 0 for all four, and save_match_settings
		# refuses all four at zero, so all zero always means the defaults.
		return dict.fromkeys(PARTS, DEFAULT_WEIGHT)
	return {part: 0 if value is None else value for part, value in result.items()}


# --- the score: no database ------------------------------------------------------------------------


def _percent(value) -> str:
	text = f"{value:.1f}"
	return text[:-2] if text.endswith(".0") else text


def _clamp(value) -> float:
	return max(0.0, min(100.0, value))


def bedrooms(configuration) -> float | None:
	"""A configuration as a number of bedrooms: 2 BHK is 2, 2.5 BHK is 2.5, 1 RK is 0.5."""
	text = " ".join(str(configuration or "").split()).upper()
	if not text:
		return None
	if text.startswith("1 RK"):
		return 0.5
	found = re.match(r"^(\d+(?:\.\d+)?)", text)
	return float(found.group(1)) if found else None


def budget_part(low, high, price):
	"""(score, reason) of a price against a budget range, or None when the lead gave no budget."""
	low, high = flt(low) or None, flt(high) or None
	if low is None and high is None:
		return None
	if not price:
		return 0.0, _("No price is set")
	if high is not None and price > high:
		over = (price - high) / high * 100
		return _clamp(100 - OVER_BUDGET_POINTS * over), _("{0} percent over budget").format(_percent(over))
	if low is not None and price < low:
		under = (low - price) / low * 100
		return _clamp(100 - UNDER_BUDGET_POINTS * under), _("{0} percent under budget").format(
			_percent(under)
		)
	return 100.0, _("Within budget")


def configuration_part(wanted, configuration, property_type):
	"""(score, reason), or None when the lead gave no configuration or the home has none (a plot, shop or office)."""
	wanted = split_values(wanted)
	if not wanted:
		return None
	if not configuration:
		if property_type in NO_CONFIGURATION:
			return None
		return 0.0, _("No configuration is recorded")
	have = bedrooms(configuration)
	best, why = 0.0, _("{0} does not match").format(configuration)
	for want in wanted:
		need = bedrooms(want)
		if want.lower() == configuration.lower():
			return 100.0, _("{0} matches").format(configuration)
		if need is None or have is None:
			continue
		if want.lower().endswith("and above") and have >= need:
			return 100.0, _("{0} matches {1}").format(configuration, want)
		gap = abs(have - need)
		score = 60.0 if gap <= 0.5 else 30.0 if gap <= 1 else 0.0
		if score > best:
			best = score
			why = (
				_("{0} is half a bedroom from {1}").format(configuration, want)
				if score == 60.0
				else _("{0} is a bedroom from {1}").format(configuration, want)
			)
	return best, why


def locality_part(preferred, locality):
	"""(score, reason), or None when the lead named no locality."""
	preferred = split_values(preferred)
	if not preferred:
		return None
	if not locality:
		return 0.0, _("No locality is recorded")
	here = locality.lower()
	for place in preferred:
		if place.lower() == here:
			return 100.0, _("{0} is a preferred locality").format(locality)
	for place in preferred:
		if place.lower() in here or here in place.lower():
			return 70.0, _("{0} is close to {1}").format(locality, place)
	return 0.0, _("{0} is not a preferred locality").format(locality)


def type_part(wanted, property_type):
	"""(score, reason), or None when the lead chose no property type."""
	if not wanted:
		return None
	if not property_type:
		return 0.0, _("No property type is recorded")
	if wanted == property_type:
		return 100.0, _("{0} matches").format(property_type)
	if frozenset({wanted, property_type}) in SIMILAR_TYPES:
		return 60.0, _("{0} is like {1}").format(property_type, wanted)
	return 0.0, _("{0} is not {1}").format(property_type, wanted)


def score(req, home, weight) -> dict:
	"""The score of one home for one lead's requirements (see requirements_view). `home` has price,
	configuration, locality and property_type. Returns {"score": 0 to 100, "parts": [...]}, each part with its
	key, label, whether it applies, its score, weight, points of the total and reason."""
	found = {
		"budget": budget_part(req["budget_from"], req["budget_to"], home.get("price")),
		"configuration": configuration_part(
			req["configuration"], home.get("configuration"), home.get("property_type")
		),
		"locality": locality_part(req["preferred_localities"], home.get("locality")),
		"property_type": type_part(req["property_type"], home.get("property_type")),
	}
	used = sum(weight[p] for p in PARTS if found[p] is not None)
	total = 0.0
	parts = []
	for part in PARTS:
		result = found[part]
		share = (weight[part] / used) if result is not None and used else 0.0
		part_score = result[0] if result is not None else 0.0
		total += part_score * share
		parts.append(
			{
				"key": part,
				"label": _(LABELS[part]),
				"applies": result is not None,
				"score": int(part_score + 0.5),
				"weight": weight[part],
				"points": round(part_score * share, 1),
				"reason": result[1] if result is not None else _("The buyer did not say"),
			}
		)
	return {"score": int(total + 0.5), "parts": parts}


# --- the homes ---------------------------------------------------------------------------------------


def _unit_prices(units) -> dict[str, int | None]:
	"""Each unit's price from its project's price list in force, in whole rupees, with the price lists read in
	one query."""
	lists = {}
	for row in frappe.get_all(
		"Price List",
		filters={"effective_from": ["<=", pricing.today()]},
		fields=["project", "base_rate", "floor_rise_rate", "floor_rise_from_floor"],
		order_by="effective_from desc, creation desc",
	):
		lists.setdefault(row.project, row)
	prices = {}
	for unit in units:
		plan = lists.get(unit.project)
		prices[unit.name] = (
			pricing.cost_breakdown(
				carpet_area=unit.carpet_area,
				floor=unit.floor,
				parking=unit.parking,
				base_rate=plan.base_rate,
				floor_rise_rate=plan.floor_rise_rate,
				floor_rise_from_floor=plan.floor_rise_from_floor,
				charges=[],
				stamp_duty_percent=0,
				registration_percent=0,
				gst_percent=0,
			)["agreement_value"]
			if plan
			else None
		)
	return prices


def candidates() -> list[dict]:
	"""Every published listing and Available unit, with what the score reads, in a handful of queries."""
	units = frappe.get_all(
		"Unit",
		filters={"status": AVAILABLE, "archived": 0},
		fields=["name", "unit_number", "project", "configuration", "carpet_area", "floor", "parking"],
	)
	projects = {
		p.name: p
		for p in frappe.get_all("Project", fields=["name", "project_name", "locality", "city", "archived"])
	}
	prices = _unit_prices(units)
	by_unit = {}
	homes = []
	for unit in units:
		project = projects.get(unit.project)
		home = {
			"kind": "Unit",
			"name": unit.name,
			"title": f"{project.project_name if project else unit.project}, unit {unit.unit_number}",
			"configuration": unit.configuration or "",
			"locality": (project.locality if project else "") or "",
			"property_type": UNIT_TYPE,
			"price": prices[unit.name],
			"carpet_area": unit.carpet_area,
		}
		by_unit[unit.name] = home
		homes.append(home)
	properties = {
		p.name: p
		for p in frappe.get_all(
			"Property",
			filters={"status": AVAILABLE, "archived": 0},
			fields=["name", "title", "property_type", "locality", "configuration", "carpet_area"],
		)
	}
	for listing in frappe.get_all(
		"Listing",
		filters={"published": 1, "archived": 0},
		fields=["name", "title", "unit", "property", "asking_price"],
	):
		base = by_unit.get(listing.unit) if listing.unit else properties.get(listing.property)
		if not base:
			continue  # its unit or property is not Available (or is archived): never suggested
		if listing.unit:
			home = dict(base)
		else:
			home = {
				"configuration": base.configuration or "",
				"locality": base.locality or "",
				"property_type": base.property_type or "",
				"price": None,
				"carpet_area": base.carpet_area,
			}
		home.update(
			kind="Listing",
			name=listing.name,
			title=listing.title,
			price=flt(listing.asking_price) or home["price"],
			target=listing.unit or listing.property,
		)
		homes.append(home)
	return homes


def one_home(kind, name) -> dict | None:
	"""A unit or a listing as the score reads it, or None when it must never be suggested."""
	return next((h for h in candidates() if h["kind"] == kind and h["name"] == name), None)


def _suggestion(home, result) -> dict:
	return {
		"kind": home["kind"],
		"name": home["name"],
		"title": home["title"],
		"configuration": home["configuration"],
		"locality": home["locality"],
		"property_type": home["property_type"],
		"price": home["price"] or 0,
		"carpet_area": home["carpet_area"] or 0,
		"score": result["score"],
		"parts": result["parts"],
	}


def match_homes(req, homes, weight, limit=MAX_RESULTS) -> tuple[list[dict], int]:
	"""The homes that suit the requirements, best first, and how many suit in all."""
	scored = []
	for home in homes:
		result = score(req, home, weight)
		if result["score"] > 0:
			scored.append(_suggestion(home, result))
	scored.sort(key=lambda s: (-s["score"], s["title"], s["name"]))
	return scored[:limit], len(scored)


# --- the whitelisted methods -----------------------------------------------------------------------


def _read(doctype, name):
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("There is no {0} {1}.").format(_(doctype).lower(), name), frappe.DoesNotExistError)
	frappe.get_doc(doctype, name).check_permission("read")


@sellos_api(*READERS)
def matches_for_lead(lead):
	"""The published listings and Available units that suit a lead the caller may see, best first, each with its
	score from 0 to 100, the four parts of it and a reason for each."""
	_read("Lead", lead)
	for doctype in ("Unit", "Listing"):
		frappe.has_permission(doctype, "read", throw=True)
	doc = frappe.get_doc("Lead", lead)
	req = requirements_view(doc)
	suggestions, total = match_homes(req, candidates(), weights())
	return {
		"lead": lead,
		"requirements": req,
		"has_requirements": any(
			(
				req["budget_from"],
				req["budget_to"],
				req["configuration"],
				req["preferred_localities"],
				req["property_type"],
			)
		),
		"weights": weights(),
		"matches": suggestions,
		"total": total,
	}


def _leads_for(home, limit=MAX_RESULTS) -> dict:
	"""The leads this home suits among the ones the caller may see: `frappe.get_list` applies the lead
	permissions (an agent's own, a Sales Manager's team, a Company Admin's all), and a phone number is masked as
	the role requires."""
	weight = weights()
	scored = []
	for lead in frappe.get_list(
		"Lead",
		filters={"archived": 0},
		fields=["name", "lead_title", "client", "stage", "assigned_to", *REQUIREMENT_FIELDS],
		limit_page_length=0,
	):
		result = score(requirements_view(lead), home, weight)
		if result["score"] > 0:
			scored.append((lead, result))
	scored.sort(key=lambda pair: (-pair[1]["score"], pair[0].lead_title or "", pair[0].name))
	shown = scored[:limit]
	clients = {}
	for client in {lead.client for lead, _result in shown if lead.client}:
		clients[client] = crm_api.client_view(frappe.get_doc("Client", client), log=False)
	if COMPANY_ADMIN in frappe.get_roles():
		crm_api.log_full_number_shown(
			[c for c in clients if clients[c]["phone"] or clients[c]["overseas_phone"]]
		)
	people = {u.name: u.full_name for u in frappe.get_all("User", fields=["name", "full_name"])}
	return {
		"leads": [
			{
				"name": lead.name,
				"lead_title": lead.lead_title or "",
				"client_name": clients.get(lead.client, {}).get("client_name", ""),
				"phone": clients.get(lead.client, {}).get("phone", ""),
				"stage": lead.stage or "",
				"assigned_to": lead.assigned_to or "",
				"assigned_to_name": people.get(lead.assigned_to, lead.assigned_to or ""),
				"score": result["score"],
				"parts": result["parts"],
			}
			for lead, result in shown
		],
		"total": len(scored),
		"weights": weight,
	}


def _answer(kind, name, doctype_label):
	home = one_home(kind, name)
	if home is None:
		return {
			"name": name,
			"eligible": False,
			"message": _(
				"Only an Available unit or a published listing is matched. This {0} is not one."
			).format(doctype_label),
			"leads": [],
			"total": 0,
		}
	return {"name": name, "eligible": True, "message": "", **_leads_for(home)}


@sellos_api(*READERS)
def leads_for_unit(unit):
	"""The leads an Available unit suits that the caller may see, best first, with masked phone numbers."""
	_read("Unit", unit)
	return _answer("Unit", unit, _("unit"))


@sellos_api(*READERS)
def leads_for_listing(listing):
	"""The leads a published listing suits that the caller may see, best first, with masked phone numbers."""
	_read("Listing", listing)
	return _answer("Listing", listing, _("listing"))


@sellos_api(COMPANY_ADMIN)
def get_match_settings():
	return {"weights": weights()}


@sellos_api(COMPANY_ADMIN)
def save_match_settings(budget, configuration, locality, property_type):
	"""Save the four weights, each 0 to 100, not all zero."""
	given = {
		"budget": budget,
		"configuration": configuration,
		"locality": locality,
		"property_type": property_type,
	}
	clean = {}
	for part, value in given.items():
		try:
			number = int(str(value).strip())
		except ValueError:
			number = -1
		if not 0 <= number <= MAX_WEIGHT:
			frappe.throw(
				_("Enter the {0} weight as a whole number from 0 to {1}.").format(
					LABELS[part].lower(), MAX_WEIGHT
				)
			)
		clean[part] = number
	if not sum(clean.values()):
		frappe.throw(_("At least one weight must be above zero."))
	for part, number in clean.items():
		frappe.db.set_single_value(SETTINGS, WEIGHT_FIELDS[part], number)
	return {"weights": weights()}
