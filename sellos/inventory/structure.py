"""Towers, wings and floors of a project, the units of a floor, and a project's possession date, amenities
and brochures (SOS-P7-05).

A Company Admin or an Agent (who may edit inventory, SOS-P4-01) lays out the structure; a Sales Manager reads
it through get_project. Nothing is deleted: removing a tower or a floor archives it and the Available units on it, and is refused
when any unit on it is Held, Sold or in any other status but Available. Brochures are kept as private files
on the project; SOS-P4-03 links the Media Asset library to listings later.
"""

import base64
import binascii
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN
from sellos.inventory.base import AVAILABLE, squash

EDITORS = (COMPANY_ADMIN, AGENT)
MAX_UNITS_AT_ONCE = 100
BROCHURE_TYPES = (".pdf", ".png", ".jpg", ".jpeg")
BROCHURE_LIMIT = 10 * 1024 * 1024
_MAGIC = (b"%PDF", b"\x89PNG", b"\xff\xd8\xff")
# "1201 to 1208" or "1201-1208"
_PATTERN = re.compile(r"^\s*(\d{1,6})\s*(?:-|to)\s*(\d{1,6})\s*$", re.IGNORECASE)


def _json(value, default):
	if value in (None, ""):
		return default
	return frappe.parse_json(value) if isinstance(value, str) else value


def parse_pattern(pattern, prefix="") -> list[str]:
	"""The unit numbers of a pattern such as "1201 to 1208", each with the prefix in front. A number with a
	leading zero keeps its width ("0101 to 0108")."""
	match = _PATTERN.match(str(pattern or ""))
	if not match:
		frappe.throw(_("Write the unit numbers as a range, for example 1201 to 1208."))
	first, last = match.group(1), match.group(2)
	prefix = squash(prefix)
	if len(prefix) > 10:
		frappe.throw(_("The prefix can be up to 10 characters."))
	if int(last) < int(first):
		frappe.throw(_("The last unit number must not be below the first."))
	if int(last) - int(first) + 1 > MAX_UNITS_AT_ONCE:
		frappe.throw(_("Make up to {0} units at a time.").format(MAX_UNITS_AT_ONCE))
	width = len(first)
	return [f"{prefix}{number:0{width}d}" for number in range(int(first), int(last) + 1)]


def _tower(name, write=False):
	if not name or not frappe.db.exists("Project Tower", name):
		frappe.throw(_("There is no tower or wing {0}.").format(name), frappe.DoesNotExistError)
	doc = frappe.get_doc("Project Tower", name)
	doc.check_permission("write" if write else "read")
	if write and doc.archived:
		frappe.throw(_("{0} has been removed.").format(doc.tower_name))
	return doc


def _project(name):
	if not name or not frappe.db.exists("Project", name):
		frappe.throw(_("There is no project {0}.").format(name), frappe.DoesNotExistError)
	return frappe.get_doc("Project", name)


def _not_available(filters) -> list:
	return frappe.get_all(
		"Unit",
		filters={**filters, "archived": 0, "status": ["!=", AVAILABLE]},
		fields=["name", "unit_number"],
	)


def _archive_units(filters):
	for name in frappe.get_all("Unit", filters={**filters, "archived": 0}, pluck="name"):
		unit = frappe.get_doc("Unit", name)
		unit.archived = 1
		unit.save()


def _refuse_if_occupied(units, what):
	if units:
		frappe.throw(
			_("{0} can not be removed: {1} of its units are not Available ({2}).").format(
				what, len(units), ", ".join(u.unit_number for u in units[:10])
			)
		)


