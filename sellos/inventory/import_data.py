"""Import developers, projects, units, properties, listings and mandates from a spreadsheet (SOS-P4-10C).

A Company Admin downloads a template for one record type, fills it in and uploads it in the web app. The file is
read with SOS-P1-12's `lead_import.read_csv` (comma, semicolon or tab, byte order mark, row cap). One file holds one
record type, and its columns are found by their names (the template's own, spelling and spacing ignored).

* A dry run (the default) does the whole import inside a savepoint and rolls it back, so its counts, and the rows
  that would fail and why, are exactly what a real run would do, and it writes nothing.
* Duplicates are matched, then updated, never doubled: a project on its RERA number, a unit on its project and unit
  number, a developer on its name, a property on its RERA number (or its title and city), a listing on the unit or
  property it offers, a mandate on its seller, type and start date. A blank cell never overwrites a value.
* Rows of one file that name the same record are folded into it first (a later filled cell wins) and read "Merged".
* Every row is saved through its DocType as the Company Admin, so the DocType checks and permissions run. A row that
  fails is reported with its reason and left out, and the others go on.
* What a file can not set: a unit's or property's status (it changes only through `set_inventory_status`), a
  listing's published flag (imported listings are drafts) and a mandate's signature. A mandate imported without its
  signed document stays a Draft, so its Dossier stays hidden (SOS-P4-05).
* A run writes a reconciliation report, a private CSV file, with the counts per outcome and one line per row, and
  returns the same counts. Running the same file again creates, updates and changes nothing: every row reads
  "Unchanged".
"""

import csv
import io

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.crm import duplicates, lead_import
from sellos.crm.base import mask_phone
from sellos.crm.lead_sources import normalise
from sellos.inventory.base import clean_rera_number, squash

CREATED, UPDATED, UNCHANGED, MERGED, FAILED = "Created", "Updated", "Unchanged", "Merged", "Failed"
OUTCOMES = (CREATED, UPDATED, UNCHANGED, MERGED, FAILED)
SHOWN_ROWS = 200

DEVELOPER, PROJECT, UNIT, PROPERTY, LISTING, MANDATE = (
	"Developer",
	"Project",
	"Unit",
	"Property",
	"Listing",
	"Mandate",
)
RECORD_TYPES = (DEVELOPER, PROJECT, UNIT, PROPERTY, LISTING, MANDATE)
# The order to import in: a project needs its developer, a unit its project, a listing its unit or property.
PLURALS = {
	DEVELOPER: "developers",
	PROJECT: "projects",
	UNIT: "units",
	PROPERTY: "properties",
	LISTING: "listings",
	MANDATE: "mandates",
}

CONFIGURATIONS = (
	"1 RK",
	"1 BHK",
	"1.5 BHK",
	"2 BHK",
	"2.5 BHK",
	"3 BHK",
	"3.5 BHK",
	"4 BHK",
	"5 BHK",
	"Penthouse",
	"Villa",
	"Plot",
	"Shop",
	"Office",
)
PROJECT_STATUSES = ("Upcoming", "Under construction", "Ready to move")
PROPERTY_TYPES = ("Apartment", "Villa", "Independent house", "Plot", "Shop", "Office")
LISTING_TYPES = ("Primary", "Direct", "Partner")
MANDATE_TYPES = ("Exclusive", "Open")

