"""SOS-P4-05: a Mandate (Exclusive or Open, with a term and a fee), its signed document, the Private Sale
Dossier that is released only when it is signed, the log of every view, and the Listed stage rule."""

import base64
from pathlib import Path

import frappe

from sellos.crm import api, pipeline
from sellos.crm.test_crm import as_user, email
from sellos.crm.test_p4_04_seller_pipeline import SellerCase
from sellos.inventory import mandates
from sellos.tests.files import tiny_pdf

PDF = tiny_pdf()
PNG = b"\x89PNG\r\n\x1a\n" + b"p405 body"
TERMS = {"mandate_type": "Exclusive", "term_months": 6, "fee_percent": 1.5}
NAMES = ("p405_signed.pdf", "p405_note.png", "p405_dossier.pdf")


def b64(content):
	return base64.b64encode(content).decode()


def can_open(file, key) -> bool:
	"""True when the user may read the file, as a request by that user would be judged."""
	as_user(key)
	return frappe.has_permission("File", "read", doc=file)


def private_files():
	folder = Path(frappe.get_site_path("private", "files"))
	return set(folder.glob("p405_*")) | set(folder.glob("regression_mandate_*"))


class MandateCase(SellerCase):
	def setUp(self):
		super().setUp()
		before = private_files()
		self.addCleanup(lambda: [p.unlink() for p in private_files() - before])

	def agent_seller(self, label="Owner"):
		"""A seller lead the test agent owns."""
		as_user("company_admin")
		client = api.save_client(values={"client_name": f"P405 {label}", "client_type": "Seller"})
		return api.save_lead(
			values={
				"client": client["name"],
				"source": "Website",
				"pipeline": "Seller",
				"assigned_to": email("agent"),
			}
		)["lead"]["name"]

	def mandate(self, lead, who="agent", **terms):
		as_user(who)
		return mandates.save_mandate({"lead": lead, **TERMS, **terms})["name"]

	def sign(self, name, who="agent", filename=NAMES[0], content=PDF):
		as_user(who)
		return mandates.sign_mandate(name, filename, b64(content))

	def row(self, name):
		return next(m for m in mandates.mandate_overview()["mandates"] if m["name"] == name)


class TestMandateTerms(MandateCase):
	"""SOS-P4-05: a mandate carries a type, a term and a fee, and starts as a Draft."""

	def test_a_mandate_carries_its_type_term_and_fee_and_starts_as_a_draft(self):
		lead = self.agent_seller()
		name = self.mandate(lead, mandate_type="Open", term_months=12, fee_percent=2)
		doc = frappe.get_doc("Mandate", name)
		self.assertEqual((doc.mandate_type, doc.term_months, doc.fee_percent), ("Open", 12, 2))
		self.assertEqual((doc.status, doc.lead, doc.signed_document), ("Draft", lead, None))
		self.assertEqual(str(doc.ends_on), str(frappe.utils.add_months(doc.start_date, 12)))
		self.assertEqual(self.row(name)["mandate_type"], "Open")

	def test_a_bad_type_term_or_fee_is_refused(self):
		lead = self.agent_seller()
		for bad in (
			{"mandate_type": "Sole"},
			{"term_months": 0},
			{"term_months": 121},
			{"fee_percent": 0},
			{"fee_percent": 101},
		):
			with self.assertRaises(frappe.ValidationError, msg=str(bad)):
				self.mandate(lead, **bad)
		self.assertEqual(frappe.db.count("Mandate", {"lead": lead}), 0)

	def test_a_mandate_is_for_a_seller_not_a_buyer(self):
		buyer = self.buyer()
		with self.assertRaises(frappe.ValidationError):
			self.mandate(buyer, who="company_admin")

	def test_a_signed_mandate_keeps_its_terms_and_a_draft_can_be_corrected(self):
		name = self.mandate(self.agent_seller())
		mandates.save_mandate({"fee_percent": 2.5}, name)
		self.assertEqual(frappe.db.get_value("Mandate", name, "fee_percent"), 2.5)
		self.sign(name)
		with self.assertRaises(frappe.ValidationError):
			mandates.save_mandate({"fee_percent": 3}, name)
		self.assertEqual(frappe.db.get_value("Mandate", name, "fee_percent"), 2.5)

	def test_nothing_is_deleted(self):
		name = self.mandate(self.agent_seller())
		as_user("company_admin")
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Mandate", name)
		mandates.set_mandate_archived(name)
		self.assertEqual(frappe.db.get_value("Mandate", name, "archived"), 1)
		self.assertNotIn(name, [m["name"] for m in mandates.mandate_overview()["mandates"]])


