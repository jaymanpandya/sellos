"""SOS-N22: the default consent wording, and {company} replaced with the company's display name on the
enquiry page and the website forms (Jayman, 24 November 2026). Each test restores the settings it changes."""

import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access import partner_registrations as pr
from sellos.crm import enquiry
from sellos.crm.test_p1_09_website_form import WebsiteCase, post
from sellos.crm.test_p1_09_website_form import counts as lead_counts

SETTINGS = "SellOS Settings"
EXPECTED_DEFAULT = (
	"I agree that {company} and its agents may contact me about my enquiry by phone, SMS, WhatsApp "
	"and email. I can ask them to stop at any time."
)
COMPANY = "N22 Test Realty"


class WordingCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		for field in ("consent_wording", "company_name"):
			old = frappe.db.get_single_value(SETTINGS, field)
			self.addCleanup(frappe.db.set_single_value, SETTINGS, field, old)
		frappe.db.set_single_value(SETTINGS, "consent_wording", "")
		frappe.db.set_single_value(SETTINGS, "company_name", COMPANY)
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		self.addCleanup(frappe.clear_document_cache, SETTINGS, SETTINGS)


class TestDefaultWording(WordingCase):
	def test_the_default_text_is_the_one_jayman_decided(self):
		self.assertEqual(pr.DEFAULT_WORDING, EXPECTED_DEFAULT)

	def test_it_is_the_default_of_the_setting_in_the_doctype(self):
		path = (
			Path(pr.__file__).parents[1] / "sellos" / "doctype" / "sellos_settings" / "sellos_settings.json"
		)
		fields = {f["fieldname"]: f for f in json.loads(path.read_text(encoding="utf-8"))["fields"]}
		self.assertEqual(fields["consent_wording"]["default"], EXPECTED_DEFAULT)

	def test_an_empty_setting_shows_the_default_with_the_company_name(self):
		self.assertEqual(pr.consent_wording(), EXPECTED_DEFAULT.replace("{company}", COMPANY))

	def test_an_empty_company_name_falls_back_to_the_company(self):
		frappe.db.set_single_value(SETTINGS, "company_name", "")
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		self.assertIn("I agree that the company and its agents", pr.consent_wording())
		self.assertNotIn("{company}", pr.consent_wording())

	def test_a_company_admins_own_wording_is_kept_and_also_substituted(self):
		frappe.db.set_single_value(SETTINGS, "consent_wording", "N22 own: {company} may call me. {x}")
		self.assertEqual(pr.consent_wording(), f"N22 own: {COMPANY} may call me. {{x}}")
		self.assertEqual(pr.raw_consent_wording(), "N22 own: {company} may call me. {x}")

	def test_the_settings_screen_gets_the_raw_text_so_saving_never_bakes_the_name_in(self):
		self.assertEqual(pr.get_partner_settings()["consent_wording"], EXPECTED_DEFAULT)

	def test_the_name_is_inserted_as_text_not_formatted(self):
		self.assertEqual(pr.render_wording("{company}!", "A {b} Co"), "A {b} Co!")


class TestEnquiryPage(WordingCase):
	def test_the_page_and_its_evidence_carry_the_substituted_wording(self):
		from sellos.www import enquiry as page

		context = frappe._dict()
		with patch.object(page.frappe, "form_dict", frappe._dict(k="n22-fake-key")):
			page.get_context(context)
		self.assertEqual(context.consent_wording, EXPECTED_DEFAULT.replace("{company}", COMPANY))
		self.assertNotIn("{company}", context.consent_wording)
		self.assertEqual(
			enquiry.wording_version(context.consent_wording),
			enquiry.wording_version(pr.consent_wording()),
		)


