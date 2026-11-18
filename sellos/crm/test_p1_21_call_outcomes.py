"""SOS-P1-21: call outcomes, logging a call by hand, the follow up rule, the suggested stage and the
lost reason."""

from unittest.mock import patch

import frappe
from frappe.utils import get_datetime

from sellos.crm import api, call_outcomes, consent, pipeline
from sellos.crm.test_crm import CrmCase, as_user

STATUSES = ("Consented", "Unknown", "Opted out", "Registered DND")
FOLLOW_UP = "2030-03-04 10:30:00"


class CallCase(CrmCase):
	def setUp(self):
		super().setUp()
		pipeline.ensure_default_stages()
		call_outcomes.ensure_defaults()

	def lead_with_status(self, status, user="agent"):
		"""A lead on the first stage whose consent status is `status`, assigned to the user."""
		as_user("company_admin")
		client = api.save_client(values={"client_name": f"P121 {status} Buyer", "client_type": "Buyer"})
		lead = api.save_lead(
			values={
				"client": client["name"],
				"source": "Website",
				"assigned_to": _email(user),
			}
		)["lead"]["name"]
		if status == "Consented":
			api.record_consent(lead, "Consent", "https://example.com/evidence/p121")
		elif status == "Opted out":
			api.record_opt_out(lead, "WhatsApp")
		elif status == "Registered DND":
			api.record_dnd_result(lead, 1)
		self.assertEqual(consent.compute_status(lead), status)
		as_user(user)
		return lead


def _email(key):
	from sellos.testing.users import TEST_USERS

	return TEST_USERS[key]["email"]


class TestTheLists(CallCase):
	"""SOS-P1-21: the seven outcomes and the lost reasons, and what a Company Admin may do to them."""

	def test_the_seven_outcomes_exist_with_their_follow_up_rule_and_suggested_stage(self):
		rows = {row["name"]: row for row in call_outcomes.list_outcomes()}
		self.assertEqual(
			list(rows),
			[
				"Interested",
				"Call back later",
				"Not reachable",
				"Busy",
				"Wrong number",
				"Not interested",
				"Site visit booked",
			],
		)
		self.assertEqual(rows["Interested"]["suggested_stage"], "Qualified")
		self.assertEqual(rows["Site visit booked"]["suggested_stage"], "Site visit booked")
		self.assertEqual(rows["Not interested"]["suggested_stage"], "Closed lost")
		self.assertEqual(rows["Busy"]["suggested_stage"], "")
		self.assertTrue(rows["Call back later"]["needs_follow_up"])
		self.assertFalse(rows["Wrong number"]["needs_follow_up"])

	def test_setting_them_up_again_changes_nothing_and_keeps_an_admins_edit(self):
		as_user("company_admin")
		api.save_call_outcome(
			name="Busy", values={"needs_follow_up": 0, "suggested_stage": "Nurture", "enabled": 0}
		)
		self.assertEqual(call_outcomes.ensure_defaults(), {"outcomes": [], "lost_reasons": []})
		busy = frappe.db.get_value(
			"Call Outcome", "Busy", ["enabled", "needs_follow_up", "suggested_stage"], as_dict=True
		)
		self.assertEqual((busy.enabled, busy.needs_follow_up, busy.suggested_stage), (0, 0, "Nurture"))

	def test_the_lost_reason_list_has_the_standard_reasons(self):
		names = [row["name"] for row in call_outcomes.list_lost_reasons()]
		self.assertEqual(names, list(call_outcomes.DEFAULT_LOST_REASONS))

	def test_a_company_admin_adds_edits_and_disables_and_an_agent_only_reads(self):
		as_user("company_admin")
		made = api.save_call_outcome(
			values={"outcome_name": "Sent brochure", "needs_follow_up": 1, "suggested_stage": "Contacted"}
		)
		self.assertEqual((made["needs_follow_up"], made["suggested_stage"]), (1, "Contacted"))
		api.save_call_outcome(name="Sent brochure", values={"enabled": 0})
		api.save_lost_reason(values={"reason_name": "Chose a rival builder"})
		admin_view = api.list_call_outcomes(include_disabled=1)
		self.assertTrue(admin_view["can_manage"])
		self.assertIn("Sent brochure", [o["name"] for o in admin_view["outcomes"]])
		as_user("agent")
		agent_view = api.list_call_outcomes(include_disabled=1)
		self.assertFalse(agent_view["can_manage"])
		self.assertNotIn("Sent brochure", [o["name"] for o in agent_view["outcomes"]])
		self.assertIn("Chose a rival builder", [r["name"] for r in api.list_lost_reasons()["lost_reasons"]])
		for method, args in (
			(api.save_call_outcome, {"values": {"outcome_name": "Agent made"}}),
			(api.save_lost_reason, {"values": {"reason_name": "Agent made"}}),
			(api.delete_call_outcome, {"name": "Busy"}),
			(api.delete_lost_reason, {"name": "Other"}),
		):
			with self.subTest(method=method.__name__), self.assertRaises(frappe.PermissionError):
				method(**args)

	def test_an_outcome_keeps_its_name(self):
		doc = frappe.get_doc("Call Outcome", "Busy")
		doc.outcome_name = "Engaged"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_an_outcome_or_reason_in_use_or_standard_is_never_deleted(self):
		as_user("company_admin")
		api.save_call_outcome(values={"outcome_name": "P121 Spare outcome"})
		api.save_lost_reason(values={"reason_name": "P121 Spare reason"})
		lead = self.lead_with_status("Unknown", "company_admin")
		api.log_call(lead, "P121 Spare outcome")
		with self.assertRaises(frappe.ValidationError) as used:
			api.delete_call_outcome("P121 Spare outcome")
		self.assertIn("1 call(s)", str(used.exception))
		with self.assertRaises(frappe.ValidationError):
			api.delete_call_outcome("Busy")
		with self.assertRaises(frappe.ValidationError):
			api.delete_lost_reason("Other")
		self.assertEqual(api.delete_lost_reason("P121 Spare reason"), {"deleted": "P121 Spare reason"})
		api.move_lead_stage(lead, "Closed lost", lost_reason="Budget too low")
		with self.assertRaises(frappe.ValidationError) as used:
			api.delete_lost_reason("Budget too low")
		self.assertIn("1 lead(s)", str(used.exception))

	def test_deleting_a_stage_a_outcome_suggests_clears_the_suggestion(self):
		stage = "P121 Spare stage"
		pipeline._make_stage(stage, "Open", 99)
		as_user("company_admin")
		api.save_call_outcome(name="Busy", values={"suggested_stage": stage})
		frappe.delete_doc(pipeline.STAGE, stage, ignore_permissions=True)
		self.assertFalse(frappe.db.get_value("Call Outcome", "Busy", "suggested_stage"))