class TestTheSignedDocument(MandateCase):
	"""SOS-P4-05: the signed document is required, and a private file."""

	def test_the_mandate_is_not_signed_without_a_valid_signed_document(self):
		name = self.mandate(self.agent_seller())
		for filename, content in (
			("p405_signed.exe", PDF),
			("p405_signed.pdf", b"<html>not a pdf</html>"),
			("p405_signed.pdf", b""),
			("p405_signed.pdf", PDF + b"x" * mandates.FILE_LIMIT),
		):
			with self.assertRaises(frappe.ValidationError, msg=filename):
				self.sign(name, filename=filename, content=content)
		with self.assertRaises(frappe.ValidationError):
			mandates.sign_mandate(name, "p405_signed.pdf", "not base64 !!")
		self.assertEqual(frappe.db.get_value("Mandate", name, "status"), "Draft")

	def test_the_record_itself_refuses_signed_with_no_document(self):
		name = self.mandate(self.agent_seller())
		doc = frappe.get_doc("Mandate", name)
		doc.status = "Signed"
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		self.assertEqual(frappe.db.get_value("Mandate", name, "status"), "Draft")

	def test_signing_stores_a_private_file_and_records_who_and_when(self):
		name = self.mandate(self.agent_seller())
		self.sign(name)
		doc = frappe.get_doc("Mandate", name)
		self.assertEqual((doc.status, doc.signed_by), ("Signed", email("agent")))
		self.assertTrue(doc.signed_document.startswith("/private/files/"))
		self.assertTrue(doc.signed_on)
		file = frappe.get_doc("File", {"file_url": doc.signed_document})
		self.assertEqual(
			(file.is_private, file.attached_to_doctype, file.attached_to_name), (1, "Mandate", name)
		)
		with self.assertRaises(frappe.ValidationError):
			self.sign(name)  # a second signature changes nothing

	def test_the_signed_document_is_opened_by_who_may_read_the_mandate_only(self):
		name = self.mandate(self.agent_seller())
		self.sign(name)
		file = frappe.get_doc("File", {"file_url": frappe.db.get_value("Mandate", name, "signed_document")})
		self.assertTrue(can_open(file, "agent"))
		self.assertTrue(can_open(file, "company_admin"))
		for key in ("channel_partner", "client", "platform_admin", "sales_manager"):
			self.assertFalse(can_open(file, key), key)


class TestTheDossier(MandateCase):
	"""SOS-P4-05: the Private Sale Dossier is hidden until the mandate is signed."""

	def draft_with_items(self):
		name = self.mandate(self.agent_seller())
		mandates.add_dossier_note(name, "Owner's reserve", "Will not go below the reserve.")
		mandates.add_dossier_file(name, "Title deed", NAMES[2], b64(PDF))
		return name

	def test_try_to_open_the_dossier_without_a_signed_mandate_and_it_fails(self):
		name = self.draft_with_items()
		with self.assertRaises(frappe.PermissionError) as caught:
			mandates.open_dossier(name)
		self.assertIn("released only when the mandate is signed", str(caught.exception))
		as_user("company_admin")
		with self.assertRaises(frappe.PermissionError):
			mandates.open_dossier(name)  # a Company Admin too
		self.assertEqual(frappe.get_doc("Mandate", name).views, [])

	def test_nothing_of_the_dossier_shows_before_the_signature(self):
		name = self.draft_with_items()
		as_user("agent")
		row = self.row(name)
		self.assertEqual((row["dossier_released"], row["dossier_count"]), (0, None))
		self.assertNotIn("Reserve", str(mandates.mandate_overview()))
		# Read through the document API's field level rules, the dossier is not there for any role.
		doc = frappe.get_doc("Mandate", name)
		doc.apply_fieldlevel_read_permissions()
		self.assertFalse(doc.get("dossier") or doc.get("views"))

	def test_a_dossier_file_is_not_downloadable_until_the_mandate_is_signed(self):
		name = self.draft_with_items()
		url = frappe.get_doc("Mandate", name).dossier[1].file
		file = frappe.get_doc("File", {"file_url": url})
		self.assertEqual(file.is_private, 1)
		for key in ("agent", "company_admin"):
			self.assertFalse(can_open(file, key), key)
		self.sign(name)
		self.assertTrue(can_open(file, "agent"))
		self.assertFalse(can_open(file, "channel_partner"))

	def test_the_signed_mandate_releases_its_notes_and_files(self):
		name = self.draft_with_items()
		self.sign(name)
		as_user("agent")
		self.assertEqual(self.row(name)["dossier_count"], 2)
		opened = mandates.open_dossier(name)
		self.assertEqual(
			[(i["kind"], i["title"]) for i in opened["items"]],
			[("Note", "Owner's reserve"), ("File", "Title deed")],
		)
		self.assertEqual(opened["items"][0]["note"], "Will not go below the reserve.")
		self.assertTrue(opened["items"][1]["file"].startswith("/private/files/"))

	def test_a_dossier_file_must_be_a_pdf_png_or_jpg(self):
		name = self.mandate(self.agent_seller())
		for filename, content in ((NAMES[2], b"MZ not a pdf"), ("p405_dossier.exe", PDF)):
			with self.assertRaises(frappe.ValidationError):
				mandates.add_dossier_file(name, "Bad", filename, b64(content))
		mandates.add_dossier_file(name, "", NAMES[1], b64(PNG))
		self.assertEqual(frappe.get_doc("Mandate", name).dossier[0].title, "p405_note")
		with self.assertRaises(frappe.ValidationError):
			mandates.add_dossier_note(name, "Empty", "  ")

	def test_an_archived_mandate_no_longer_releases_its_dossier(self):
		name = self.draft_with_items()
		self.sign(name)
		as_user("company_admin")
		mandates.set_mandate_archived(name)
		with self.assertRaises(frappe.PermissionError):
			mandates.open_dossier(name)