def project_structure(project) -> dict:
	"""The project's towers with their floors and units, its possession date, amenities and brochures."""
	towers = []
	for name in frappe.get_list(
		"Project Tower", filters={"project": project, "archived": 0}, order_by="creation asc", pluck="name"
	):
		tower = frappe.get_doc("Project Tower", name)
		units = frappe.get_list(
			"Unit",
			filters={"project": project, "tower": name, "archived": 0},
			fields=["name", "unit_number", "floor", "status", "configuration", "carpet_area"],
			order_by="unit_number asc",
		)
		floors = [
			{
				"floor_number": row.floor_number,
				"floor_label": row.floor_label or "",
				"units": [u for u in units if u.floor == row.floor_number],
			}
			for row in tower.floors
		]
		towers.append(
			{
				"name": tower.name,
				"tower_name": tower.tower_name,
				"floors": floors,
				"unit_count": len(units),
				"unplaced_units": [u for u in units if u.floor not in {f["floor_number"] for f in floors}],
			}
		)
	doc = frappe.get_doc("Project", project)
	return {
		"towers": towers,
		"possession_date": str(doc.possession_date) if doc.possession_date else "",
		"amenities": [row.amenity for row in doc.amenities],
		"amenity_options": amenity_options(),
		"brochures": [{"title": row.title, "file": row.file} for row in doc.brochures],
		"can_manage_amenities": COMPANY_ADMIN in frappe.get_roles(),
	}


def amenity_options() -> list[str]:
	return frappe.get_list("Amenity", filters={"archived": 0}, order_by="amenity_name asc", pluck="name")


def _state(project):
	from sellos.inventory.api import get_project

	return get_project(project)


@sellos_api(*EDITORS)
def add_tower(project, tower_name, floors=None):
	"""Add a tower or wing to a project, with its floors when `floors` is given ("1 to 20" or "1-20")."""
	_project(project)
	doc = frappe.get_doc({"doctype": "Project Tower", "project": project, "tower_name": tower_name})
	for number in _floor_numbers(floors):
		doc.append("floors", {"floor_number": number})
	doc.insert()
	return {"name": doc.name, **_state(project)}


def _floor_numbers(floors) -> list[int]:
	text = str(floors or "").strip()
	if not text:
		return []
	match = _PATTERN.match(text) or re.match(r"^(\d{1,3})()$", text)
	if not match:
		frappe.throw(_("Write the floors as a range, for example 1 to 20."))
	first = int(match.group(1))
	last = int(match.group(2) or first)
	if last < first or last - first + 1 > 200:
		frappe.throw(_("Add 1 to 200 floors at a time, the last not below the first."))
	return list(range(first, last + 1))


@sellos_api(*EDITORS)
def add_floors(tower, floors):
	"""Add floors to a tower from a range such as "1 to 20". Floors it already has are left as they are."""
	doc = _tower(tower, write=True)
	numbers = _floor_numbers(floors)
	if not numbers:
		frappe.throw(_("Write the floors as a range, for example 1 to 20."))
	have = {row.floor_number for row in doc.floors}
	for number in numbers:
		if number not in have:
			doc.append("floors", {"floor_number": number})
	doc.save()
	return {"name": doc.name, **_state(doc.project)}


@sellos_api(*EDITORS)
def remove_floor(tower, floor):
	"""Remove a floor from a tower. Refused, with the count, when a unit on it is in any status but Available;
	otherwise the floor and its Available units are archived."""
	doc = _tower(tower, write=True)
	floor = cint(floor)
	rows = [row for row in doc.floors if row.floor_number == floor]
	if not rows:
		frappe.throw(_("{0} has no floor {1}.").format(doc.tower_name, floor))
	on_floor = {"project": doc.project, "tower": doc.name, "floor": floor}
	_refuse_if_occupied(_not_available(on_floor), _("Floor {0}").format(floor))
	_archive_units(on_floor)
	doc.floors = [row for row in doc.floors if row.floor_number != floor]
	doc.save()
	return {"name": doc.name, **_state(doc.project)}


@sellos_api(*EDITORS)
def remove_tower(tower):
	"""Remove a tower or wing. Refused, with the count, when a unit in it is in any status but Available;
	otherwise the tower and its Available units are archived."""
	doc = _tower(tower, write=True)
	in_tower = {"project": doc.project, "tower": doc.name}
	_refuse_if_occupied(_not_available(in_tower), doc.tower_name)
	_archive_units(in_tower)
	doc.archived = 1
	doc.save()
	return {"name": doc.name, **_state(doc.project)}


