"""SOS-P4-10C: the listings and mandates import. A sample file per record type holding duplicates and bad rows, a
dry run that writes nothing, a second run that changes nothing, a mandate that stays unsigned with its Dossier
hidden, the reconciliation report and the permission check."""

import csv
import io
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import ensure_roles
from sellos.crm import api as crm
from sellos.crm import pipeline
from sellos.crm.lead_sources import ensure_default_sources
from sellos.crm.test_crm import as_user
from sellos.inventory import import_data as imp
from sellos.inventory import mandates
from sellos.testing.users import create_test_users
from sellos.tests import phones

DEV = "P410C Developer"
RERA = "P51800410001"
RERA_TWO = "P51800410002"
SELLER_PHONE = phones.in_mobile(4101)


def sheet(*rows):
	return "\n".join(rows)


class ImportCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		pipeline.ensure_default_stages()
		ensure_default_sources()
		folder = Path(frappe.get_site_path("private", "files"))
		before = set(folder.glob("import-report-*"))
		self.addCleanup(lambda: [p.unlink() for p in set(folder.glob("import-report-*")) - before])
		self.addCleanup(frappe.db.rollback)  # each test starts with none of the records another made
		self.addCleanup(frappe.set_user, "Administrator")
		as_user("company_admin")

	def run_import(self, kind, text, dry=False):
		method = imp.preview_inventory_import if dry else imp.run_inventory_import
		return method(kind, text)

	def counts(self):
		return {
			d: frappe.db.count(d)
			for d in ("Developer", "Project", "Unit", "Property", "Listing", "Mandate", "File", "Version")
		}

	def load_project(self):
		self.run_import("Developer", sheet("Developer name,Contact person", f"{DEV},Sales"))
		self.run_import(
			"Project",
			sheet(
				"Project name,Developer,RERA number,City",
				f"P410C Heights,{DEV},{RERA},Pune",
			),
		)
		self.run_import(
			"Unit",
			sheet("Project,Unit number,Carpet area,Configuration", f"{RERA},1201,640,2 BHK"),
		)
		return frappe.db.get_value("Project", {"rera_number": RERA})


class TestImportTemplates(ImportCase):
	"""SOS-P4-10C: a template per record type."""

	def test_each_record_type_has_a_template_that_reads_back_as_its_own_headings(self):
		for kind in imp.RECORD_TYPES:
			template = imp.import_template(kind)
			rows = list(csv.reader(io.StringIO(template["csv"])))
			self.assertEqual(rows[0], [c[1] for c in imp.COLUMNS[kind]])
			self.assertEqual(len(rows), 2)
			self.assertTrue(template["file_name"].endswith("-template.csv"))
			self.assertTrue(template["help"])

	def test_the_project_template_names_its_matching_rule_and_an_unknown_type_is_refused(self):
		self.assertIn("RERA number", imp.import_template("Project")["help"])
		with self.assertRaises(frappe.ValidationError):
			imp.import_template("Lead")


