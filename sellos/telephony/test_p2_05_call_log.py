"""SOS-P2-05: the Call Log. Cost conversion to rupees, billed duration, a placed call (through the fake
provider) creates one log that links to the lead, its Consent Check and the live Consent Record."""

from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import ensure_roles
from sellos.crm import consent
from sellos.crm.test_consent import make_record
from sellos.crm.test_crm import CrmCase, as_user
from sellos.telephony import call_log
from sellos.telephony.base import CallEvent, ProviderError
from sellos.telephony.settings import save_telephony_settings
from sellos.testing.users import create_test_users
from sellos.tests import phones

LANDLINE = f"{phones.in_mobile(3500)[:3]}22{phones.in_mobile(3500)[-8:]}"


class TestCostConversion(IntegrationTestCase):
	"""SOS-P2-05: cost is stored in rupees."""

	def test_paise_become_rupees(self):
		self.assertEqual(call_log.to_rupees(250, "paise"), Decimal("2.5000"))
		self.assertEqual(call_log.to_rupees("1", "paise"), Decimal("0.0100"))
		self.assertEqual(call_log.to_rupees(0, "paise"), Decimal("0.0000"))

	def test_rupees_stay_rupees_and_round_half_up(self):
		self.assertEqual(call_log.to_rupees("1.23455"), Decimal("1.2346"))
		self.assertEqual(call_log.to_rupees(3), Decimal("3.0000"))
		self.assertEqual(call_log.to_rupees(None), Decimal("0.0000"))

	def test_bad_units_and_negative_costs_are_refused(self):
		with self.assertRaises(ValueError):
			call_log.to_rupees(1, "dollars")
		with self.assertRaises(ValueError):
			call_log.to_rupees(-1)

	def test_billed_duration_rounds_up_to_the_started_minute(self):
		self.assertEqual(
			[call_log.billed_seconds(n) for n in (0, None, 1, 60, 61, 125)], [0, 0, 60, 60, 120, 180]
		)
		self.assertEqual(call_log.billed_seconds(10, pulse=6), 12)


class TestPlacedCall(CrmCase):
	"""SOS-P2-05: a placed call creates one log."""

	def setUp(self):
		ensure_roles()
		create_test_users()
		_, self.lead = self.make_lead()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		frappe.db.set_single_value("Telephony Settings", "provider", "fake")
		save_telephony_settings("FAKEOK1", "token-for-the-fake", LANDLINE)

	def test_a_placed_call_creates_one_log_linked_to_lead_check_and_record(self):
		record = make_record(self.lead, "Consent")
		result = call_log.place_logged_call(self.lead, "service")
		log = frappe.get_doc("Call Log", result["log"])
		self.assertEqual(
			(log.lead, log.provider, log.mode, log.purpose, log.state),
			(self.lead, "fake", "Manual", "Service", "queued"),
		)
		self.assertTrue(log.call_id.startswith("fake-"))
		self.assertEqual((log.consent_check, log.consent_record), (result["check"].check, record.name))
		self.assertEqual(frappe.db.count("Call Log", {"lead": self.lead}), 1)
		self.assertEqual(
			tuple(
				frappe.db.get_value(
					"Consent Check", log.consent_check, ["reference_doctype", "reference_name"]
				)
			),
			("Call Log", log.name),
		)
		self.assertFalse(log.meta.has_field("consent_status"))

	def test_without_a_live_record_the_link_is_empty_and_the_call_still_goes(self):
		result = call_log.place_logged_call(self.lead, "Transactional", mode="AI")
		log = frappe.get_doc("Call Log", result["log"])
		self.assertEqual((log.consent_record, log.mode), (None, "AI"))
		self.assertEqual(frappe.db.get_value("Consent Check", log.consent_check, "consent_status"), "Unknown")

	def test_an_event_fills_duration_cost_recording_and_cause(self):
		log = call_log.place_logged_call(self.lead, "Service")["log"]
		call_id = frappe.db.get_value("Call Log", log, "call_id")
		event = CallEvent(call_id, "completed", duration=61, recording_url="https://example.com/r.mp3")
		self.assertEqual(call_log.apply_event(event, cost=250, cost_unit="paise", hangup_cause="Normal"), log)
		row = frappe.db.get_value(
			"Call Log",
			log,
			["state", "duration", "billed_duration", "cost_rupees", "hangup_cause", "recording_link"],
			as_dict=True,
		)
		self.assertEqual(
			(row.state, row.duration, row.billed_duration, float(row.cost_rupees), row.hangup_cause),
			("completed", 61, 120, 2.5, "Normal"),
		)
		self.assertEqual(row.recording_link, "https://example.com/r.mp3")
		self.assertIsNone(call_log.apply_event(CallEvent("nope", "completed")))

	def test_a_second_log_for_one_call_is_refused(self):
		log = call_log.place_logged_call(self.lead, "Service")["log"]
		duplicate = frappe.get_doc(
			{
				"doctype": "Call Log",
				"lead": self.lead,
				"provider": "fake",
				"call_id": frappe.db.get_value("Call Log", log, "call_id"),
				"mode": "Manual",
				"purpose": "Service",
			}
		)
		with self.assertRaises(frappe.UniqueValidationError):
			duplicate.insert(ignore_permissions=True)

	def test_enforcement_on_refuses_an_unconsented_lead_with_no_log(self):
		consent.set_enforcement(True)
		result = call_log.place_logged_call(self.lead, "Service")
		self.assertTrue(result["check"].refused)
		self.assertIsNone(result["log"])
		self.assertEqual(frappe.db.count("Call Log", {"lead": self.lead}), 0)

	def test_a_bad_purpose_or_missing_number_places_no_call(self):
		with self.assertRaises(ProviderError):
			call_log.place_logged_call(self.lead, "Marketing")
		self.assertEqual(frappe.db.count("Call Log", {"lead": self.lead}), 0)

	def test_nobody_deletes_a_log_and_roles_only_read_their_leads(self):
		log = call_log.place_logged_call(self.lead, "Service")["log"]
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Call Log", log, force=True)
		as_user("agent")
		self.assertTrue(frappe.has_permission("Call Log", "read", doc=log))
		self.assertFalse(frappe.has_permission("Call Log", "write", doc=log))
		as_user("channel_partner")
		self.assertFalse(frappe.has_permission("Call Log", "read", doc=log))
		as_user("platform_admin")
		self.assertFalse(frappe.has_permission("Call Log", "read", doc=log))
