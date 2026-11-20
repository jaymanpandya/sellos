"""SOS-P2-07: click to call. The agent's Indian mobile rings first, then the lead, through the fake provider
that plays both legs; the consent status and warning show and never block; a number outside India is a clear
error; the media anchoring error path; the outcome form is required after the call."""

import json
from unittest import mock

import frappe
from frappe.utils import now_datetime

from sellos.crm import consent
from sellos.crm.test_consent import make_record
from sellos.crm.test_crm import PHONE as LEAD_PHONE
from sellos.crm.test_crm import CrmCase, as_user, email
from sellos.telephony import click_to_call, webhook
from sellos.telephony.base import CallEvent, ProviderError
from sellos.telephony.settings import save_telephony_settings
from sellos.tests import phones

AGENT_PHONE = phones.in_mobile(2071)
ABROAD_PHONE = phones.au_mobile(2072)
LANDLINE = f"{phones.in_mobile(2073)[:3]}22{phones.in_mobile(2073)[-8:]}"
STATUSES = ("Consented", "Unknown", "Registered DND", "Opted out")


class ClickToCallCase(CrmCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.db.set_single_value("Telephony Settings", "provider", "fake")
		save_telephony_settings("FAKEOK-P207", "token-for-the-fake", LANDLINE)
		frappe.db.set_value("User", email("agent"), "mobile_no", AGENT_PHONE)
		_, self.lead = self.make_lead()
		as_user("agent")

	def make_status(self, status):
		if status == "Consented":
			make_record(self.lead, "Consent")
		elif status == "Registered DND":
			frappe.db.set_value("Lead", self.lead, "dnd_registered", 1)
		elif status == "Opted out":
			frappe.db.set_value("Lead", self.lead, "opted_out_on", now_datetime())
		self.assertEqual(consent.compute_status(self.lead), status)

	def event(self, call_id, state, duration=0, **extra):
		return webhook.apply_plivo_event(CallEvent(call_id, state, duration=duration, **extra))

	def status(self, log):
		return click_to_call.call_status(log)

	def start(self, purpose="Service"):
		return click_to_call.click_to_call(self.lead, purpose)

	def lead_leg(self, log):
		return frappe.db.get_value("Call Log", log, "lead_call_id")


class TestBothLegs(ClickToCallCase):
	"""SOS-P2-07: the end to end call, with the fake provider playing both legs."""

	def test_the_agent_rings_first_then_the_lead_then_hangup_then_the_outcome(self):
		started = self.start()
		log = started["call_log"]
		self.assertFalse(started["refused"])
		self.assertEqual(self.status(log)["stage"], "agent_ringing")
		row = frappe.get_doc("Call Log", log)
		self.assertEqual(
			(row.agent, row.state, row.lead_call_id, row.purpose), (email("agent"), "queued", None, "Service")
		)
		# The first leg is to the agent's own mobile: the fake provider's id ends with its digits.
		self.assertIn(f"-{AGENT_PHONE[-6:]}-", row.call_id)
		self.assertNotIn(f"-{LEAD_PHONE[-6:]}-", row.call_id)

		# The lead is not rung until the agent answers.
		self.event(row.call_id, "ringing")
		self.assertIsNone(self.lead_leg(log))
		self.event(row.call_id, "in-progress")
		lead_leg = self.lead_leg(log)
		self.assertIn(f"-{LEAD_PHONE[-6:]}-", lead_leg)
		self.assertEqual(self.status(log)["stage"], "connecting")

		self.event(lead_leg, "ringing")
		self.assertEqual(self.status(log)["stage"], "lead_ringing")
		self.event(lead_leg, "in-progress")
		connected = self.status(log)
		self.assertEqual(
			(connected["stage"], connected["ended"], connected["outcome_needed"]), ("connected", False, False)
		)

		self.event(lead_leg, "completed", duration=95)
		ended = self.status(log)
		self.assertEqual((ended["stage"], ended["ended"], ended["outcome_needed"]), ("ended", True, True))
		self.assertEqual(frappe.db.get_value("Call Log", log, ["state", "duration"]), ("completed", 95))
		self.assertEqual([c["call_log"] for c in click_to_call.pending_outcomes()], [log])

		done = click_to_call.record_outcome(log, "Wrong number", notes="p207 call")
		self.assertTrue(frappe.db.exists("Lead Activity", done["activity"]))
		self.assertEqual(frappe.db.get_value("Call Log", log, "outcome"), "Wrong number")
		self.assertEqual(click_to_call.pending_outcomes(), [])
		self.assertEqual(frappe.db.get_value("Lead Activity", done["activity"], "duration_seconds"), 95)

	def test_a_replayed_answer_does_not_ring_the_lead_twice(self):
		log = self.start()["call_log"]
		call_id = frappe.db.get_value("Call Log", log, "call_id")
		self.event(call_id, "in-progress")
		first = self.lead_leg(log)
		with mock.patch("sellos.telephony.provider.FakeProvider.place_call") as place:
			self.event(call_id, "in-progress")
		place.assert_not_called()
		self.assertEqual(self.lead_leg(log), first)

	def test_an_agent_who_does_not_answer_never_rings_the_lead(self):
		log = self.start()["call_log"]
		call_id = frappe.db.get_value("Call Log", log, "call_id")
		self.event(call_id, "no-answer")
		status = self.status(log)
		self.assertEqual((status["stage"], status["outcome_needed"]), ("no_answer", True))
		self.assertIsNone(self.lead_leg(log))

	def test_no_response_holds_the_lead_phone_number(self):
		started = self.start()
		call_id = frappe.db.get_value("Call Log", started["call_log"], "call_id")
		self.event(call_id, "in-progress")
		seen = json.dumps(
			[
				started,
				click_to_call.call_preview(self.lead),
				self.status(started["call_log"]),
				click_to_call.pending_outcomes(),
			],
			default=str,
		)
		for form in phones.forms(LEAD_PHONE):
			self.assertNotIn(form, seen)


class TestConsentNeverBlocks(ClickToCallCase):
	"""SOS-P2-07: a lead in any consent status can be called, and the warning shows before and during."""

	def test_every_status_is_called_with_its_warning_before_and_during_the_call(self):
		for status in STATUSES:
			with self.subTest(status=status):
				point = f"p207_{status.split()[0].lower()}"
				frappe.db.savepoint(point)
				frappe.set_user("Administrator")
				self.make_status(status)
				as_user("agent")
				before = click_to_call.call_preview(self.lead)
				self.assertEqual((before["consent_status"], before["can_call"]), (status, True))
				started = self.start()
				self.assertFalse(started["refused"])
				during = self.status(started["call_log"])
				self.assertEqual(during["consent_status"], status)
				self.assertEqual(during["consent_warning"], before["consent_warning"])
				self.assertTrue(started["call_log"])
				if status == "Consented":
					self.assertEqual(before["consent_warning"], "none")
				else:
					self.assertEqual(before["consent_warning"], "red" if status == "Opted out" else "amber")
					self.assertTrue(before["consent_message"])
					self.assertEqual(during["consent_message"], before["consent_message"])
				frappe.db.rollback(save_point=point)

	def test_enforcement_on_is_the_only_refusal_and_it_is_the_consent_function(self):
		frappe.set_user("Administrator")
		consent.set_enforcement(True)
		as_user("agent")
		result = self.start()
		self.assertTrue(result["refused"])
		self.assertIsNone(result["call_log"])
		self.assertIn("Consent enforcement is On", result["reason"])
		self.assertEqual(frappe.db.count("Call Log", {"lead": self.lead}), 0)

	def test_a_promotional_call_shows_the_022_warning_and_is_placed(self):
		started = self.start("Promotional")
		self.assertFalse(started["refused"])
		self.assertIn("022", started["consent_message"])
		self.assertEqual(frappe.db.get_value("Call Log", started["call_log"], "purpose"), "Promotional")


class TestIndiaOnly(ClickToCallCase):
	"""SOS-P2-07: both legs stay in India."""

	def test_an_agent_number_outside_india_is_a_clear_error_and_no_call_is_placed(self):
		frappe.db.set_value("User", email("agent"), "mobile_no", ABROAD_PHONE)
		preview = click_to_call.call_preview(self.lead)
		self.assertFalse(preview["can_call"])
		self.assertIn("not an Indian number", preview["error"])
		with self.assertRaises(frappe.ValidationError) as caught:
			self.start()
		self.assertIn("not an Indian number", str(caught.exception))
		self.assertEqual(frappe.db.count("Call Log", {"lead": self.lead}), 0)

	def test_an_agent_with_no_mobile_number_is_told_to_ask_the_company_admin(self):
		frappe.db.set_value("User", email("agent"), "mobile_no", "")
		with self.assertRaises(frappe.ValidationError) as caught:
			self.start()
		self.assertIn("no mobile number", str(caught.exception))
		self.assertEqual(frappe.db.count("Call Log", {"lead": self.lead}), 0)

	def test_a_lead_number_outside_india_is_refused_before_the_agent_is_rung(self):
		client = frappe.db.get_value("Lead", self.lead, "client")
		frappe.db.set_value("Client", client, "phone", ABROAD_PHONE)
		with self.assertRaises(frappe.ValidationError):
			self.start()
		self.assertEqual(frappe.db.count("Call Log", {"lead": self.lead}), 0)

	def test_agent_mobile_accepts_only_an_indian_mobile(self):
		self.assertEqual(click_to_call.agent_mobile(), AGENT_PHONE)
		frappe.db.set_value("User", email("agent"), "mobile_no", ABROAD_PHONE)
		with self.assertRaises(ProviderError):
			click_to_call.agent_mobile()


class TestMediaAnchoringErrorPath(ClickToCallCase):
	"""SOS-P2-07: when the lead cannot be anchored in India after the agent answers, the error is kept and shown."""

	def answered(self):
		log = self.start()["call_log"]
		self.event(frappe.db.get_value("Call Log", log, "call_id"), "in-progress")
		return log

	def test_a_lead_number_that_moved_outside_india_is_not_rung_and_the_agent_is_told(self):
		log = self.start()["call_log"]
		client = frappe.db.get_value("Lead", self.lead, "client")
		frappe.db.set_value("Client", client, "phone", ABROAD_PHONE)  # changed after the agent leg began
		self.event(frappe.db.get_value("Call Log", log, "call_id"), "in-progress")
		status = self.status(log)
		self.assertEqual((status["stage"], status["ended"], status["outcome_needed"]), ("error", True, True))
		self.assertIn("Indian numbers", status["error"])
		self.assertIsNone(self.lead_leg(log))

	def test_the_provider_failing_to_connect_the_second_leg_is_kept_on_the_log(self):
		log = self.start()["call_log"]
		call_id = frappe.db.get_value("Call Log", log, "call_id")
		failure = ProviderError("The provider could not connect the call in India.")
		with mock.patch("sellos.telephony.provider.FakeProvider.place_call", side_effect=failure):
			self.event(call_id, "in-progress")
		row = frappe.db.get_value("Call Log", log, ["state", "bridge_error", "lead_call_id"], as_dict=True)
		self.assertEqual((row.state, row.bridge_error, row.lead_call_id), ("failed", str(failure), None))
		self.assertEqual(self.status(log)["error"], str(failure))
		# Nothing rings the lead afterwards, and the agent still owes the outcome.
		self.event(call_id, "in-progress")
		self.assertIsNone(self.lead_leg(log))
		click_to_call.record_outcome(log, "Wrong number")
		self.assertEqual(click_to_call.pending_outcomes(), [])


class TestOutcomeIsRequired(ClickToCallCase):
	"""SOS-P2-07: an outcome form is required after the call."""

	def ended_call(self):
		log = self.start()["call_log"]
		call_id = frappe.db.get_value("Call Log", log, "call_id")
		self.event(call_id, "in-progress")
		lead_leg = self.lead_leg(log)
		self.event(lead_leg, "in-progress")
		self.event(lead_leg, "completed", duration=30)
		return log

	def test_a_blank_or_unknown_outcome_is_refused_and_the_call_stays_owed(self):
		log = self.ended_call()
		for outcome in ("", None, "Not an outcome"):
			with self.subTest(outcome=outcome), self.assertRaises(frappe.ValidationError):
				click_to_call.record_outcome(log, outcome)
		self.assertEqual([c["call_log"] for c in click_to_call.pending_outcomes()], [log])
		self.assertEqual(frappe.db.count("Lead Activity", {"lead": self.lead, "activity_type": "Call"}), 0)

	def test_an_outcome_that_needs_a_follow_up_needs_its_date(self):
		log = self.ended_call()
		follow = frappe.db.get_value("Call Outcome", {"needs_follow_up": 1, "enabled": 1}, "name")
		if not follow:
			self.skipTest("no outcome needs a follow up on this site")
		with self.assertRaises(frappe.ValidationError):
			click_to_call.record_outcome(log, follow)

	def test_the_outcome_cannot_be_recorded_while_the_call_is_going_or_twice(self):
		log = self.start()["call_log"]
		with self.assertRaises(frappe.ValidationError):
			click_to_call.record_outcome(log, "Wrong number")
		self.assertEqual(click_to_call.pending_outcomes(), [])
		log = self.ended_call()
		click_to_call.record_outcome(log, "Wrong number")
		with self.assertRaises(frappe.ValidationError):
			click_to_call.record_outcome(log, "Wrong number")

	def test_a_call_is_only_its_own_agents(self):
		log = self.ended_call()
		as_user("company_admin")
		with self.assertRaises(frappe.PermissionError):
			click_to_call.call_status(log)
		with self.assertRaises(frappe.PermissionError):
			click_to_call.record_outcome(log, "Wrong number")
		self.assertEqual(click_to_call.pending_outcomes(), [])


class TestRegressionSeed(ClickToCallCase):
	"""SOS-P2-07: the regression data gives the gate agent the mobile number click to call rings first."""

	def test_the_seed_saves_the_agents_indian_mobile_through_the_users_api_and_is_safe_to_run_again(self):
		from sellos.tests import ui_fixtures

		frappe.set_user("Administrator")
		frappe.db.set_value("User", email("agent"), "mobile_no", "")
		ui_fixtures._seed_click_to_call_agent(email("company_admin"), email("agent"))
		saved = frappe.db.get_value("User", email("agent"), "mobile_no")
		self.assertEqual(saved, phones.in_mobile(ui_fixtures.CLICK_TO_CALL_SEED))
		ui_fixtures._seed_click_to_call_agent(email("company_admin"), email("agent"))
		self.assertEqual(frappe.db.get_value("User", email("agent"), "mobile_no"), saved)
		as_user("agent")
		self.assertEqual(click_to_call.agent_mobile(), saved)