class TestLoggingACall(CallCase):
	"""SOS-P1-21: an agent logs a call with an outcome, notes and duration as a Call activity."""

	def test_a_call_is_a_call_activity_with_the_outcome_notes_and_duration(self):
		lead = self.lead_with_status("Consented")
		result = api.log_call(lead, "Wrong number", notes="Not the buyer", duration_seconds=95)
		row = frappe.db.get_value(
			"Lead Activity",
			result["activity"],
			["lead", "activity_type", "outcome", "notes", "duration_seconds", "owner"],
			as_dict=True,
		)
		self.assertEqual(
			(row.lead, row.activity_type, row.outcome, row.notes, row.duration_seconds, row.owner),
			(lead, "Call", "Wrong number", "Not the buyer", 95, frappe.session.user),
		)
		self.assertIsNone(result["follow_up"])
		item = next(i for i in api.get_lead(lead)["timeline"] if i["kind"] == "activity")
		self.assertEqual(
			(item["title"], item["outcome"], item["duration_seconds"]), ("Call", "Wrong number", 95)
		)

	def test_a_call_is_logged_whatever_the_consent_status(self):
		for status in STATUSES:
			with self.subTest(status=status):
				lead = self.lead_with_status(status)
				result = api.log_call(lead, "Interested", follow_up_at=FOLLOW_UP)
				self.assertTrue(frappe.db.exists("Lead Activity", result["activity"]))
				self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "New")

	def test_an_outcome_not_on_the_list_or_disabled_is_refused_and_nothing_is_written(self):
		lead = self.lead_with_status("Unknown")
		with self.assertRaises(frappe.MandatoryError):
			api.log_call(lead, "")
		with self.assertRaises(frappe.MandatoryError):
			api.log_call(lead, "Made up")
		as_user("company_admin")
		api.save_call_outcome(name="Busy", values={"enabled": 0})
		as_user("agent")
		with self.assertRaises(frappe.ValidationError):
			api.log_call(lead, "Busy", follow_up_at=FOLLOW_UP)
		with self.assertRaises(frappe.ValidationError):
			api.log_call(lead, "Wrong number", duration_seconds=-5)
		self.assertEqual(frappe.db.count("Lead Activity", {"lead": lead}), 0)

	def test_a_channel_partner_a_client_and_another_agent_cannot_log_a_call(self):
		lead = self.lead_with_status("Unknown")
		for who in ("channel_partner", "client", "basic"):
			as_user(who)
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				api.log_call(lead, "Wrong number")
		self.assertEqual(frappe.db.count("Lead Activity", {"lead": lead}), 0)


