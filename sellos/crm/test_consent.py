# SOS-P1-08 the Consent Record: expiry by basis, evidence, renewals, opt out, DND, and that nothing blocks.
import frappe
from frappe.utils import add_days, add_months, add_to_date, now_datetime

from sellos.crm import api, consent
from sellos.crm.test_crm import CrmCase, as_user, email

EVIDENCE = "https://example.com/evidence/form-17"


def make_record(lead, basis, recorded_on=None, evidence=EVIDENCE):
	return frappe.get_doc(
		{
			"doctype": "Consent Record",
			"lead": lead,
			"basis": basis,
			"evidence_link": evidence,
			"recorded_on": recorded_on or now_datetime(),
		}
	).insert(ignore_permissions=True)


class TestConsentRecord(CrmCase):
	def setUp(self):
		_, self.lead = self.make_lead()
		frappe.set_user("Administrator")

	def status_at(self, when):
		return consent.compute_status(self.lead, when)

	def test_a_lead_with_no_record_is_unknown_with_an_amber_warning(self):
		self.assertEqual(consent.compute_status(self.lead), "Unknown")
		view = consent.consent_view(self.lead)
		self.assertEqual((view["status"], view["warning"]), ("Unknown", "amber"))

	def test_a_live_record_makes_the_lead_consented_with_no_warning(self):
		make_record(self.lead, "Consent")
		self.assertEqual(frappe.db.get_value("Lead", self.lead, "consent_status"), "Consented")
		view = consent.consent_view(self.lead)
		self.assertEqual((view["status"], view["warning"], view["message"]), ("Consented", None, ""))

	def test_an_inquiry_expires_after_7_days(self):
		start = now_datetime()
		record = make_record(self.lead, "Inquiry", start)
		self.assertEqual(record.expires_on, add_days(start, 7))
		self.assertEqual(self.status_at(add_to_date(start, days=6, hours=23)), "Consented")
		self.assertEqual(self.status_at(add_to_date(start, days=7, minutes=1)), "Unknown")

	def test_an_application_expires_after_3_months(self):
		start = now_datetime()
		record = make_record(self.lead, "Application", start)
		self.assertEqual(record.expires_on, add_months(start, 3))
		self.assertEqual(self.status_at(add_to_date(start, months=3, minutes=-1)), "Consented")
		self.assertEqual(self.status_at(add_to_date(start, months=3, minutes=1)), "Unknown")

	def test_a_consent_basis_has_no_expiry(self):
		start = now_datetime()
		record = make_record(self.lead, "Consent", start)
		self.assertIsNone(record.expires_on)
		self.assertEqual(self.status_at(add_to_date(start, years=5)), "Consented")

	def test_the_hourly_job_returns_an_expired_lead_to_unknown(self):
		start = now_datetime()
		make_record(self.lead, "Inquiry", start)
		self.assertEqual(consent.expire_due_records(add_to_date(start, days=6)), [])
		self.assertEqual(frappe.db.get_value("Lead", self.lead, "consent_status"), "Consented")
		self.assertEqual(consent.expire_due_records(add_to_date(start, days=8)), [self.lead])
		self.assertEqual(frappe.db.get_value("Lead", self.lead, "consent_status"), "Unknown")

	def test_a_record_without_evidence_is_refused(self):
		for evidence in (None, "", "   ", "no link at all", "javascript:alert(1)"):
			with self.assertRaises(frappe.ValidationError, msg=repr(evidence)):
				make_record(self.lead, "Inquiry", evidence=evidence)
		for basis in consent.BASES:
			with self.assertRaises(frappe.ValidationError):
				make_record(self.lead, basis, evidence="")
		self.assertEqual(frappe.db.count("Consent Record", {"lead": self.lead}), 0)

	def test_the_api_refuses_a_record_without_evidence(self):
		as_user("agent")
		with self.assertRaises(frappe.ValidationError):
			api.record_consent(self.lead, "Inquiry", "")
		self.assertEqual(api.get_lead(self.lead)["consent"]["status"], "Unknown")

	def test_a_file_in_the_company_files_is_accepted_as_evidence(self):
		make_record(self.lead, "Application", evidence="/private/files/signed-form.pdf")
		self.assertEqual(consent.compute_status(self.lead), "Consented")

	def test_a_record_is_never_edited(self):
		record = make_record(self.lead, "Inquiry")
		record.evidence_link = "https://example.com/other"
		with self.assertRaises(frappe.ValidationError):
			record.save(ignore_permissions=True)

	def test_a_renewal_is_linked_counted_and_logged(self):
		first = make_record(self.lead, "Inquiry", add_days(now_datetime(), -8))
		self.assertEqual(consent.compute_status(self.lead), "Unknown")
		second = make_record(self.lead, "Inquiry")
		self.assertEqual((second.renews, second.renewal_count), (first.name, 1))
		third = make_record(self.lead, "Inquiry")
		self.assertEqual((third.renews, third.renewal_count), (second.name, 2))
		self.assertEqual(consent.compute_status(self.lead), "Consented")
		notes = frappe.get_all(
			"Comment", filters={"reference_doctype": "Lead", "reference_name": self.lead}, pluck="content"
		)
		self.assertEqual(len([n for n in notes if "renews" in n]), 2)
		self.assertTrue(any(second.name in n and first.name in n for n in notes))

	def test_a_different_basis_is_not_a_renewal(self):
		make_record(self.lead, "Inquiry")
		self.assertIsNone(make_record(self.lead, "Application").renews)

	def test_records_cannot_be_deleted_and_are_change_tracked(self):
		record = make_record(self.lead, "Consent")
		self.assertTrue(frappe.get_meta("Consent Record").track_changes)
		for row in frappe.get_meta("Consent Record").permissions:
			self.assertFalse(row.delete, row.role)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Consent Record", record.name, force=True)