class TestImportRecords(ImportCase):
	"""SOS-P4-10C: duplicates are updated, not doubled, and bad rows are reported."""

	def test_developers_and_projects_are_matched_on_name_and_rera_number(self):
		self.load_project()
		text = sheet(
			"Project name,Developer,RERA number,City,Locality",
			f"P410C Heights Renamed,{DEV},p518 00410001,Pune,Baner",
			f"P410C Second,{DEV},{RERA_TWO},Mumbai,",
			f"P410C Second Again,{DEV},{RERA_TWO},Mumbai,Andheri",
			"P410C Orphan,No Such Developer,P51800410003,Pune,",
			f"P410C Bad,{DEV},!!,Pune,",
		)
		report = self.run_import("Project", text)
		self.assertEqual(
			report["counts"],
			{"rows": 5, "created": 1, "updated": 1, "unchanged": 0, "merged": 1, "failed": 2},
		)
		self.assertEqual(frappe.db.count("Project", {"rera_number": RERA}), 1)
		self.assertEqual(frappe.db.count("Project", {"rera_number": RERA_TWO}), 1)
		first = frappe.get_doc("Project", {"rera_number": RERA})
		self.assertEqual((first.project_name, first.locality), ("P410C Heights Renamed", "Baner"))
		second = frappe.get_doc("Project", {"rera_number": RERA_TWO})
		self.assertEqual((second.project_name, second.locality), ("P410C Second Again", "Andheri"))
		reasons = {r["row"]: r["reason"] for r in report["failed"]}
		self.assertEqual(set(reasons), {5, 6})
		self.assertIn("No Such Developer", reasons[5])
		self.assertIn("RERA", reasons[6])

	def test_units_are_matched_on_project_and_unit_number_and_status_is_not_imported(self):
		project = self.load_project()
		unit = frappe.db.get_value("Unit", {"project": project, "unit_number": "1201"})
		text = sheet(
			"Project,Unit number,Carpet area,Floor,Configuration",
			f"{RERA},1201,655,12,3 BHK",
			"P410C Heights,1202,700,12,2 BHK",
			f"{RERA},1203,not a number,12,2 BHK",
			f"{RERA},1204,500,12,9 BHK",
			"No Such Project,1205,500,12,2 BHK",
			",1206,500,12,2 BHK",
		)
		report = self.run_import("Unit", text)
		self.assertEqual(
			report["counts"],
			{"rows": 6, "created": 1, "updated": 1, "unchanged": 0, "merged": 0, "failed": 4},
		)
		self.assertEqual(frappe.db.count("Unit", {"project": project, "unit_number": "1201"}), 1)
		doc = frappe.get_doc("Unit", unit)
		self.assertEqual(
			(doc.carpet_area, doc.configuration, doc.floor, doc.status), (655, "3 BHK", 12, "Available")
		)
		self.assertEqual(frappe.db.count("Unit", {"project": project}), 2)
		reasons = [r["reason"] for r in report["failed"]]
		self.assertTrue(any("Carpet area must be a number" in r for r in reasons))
		self.assertTrue(any("Configuration must be one of" in r for r in reasons))
		self.assertTrue(any("There is no project" in r for r in reasons))
		self.assertTrue(any("Project is empty" in r for r in reasons))

	def test_properties_are_matched_on_rera_number_or_title_and_city(self):
		text = sheet(
			"Title,Property type,Carpet area,City,RERA number",
			"P410C Flat,Apartment,700,Pune,",
			"P410C Flat,Apartment,720,Pune,",
			"P410C Flat,Apartment,700,Thane,",
			"P410C Plot,Plot,900,Pune,P51800410009",
			"P410C Plot Again,Plot,900,Pune,P51800410009",
			"P410C Bad Type,Castle,900,Pune,",
		)
		report = self.run_import("Property", text)
		self.assertEqual(
			report["counts"],
			{"rows": 6, "created": 3, "updated": 0, "unchanged": 0, "merged": 2, "failed": 1},
		)
		self.assertEqual(frappe.db.count("Property", {"title": "P410C Flat"}), 2)
		self.assertEqual(
			frappe.db.get_value("Property", {"title": "P410C Flat", "city": "Pune"}, "carpet_area"), 720
		)
		self.assertEqual(frappe.db.count("Property", {"rera_number": "P51800410009"}), 1)

	def test_listings_are_matched_on_what_they_offer_and_come_in_as_drafts(self):
		project = self.load_project()
		unit = frappe.db.get_value("Unit", {"project": project, "unit_number": "1201"})
		self.run_import(
			"Property", sheet("Title,Property type,Carpet area,City", "P410C Resale,Apartment,700,Pune")
		)
		text = sheet(
			"Title,Listing type,Project,Unit number,Property,Asking price,Description",
			f"P410C Primary,Primary,{RERA},1201,,9500000,A bright 2 BHK.",
			f"P410C Primary Better,Primary,{RERA},1201,,9600000,",
			"P410C Resale,Direct,,,P410C Resale,5000000,Near the station.",
			f"P410C Both,Direct,{RERA},1201,P410C Resale,5000000,",
			"P410C Neither,Direct,,,,5000000,",
			f"P410C Gone,Primary,{RERA},9999,,5000000,",
		)
		report = self.run_import("Listing", text)
		self.assertEqual(
			report["counts"],
			{"rows": 6, "created": 2, "updated": 0, "unchanged": 0, "merged": 1, "failed": 3},
		)
		listing = frappe.get_doc("Listing", {"unit": unit})
		self.assertEqual(
			(listing.title, listing.asking_price, listing.published), ("P410C Primary Better", 9600000, 0)
		)
		self.assertEqual(frappe.db.count("Listing", {"unit": unit}), 1)
		self.assertEqual(frappe.db.count("Listing", {"title": "P410C Resale"}), 1)
		self.assertFalse(frappe.db.exists("Listing", {"published": 1, "title": ["like", "P410C %"]}))

	def test_a_mandate_comes_in_unsigned_and_its_dossier_stays_hidden(self):
		as_user("company_admin")
		client = crm.save_client(
			values={"client_name": "P410C Seller", "client_type": "Seller", "phone": SELLER_PHONE}
		)
		lead = crm.save_lead(values={"client": client["name"], "source": "Website", "pipeline": "Seller"})[
			"lead"
		]["name"]
		text = sheet(
			"Seller phone,Mandate type,Start date,Term months,Fee percent",
			f"{SELLER_PHONE},Exclusive,2026-12-01,6,1.5",
			f"{SELLER_PHONE},Exclusive,2026-12-01,12,2",
			f"{phones.in_mobile(4102)},Open,2026-12-01,6,1.5",
			f"{SELLER_PHONE},Open,2026-12-01,0,1.5",
			f"{SELLER_PHONE},Open,2026-12-01,6,150",
		)
		report = self.run_import("Mandate", text)
		self.assertEqual(
			report["counts"],
			{"rows": 5, "created": 1, "updated": 0, "unchanged": 0, "merged": 1, "failed": 3},
		)
		self.assertEqual(frappe.db.count("Mandate", {"lead": lead}), 1)
		doc = frappe.get_doc("Mandate", {"lead": lead})
		self.assertEqual((doc.status, doc.term_months, doc.fee_percent), ("Draft", 12, 2))
		self.assertFalse(doc.signed_document)
		with self.assertRaises(frappe.PermissionError):
			mandates.open_dossier(doc.name)
		row = next(m for m in mandates.mandate_overview()["mandates"] if m["name"] == doc.name)
		self.assertEqual((row["dossier_released"], row["dossier_count"]), (0, None))
		self.assertFalse(any(SELLER_PHONE in r["reason"] for r in report["failed"]))

	def test_a_signed_mandate_keeps_its_terms_when_a_file_changes_them(self):
		as_user("company_admin")
		client = crm.save_client(
			values={"client_name": "P410C Signed", "client_type": "Seller", "phone": phones.in_mobile(4103)}
		)
		lead = crm.save_lead(values={"client": client["name"], "source": "Website", "pipeline": "Seller"})[
			"lead"
		]["name"]
		frappe.get_doc(
			{
				"doctype": "Mandate",
				"lead": lead,
				"mandate_type": "Open",
				"start_date": "2026-12-01",
				"term_months": 6,
				"fee_percent": 1,
				"status": "Signed",
				"signed_document": "/private/files/p410c.pdf",
			}
		).insert()
		sample = f"{phones.in_mobile(4103)},Open,2026-12-01,12,1"
		report = self.run_import(
			"Mandate", sheet("Seller phone,Mandate type,Start date,Term months,Fee percent", sample)
		)
		self.assertEqual(report["counts"]["failed"], 1)
		self.assertIn("keeps its terms", report["failed"][0]["reason"])
		self.assertEqual(frappe.db.get_value("Mandate", {"lead": lead}, "term_months"), 6)