# A column: (field, heading, kind, required). Kinds: text, rera, float, int, date, ref (looked up, never set
# directly) or a tuple of the allowed values.
COLUMNS = {
	DEVELOPER: (
		("developer_name", "Developer name", "text", True),
		("rera_registration", "RERA registration", "text", False),
		("contact_person", "Contact person", "text", False),
		("email", "Email", "text", False),
		("website", "Website", "text", False),
		("notes", "Notes", "text", False),
	),
	PROJECT: (
		("project_name", "Project name", "text", True),
		("developer", "Developer", "ref", True),
		("rera_number", "RERA number", "rera", True),
		("project_status", "Project status", PROJECT_STATUSES, False),
		("city", "City", "text", True),
		("locality", "Locality", "text", False),
		("address", "Address", "text", False),
		("possession_date", "Possession date", "date", False),
	),
	UNIT: (
		("project", "Project", "ref", True),
		("unit_number", "Unit number", "text", True),
		("configuration", "Configuration", CONFIGURATIONS, False),
		("carpet_area", "Carpet area", "float", True),
		("floor", "Floor", "int", False),
		("parking", "Parking", "int", False),
	),
	PROPERTY: (
		("title", "Title", "text", True),
		("property_type", "Property type", PROPERTY_TYPES, True),
		("building_name", "Building name", "text", False),
		("rera_number", "RERA number", "rera", False),
		("configuration", "Configuration", CONFIGURATIONS, False),
		("carpet_area", "Carpet area", "float", True),
		("floor", "Floor", "int", False),
		("parking", "Parking", "int", False),
		("city", "City", "text", True),
		("locality", "Locality", "text", False),
		("address", "Address", "text", False),
	),
	LISTING: (
		("title", "Title", "text", True),
		("listing_type", "Listing type", LISTING_TYPES, True),
		("project", "Project", "ref", False),
		("unit_number", "Unit number", "text", False),
		("property", "Property", "ref", False),
		("asking_price", "Asking price", "float", False),
		("description", "Description", "text", False),
	),
	MANDATE: (
		("seller_phone", "Seller phone", "ref", True),
		("mandate_type", "Mandate type", MANDATE_TYPES, True),
		("start_date", "Start date", "date", True),
		("term_months", "Term months", "int", True),
		("fee_percent", "Fee percent", "float", True),
	),
}

# One example row per template, with words and numbers that show the form. Nothing here is a person's number.
EXAMPLES = {
	DEVELOPER: ("Example Developer", "", "Sales desk", "sales@example.com", "", ""),
	PROJECT: (
		"Example Heights",
		"Example Developer",
		"P51800000001",
		"Under construction",
		"Pune",
		"",
		"",
		"",
	),
	UNIT: ("P51800000001", "1201", "2 BHK", "640", "12", "1"),
	PROPERTY: ("Example Resale Flat", "Apartment", "", "", "2 BHK", "720", "4", "1", "Pune", "Kothrud", ""),
	LISTING: ("Example listing", "Primary", "P51800000001", "1201", "", "9500000", "A bright 2 BHK."),
	MANDATE: ("<the seller's phone number>", "Exclusive", "2026-12-01", "6", "1.5"),
}
HELP = {
	DEVELOPER: "A developer is matched on its name.",
	PROJECT: "A project is matched on its RERA number. Developer is the name of a developer already in SellOS.",
	UNIT: (
		"A unit is matched on its project and unit number. Project is the project's RERA number or name. "
		"The status is not imported."
	),
	PROPERTY: "A property is matched on its RERA number, or on its title and city when it has none.",
	LISTING: (
		"A listing is matched on the unit (Project and Unit number) or the property (Property is its title) "
		"it offers. Listings come in as drafts. Publish them in SellOS."
	),
	MANDATE: (
		"Seller phone is the phone number of a seller already in SellOS. A mandate is matched on its seller, "
		"type and start date, and comes in as a Draft: it is signed in SellOS with its signed document."
	),
}


def _check_type(record_type) -> str:
	if record_type not in RECORD_TYPES:
		frappe.throw(_("Choose what to import: {0}.").format(", ".join(RECORD_TYPES)))
	return record_type


def template_text(record_type) -> str:
	"""The CSV template for a record type: its headings and one example row to replace."""
	record_type = _check_type(record_type)
	out = io.StringIO()
	writer = csv.writer(out, lineterminator="\n")
	writer.writerow([c[1] for c in COLUMNS[record_type]])
	writer.writerow(EXAMPLES[record_type])
	return out.getvalue()