class TestOptOutAndDnd(CrmCase):
	def setUp(self):
		_, self.lead = self.make_lead()

	def test_a_stop_request_is_recorded_with_its_time_and_source_and_shows_red(self):
		before = now_datetime()
		view = api.record_opt_out(self.lead, "WhatsApp")
		self.assertEqual((view["status"], view["warning"]), ("Opted out", "red"))
		self.assertEqual(view["opted_out_source"], "WhatsApp")
		self.assertGreaterEqual(
			frappe.utils.get_datetime(view["opted_out_on"]), before.replace(microsecond=0)
		)
		self.assertIn("WhatsApp", view["message"])
		self.assertEqual(frappe.db.get_value("Lead", self.lead, "consent_status"), "Opted out")

	def test_a_stop_request_blocks_nothing(self):
		api.record_consent(self.lead, "Consent", EVIDENCE)
		api.record_opt_out(self.lead, "Phone call")
		# Calls, WhatsApp messages and emails are logged, and the lead is edited, as for any lead.
		for kind in ("Call", "WhatsApp", "Email"):
			self.assertEqual(
				api.add_activity(self.lead, kind, "after the stop request")["activity_type"], kind
			)
		self.assertEqual(
			api.save_lead(self.lead, {"notes": "still editable"})["lead"]["notes"], "still editable"
		)
		api.save_task(
			values={"lead": self.lead, "title": "Call back", "due_date": add_days(now_datetime(), 1)}
		)
		self.assertEqual(api.get_lead(self.lead)["consent"]["warning"], "red")

	def test_nothing_in_the_crm_package_refuses_on_consent(self):
		# P1.08: consent is recorded and shown, never enforced here (enforcement is P2.04, off by default).
		for status in consent.STATUSES:
			doc = frappe.get_doc("Lead", self.lead)
			doc.consent_status = status
			doc.flags.ignore_permissions = True
			doc.save()
			self.assertEqual(api.add_activity(self.lead, "Call", f"while {status}")["activity_type"], "Call")

	def test_opt_out_outranks_a_live_record_and_a_new_record_does_not_clear_it(self):
		api.record_consent(self.lead, "Consent", EVIDENCE)
		api.record_opt_out(self.lead, "SMS")
		self.assertEqual(consent.compute_status(self.lead), "Opted out")
		api.record_consent(self.lead, "Inquiry", EVIDENCE)
		self.assertEqual(consent.compute_status(self.lead), "Opted out")

	def test_the_first_stop_request_is_kept(self):
		first = api.record_opt_out(self.lead, "Phone call")
		second = api.record_opt_out(self.lead, "Email")
		self.assertEqual(second["opted_out_source"], "Phone call")
		self.assertEqual(second["opted_out_on"], first["opted_out_on"])

	def test_a_stop_request_needs_a_known_source(self):
		with self.assertRaises(frappe.ValidationError):
			api.record_opt_out(self.lead, "Carrier pigeon")

	def test_a_known_dnd_result_shows_amber_and_a_clear_result_removes_it(self):
		view = api.record_dnd_result(self.lead, 1)
		self.assertEqual((view["status"], view["warning"]), ("Registered DND", "amber"))
		self.assertTrue(view["dnd_checked_on"])
		self.assertEqual(api.add_activity(self.lead, "Call", "calls go ahead")["activity_type"], "Call")
		self.assertEqual(api.record_dnd_result(self.lead, 0)["status"], "Unknown")

	def test_dnd_outranks_a_live_record_but_not_a_stop_request(self):
		api.record_consent(self.lead, "Consent", EVIDENCE)
		self.assertEqual(api.record_dnd_result(self.lead, 1)["status"], "Registered DND")
		self.assertEqual(api.record_opt_out(self.lead, "Website")["status"], "Opted out")

	def test_the_lead_list_and_detail_carry_the_status(self):
		api.record_dnd_result(self.lead, 1)
		row = next(r for r in api.list_leads() if r.name == self.lead)
		self.assertEqual((row.consent_status, row.consent_warning), ("Registered DND", "amber"))
		self.assertEqual(api.get_lead(self.lead)["consent"]["status"], "Registered DND")


class TestConsentPermissions(CrmCase):
	def setUp(self):
		_, self.lead = self.make_lead("company_admin", assigned_to=email("agent"))
		frappe.set_user("Administrator")
		make_record(self.lead, "Consent")

	def test_the_assigned_agent_records_and_sees_the_records(self):
		as_user("agent")
		view = api.record_consent(self.lead, "Application", EVIDENCE)
		self.assertEqual(len(view["records"]), 2)

	def test_a_channel_partner_cannot_record_anything(self):
		as_user("channel_partner")
		for call in (
			lambda: api.record_consent(self.lead, "Inquiry", EVIDENCE),
			lambda: api.record_opt_out(self.lead, "Phone call"),
			lambda: api.record_dnd_result(self.lead, 1),
		):
			with self.assertRaises(frappe.PermissionError):
				call()

	def test_an_agent_cannot_record_on_a_lead_that_is_not_theirs(self):
		_, other = self.make_lead("company_admin")
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			api.record_consent(other, "Inquiry", EVIDENCE)
		self.assertEqual(frappe.get_list("Consent Record", filters={"lead": other}), [])

	def test_the_platform_admin_sees_no_consent_records_by_role(self):
		as_user("platform_admin")
		self.assertEqual(frappe.get_list("Consent Record"), [])
