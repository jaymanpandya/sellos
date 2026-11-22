"""SOS-P5-09: the AI against human comparison. AI and human calls are placed through the fake provider and
the production call functions, then every measure is reconciled with the Call Log (read with its own SQL)
and with the calls it drills down to."""

import frappe
from frappe.utils import get_datetime

from sellos.crm import api as crm
from sellos.crm.call_outcomes import INTERESTED, SITE_VISIT_BOOKED, ensure_default_outcomes
from sellos.crm.test_crm import CrmCase, as_user
from sellos.reports import ai_comparison
from sellos.telephony import call_log, settings
from sellos.telephony.base import CallEvent
from sellos.tests import phones
from sellos.tests.ui_fixtures import (
	TELEPHONY_FAKE_ID,
	TELEPHONY_FAKE_TOKEN,
	TELEPHONY_SEED,
	landline_022,
)

START, END = "2031-03-01", "2031-03-14"
BASELINE_START, BASELINE_END = "2031-02-01", "2031-02-28"  # the 28 days before START

# mode, state, seconds, paise, day, outcome, handed over
PLAN = (
	("AI", "completed", 120, 300, "2031-03-02", INTERESTED, 0),
	("AI", "completed", 90, 200, "2031-03-03", SITE_VISIT_BOOKED, 0),
	("AI", "completed", 40, 100, "2031-03-04", "Not interested", 1),
	("AI", "no-answer", 0, 0, "2031-03-05", None, 0),
	("AI", "completed", 60, 150, "2031-03-14", "Complaint", 1),
	("Manual", "completed", 100, 500, "2031-03-06", INTERESTED, 0),
	("Manual", "busy", 0, 0, "2031-03-07", None, 0),
	# the baseline, and the calls just outside it and outside the range
	("Manual", "completed", 200, 1000, "2031-02-10", SITE_VISIT_BOOKED, 0),
	("Manual", "completed", 50, 400, "2031-02-20", INTERESTED, 0),
	("Manual", "failed", 0, 0, "2031-02-21", None, 0),
	("Manual", "completed", 30, 100, "2031-02-28", "Not interested", 0),
	("AI", "completed", 60, 100, "2031-02-15", INTERESTED, 0),
	("Manual", "completed", 10, 100, "2031-01-31", INTERESTED, 0),
	("Manual", "completed", 10, 100, "2031-03-15", INTERESTED, 0),
)


