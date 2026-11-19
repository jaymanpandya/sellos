"""SOS-P2-04: the one consent function. A matrix of the four consent statuses against call, SMS and
WhatsApp, with Consent enforcement Off (everything proceeds, the warning is recorded) and On (only
Consented proceeds), who may change the setting, that every change is logged, the 022 promotional
warning, a bought list lead, and that no other module decides on consent."""

import re
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import ensure_roles
from sellos.crm import api, consent, pipeline
from sellos.crm.lead_sources import BOUGHT_LIST, ensure_default_sources
from sellos.crm.test_consent import make_record
from sellos.crm.test_crm import CrmCase, as_user
from sellos.testing.users import create_test_users
from sellos.tests import phones

CHANNELS = ("Call", "SMS", "WhatsApp")
STATUSES = ("Unknown", "Consented", "Opted out", "Registered DND")


class TestConsentCheck(CrmCase):
	"""SOS-P2-04: check_contact, the Consent Check record and Consent enforcement."""

	def setUp(self):
		_, self.lead = self.make_lead()
		frappe.set_user("Administrator")

	def lead_in_status(self, status):
		"""A new lead whose consent status is `status`."""
		_, lead = self.make_lead()
		frappe.set_user("Administrator")
		if status == "Consented":
			make_record(lead, "Consent")
		elif status == "Opted out":
			consent.record_opt_out(lead, "Phone call")
		elif status == "Registered DND":
			consent.record_dnd_result(lead, True)
		self.assertEqual(consent.compute_status(lead), status)
		return lead

	def test_enforcement_is_off_by_default(self):
		self.assertFalse(consent.enforcement_on())
		self.assertEqual(frappe.get_meta("SellOS Settings").get_field("consent_enforcement").default, "0")

	def test_with_enforcement_off_every_status_proceeds_on_every_channel_and_is_recorded(self):
		for status in STATUSES:
			lead = self.lead_in_status(status)
			for channel in CHANNELS:
				result = consent.check_contact(lead, channel)
				row = frappe.db.get_value(
					"Consent Check",
					result.check,
					["lead", "channel", "consent_status", "warning", "enforcement", "refused", "reason"],
					as_dict=True,
				)
				self.assertFalse(result.refused, (status, channel))
				self.assertEqual(
					(row.lead, row.channel, row.consent_status, row.enforcement, row.refused, row.reason),
					(lead, channel, status, "Off", 0, ""),
				)
				self.assertEqual(row.warning, result.warning)
				self.assertEqual(bool(row.warning), status != "Consented", (status, channel))

	def test_an_opted_out_lead_gets_a_red_warning_and_still_proceeds(self):
		lead = self.lead_in_status("Opted out")
		result = consent.check_contact(lead, "WhatsApp")
		self.assertEqual((result.warning_level, result.refused), ("red", False))
		self.assertIn("Opted out", result.warning)

	def test_with_enforcement_on_only_consented_proceeds(self):
		consent.set_enforcement(True)
		for status in STATUSES:
			lead = self.lead_in_status(status)
			for channel in CHANNELS:
				result = consent.check_contact(lead, channel)
				row = frappe.db.get_value(
					"Consent Check", result.check, ["refused", "reason", "enforcement"], as_dict=True
				)
				self.assertEqual(result.refused, status != "Consented", (status, channel))
				self.assertEqual(bool(row.refused), result.refused)
				self.assertEqual(row.enforcement, "On")
				if result.refused:
					self.assertIn(status, row.reason)
					self.assertEqual(row.reason, result.reason)
				else:
					self.assertEqual(row.reason, "")

	def test_a_promotional_call_on_the_022_number_is_a_warning_not_a_refusal(self):
		lead = self.lead_in_status("Consented")
		result = consent.check_contact(lead, "Call", purpose="promotional")
		self.assertFalse(result.refused)
		self.assertIn("promotional", result.warning)
		self.assertEqual(frappe.db.get_value("Consent Check", result.check, "purpose"), "Promotional")
		service = consent.check_contact(lead, "Call", purpose="Service")
		self.assertEqual(service.warning, "")

	def test_a_check_links_to_its_log_entry(self):
		result = consent.check_contact(self.lead, "Call", reference_doctype="Lead", reference_name=self.lead)
		row = frappe.db.get_value("Consent Check", result.check, ["reference_doctype", "reference_name"])
		self.assertEqual(tuple(row), ("Lead", self.lead))
		consent.link_check(result.check, "Client", "X")
		self.assertEqual(frappe.db.get_value("Consent Check", result.check, "reference_name"), "X")

	def test_a_channel_outside_the_three_is_refused_as_a_mistake(self):
		with self.assertRaises(frappe.ValidationError):
			consent.check_contact(self.lead, "Email")

	def test_only_a_company_admin_changes_the_setting_and_every_change_is_logged(self):
		for key in ("agent", "sales_manager", "channel_partner", "client", "platform_admin"):
			as_user(key)
			with self.assertRaises(frappe.PermissionError, msg=key):
				api.set_consent_enforcement(1)
		as_user("company_admin")
		self.assertEqual(api.get_consent_enforcement(), {"consent_enforcement": False})
		self.assertEqual(api.set_consent_enforcement(1), {"consent_enforcement": True})
		self.assertEqual(api.set_consent_enforcement(0), {"consent_enforcement": False})
		frappe.set_user("Administrator")
		versions = frappe.get_all(
			"Version",
			filters={"ref_doctype": "SellOS Settings", "docname": "SellOS Settings"},
			fields=["owner", "data"],
		)
		changed = [v for v in versions if "consent_enforcement" in v.data]
		self.assertEqual(len(changed), 2)
		self.assertTrue(all(v.owner == "sos_test_company_admin@example.com" for v in changed))

	def test_nobody_can_delete_a_consent_check(self):
		result = consent.check_contact(self.lead, "SMS")
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Consent Check", result.check, force=True)

	def test_no_other_module_refuses_on_consent(self):
		"""Only sellos/crm/consent.py reads the setting or builds a refusal from a consent status."""
		root = Path(frappe.get_app_path("sellos"))
		offenders = []
		for path in root.rglob("*.py"):
			rel = path.relative_to(root).as_posix()
			if rel.startswith(("tests/", "testing/", "patches/")) or "/test_" in f"/{rel}":
				continue
			if rel == "crm/consent.py":
				continue
			text = path.read_text(encoding="utf-8")
			if re.search(r"Value\([^)]*consent_enforcement|[\"']doctype[\"']: [\"']Consent Check[\"']", text):
				offenders.append(rel)
		self.assertEqual(offenders, [])