class TestImportDryRunAndRerun(ImportCase):
	"""SOS-P4-10C: a dry run writes nothing, a second run changes nothing, a run writes a report."""

	TEXT = sheet(
		"Project name,Developer,RERA number,City",
		f"P410C Dry,{DEV},{RERA_TWO},Pune",
		f"P410C Dry Twin,{DEV},{RERA_TWO},Pune",
		"P410C Dry Bad,No Such Developer,P51800410004,Pune",
	)

	def test_a_dry_run_shows_the_counts_and_the_failures_and_writes_nothing(self):
		self.run_import("Developer", sheet("Developer name", DEV))
		before = self.counts()
		report = self.run_import("Project", self.TEXT, dry=True)
		self.assertEqual(report["dry_run"], 1)
		self.assertEqual(
			report["counts"],
			{"rows": 3, "created": 1, "updated": 0, "unchanged": 0, "merged": 1, "failed": 1},
		)
		self.assertEqual([r["row"] for r in report["failed"]], [4])
		self.assertIn("No Such Developer", report["failed"][0]["reason"])
		self.assertEqual(report["report_file"], "")
		self.assertEqual(self.counts(), before)
		self.assertFalse(frappe.db.exists("Project", {"rera_number": RERA_TWO}))

	def test_the_same_file_run_again_changes_nothing(self):
		self.run_import("Developer", sheet("Developer name", DEV))
		first = self.run_import("Project", self.TEXT)
		self.assertEqual(
			first["counts"], {"rows": 3, "created": 1, "updated": 0, "unchanged": 0, "merged": 1, "failed": 1}
		)
		project = frappe.db.get_value(
			"Project", {"rera_number": RERA_TWO}, ["name", "modified"], as_dict=True
		)
		before = self.counts()
		second = self.run_import("Project", self.TEXT)
		self.assertEqual(
			second["counts"],
			{"rows": 3, "created": 0, "updated": 0, "unchanged": 1, "merged": 1, "failed": 1},
		)
		again = frappe.db.get_value(
			"Project", {"rera_number": RERA_TWO}, ["name", "modified", "project_name"], as_dict=True
		)
		self.assertEqual((again.name, again.modified), (project.name, project.modified))
		self.assertEqual(again.project_name, "P410C Dry Twin")
		for doctype in ("Developer", "Project", "Unit", "Property", "Listing", "Mandate", "Version"):
			self.assertEqual(frappe.db.count(doctype), before[doctype], doctype)

	def test_a_clean_file_run_twice_reports_every_row_unchanged_the_second_time(self):
		text = sheet(
			"Developer name,Contact person",
			f"{DEV},Sales",
			"P410C Developer Two,Desk",
		)
		first = self.run_import("Developer", text)
		self.assertEqual(
			first["counts"], {"rows": 2, "created": 2, "updated": 0, "unchanged": 0, "merged": 0, "failed": 0}
		)
		modified = frappe.db.get_value("Developer", DEV, "modified")
		versions = frappe.db.count("Version", {"ref_doctype": "Developer"})
		second = self.run_import("Developer", text)
		self.assertEqual(
			second["counts"],
			{"rows": 2, "created": 0, "updated": 0, "unchanged": 2, "merged": 0, "failed": 0},
		)
		self.assertEqual(frappe.db.get_value("Developer", DEV, "modified"), modified)
		self.assertEqual(frappe.db.count("Version", {"ref_doctype": "Developer"}), versions)
		self.assertEqual(frappe.db.count("Developer", {"developer_name": ["like", "P410C %"]}), 2)

	def test_a_run_writes_a_private_reconciliation_report(self):
		report = self.run_import("Developer", sheet("Developer name", DEV, DEV, ",", "P410C Developer Three"))
		self.assertTrue(report["report_file"].startswith("/private/files/import-report-developers-"))
		file = frappe.get_doc("File", {"file_url": report["report_file"]})
		self.assertEqual(file.is_private, 1)
		lines = list(csv.reader(io.StringIO(frappe.utils.cstr(file.get_content()))))
		self.assertEqual(lines[0], ["Import of", "developers"])
		counts = {line[0]: int(line[1]) for line in lines[1:7]}
		self.assertEqual(
			counts, {"Rows": 4, "Created": 2, "Updated": 0, "Unchanged": 0, "Merged": 1, "Failed": 1}
		)
		self.assertIn(["Row", "Outcome", "Reason"], lines)
		self.assertEqual(sum(1 for line in lines if len(line) == 3 and line[1] in imp.OUTCOMES), 4)

	def test_a_file_without_a_required_column_or_rows_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.run_import("Project", sheet("Project name,City", "X,Pune"))
		with self.assertRaises(frappe.ValidationError):
			self.run_import("Developer", "Developer name")