class TestAiComparison(CrmCase):
	"""SOS-P5-09: six measures for AI, human and the human baseline, for any range of dates."""

	def setUp(self):
		as_user("company_admin")
		client = crm.save_client(
			values={"client_name": "P509 caller", "client_type": "Buyer", "phone": phones.in_mobile(5090)}
		)
		lead = crm.save_lead(values={"client": client["name"], "source": "Website"})["lead"]["name"]
		frappe.set_user("Administrator")
		ensure_default_outcomes()
		if not frappe.db.exists("Call Outcome", ai_comparison.COMPLAINT):
			frappe.get_doc({"doctype": "Call Outcome", "outcome_name": ai_comparison.COMPLAINT}).insert()
		frappe.db.set_single_value("Telephony Settings", "provider", "fake")
		as_user("company_admin")
		settings.save_telephony_settings(
			auth_id=TELEPHONY_FAKE_ID,
			auth_token=TELEPHONY_FAKE_TOKEN,
			phone_number=landline_022(TELEPHONY_SEED),
		)
		frappe.set_user("Administrator")
		self.logs = []
		for mode, state, seconds, paise, day, outcome, handed in PLAN:
			log = call_log.place_logged_call(lead, "Service", mode=mode)["log"]
			call_id = frappe.db.get_value("Call Log", log, "call_id")
			call_log.apply_event(CallEvent(call_id, state, duration=seconds), cost=paise, cost_unit="paise")
			frappe.db.set_value(
				"Call Log",
				log,
				{
					"started_on": get_datetime(f"{day} 10:00:00"),
					"outcome": outcome,
					"handed_over": handed,
				},
			)
			self.logs.append(log)
		as_user("company_admin")

	def report(self, *dates):
		return ai_comparison.ai_comparison(*dates)

	def raw(self, mode_is_ai, start, end):
		"""The Call Log table's own counts for a group and two days, with SQL that shares no code with the report."""
		mode = "mode = 'AI'" if mode_is_ai else "coalesce(mode, '') != 'AI'"
		row = frappe.db.sql(
			f"""select count(*), coalesce(sum(state = 'completed' and duration > 0), 0),
				coalesce(sum(state = 'completed' and duration > 0
					and outcome in ('Interested', 'Site visit booked')), 0),
				coalesce(sum(state = 'completed' and duration > 0 and outcome = 'Site visit booked'), 0),
				coalesce(sum(handed_over = 1 and state = 'completed' and duration > 0), 0),
				coalesce(sum(outcome = 'Complaint'), 0), coalesce(sum(cost_rupees), 0)
			from `tabCall Log` where {mode} and date(started_on) between %s and %s""",
			(start, end),
		)[0]
		return [float(v) if i == 6 else int(v) for i, v in enumerate(row)]

	def counts(self, group):
		return [
			group[k]
			for k in ("calls", "connected", "qualified", "site_visits", "handovers", "complaints", "cost")
		]

	def test_the_six_measures_for_ai_human_and_the_baseline(self):
		report = self.report(START, END)
		ai, human, base = report["ai"], report["human"], report["baseline"]
		self.assertEqual((report["baseline_from"], report["baseline_to"]), (BASELINE_START, BASELINE_END))
		self.assertEqual((ai["calls"], ai["connected"], ai["connect_rate"]), (5, 4, 80.0))
		self.assertEqual((ai["qualified"], ai["qualified_rate"]), (2, 50.0))
		self.assertEqual(ai["site_visits"], 1)
		self.assertEqual((ai["cost"], ai["cost_per_qualified"]), (7.5, 3.75))
		self.assertEqual((ai["handovers"], ai["handover_rate"]), (2, 50.0))
		self.assertEqual(ai["complaints"], 1)
		self.assertEqual((human["calls"], human["connected"], human["connect_rate"]), (2, 1, 50.0))
		self.assertEqual(
			(human["qualified"], human["cost_per_qualified"], human["handover_rate"]), (1, 5.0, None)
		)
		self.assertEqual((base["calls"], base["connected"], base["connect_rate"]), (4, 3, 75.0))
		self.assertEqual((base["qualified"], base["qualified_rate"], base["site_visits"]), (2, 66.7, 1))
		self.assertEqual((base["cost_per_qualified"], base["complaints"]), (7.5, 0))
		self.assertEqual(
			report["difference"],
			{
				"connect_rate": 5.0,
				"qualified_rate": -16.7,
				"cost_per_qualified": -3.75,
				"site_visits": 0,
				"complaints": 1,
			},
		)

	def test_every_group_reconciles_with_the_call_log(self):
		report = self.report(START, END)
		self.assertEqual(self.counts(report["ai"]), self.raw(True, START, END))
		self.assertEqual(self.counts(report["human"]), self.raw(False, START, END))
		self.assertEqual(self.counts(report["baseline"]), self.raw(False, BASELINE_START, BASELINE_END))

	def test_the_drill_down_returns_the_calls_each_figure_counts(self):
		for group in ai_comparison.GROUPS:
			whole = ai_comparison.ai_comparison_calls(group, None, START, END)
			figures = self.report(START, END)[group]
			self.assertEqual(len(whole["calls"]), figures["calls"])
			self.assertEqual(whole["totals"], figures)
			for measure in ai_comparison.MEASURES:
				part = ai_comparison.ai_comparison_calls(group, measure, START, END)
				self.assertEqual(len(part["calls"]), figures[measure], (group, measure))
				self.assertTrue(set(c["name"] for c in part["calls"]) <= set(self.logs))

	def test_any_range_and_a_chosen_baseline(self):
		one_day = self.report("2031-03-02", "2031-03-02")
		self.assertEqual((one_day["ai"]["calls"], one_day["human"]["calls"]), (1, 0))
		self.assertEqual(one_day["human"]["connect_rate"], 0.0)
		self.assertEqual((one_day["baseline_from"], one_day["baseline_to"]), ("2031-02-02", "2031-03-01"))
		own = self.report(START, END, "2031-01-31", "2031-01-31")
		self.assertEqual((own["baseline"]["calls"], own["baseline"]["qualified"]), (1, 1))
		self.assertEqual(own["baseline"]["cost_per_qualified"], 1.0)
		empty = self.report("2032-01-01", "2032-01-31")
		self.assertEqual((empty["ai"]["calls"], empty["ai"]["cost_per_qualified"]), (0, None))
		self.assertEqual(empty["difference"]["connect_rate"], 0.0)
		self.assertEqual(empty["difference"]["cost_per_qualified"], None)
		self.assertEqual(self.report("2031-03-14", "2031-03-14")["ai"]["complaints"], 1)

	def test_a_bad_range_or_group_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.report(END, START)
		with self.assertRaises(frappe.ValidationError):
			self.report(START, END, "2031-02-28", "2031-02-01")
		with self.assertRaises(frappe.ValidationError):
			ai_comparison.ai_comparison_calls("robots", None, START, END)
		with self.assertRaises(frappe.ValidationError):
			ai_comparison.ai_comparison_calls("ai", "revenue", START, END)

	def test_only_a_company_admin_may_read_it(self):
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			self.report(START, END)