@sellos_api(*EDITORS)
def generate_floor_units(tower, floor, pattern, carpet_area, configuration="", prefix="", parking=0):
	"""Make the units of one floor from a pattern such as "1201 to 1208". A unit number the tower already has
	(archived ones too) is left as it is, so making them again changes nothing."""
	doc = _tower(tower, write=True)
	floor = cint(floor)
	if floor not in {row.floor_number for row in doc.floors}:
		frappe.throw(_("{0} has no floor {1}. Add the floor first.").format(doc.tower_name, floor))
	numbers = parse_pattern(pattern, prefix)
	if flt(carpet_area) <= 0:
		frappe.throw(_("Enter the carpet area in square feet, more than zero."))
	configuration = squash(configuration)
	options = frappe.get_meta("Unit").get_field("configuration").options.split("\n")
	if configuration not in options:
		frappe.throw(_("Choose a configuration from the list."))
	have = set(
		frappe.get_all("Unit", filters={"project": doc.project, "tower": doc.name}, pluck="unit_number")
	)
	created, skipped = [], []
	for number in numbers:
		if number in have:
			skipped.append(number)
			continue
		frappe.get_doc(
			{
				"doctype": "Unit",
				"project": doc.project,
				"tower": doc.name,
				"unit_number": number,
				"floor": floor,
				"configuration": configuration,
				"carpet_area": carpet_area,
				"parking": parking or 0,
			}
		).insert()
		created.append(number)
	return {"name": doc.name, "created": created, "skipped": skipped, **_state(doc.project)}


@sellos_api(*EDITORS)
def save_project_details(project, possession_date=None, amenities=None):
	"""Set the project's possession date ("" clears it) and its amenities, chosen from the Company Admin's list."""
	doc = _project(project)
	doc.check_permission("write")
	if possession_date is not None:
		doc.possession_date = getdate(possession_date) if str(possession_date).strip() else None
	if amenities is not None:
		chosen = list(dict.fromkeys(_json(amenities, [])))
		known = set(amenity_options())
		unknown = [name for name in chosen if name not in known]
		if unknown:
			frappe.throw(_("{0} is not in the amenity list.").format(", ".join(str(n) for n in unknown)))
		doc.set("amenities", [])
		for name in chosen:
			doc.append("amenities", {"amenity": name})
	doc.save()
	return {"name": doc.name, **_state(doc.name)}


@sellos_api(COMPANY_ADMIN)
def save_amenity(amenity_name, archived=0):
	"""Add an amenity to the list projects choose from, or archive or restore one. Nothing is deleted."""
	name = squash(amenity_name)
	if frappe.db.exists("Amenity", name):
		doc = frappe.get_doc("Amenity", name)
		doc.archived = 1 if str(archived).lower() in ("1", "true", "yes") else 0
		doc.save()
	else:
		frappe.get_doc({"doctype": "Amenity", "amenity_name": name}).insert()
	return {"amenity_options": amenity_options()}


def _decode(content_base64) -> bytes:
	text = str(content_base64 or "")
	if len(text) > BROCHURE_LIMIT * 4 // 3 + 8:
		frappe.throw(_("The brochure must be a file of up to 10 MB."))
	try:
		return base64.b64decode(text, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The brochure could not be read. Choose the file again."))


@sellos_api(*EDITORS)
def add_project_brochure(project, title, filename, content_base64):
	"""Attach a brochure (a PDF, PNG or JPG up to 10 MB, as base64) to a project. It is kept as a private file."""
	doc = _project(project)
	doc.check_permission("write")
	title = squash(title)
	filename = frappe.utils.cstr(filename).strip()
	content = _decode(content_base64)
	if not title:
		frappe.throw(_("Enter a title for the brochure."))
	if not filename.lower().endswith(BROCHURE_TYPES) or not content.startswith(_MAGIC):
		frappe.throw(_("The brochure must be a PDF, PNG or JPG file."))
	if not content or len(content) > BROCHURE_LIMIT:
		frappe.throw(_("The brochure must be a file of up to 10 MB."))
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"is_private": 1,
			"attached_to_doctype": "Project",
			"attached_to_name": doc.name,
		}
	)
	file.flags.ignore_permissions = True
	file.insert()
	doc.append("brochures", {"title": title, "file": file.file_url})
	doc.save()
	return {"name": doc.name, **_state(doc.name)}


@sellos_api(*EDITORS)
def remove_project_brochure(project, file):
	"""Take a brochure off a project. The file itself is kept."""
	doc = _project(project)
	doc.check_permission("write")
	if any(row.file == file for row in doc.brochures):
		doc.brochures = [row for row in doc.brochures if row.file != file]
		doc.save()
	return {"name": doc.name, **_state(doc.name)}