class TestImportPermissions(ImportCase):
	"""SOS-P4-10C: only a Company Admin imports."""

	def test_no_other_role_downloads_a_template_or_imports(self):
		for role in ("agent", "channel_partner", "client", "platform_admin", "basic"):
			as_user(role)
			for call in (
				lambda: frappe.call(imp.import_template, record_type="Developer"),
				lambda: frappe.call(imp.preview_inventory_import, record_type="Developer", csv_text="a\nb"),
				lambda: frappe.call(imp.run_inventory_import, record_type="Developer", csv_text="a\nb"),
			):
				with self.assertRaises(frappe.PermissionError, msg=role):
					call()
		self.assertFalse(frappe.db.exists("Developer", {"developer_name": "b"}))


class TestImportRegressionSeed(ImportCase):
	"""SOS-P4-10C: the regression data brought in by import, made twice, is there once."""

	def test_the_imported_regression_records_are_there_once_after_two_runs(self):
		from sellos.tests import ui_fixtures

		admin = ui_fixtures.TEST_USERS["company_admin"]["email"]
		for _run in range(2):
			ui_fixtures._seed_inventory_import(admin)
		self.assertEqual(frappe.db.count("Developer", {"developer_name": "Regression Imported Developer"}), 1)
		project = frappe.get_doc("Project", {"rera_number": "P51800099101"})
		self.assertEqual((project.project_name, project.city), ("Regression Imported Towers", "Thane"))
		self.assertEqual(frappe.db.count("Unit", {"project": project.name, "unit_number": "101"}), 1)
		self.assertEqual(frappe.db.get_value("Unit", {"project": project.name}, "carpet_area"), 610)