class TestTheFollowUpRule(CallCase):
	"""SOS-P1-21: an outcome that needs a follow up asks for its date and time and creates the follow up."""

	def test_an_outcome_that_needs_a_follow_up_is_refused_without_one_and_logs_nothing(self):
		lead = self.lead_with_status("Unknown")
		with self.assertRaises(frappe.MandatoryError) as raised:
			api.log_call(lead, "Call back later", notes="Asked to ring tomorrow")
		self.assertIn("follow up", str(raised.exception))
		self.assertEqual(frappe.db.count("Lead Activity", {"lead": lead}), 0)
		self.assertEqual(frappe.db.count("Lead Task", {"lead": lead}), 0)

	def test_the_follow_up_is_a_lead_task_with_the_date_and_time_for_the_leads_agent(self):
		lead = self.lead_with_status("Consented")
		result = api.log_call(lead, "Call back later", notes="Ring after lunch", follow_up_at=FOLLOW_UP)
		task = frappe.db.get_value(
			"Lead Task",
			result["follow_up"],
			["lead", "title", "due_at", "due_date", "status", "assigned_to"],
			as_dict=True,
		)
		self.assertEqual(task.lead, lead)
		self.assertEqual(task.title, "Follow up: Call back later")
		self.assertEqual(get_datetime(task.due_at), get_datetime(FOLLOW_UP))
		self.assertEqual(str(task.due_date), "2030-03-04")
		self.assertEqual((task.status, task.assigned_to), ("Open", _email("agent")))
		item = next(i for i in api.get_lead(lead)["timeline"] if i["kind"] == "task")
		self.assertEqual(get_datetime(item["when"]), get_datetime(FOLLOW_UP))

	def test_an_outcome_that_needs_none_creates_none_unless_one_is_given(self):
		lead = self.lead_with_status("Unknown")
		self.assertIsNone(api.log_call(lead, "Wrong number")["follow_up"])
		self.assertIsNotNone(api.log_call(lead, "Wrong number", follow_up_at=FOLLOW_UP)["follow_up"])

	def test_the_company_admin_decides_which_outcomes_need_a_follow_up(self):
		lead = self.lead_with_status("Unknown")
		as_user("company_admin")
		api.save_call_outcome(name="Busy", values={"needs_follow_up": 0})
		api.save_call_outcome(name="Wrong number", values={"needs_follow_up": 1})
		as_user("agent")
		self.assertIsNone(api.log_call(lead, "Busy")["follow_up"])
		with self.assertRaises(frappe.MandatoryError):
			api.log_call(lead, "Wrong number")