# --- reading a row ------------------------------------------------------------------------------


def _find_columns(record_type, headers) -> dict:
	"""{field: heading} for the headings the file has. A required column the file lacks is refused."""
	by_key = {normalise(h): h for h in headers if h}
	found = {}
	for field, heading, _kind, required in COLUMNS[record_type]:
		header = by_key.get(normalise(heading)) or by_key.get(normalise(field))
		if header:
			found[field] = header
		elif required:
			frappe.throw(
				_(
					"The file has no column called {0}. Download the template for {1} and use its headings."
				).format(heading, PLURALS[record_type])
			)
	return found


def _convert(kind, heading, raw):
	"""The cell as the value to store, or "" when blank. Raises ValueError with a sentence on a bad value."""
	raw = squash(raw)
	if not raw:
		return ""
	if kind == "text" or kind == "ref":
		return raw
	if kind == "rera":
		return clean_rera_number(raw)
	if kind == "float":
		try:
			value = float(raw.replace(",", ""))
		except ValueError:
			raise ValueError(_("{0} must be a number.").format(heading)) from None
		if value < 0:
			raise ValueError(_("{0} can not be negative.").format(heading))
		return value
	if kind == "int":
		try:
			return int(float(raw))
		except ValueError:
			raise ValueError(_("{0} must be a whole number.").format(heading)) from None
	if kind == "date":
		try:
			return str(getdate(raw))
		except Exception:
			raise ValueError(_("{0} must be a date such as 2026-12-31.").format(heading)) from None
	for option in kind:
		if normalise(option) == normalise(raw):
			return option
	raise ValueError(_("{0} must be one of {1}.").format(heading, ", ".join(kind)))


def _read_row(record_type, columns, row) -> dict:
	"""{field: value} for the cells that are filled. A required cell that is blank is refused."""
	values = {}
	for field, heading, kind, required in COLUMNS[record_type]:
		raw = row.get(columns[field]) if field in columns else ""
		value = _convert(kind, heading, raw)
		if value == "":
			if required:
				raise ValueError(_("{0} is empty.").format(heading))
			continue
		values[field] = value
	return values


# --- finding what a row refers to ---------------------------------------------------------------


def _one(doctype, filters, what):
	"""The live record matching, None if there is none. Two matches, or an archived one, is an error."""
	names = frappe.get_all(doctype, filters=filters, pluck="name", limit=3)
	if len(names) > 1:
		raise ValueError(_("More than one {0} matches {1}.").format(doctype.lower(), what))
	return names[0] if names else None


def _project(reference):
	"""A project by its RERA number, or by its name when that is not one that exists."""
	try:
		rera = clean_rera_number(reference)
	except frappe.ValidationError:
		rera = ""
	name = _one("Project", {"rera_number": rera}, reference) if rera else None
	name = name or _one("Project", {"project_name": reference}, reference)
	if not name:
		raise ValueError(_("There is no project {0}. Import the projects first.").format(reference))
	return name


def _developer(reference):
	name = _one("Developer", {"developer_name": reference}, reference)
	if not name:
		raise ValueError(_("There is no developer {0}. Import the developers first.").format(reference))
	return name


def _unit(project, number):
	return _one("Unit", {"project": project, "unit_number": number}, f"unit {number}")


def _seller_lead(phone):
	"""The live Seller lead of the client with this phone number."""
	key = duplicates.normalise_phone(phone)
	clients = [m["name"] for m in duplicates.find_matches(key, key) if not m["archived"]] if key else []
	if not clients:
		raise ValueError(_("No seller in SellOS has the phone number {0}.").format(mask_phone(key)))
	leads = frappe.get_all(
		"Lead", filters={"client": ["in", clients], "pipeline": "Seller", "archived": 0}, pluck="name"
	)
	if not leads:
		raise ValueError(_("{0} has no seller lead.").format(mask_phone(key)))
	if len(leads) > 1:
		raise ValueError(_("{0} has more than one seller lead.").format(mask_phone(key)))
	return leads[0]