class TestConsentCheckBoughtList(IntegrationTestCase):
	"""SOS-P2-04: a lead imported the way SOS-P1-12 imports one proceeds."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_bought_list_leads_proceed_with_their_warning(self):
		frappe.set_user("Administrator")
		pipeline.ensure_default_stages()
		ensure_default_sources()
		unknown, dnd = phones.in_mobile(2401), phones.in_mobile(2402)
		as_user("company_admin")
		api.import_bought_list(
			"\n".join(
				(
					"Full Name,Mobile,Email ID,City,DND Status,Remarks",
					f"P204 Unknown,{unknown},,Pune,,",
					f"P204 Dnd,{dnd},,Pune,Registered,",
				)
			),
			list_name="P204 list",
		)
		frappe.set_user("Administrator")
		seen = set()
		for name in ("P204 Unknown", "P204 Dnd"):
			client = frappe.db.get_value("Client", {"client_name": name}, "name")
			lead = frappe.get_all("Lead", filters={"client": client}, pluck="name")[0]
			self.assertEqual(frappe.db.get_value("Lead", lead, "source"), BOUGHT_LIST)
			for channel in CHANNELS:
				result = consent.check_contact(lead, channel)
				self.assertFalse(result.refused)
				self.assertTrue(result.warning)
				seen.add(result.status)
		self.assertEqual(seen, {"Unknown", "Registered DND"})
