"""What a buyer wants (SOS-P1-15): the lists of allowed values, cleaning, and the list filters.

The fields sit on the Lead. Configuration and preferred localities hold several values, stored one per
line in a text field, so the change history shows the whole list. The lists below are the single source
of the options: a test checks that lead.json offers exactly these.
"""

import frappe
from frappe import _
from frappe.utils import flt

CONFIGURATIONS = ("1 RK", "1 BHK", "2 BHK", "3 BHK", "4 BHK and above")
PROPERTY_TYPES = ("Apartment", "Villa", "Plot", "Office", "Shop")
PURPOSES = ("End use", "Investment")
TIMELINES = ("Immediate", "Within 3 months", "3 to 6 months", "Over 6 months")
POSSESSIONS = ("Ready", "Under construction", "Any")

MULTI_FIELDS = ("configuration", "preferred_localities")
BUDGET_FIELDS = ("budget_from", "budget_to")
REQUIREMENT_FIELDS = (
	*BUDGET_FIELDS,
	"configuration",
	"property_type",
	"preferred_localities",
	"purpose",
	"timeline",
	"possession",
)
SINGLE_CHOICES = {
	"property_type": PROPERTY_TYPES,
	"purpose": PURPOSES,
	"timeline": TIMELINES,
	"possession": POSSESSIONS,
}


def split_values(value) -> list[str]:
	"""A stored text, or a list from the screen, as a clean list: trimmed, no blanks, no repeats."""
	if value is None:
		return []
	if isinstance(value, str):
		value = value.splitlines()
	seen, clean = set(), []
	for item in value:
		item = " ".join(str(item).split())
		if item and item.lower() not in seen:
			seen.add(item.lower())
			clean.append(item)
	return clean


def join_values(value) -> str:
	return "\n".join(split_values(value))


def budget_of(value) -> float | None:
	"""A budget in rupees, or None when it is empty or zero."""
	return flt(value) or None


def validate_requirements(doc) -> None:
	"""Clean the lists and refuse a budget or a choice the product does not offer."""
	for field in MULTI_FIELDS:
		doc.set(field, join_values(doc.get(field)))
	allowed = {c.lower(): c for c in CONFIGURATIONS}
	chosen = split_values(doc.configuration)
	unknown = [c for c in chosen if c.lower() not in allowed]
	if unknown:
		frappe.throw(
			_("{0} is not a configuration. Choose from: {1}.").format(unknown[0], ", ".join(CONFIGURATIONS))
		)
	doc.configuration = "\n".join(allowed[c.lower()] for c in chosen)
	for field, options in SINGLE_CHOICES.items():
		if doc.get(field) and doc.get(field) not in options:
			frappe.throw(_("{0} is not an option for {1}.").format(doc.get(field), doc.meta.get_label(field)))
	for field in BUDGET_FIELDS:
		if flt(doc.get(field)) < 0:
			frappe.throw(_("{0} cannot be below zero.").format(doc.meta.get_label(field)))
	low, high = budget_of(doc.budget_from), budget_of(doc.budget_to)
	if low and high and low > high:
		frappe.throw(_("Budget from cannot be above budget to."))


def requirements_view(lead) -> dict:
	"""The requirements of a lead (a document or a row) with the two lists split."""
	get = lead.get
	return {
		"budget_from": budget_of(get("budget_from")),
		"budget_to": budget_of(get("budget_to")),
		"configuration": split_values(get("configuration")),
		"property_type": get("property_type") or "",
		"preferred_localities": split_values(get("preferred_localities")),
		"purpose": get("purpose") or "",
		"timeline": get("timeline") or "",
		"possession": get("possession") or "",
	}


def matches(row, budget_min=None, budget_max=None, configuration=None, locality=None, timeline=None) -> bool:
	"""True when a lead satisfies every filter given. Budget filters match a lead whose range overlaps
	the asked range; a lead with no budget at all never matches one. Configuration takes any of the
	values given, a locality matches a part of a preferred locality, the timeline is exact."""
	low, high = budget_of(row.get("budget_from")), budget_of(row.get("budget_to"))
	wanted_min, wanted_max = budget_of(budget_min), budget_of(budget_max)
	if wanted_min or wanted_max:
		if low is None and high is None:
			return False
		if wanted_min and high is not None and high < wanted_min:
			return False
		if wanted_max and low is not None and low > wanted_max:
			return False
	wanted = {c.lower() for c in split_values(configuration)}
	if wanted and not wanted & {c.lower() for c in split_values(row.get("configuration"))}:
		return False
	if locality:
		needle = " ".join(str(locality).split()).lower()
		if needle and not any(needle in p.lower() for p in split_values(row.get("preferred_localities"))):
			return False
	return not (timeline and row.get("timeline") != timeline)


def has_filters(**filters) -> bool:
	return any(v not in (None, "", [], 0, "0") for v in filters.values())