class TestWebsiteForm(WebsiteCase):
	def setUp(self):
		super().setUp()
		old = frappe.db.get_single_value(SETTINGS, "company_name")
		self.addCleanup(frappe.db.set_single_value, SETTINGS, "company_name", old)
		frappe.db.set_single_value(SETTINGS, "company_name", COMPANY)
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		self.addCleanup(frappe.clear_document_cache, SETTINGS, SETTINGS)

	def test_a_wording_with_the_placeholder_is_stored_with_the_company_name(self):
		wording = "N22 form: I agree that {company} may contact me."
		before = lead_counts()
		post(self.form(consent_wording=wording), self.address)
		self.assertEqual(lead_counts()["Consent Record"], before["Consent Record"] + 1)
		lead = self.lead_of(self.person)
		url = frappe.get_all("Consent Record", {"lead": lead.name}, ["evidence_link"])[0].evidence_link
		evidence = json.loads(frappe.get_doc("File", {"file_url": url}).get_content())
		self.assertEqual(evidence["wording"], f"N22 form: I agree that {COMPANY} may contact me.")
		self.assertEqual(evidence["wording_version"], enquiry.wording_version(evidence["wording"]))

	def test_a_wording_without_the_placeholder_is_stored_as_sent(self):
		wording = "N22 plain wording."
		post(self.form(consent_wording=wording), self.address)
		lead = self.lead_of(self.person)
		url = frappe.get_all("Consent Record", {"lead": lead.name}, ["evidence_link"])[0].evidence_link
		self.assertEqual(
			json.loads(frappe.get_doc("File", {"file_url": url}).get_content())["wording"], wording
		)


PARTNER_DEFAULT = (
	"I confirm my client has agreed that {company} and its agents may contact them about this enquiry."
)


class TestPartnerConfirmationWording(WordingCase):
	"""SOS-P7-02 (Jayman, 24 November 2026): the partner confirms with its own setting, "Partner
	confirmation wording", never the buyer's "Consent wording". {company} is replaced the same way."""

	def setUp(self):
		super().setUp()
		old = frappe.db.get_single_value(SETTINGS, "partner_confirmation_wording")
		self.addCleanup(frappe.db.set_single_value, SETTINGS, "partner_confirmation_wording", old)
		frappe.db.set_single_value(SETTINGS, "partner_confirmation_wording", "")

	def test_the_default_is_the_decided_text_and_the_default_of_the_setting(self):
		self.assertEqual(pr.DEFAULT_PARTNER_CONFIRMATION, PARTNER_DEFAULT)
		path = (
			Path(pr.__file__).parents[1] / "sellos" / "doctype" / "sellos_settings" / "sellos_settings.json"
		)
		fields = {f["fieldname"]: f for f in json.loads(path.read_text(encoding="utf-8"))["fields"]}
		self.assertEqual(fields["partner_confirmation_wording"]["default"], PARTNER_DEFAULT)

	def test_company_is_replaced_and_an_empty_name_falls_back(self):
		self.assertEqual(pr.partner_confirmation_wording(), PARTNER_DEFAULT.replace("{company}", COMPANY))
		frappe.db.set_single_value(SETTINGS, "company_name", "")
		frappe.clear_document_cache(SETTINGS, SETTINGS)
		self.assertIn("agreed that the company and its agents", pr.partner_confirmation_wording())
		self.assertNotIn("{company}", pr.partner_confirmation_wording())

	def test_it_is_independent_of_the_consent_wording(self):
		frappe.db.set_single_value(SETTINGS, "consent_wording", "N22 buyer wording {company}")
		self.assertEqual(pr.partner_confirmation_wording(), PARTNER_DEFAULT.replace("{company}", COMPANY))
		frappe.db.set_single_value(SETTINGS, "partner_confirmation_wording", "N22 partner: {company} {x}")
		self.assertEqual(pr.partner_confirmation_wording(), f"N22 partner: {COMPANY} {{x}}")
		self.assertEqual(pr.consent_wording(), f"N22 buyer wording {COMPANY}")

	def test_the_settings_screen_gets_the_raw_text(self):
		self.assertEqual(pr.get_partner_settings()["partner_confirmation_wording"], PARTNER_DEFAULT)
