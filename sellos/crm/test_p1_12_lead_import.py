"""SOS-P1-12: import the bought lead lists. A sample file with duplicates inside it, duplicates of clients
already in SellOS and a do not call column: the statuses, the warnings, the merges, and that the import
sets nothing that stops contact."""

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import ensure_roles
from sellos.crm import api, consent, lead_import, pipeline
from sellos.crm.lead_sources import BOUGHT_LIST, ensure_default_sources
from sellos.crm.test_crm import as_user, email
from sellos.testing.users import create_test_users
from sellos.tests import phones

HEADER = "Full Name,Mobile,Email ID,City,DND Status,Remarks"
ONE, TWO, THREE, FOUR, FIVE = (phones.in_mobile(1200 + n) for n in range(5))
OVERSEAS = phones.au_mobile(1210)


def spaced(number):
	"""The same number as a list might write it: country code, then two groups of digits."""
	return f"{number[:3]} {number[3:8]} {number[8:]}"


def csv_text(*lines):
	return "\n".join((HEADER, *lines))


def lead_of(client_name):
	client = frappe.db.get_value("Client", {"client_name": client_name}, "name")
	return frappe.get_all("Lead", filters={"client": client}, pluck="name")


class TestLeadImport(IntegrationTestCase):
	"""SOS-P1-12: the bought list import."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		pipeline.ensure_default_stages()
		ensure_default_sources()
		as_user("company_admin")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def run_import(self, *lines, list_name="P112 list"):
		return api.import_bought_list(csv_text(*lines), list_name=list_name)

	def status(self, name):
		return frappe.db.get_value("Lead", name, "consent_status")

	def test_every_lead_is_unknown_from_the_bought_list_and_shows_the_warning(self):
		result = self.run_import(
			f"P112 Alpha,{ONE},p112_alpha@example.com,Pune,,wants 2 BHK",
			f"P112 Beta,{spaced(TWO)},,Thane,,",
		)
		self.assertEqual(result["counts"]["new_leads"], 2)
		self.assertEqual(result["source"], BOUGHT_LIST)
		for name in ("P112 Alpha", "P112 Beta"):
			(lead,) = lead_of(name)
			doc = frappe.get_doc("Lead", lead)
			self.assertEqual(doc.source, BOUGHT_LIST)
			self.assertEqual(doc.campaign, "P112 list")
			self.assertEqual(self.status(lead), consent.UNKNOWN)
			view = consent.consent_view(lead)
			self.assertEqual((view["status"], view["warning"]), (consent.UNKNOWN, "amber"))
			self.assertEqual(frappe.db.count("Consent Record", {"lead": lead}), 0)
		self.assertEqual(frappe.get_doc("Lead", lead_of("P112 Alpha")[0]).notes, "wants 2 BHK")
		client = frappe.get_doc("Client", frappe.db.get_value("Client", {"client_name": "P112 Beta"}))
		self.assertEqual(client.phone, TWO)

	def test_a_known_do_not_call_result_gives_registered_dnd_and_the_warning(self):
		self.run_import(
			f"P112 Listed,{ONE},,,Yes,",
			f"P112 Clear,{TWO},,,No,",
			f"P112 Silent,{THREE},,,,",
			f"P112 Odd,{FOUR},,,maybe later,",
		)
		listed, clear, silent, odd = (
			lead_of(n)[0] for n in ("P112 Listed", "P112 Clear", "P112 Silent", "P112 Odd")
		)
		self.assertEqual(self.status(listed), consent.REGISTERED_DND)
		self.assertEqual(consent.consent_view(listed)["warning"], "amber")
		self.assertEqual(frappe.db.get_value("Lead", listed, "dnd_registered"), 1)
		self.assertIsNotNone(frappe.db.get_value("Lead", listed, "dnd_checked_on"))
		# A "No" is a result too: recorded, and the status stays Unknown.
		self.assertEqual(self.status(clear), consent.UNKNOWN)
		self.assertEqual(frappe.db.get_value("Lead", clear, "dnd_registered"), 0)
		self.assertIsNotNone(frappe.db.get_value("Lead", clear, "dnd_checked_on"))
		# No result, or a value that is not a known result, is not a result.
		for lead in (silent, odd):
			self.assertEqual(self.status(lead), consent.UNKNOWN)
			self.assertIsNone(frappe.db.get_value("Lead", lead, "dnd_checked_on"))

	def test_duplicates_inside_the_file_are_merged_into_one_lead(self):
		result = self.run_import(
			f"P112 Twin,{ONE},,,,",
			f"P112 Twin Again,{spaced(ONE)},p112_twin@example.com,Pune,,second row",
			f"P112 Other,{TWO},P112_TWIN@example.com,,Yes,",
		)
		self.assertEqual(result["counts"]["new_leads"], 1)
		self.assertEqual(result["counts"]["merged_in_file"], 2)
		self.assertEqual(frappe.db.count("Client", {"client_name": ["like", "P112 %"]}), 1)
		(lead,) = lead_of("P112 Twin")
		client = frappe.get_doc("Client", frappe.db.get_value("Lead", lead, "client"))
		self.assertEqual((client.email, client.city), ("p112_twin@example.com", "Pune"))
		# The later row's registered result is kept.
		self.assertEqual(self.status(lead), consent.REGISTERED_DND)

	def test_a_row_that_matches_a_client_already_there_is_merged_into_it(self):
		saved = api.save_client(values={"client_name": "P112 Known", "phone": ONE})
		first = api.save_lead(values={"client": saved["name"], "source": "Website"})["lead"]["name"]
		result = self.run_import(f"P112 Known Renamed,{spaced(ONE)},p112_known@example.com,Nashik,Yes,")
		self.assertEqual(result["counts"]["new_leads"], 0)
		self.assertEqual(result["merged"], [first])
		self.assertEqual(frappe.db.count("Client", {"client_name": ["like", "P112 Known%"]}), 1)
		self.assertEqual(frappe.db.count("Lead", {"client": saved["name"]}), 1)
		client = frappe.get_doc("Client", saved["name"])
		self.assertEqual(client.client_name, "P112 Known")  # what it had is kept
		self.assertEqual((client.email, client.city), ("p112_known@example.com", "Nashik"))
		self.assertEqual(
			frappe.db.get_value("Lead", first, "source"), "Website"
		)  # not changed to Bought list
		self.assertEqual(self.status(first), consent.REGISTERED_DND)
		notes = frappe.get_all(
			"Comment", filters={"reference_name": first, "comment_type": "Info"}, pluck="content"
		)
		self.assertTrue(any("Appeared again" in n for n in notes))

	def test_a_client_with_no_lead_gets_one_and_an_archived_client_is_not_merged_into(self):
		saved = api.save_client(values={"client_name": "P112 Leadless", "phone": TWO})
		retired = api.save_client(values={"client_name": "P112 Retired", "phone": THREE})
		frappe.db.set_value("Client", retired["name"], "archived", 1)
		result = self.run_import(f"P112 Leadless,{TWO},,,,", f"P112 Retired New,{THREE},,,,")
		self.assertEqual(result["counts"]["new_leads"], 2)
		self.assertEqual(frappe.db.count("Lead", {"client": saved["name"]}), 1)
		self.assertEqual(frappe.db.count("Client", {"phone_key": THREE}), 2)

	def test_importing_the_same_file_twice_makes_no_second_lead(self):
		lines = (f"P112 Again,{ONE},,,,",)
		self.run_import(*lines)
		second = self.run_import(*lines)
		self.assertEqual((second["counts"]["new_leads"], len(second["merged"])), (0, 1))
		self.assertEqual(len(lead_of("P112 Again")), 1)

	def test_a_not_registered_result_never_overwrites_a_known_registered_one(self):
		self.run_import(f"P112 Keep,{ONE},,,Yes,")
		self.run_import(f"P112 Keep,{ONE},,,No,")
		(lead,) = lead_of("P112 Keep")
		self.assertEqual(self.status(lead), consent.REGISTERED_DND)

	def test_a_row_with_no_name_or_nothing_to_reach_it_by_is_skipped_with_its_reason(self):
		result = self.run_import(
			f",{ONE},,,,",
			"P112 Nobody,,,,,",
			"P112 Bad,12,not an email,,,",
			f"P112 Fine,{TWO},,,,",
		)
		self.assertEqual(result["counts"]["new_leads"], 1)
		self.assertEqual(result["counts"]["skipped"], 3)
		self.assertEqual([s["row"] for s in result["skipped"]], [2, 3, 4])
		self.assertIn("No name", result["skipped"][0]["reason"])
		self.assertIn("No usable phone number or email", result["skipped"][1]["reason"])

	def test_a_foreign_number_goes_to_the_overseas_phone(self):
		self.run_import(f"P112 Abroad,{OVERSEAS},,,,")
		client = frappe.get_doc("Client", frappe.db.get_value("Client", {"client_name": "P112 Abroad"}))
		self.assertEqual((client.phone, client.overseas_phone_key), (None, OVERSEAS))

	def test_the_import_sets_nothing_that_stops_contact(self):
		self.run_import(f"P112 Free,{ONE},,,Yes,", f"P112 Plain,{TWO},,,,")
		for name in ("P112 Free", "P112 Plain"):
			doc = frappe.get_doc("Lead", lead_of(name)[0])
			self.assertEqual(doc.archived, 0)
			self.assertIsNone(doc.opted_out_on)
			self.assertFalse(doc.opted_out_source)
			self.assertFalse(doc.lost_reason)
			self.assertEqual(doc.stage, pipeline.first_stage())
			self.assertNotIn(doc.consent_status, (consent.OPTED_OUT,))
			self.assertNotIn(frappe.db.get_value("Pipeline Stage", doc.stage, "stage_type"), ("Lost", "Won"))
		# The status is a warning only: Registered DND is the most the import ever records.
		self.assertEqual(
			frappe.get_doc("Lead", lead_of("P112 Free")[0]).consent_status, consent.REGISTERED_DND
		)

	def test_the_preview_writes_nothing_and_masks_the_numbers(self):
		saved = api.save_client(values={"client_name": "P112 Seen", "phone": ONE})
		api.save_lead(values={"client": saved["name"], "source": "Website"})
		clients_before, leads_before = frappe.db.count("Client"), frappe.db.count("Lead")
		preview = api.preview_lead_import(
			csv_text(f"P112 Seen,{ONE},,,,", f"P112 Fresh,{TWO},,,Yes,", f"P112 Fresh Two,{TWO},,,,", ",,,,,")
		)
		self.assertEqual((frappe.db.count("Client"), frappe.db.count("Lead")), (clients_before, leads_before))
		counts = preview["counts"]
		self.assertEqual(
			(counts["rows"], counts["new_leads"], counts["merged_with_existing"], counts["merged_in_file"]),
			(4, 1, 1, 1),
		)
		self.assertEqual((counts["registered_dnd"], counts["skipped"]), (1, 1))
		self.assertEqual(preview["mapping"]["do_not_call"], "DND Status")
		shown = frappe.as_json(preview["sample"])
		for number in (ONE, TWO, ONE[-10:], TWO[-10:]):
			self.assertNotIn(number, shown)

	def test_a_mapping_can_be_chosen_and_a_bad_one_is_refused(self):
		text = "Who,Number\nP112 Mapped," + ONE
		result = api.import_bought_list(text, mapping={"name": "Who", "phone": "Number"})
		self.assertEqual(result["counts"]["new_leads"], 1)
		for mapping, message in (
			({"name": "Who"}, "phone"),
			({"phone": "Number"}, "name"),
			({"name": "Who", "phone": "Missing"}, "no column"),
			({"name": "Who", "phone": "Number", "stage": "Number"}, "not a field"),
		):
			with self.assertRaises(frappe.ValidationError) as caught:
				api.import_bought_list(text, mapping=mapping)
			self.assertIn(message, str(caught.exception))

	def test_semicolon_and_tab_files_and_a_byte_order_mark_are_read(self):
		for delimiter in (";", "\t"):
			headers, rows = lead_import.read_csv(f"﻿Name{delimiter}Phone\nP112 Sep{delimiter}{ONE}")
			self.assertEqual(headers, ["Name", "Phone"])
			self.assertEqual(rows[0]["Phone"], ONE)
		with self.assertRaises(frappe.ValidationError):
			lead_import.read_csv("Name,Phone")

	def test_only_a_company_admin_may_import(self):
		for key in ("agent", "sales_manager", "channel_partner", "client", "platform_admin"):
			as_user(key)
			for method in (api.import_bought_list, api.preview_lead_import):
				with self.assertRaises(frappe.PermissionError, msg=f"{key} {method.__name__}"):
					method(csv_text(f"P112 Denied,{ONE},,,,"))
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Client", {"client_name": "P112 Denied"}))

	def test_the_leads_are_listed_with_the_bought_list_source_and_their_warning(self):
		self.run_import(f"P112 Listed Row,{ONE},,,Yes,")
		rows = api.list_leads(source=BOUGHT_LIST, search="P112 Listed Row")
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["consent_status"], consent.REGISTERED_DND)
		as_user("agent")
		self.assertEqual(api.list_leads(search="P112 Listed Row"), [])
		self.assertEqual(email("agent"), frappe.session.user)

	def test_the_regression_seed_makes_the_bought_list_and_reads_back(self):
		from sellos.tests import ui_fixtures

		ui_fixtures._seed_bought_list(email("company_admin"))
		state = ui_fixtures.import_state(["Regression Bought One", "Regression Bought Two"])
		one, two = state["Regression Bought One"], state["Regression Bought Two"]
		self.assertEqual((one["clients"], two["clients"]), (1, 1))
		self.assertEqual(
			(one["leads"][0]["consent_status"], two["leads"][0]["consent_status"]),
			(consent.UNKNOWN, consent.REGISTERED_DND),
		)
		self.assertEqual((len(one["leads"]), len(two["leads"])), (1, 1))
		self.assertEqual({one["leads"][0]["source"], two["leads"][0]["source"]}, {BOUGHT_LIST})
		self.assertFalse(one["leads"][0]["blocked"] or two["leads"][0]["blocked"])
		self.assertEqual(frappe.db.count("Client", {"client_name": ["like", "Regression Bought Two%"]}), 1)
		ui_fixtures._seed_bought_list(email("company_admin"))  # safe to run again
		self.assertEqual(
			len(ui_fixtures.import_state(["Regression Bought Two"])["Regression Bought Two"]["leads"]), 1
		)