class TestEachViewIsLogged(MandateCase):
	"""SOS-P4-05: each opening of the Dossier is logged with who and when, and the log only grows."""

	def test_each_view_is_logged_with_who_and_when(self):
		name = self.mandate(self.agent_seller())
		mandates.add_dossier_note(name, "Note", "Text")
		self.sign(name)
		as_user("agent")
		first = mandates.open_dossier(name)
		self.assertEqual(len(first["views"]), 1)
		as_user("company_admin")
		second = mandates.open_dossier(name)
		self.assertEqual(len(second["views"]), 2)
		doc = frappe.get_doc("Mandate", name)
		self.assertEqual([v.viewed_by for v in doc.views], [email("agent"), email("company_admin")])
		self.assertTrue(all(v.viewed_on for v in doc.views))
		self.assertEqual(
			second["views"][0]["viewed_by_name"],
			frappe.get_value("User", email("company_admin"), "full_name"),
		)

	def test_the_view_log_and_the_dossier_can_not_be_cut_back(self):
		name = self.mandate(self.agent_seller())
		mandates.add_dossier_note(name, "Note", "Text")
		self.sign(name)
		mandates.open_dossier(name)
		doc = frappe.get_doc("Mandate", name)
		doc.set("views", [])
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)
		doc = frappe.get_doc("Mandate", name)
		doc.set("dossier", [])
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)
		self.assertEqual(len(frappe.get_doc("Mandate", name).views), 1)
		self.assertEqual(len(frappe.get_doc("Mandate", name).dossier), 1)


class TestTheListedStageRule(MandateCase):
	"""SOS-P4-05: a seller cannot be moved to the Listed stage without a signed mandate."""

	def move(self, lead, stage, who="agent"):
		as_user(who)
		return api.move_lead_stage(lead, stage)

	def test_a_seller_cannot_reach_listed_without_a_signed_mandate(self):
		lead = self.agent_seller()
		with self.assertRaises(frappe.ValidationError) as caught:
			self.move(lead, "Seller Listed")
		self.assertIn("signed mandate", str(caught.exception))
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "Seller New owner enquiry")
		self.mandate(lead)  # a Draft is not enough
		with self.assertRaises(frappe.ValidationError):
			self.move(lead, "Seller Listed")
		for later in ("Seller Offers received", "Seller Sold"):
			with self.assertRaises(frappe.ValidationError, msg=later):
				self.move(lead, later)

	def test_a_seller_with_a_signed_mandate_reaches_listed(self):
		lead = self.agent_seller()
		self.sign(self.mandate(lead))
		self.assertTrue(self.move(lead, "Seller Listed")["moved"])
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "Seller Listed")
		self.assertTrue(self.move(lead, "Seller Offers received")["moved"])

	def test_an_archived_signed_mandate_does_not_count(self):
		lead = self.agent_seller()
		name = self.mandate(lead)
		self.sign(name)
		as_user("company_admin")
		mandates.set_mandate_archived(name)
		self.assertFalse(pipeline.has_signed_mandate(lead))
		with self.assertRaises(frappe.ValidationError):
			self.move(lead, "Seller Listed")
		as_user("company_admin")
		mandates.set_mandate_archived(name, 0)
		self.assertTrue(self.move(lead, "Seller Listed")["moved"])

	def test_the_other_seller_stages_need_no_mandate_and_it_is_the_leads_own_mandate_that_counts(self):
		lead, other = self.agent_seller("One"), self.agent_seller("Two")
		self.sign(self.mandate(other))
		self.assertTrue(self.move(lead, "Seller Nurture")["moved"])
		with self.assertRaises(frappe.ValidationError):
			self.move(lead, "Seller Listed")  # the other seller's mandate is not this one's