class TestTheSuggestedStage(CallCase):
	"""SOS-P1-21: the suggested stage is offered and never forced, whatever the consent status."""

	def test_the_suggestion_comes_back_and_the_stage_does_not_move(self):
		for status in STATUSES:
			with self.subTest(status=status):
				lead = self.lead_with_status(status)
				result = api.log_call(lead, "Interested", follow_up_at=FOLLOW_UP)
				self.assertEqual(result["suggested_stage"], "Qualified")
				self.assertFalse(result["moved"])
				self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "New")
				self.assertEqual(frappe.get_doc("Lead", lead).stage_log, [])

	def test_no_suggestion_when_the_outcome_has_none_or_the_lead_is_already_there(self):
		lead = self.lead_with_status("Unknown")
		self.assertIsNone(api.log_call(lead, "Busy", follow_up_at=FOLLOW_UP)["suggested_stage"])
		api.move_lead_stage(lead, "Qualified")
		self.assertIsNone(api.log_call(lead, "Interested", follow_up_at=FOLLOW_UP)["suggested_stage"])

	def test_the_agent_may_take_the_suggestion_or_pick_any_other_stage(self):
		for status in STATUSES:
			with self.subTest(status=status):
				lead = self.lead_with_status(status)
				taken = api.log_call(lead, "Interested", follow_up_at=FOLLOW_UP, stage="Qualified")
				self.assertEqual((taken["moved"], taken["stage"]), (True, "Qualified"))
				other = api.log_call(lead, "Interested", follow_up_at=FOLLOW_UP, stage="Negotiation")
				self.assertEqual((other["moved"], other["stage"]), (True, "Negotiation"))
				self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "Negotiation")

	def test_picking_contacted_keeps_the_pipeline_warning_and_still_goes_ahead(self):
		lead = self.lead_with_status("Opted out")
		result = api.log_call(lead, "Wrong number", stage="Contacted")
		self.assertTrue(result["moved"])
		self.assertIn("Contacted", result["warning"]["message"])

	def test_a_stage_that_does_not_exist_is_refused_before_the_call_is_logged(self):
		lead = self.lead_with_status("Unknown")
		with self.assertRaises(frappe.ValidationError):
			api.log_call(lead, "Wrong number", stage="Nowhere")
		self.assertEqual(frappe.db.count("Lead Activity", {"lead": lead}), 0)

	def test_a_stage_the_company_removed_is_simply_not_suggested(self):
		frappe.db.set_value("Call Outcome", "Interested", "suggested_stage", None)
		lead = self.lead_with_status("Unknown")
		self.assertIsNone(api.log_call(lead, "Interested", follow_up_at=FOLLOW_UP)["suggested_stage"])


class TestTheLostReason(CallCase):
	"""SOS-P1-21: moving a lead to Closed lost asks for a reason from the list a Company Admin edits."""

	def test_closed_lost_is_refused_without_a_reason_and_the_lead_stays_put(self):
		for status in STATUSES:
			with self.subTest(status=status):
				lead = self.lead_with_status(status)
				with self.assertRaises(frappe.MandatoryError) as raised:
					api.move_lead_stage(lead, "Closed lost")
				self.assertIn("lost reason", str(raised.exception))
				self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "New")

	def test_a_reason_from_the_list_moves_it_and_is_recorded_on_the_lead_and_the_log(self):
		for status in STATUSES:
			with self.subTest(status=status):
				lead = self.lead_with_status(status)
				api.move_lead_stage(lead, "Closed lost", lost_reason="Bought elsewhere")
				view = api.get_lead(lead)["pipeline"]
				self.assertEqual((view["stage"], view["lost_reason"]), ("Closed lost", "Bought elsewhere"))
				self.assertEqual(view["log"][0]["lost_reason"], "Bought elsewhere")

	def test_a_reason_that_is_not_on_the_list_or_is_disabled_is_refused(self):
		lead = self.lead_with_status("Unknown")
		with self.assertRaises(frappe.ValidationError):
			api.move_lead_stage(lead, "Closed lost", lost_reason="Made up")
		as_user("company_admin")
		api.save_lost_reason(name="Other", values={"enabled": 0})
		as_user("agent")
		with self.assertRaises(frappe.ValidationError):
			api.move_lead_stage(lead, "Closed lost", lost_reason="Other")
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "New")

	def test_no_other_stage_asks_for_one_and_leaving_closed_lost_clears_it(self):
		lead = self.lead_with_status("Unknown")
		api.move_lead_stage(lead, "Contacted")
		api.move_lead_stage(lead, "Closed won")
		api.move_lead_stage(lead, "Closed lost", lost_reason="Budget too low")
		api.move_lead_stage(lead, "Nurture")
		self.assertEqual(api.get_lead(lead)["pipeline"]["lost_reason"], "")
		# The log keeps the reason the lead was lost for.
		self.assertEqual(
			[row["lost_reason"] for row in api.get_lead(lead)["pipeline"]["log"]][:2], ["", "Budget too low"]
		)

	def test_a_stage_the_company_added_as_a_lost_stage_asks_too(self):
		pipeline._make_stage("P121 Went cold", "Lost", 98)
		lead = self.lead_with_status("Unknown")
		with self.assertRaises(frappe.MandatoryError):
			api.move_lead_stage(lead, "P121 Went cold")
		api.move_lead_stage(lead, "P121 Went cold", lost_reason="No longer looking")
		self.assertEqual(frappe.db.get_value("Lead", lead, "lost_reason"), "No longer looking")

	def test_a_call_can_move_the_lead_to_closed_lost_with_a_reason_and_not_without(self):
		lead = self.lead_with_status("Opted out")
		with self.assertRaises(frappe.MandatoryError):
			api.log_call(lead, "Not interested", stage="Closed lost")
		self.assertEqual(frappe.db.count("Lead Activity", {"lead": lead}), 0)
		result = api.log_call(lead, "Not interested", stage="Closed lost", lost_reason="No longer looking")
		self.assertEqual((result["moved"], result["stage"]), (True, "Closed lost"))
		self.assertEqual(frappe.db.get_value("Lead", lead, "lost_reason"), "No longer looking")