def _resolve(record_type, values):
	"""(existing name or None, the key fields to create with, the fields to set). Raises ValueError."""
	data = dict(values)
	if record_type == DEVELOPER:
		key = {"developer_name": data.pop("developer_name")}
		return _one("Developer", key, key["developer_name"]), key, data
	if record_type == PROJECT:
		data["developer"] = _developer(data["developer"])
		key = {"rera_number": data.pop("rera_number")}
		return _one("Project", key, key["rera_number"]), key, data
	if record_type == UNIT:
		key = {"project": _project(data.pop("project")), "unit_number": data.pop("unit_number")}
		return _unit(key["project"], key["unit_number"]), key, data
	if record_type == PROPERTY:
		if data.get("rera_number"):
			key = {"rera_number": data.pop("rera_number")}
			return _one("Property", key, key["rera_number"]), key, data
		key = {"title": data.pop("title"), "city": data.pop("city")}
		return _one("Property", key, key["title"]), key, data
	if record_type == LISTING:
		return _resolve_listing(data)
	return _resolve_mandate(data)


def _resolve_listing(data):
	project, number, prop = (
		data.pop("project", None),
		data.pop("unit_number", None),
		data.pop("property", None),
	)
	if bool(project and number) == bool(prop) or bool(project) != bool(number):
		raise ValueError(
			_("Give the unit (Project and Unit number) or the property, not both and not neither.")
		)
	if prop:
		target = {"property": _one("Property", {"title": prop}, prop)}
		if not target["property"]:
			raise ValueError(_("There is no property {0}. Import the properties first.").format(prop))
	else:
		unit = _unit(_project(project), number)
		if not unit:
			raise ValueError(
				_("There is no unit {0} in {1}. Import the units first.").format(number, project)
			)
		target = {"unit": unit}
	field, name = next(iter(target.items()))
	return _one("Listing", {field: name, "archived": 0}, name), target, data


def _resolve_mandate(data):
	key = {
		"lead": _seller_lead(data.pop("seller_phone")),
		"mandate_type": data.pop("mandate_type"),
		"start_date": data.pop("start_date"),
	}
	return _one("Mandate", {**key, "archived": 0}, "the seller, type and start date"), key, data


# --- saving a row -------------------------------------------------------------------------------


def _canon(value) -> str:
	if value is None or value == "":
		return ""
	if isinstance(value, bool):
		return str(int(value))
	if isinstance(value, int | float):
		return f"{flt(value):g}"
	return squash(value)


def _save(record_type, existing, key, data) -> str:
	"""Create the record, or update what differs. Returns Created, Updated or Unchanged."""
	if not existing:
		frappe.get_doc({"doctype": record_type, **key, **data}).insert()
		return CREATED
	doc = frappe.get_doc(record_type, existing)
	if doc.get("archived"):
		raise ValueError(_("{0} is archived. Restore it first.").format(existing))
	changed = {f: v for f, v in data.items() if _canon(doc.get(f)) != _canon(v)}
	if not changed:
		return UNCHANGED
	doc.update(changed)
	doc.save()
	return UPDATED


def _problem(error) -> str:
	text = frappe.utils.strip_html(str(error)).strip()
	return text[:240] or _("The row could not be saved.")