class TestWhoMayUseMandates(MandateCase):
	"""SOS-P4-05: a Company Admin and an Agent (on a lead they may write) hold the methods, nobody else."""

	def test_an_agent_sees_and_opens_only_the_mandates_of_leads_they_may_see(self):
		own = self.mandate(self.agent_seller())
		self.sign(own)
		as_user("company_admin")
		lead = self.seller("Admin's")  # assigned to the Company Admin, not to the agent
		theirs = self.mandate(lead, who="company_admin")
		self.sign(theirs, who="company_admin")
		as_user("agent")
		names = [m["name"] for m in mandates.mandate_overview()["mandates"]]
		self.assertEqual(names, [own])
		self.assertNotIn(lead, [s["value"] for s in mandates.mandate_overview()["sellers"]])
		for call in (
			lambda: mandates.open_dossier(theirs),
			lambda: mandates.sign_mandate(theirs, NAMES[0], b64(PDF)),
			lambda: mandates.add_dossier_note(theirs, "Note", "Text"),
			lambda: mandates.save_mandate({"lead": lead, **TERMS}),
		):
			with self.assertRaises(frappe.PermissionError):
				call()
		as_user("company_admin")
		self.assertEqual({m["name"] for m in mandates.mandate_overview()["mandates"]}, {own, theirs})

	def test_every_other_role_is_refused_every_method(self):
		name = self.mandate(self.agent_seller())
		calls = (
			lambda: mandates.mandate_overview(),
			lambda: mandates.save_mandate({"lead": "x", **TERMS}),
			lambda: mandates.sign_mandate(name, NAMES[0], b64(PDF)),
			lambda: mandates.add_dossier_note(name, "Note", "Text"),
			lambda: mandates.add_dossier_file(name, "File", NAMES[2], b64(PDF)),
			lambda: mandates.open_dossier(name),
			lambda: mandates.set_mandate_archived(name),
		)
		for key in ("sales_manager", "client", "channel_partner", "platform_admin", "basic"):
			as_user(key)
			for call in calls:
				with self.assertRaises(frappe.PermissionError, msg=key):
					call()

	def test_only_a_company_admin_archives(self):
		name = self.mandate(self.agent_seller())
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			mandates.set_mandate_archived(name)


class TestTheRegressionMandates(MandateCase):
	"""SOS-P4-05: the regression seed makes a Draft and a signed mandate through the API, and a second run
	changes nothing."""

	def test_the_seed_makes_a_draft_and_a_signed_mandate_and_a_second_run_changes_nothing(self):
		from sellos.testing.users import TEST_USERS
		from sellos.tests import ui_fixtures

		ui_fixtures._test_users()
		admin, agent = TEST_USERS["company_admin"]["email"], TEST_USERS["agent"]["email"]
		ui_fixtures._seed_sellers(admin, agent)
		ui_fixtures._seed_mandates(agent)
		ui_fixtures._seed_mandates(agent)
		seeded = {}
		for row in frappe.get_all(
			"Mandate", fields=["lead", "status", "mandate_type", "term_months", "fee_percent"]
		):
			title = frappe.db.get_value("Lead", row.lead, "lead_title") or ""
			if title.startswith("Regression Seller One"):
				seeded["One"] = row
			elif title.startswith("Regression Seller Two"):
				seeded["Two"] = row
		self.assertEqual(set(seeded), {"One", "Two"})
		self.assertEqual(frappe.db.count("Mandate"), 2, "a second run adds none")
		self.assertEqual((seeded["One"].status, seeded["One"].mandate_type), ("Draft", "Exclusive"))
		self.assertEqual((seeded["Two"].status, seeded["Two"].mandate_type), ("Signed", "Open"))
		doc = frappe.get_doc("Mandate", {"lead": seeded["Two"].lead})
		self.assertEqual(len(doc.dossier), 2)
		self.assertTrue(doc.signed_document.startswith("/private/files/"))