class TestOneOutcomeList(CallCase):
	"""SOS-P1-21: SOS-P2-07's outcome form and SOS-P2-05's Call Log use this list and define none."""

	def test_the_call_activity_links_to_the_call_outcome_doctype(self):
		field = frappe.get_meta("Lead Activity").get_field("outcome")
		self.assertEqual((field.fieldtype, field.options), ("Link", "Call Outcome"))

	def test_no_other_doctype_defines_its_own_outcome_select(self):
		for doctype in frappe.get_all("DocType", filters={"module": "SellOS", "istable": 0}, pluck="name"):
			for field in frappe.get_meta(doctype).fields:
				if field.fieldname in {"outcome", "call_outcome"} and doctype != "Call Outcome":
					self.assertEqual(field.fieldtype, "Link", f"{doctype}.{field.fieldname}")
					self.assertEqual(field.options, "Call Outcome", f"{doctype}.{field.fieldname}")


class TestTheRegressionSeed(CallCase):
	"""SOS-P1-21: the regression data holds the outcome and reason a company added and one logged call."""

	def test_the_seed_is_read_back_and_safe_to_run_twice(self):
		from sellos.tests import ui_fixtures

		as_user("company_admin")
		client = api.save_client(values={"client_name": "Regression Buyer Two", "client_type": "Buyer"})
		lead = api.save_lead(
			values={"client": client["name"], "source": "Walk in", "assigned_to": _email("agent")}
		)["lead"]["name"]
		for _ in range(2):
			ui_fixtures._seed_call_outcomes(_email("company_admin"), _email("agent"))
			outcomes = {o["name"]: o for o in api.list_call_outcomes(include_disabled=1)["outcomes"]}
			brochure = outcomes["Regression Sent brochure"]
			self.assertEqual((brochure["needs_follow_up"], brochure["suggested_stage"]), (1, "Contacted"))
			self.assertIn(
				"Regression Price too high",
				[r["name"] for r in api.list_lost_reasons(include_disabled=1)["lost_reasons"]],
			)
			calls = frappe.get_all(
				"Lead Activity", filters={"lead": lead, "outcome": "Busy"}, fields=["duration_seconds"]
			)
			self.assertEqual([c.duration_seconds for c in calls], [120])
			self.assertEqual(frappe.db.count("Lead Task", {"lead": lead, "title": "Follow up: Busy"}), 1)

	def test_the_cleanup_removes_only_the_gate_lists(self):
		from sellos.tests import ui_fixtures

		as_user("company_admin")
		api.save_call_outcome(values={"outcome_name": "Gate Outcome P121"})
		api.save_lost_reason(values={"reason_name": "Gate Reason P121"})
		with patch.object(frappe.db, "commit"):  # the cleanup commits for the browser. The test rolls back.
			self.assertEqual(ui_fixtures.remove_gate_call_lists(), {"outcomes": 1, "lost_reasons": 1})
		self.assertFalse(frappe.db.exists("Call Outcome", "Gate Outcome P121"))
		self.assertTrue(frappe.db.exists("Call Outcome", "Busy"))