def _run_rows(record_type, columns, rows) -> list[dict]:
	"""Read and resolve every row, fold the rows that are one record (a later filled cell wins), then save each
	record once. A record that can not be saved fails every row that names it, with its reason."""
	results, groups = {}, {}
	for row in rows:
		line = row["_row"]
		try:
			existing, key, data = _resolve(record_type, _read_row(record_type, columns, row))
		except Exception as error:
			results[line] = {"row": line, "outcome": FAILED, "reason": _problem(error)}
			continue
		group = groups.setdefault(
			tuple(sorted(key.items())), {"existing": existing, "key": key, "data": {}, "rows": []}
		)
		group["data"].update(data)
		group["rows"].append(line)
	for group in groups.values():
		first, *rest = group["rows"]
		frappe.db.savepoint("inventory_import_row")
		try:
			outcome, reason = _save(record_type, group["existing"], group["key"], group["data"]), ""
		except Exception as error:
			frappe.db.rollback(save_point="inventory_import_row")
			outcome, reason = FAILED, _problem(error)
		else:
			frappe.db.release_savepoint("inventory_import_row")
		results[first] = {"row": first, "outcome": outcome, "reason": reason}
		for line in rest:
			again = {"outcome": MERGED, "reason": _("Same record as row {0}.").format(first)}
			results[line] = {
				"row": line,
				**(again if outcome != FAILED else {"outcome": FAILED, "reason": reason}),
			}
	return [results[line] for line in sorted(results)]


def _run(record_type, csv_text, dry_run) -> dict:
	record_type = _check_type(record_type)
	headers, rows = lead_import.read_csv(csv_text)
	columns = _find_columns(record_type, headers)
	frappe.db.savepoint("inventory_import")
	results = _run_rows(record_type, columns, rows)
	if dry_run:
		frappe.db.rollback(save_point="inventory_import")
		frappe.db.after_commit.reset()  # a change webhook queued by a row that never happened
	counts = {outcome: sum(r["outcome"] == outcome for r in results) for outcome in OUTCOMES}
	report = {
		"record_type": record_type,
		"dry_run": int(bool(dry_run)),
		"counts": {"rows": len(rows), **{o.lower(): n for o, n in counts.items()}},
		"failed": [r for r in results if r["outcome"] == FAILED][:SHOWN_ROWS],
		"report_file": "",
	}
	if not dry_run:
		report["report_file"] = _write_report(record_type, report["counts"], results)
	return report


def _write_report(record_type, counts, results) -> str:
	"""The reconciliation report: the counts of the run, then each row with its outcome. A private file."""
	out = io.StringIO()
	writer = csv.writer(out, lineterminator="\n")
	writer.writerow(["Import of", PLURALS[record_type]])
	for key, value in counts.items():
		writer.writerow([key.capitalize(), value])
	writer.writerow([])
	writer.writerow(["Row", "Outcome", "Reason"])
	for r in results:
		writer.writerow([r["row"], r["outcome"], r["reason"]])
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"import-report-{PLURALS[record_type]}-{frappe.utils.now_datetime():%Y%m%d-%H%M%S}.csv",
			"content": out.getvalue().encode("utf-8"),
			"is_private": 1,
		}
	)
	file.flags.ignore_permissions = True  # the caller is a Company Admin (checked by the method's role)
	file.insert()
	return file.file_url


# --- the methods --------------------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN)
def import_template(record_type):
	"""The CSV template for one record type, with its headings, one example row and a line on how it is matched."""
	record_type = _check_type(record_type)
	return {
		"record_type": record_type,
		"file_name": f"sellos-{PLURALS[record_type]}-template.csv",
		"csv": template_text(record_type),
		"help": HELP[record_type],
	}


@sellos_api(COMPANY_ADMIN)
def import_overview():
	"""The record types a file can hold, in the order to import them, each with how its rows are matched."""
	return {
		"types": [
			{"record_type": t, "label": PLURALS[t].capitalize(), "help": HELP[t]} for t in RECORD_TYPES
		],
	}


@sellos_api(COMPANY_ADMIN)
def preview_inventory_import(record_type, csv_text):
	"""A dry run: what importing this file would do, the rows that would fail and why. Nothing is written."""
	return _run(record_type, csv_text, dry_run=True)


@sellos_api(COMPANY_ADMIN)
def run_inventory_import(record_type, csv_text):
	"""Import the file, updating what it matches and making what it does not, and write the reconciliation report."""
	return _run(record_type, csv_text, dry_run=False)
