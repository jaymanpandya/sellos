"""SOS-LOOP: the Company Profile (branding, contrast checks, logo) and the Private Sale Dossier as a branded PDF
(cover, summary, mandate and signing status, notes grouped by type with images, page numbers, versions)."""

import base64
import io
from pathlib import Path

import frappe
from PIL import Image
from pypdf import PdfReader

from sellos.crm import notes
from sellos.crm.test_crm import as_user
from sellos.crm.test_loop_notes import file_of
from sellos.inventory import branding, dossier_pdf, mandates
from sellos.inventory.test_p4_05_mandate import MandateCase, can_open, private_files
from sellos.tests import phones


def png_bytes(colour=(20, 90, 160), size=(60, 40)) -> bytes:
	out = io.BytesIO()
	Image.new("RGB", size, colour).save(out, "PNG")
	return out.getvalue()


def b64(content: bytes) -> str:
	return base64.b64encode(content).decode()


def text_of(pdf_bytes: bytes) -> str:
	return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf_bytes)).pages)


def images_in(pdf_bytes: bytes) -> int:
	return sum(len(page.images) for page in PdfReader(io.BytesIO(pdf_bytes)).pages)


class ProfileCase(MandateCase):
	"""Starts every test with an empty company profile, and puts it back."""

	FIELDS = (*branding.FIELDS, "logo")

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.before = {f: frappe.db.get_single_value("SellOS Settings", f) for f in self.FIELDS}
		for f in self.FIELDS:
			frappe.db.set_single_value("SellOS Settings", f, None)
		self.addCleanup(self.restore)
		self.logo_files = set(Path(frappe.get_site_path("public", "files")).glob("company-logo-*"))

	def restore(self):
		frappe.set_user("Administrator")
		for f, value in self.before.items():
			frappe.db.set_single_value("SellOS Settings", f, value)
		for path in (
			set(Path(frappe.get_site_path("public", "files")).glob("company-logo-*")) - self.logo_files
		):
			path.unlink()


class TestCompanyProfile(ProfileCase):
	def test_the_contrast_of_a_colour_against_white(self):
		self.assertEqual(branding.contrast_with_white("#000000"), 21.0)
		self.assertEqual(branding.contrast_with_white("#FFFFFF"), 1.0)
		self.assertAlmostEqual(branding.contrast_with_white("#767676"), 4.54, places=2)

	def test_a_readable_profile_is_saved_and_read_back(self):
		as_user("company_admin")
		saved = branding.save_company_profile(
			{
				"company_name": "Pandya Realtors",
				"brand_color": "#0B5D3B",
				"accent_color": "#B45309",
				"rera_number": "a51700012345",
				"address": "12 Law Garden Road",
				"city": "Ahmedabad",
				"contact_phone": phones.in_mobile(121),
				"contact_email": "office@example.com",
				"website": "https://pandya.example.com",
				"footer_text": "Pandya Realtors, RERA registered",
			}
		)
		self.assertEqual((saved["company_name"], saved["rera_number"]), ("Pandya Realtors", "A51700012345"))
		self.assertGreaterEqual(saved["primary_contrast"], 4.5)
		self.assertEqual(branding.get_company_profile()["footer_text"], "Pandya Realtors, RERA registered")
		self.assertEqual(branding.brand()["primary"], "#0B5D3B")

	def test_a_colour_that_is_too_pale_is_refused_with_its_ratio(self):
		as_user("company_admin")
		with self.assertRaisesRegex(frappe.ValidationError, "contrast"):
			branding.save_company_profile({"brand_color": "#9EC9B0"})
		with self.assertRaises(frappe.ValidationError):
			branding.save_company_profile({"accent_color": "#F5F5DC"})
		with self.assertRaises(frappe.ValidationError):
			branding.save_company_profile({"brand_color": "green"})
		self.assertFalse(frappe.db.get_single_value("SellOS Settings", "brand_color"))

	def test_bad_contact_details_are_refused(self):
		as_user("company_admin")
		for bad in (
			{"contact_email": "not an email"},
			{"contact_phone": "call me maybe"},
			{"website": "javascript:alert(1)"},
			{"rera_number": "!!"},
			{"footer_text": "x" * 201},
		):
			with self.assertRaises(frappe.ValidationError, msg=str(bad)):
				branding.save_company_profile(bad)

	def test_with_nothing_set_the_documents_use_the_default_look(self):
		brand = branding.brand()
		self.assertTrue(brand["is_default"])
		self.assertEqual(
			(brand["primary"], brand["accent"]), (branding.DEFAULT_PRIMARY, branding.DEFAULT_ACCENT)
		)

	def test_a_colour_set_before_the_check_existed_falls_back_when_too_pale(self):
		frappe.db.set_single_value("SellOS Settings", "brand_color", "#EEEEEE")
		self.assertEqual(branding.brand()["primary"], branding.DEFAULT_PRIMARY)

	def test_the_logo_is_a_small_real_png_or_jpg(self):
		as_user("company_admin")
		saved = branding.upload_company_logo("logo.png", b64(png_bytes()))
		self.assertTrue(saved["logo"].startswith("/files/company-logo-"))
		for name, content in (
			("logo.png", b"not an image"),
			("logo.png", b""),
			("logo.gif", self.gif()),
			("big.png", png_bytes(size=(2100, 10))),
		):
			with self.assertRaises(frappe.ValidationError, msg=name):
				branding.upload_company_logo(name, b64(content))

	@staticmethod
	def gif() -> bytes:
		out = io.BytesIO()
		Image.new("RGB", (4, 4)).save(out, "GIF")
		return out.getvalue()

	def test_only_a_company_admin_holds_the_profile_methods(self):
		for who in ("agent", "sales_manager", "channel_partner", "client", "platform_admin"):
			as_user(who)
			with self.assertRaises(frappe.PermissionError, msg=who):
				branding.get_company_profile()
			with self.assertRaises(frappe.PermissionError, msg=who):
				branding.save_company_profile({"footer_text": "x"})


class TestDossierPdf(ProfileCase):
	def released_mandate(self):
		lead = self.agent_seller("Dossier Owner")
		name = self.mandate(lead)
		self.sign(name)
		return lead, name

	def brand_it(self):
		as_user("company_admin")
		branding.save_company_profile(
			{
				"company_name": "Pandya Realtors",
				"brand_color": "#0B5D3B",
				"accent_color": "#B45309",
				"rera_number": "A51700012345",
				"footer_text": "Pandya Realtors | Confidential",
			}
		)
		branding.upload_company_logo("logo.png", b64(png_bytes((200, 30, 30), (120, 40))))

	def add_notes(self, lead, mandate=None):
		as_user("agent")
		type_ids = {t["label"]: t["name"] for t in notes.note_types()["types"]}
		notes.add_note(type_ids["Price discussion"], "Owner wants 1.2 crore, flexible to 1.1.", lead=lead)
		notes.add_note(
			type_ids["Photos"],
			"Hall and balcony",
			lead=lead,
			files=[file_of("hall.png", png_bytes((10, 120, 60))), file_of("balcony.png", png_bytes())],
		)
		notes.add_note(
			type_ids["Legal and title"], "Title deed seen, society NOC pending.", lead=lead, mandate=mandate
		)
		notes.add_note(type_ids["Other"], "Parking is shared", lead=lead, custom_label="Parking")

	def pdf_of(self, name):
		return branding.file_bytes(frappe.get_doc("Mandate", name).dossier_pdf)

	def test_it_is_refused_until_the_mandate_is_signed(self):
		lead = self.agent_seller("Dossier Draft")
		name = self.mandate(lead)
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			mandates.generate_dossier_pdf(name)
		self.assertIsNone(self.row(name)["dossier_pdf"])

	def test_a_branded_dossier_has_a_cover_every_section_images_and_page_numbers(self):
		self.brand_it()
		lead, name = self.released_mandate()
		self.add_notes(lead, name)
		as_user("agent")
		result = mandates.generate_dossier_pdf(name)
		row = next(m for m in result["mandates"] if m["name"] == name)
		self.assertEqual(row["dossier_pdf"]["version"], 1)
		pdf = self.pdf_of(name)
		reader = PdfReader(io.BytesIO(pdf))
		pages = len(reader.pages)
		self.assertGreaterEqual(pages, 2)
		cover = reader.pages[0].extract_text()
		for word in (
			"Pandya Realtors",
			"Private Sale Dossier",
			"Dossier Owner",
			"A51700012345",
			f"Mandate {name}",
		):
			self.assertIn(word, cover)
		text = text_of(pdf)
		for word in (
			"Seller and property",
			"Mandate and signing",
			"Signed",
			"Price discussion (1)",
			"Owner wants 1.2 crore",
			"Photos (1)",
			"Legal and title (1)",
			"Parking (1)",
			"Pandya Realtors | Confidential",
		):
			self.assertIn(word, text)
		for number in range(1, pages + 1):
			self.assertIn(f"Page {number} of {pages}", text)
		# The logo and the two photos are embedded.
		self.assertGreaterEqual(images_in(pdf), 3)

	def test_the_notes_are_grouped_by_type_in_the_companys_order(self):
		self.brand_it()
		lead, name = self.released_mandate()
		self.add_notes(lead)
		as_user("agent")
		mandates.generate_dossier_pdf(name)
		text = text_of(self.pdf_of(name))
		order = [
			text.index(label)
			for label in ("Price discussion (1)", "Legal and title (1)", "Photos (1)", "Parking (1)")
		]
		self.assertEqual(order, sorted(order))

	def test_regenerating_makes_a_new_version_and_keeps_the_old_one(self):
		_lead, name = self.released_mandate()
		as_user("agent")
		mandates.generate_dossier_pdf(name)
		first = frappe.get_doc("Mandate", name).dossier_pdf
		result = mandates.generate_dossier_pdf(name)
		row = next(m for m in result["mandates"] if m["name"] == name)
		self.assertEqual(row["dossier_pdf"]["version"], 2)
		self.assertNotEqual(row["dossier_pdf"]["file"], first)
		self.assertTrue(frappe.db.exists("File", {"file_url": first}))
		self.assertIn("Version 2", PdfReader(io.BytesIO(self.pdf_of(name))).pages[0].extract_text())

	def test_with_no_branding_it_has_a_clean_default_look(self):
		_lead, name = self.released_mandate()
		as_user("agent")
		mandates.generate_dossier_pdf(name)
		text = text_of(self.pdf_of(name))
		self.assertIn("Private Sale Dossier", text)
		self.assertIn("No notes have been written yet.", text)

	def test_it_holds_no_phone_number_or_email(self):
		self.brand_it()
		lead, name = self.released_mandate()
		client = frappe.db.get_value("Lead", lead, "client")
		phone = frappe.db.get_value("Client", client, "phone") or ""
		as_user("agent")
		mandates.generate_dossier_pdf(name)
		text = text_of(self.pdf_of(name))
		if phone:
			self.assertNotIn(phone[-6:], text.replace(" ", ""))
		self.assertNotIn("@", text.split("Seller and property", 1)[1])

	def test_the_pdf_is_opened_only_by_who_may_read_the_mandate_and_only_while_signed(self):
		_lead, name = self.released_mandate()
		as_user("agent")
		mandates.generate_dossier_pdf(name)
		file = frappe.get_doc("File", {"file_url": frappe.get_doc("Mandate", name).dossier_pdf})
		self.assertTrue(file.is_private)
		self.assertTrue(can_open(file, "agent"))
		self.assertTrue(can_open(file, "company_admin"))
		for who in ("channel_partner", "client", "sales_manager"):
			self.assertFalse(can_open(file, who), who)
		as_user("company_admin")
		mandates.set_mandate_archived(name, 1)
		self.assertFalse(can_open(file, "agent"))
		archived = next(
			m for m in mandates.mandate_overview(include_archived=1)["mandates"] if m["name"] == name
		)
		self.assertIsNone(archived["dossier_pdf"])

	def test_a_long_dossier_runs_over_several_pages_each_numbered(self):
		self.brand_it()
		lead, name = self.released_mandate()
		as_user("agent")
		call = {t["label"]: t["name"] for t in notes.note_types()["types"]}["Call"]
		for n in range(45):
			notes.add_note(
				call, f"Call number {n}: the owner asked about the society NOC and the parking.", lead=lead
			)
		mandates.generate_dossier_pdf(name)
		pdf = self.pdf_of(name)
		pages = len(PdfReader(io.BytesIO(pdf)).pages)
		self.assertGreaterEqual(pages, 4)
		text = text_of(pdf)
		self.assertIn(f"Page {pages} of {pages}", text)
		self.assertIn("Call number 44", text)

	def tearDown(self):
		super().tearDown()
		for path in private_files() | set(
			Path(frappe.get_site_path("private", "files")).glob("dossier-MND-*")
		):
			if path.name.startswith(("dossier-MND-", "p405_")):
				path.unlink(missing_ok=True)
