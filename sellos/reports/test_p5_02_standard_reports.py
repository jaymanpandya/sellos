"""SOS-P5-02: the agent and Company Admin reports. Every record is made in 2021, a year nothing else on the
site touches, and every figure is compared with a hand calculation written beside the data (not computed
from it): the funnel, source performance, agent productivity, ageing, and the reports that are Report
Definitions on the engine (my pipeline, calls and outcomes, deals, commission, payouts, listings, mandates
and the call reports of SOS-P2-11, which are reconciled with `sellos.reports.calls`)."""

import json
from decimal import Decimal

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from sellos.access.roles import AGENT, ensure_roles
from sellos.crm import api as crm
from sellos.reports import calls, engine, standard
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

START, END = "2021-05-01", "2021-05-31"
WIDE_START = "2021-02-01"
OTHER = "p502_agent_two@example.com"

# key: (created, source, stage now, agent key, stages it went through, budget). By hand for May 2021:
# five leads (a to e). Won 1 (a, in Booking), lost 1 (d, in Closed lost), conversion 20.0 percent.
# Reached (the funnel stops at Closed lost, so Nurture is a side stage): New 5 (all), Consent pending 3
# (a, b, d), Contacted 3 (a, b, d), Qualified 2 (a, d), Site visit booked 1 (a), Site visit done 1,
# Negotiation 1, Booking 1, Closed won 0. In it now: Booking 1 (a), Contacted 1 (b), New 1 (c),
# Closed lost 1 (d), Nurture 1 (e). Sources: Website a, b, e = 3 leads, 1 won, 0 lost, 33.3 percent;
# Referral c, d = 2 leads, 0 won, 1 lost, 0.0 percent.
LEADS = {
	"a": ("2021-05-03 09:00:00", "Website", "Booking", "agent", ("New", "Contacted", "Booking"), 5000000),
	"b": ("2021-05-04 09:00:00", "Website", "Contacted", "agent", ("New", "Contacted"), 3000000),
	"c": ("2021-05-05 09:00:00", "Referral", "New", "other", ("New",), 0),
	"d": ("2021-05-06 09:00:00", "Referral", "Closed lost", "other", ("New", "Qualified", "Closed lost"), 0),
	"e": ("2021-05-07 09:00:00", "Website", "Nurture", "agent", ("New", "Nurture"), 1000000),
	"june": ("2021-06-01 00:00:00", "Website", "New", "agent", ("New",), 0),
}
REACHED = {
	"New": 5,
	"Consent pending": 3,
	"Contacted": 3,
	"Qualified": 2,
	"Site visit booked": 1,
	"Site visit done": 1,
	"Negotiation": 1,
	"Booking": 1,
	"Closed won": 0,
}
NOW = {"Booking": 1, "Contacted": 1, "New": 1, "Closed lost": 1, "Nurture": 1}

# By hand: calls c1 (agent, completed, 60 s, 0.10), c2 (no agent, so the lead's owner, no answer, 0 s, 0.20)
# and c3 (the other agent, completed, 30 s, 0.30). In all: 3 calls, 2 connected, 90 s, 0.60 rupees.
CALLS = {
	"c1": ("2021-05-04 10:00:00", "agent", "completed", 60, "0.10", "a", "P502 Interested"),
	"c2": ("2021-05-04 11:00:00", None, "no-answer", 0, "0.20", "a", None),
	"c3": ("2021-05-05 10:00:00", "other", "completed", 30, "0.30", "c", "P502 Interested"),
	"old": ("2021-04-30 10:00:00", "agent", "completed", 99, "9.99", "a", None),
}

# Deals: key: (date, agent, price, commission, approval, status). By hand: three in May. Approved 1
# (8,000,000, commission 160,000), Pending approval 2 (5,000,000 and 1,000,000 = 6,000,000, commission
# 100,000 and 20,000 = 120,000). By agent: the agent 2 (9,000,000), the other agent 1 (5,000,000).
DEALS = {
	"d1": ("2021-05-20", "agent", 8000000, 160000, "Approved", "Active"),
	"d2": ("2021-05-25", "other", 5000000, 100000, "Pending approval", "Active"),
	"d3": ("2021-05-26", "agent", 1000000, 20000, "Pending approval", "Cancelled"),
}
# Payouts: key: (booking date, status, commission due). By hand: Due 2 (700.50 + 99.50 = 800.00), Paid 1 (50.00).
PAYOUTS = (("2021-05-21", "Due", "700.50"), ("2021-05-22", "Due", "99.50"), ("2021-05-23", "Paid", "50.00"))

# Ageing on 31 May 2021 for 1 February to 31 May. Listings by creation, asking price:
# 20 May (11 days) 0 to 30; 10 April (51) 31 to 60; 10 March (82) 61 to 90, 2 February (118) over 90, published.
# 31 January is before the dates. Asking: 5,000,000, 4,000,000, 3,000,000, 2,000,000.
LISTINGS = (
	("2021-05-20", 5000000, 0),
	("2021-04-10", 4000000, 0),
	("2021-03-10", 3000000, 0),
	("2021-02-02", 2000000, 1),
	("2021-01-31", 1000000, 0),
)
# Mandates: start, term, status. 30 May Signed 11 months (30 days: 0 to 30, not expired); 20 April Draft
# (41 days: 31 to 60); 10 February Signed 1 month (110 days: over 90, expired on 10 March).
MANDATES = (("2021-05-30", 11, "Signed"), ("2021-04-20", 6, "Draft"), ("2021-02-10", 1, "Signed"))


def email(key):
	return TEST_USERS[key]["email"]


def raw(doctype, name, **values):
	"""A record written straight to its table, for data whose own checks (a unit, a seller) are not the point."""
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.name = name
	doc.creation = doc.modified = values.get("creation") or now_datetime()
	doc.owner = doc.modified_by = "Administrator"
	doc.db_insert()
	return name


class TestStandardReports(IntegrationTestCase):
	"""SOS-P5-02: every standard report reconciles with the raw records and filters by date."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		engine.ensure_default_definitions()
		other = frappe.get_doc(
			{
				"doctype": "User",
				"email": OTHER,
				"first_name": "P502 Agent Two",
				"send_welcome_email": 0,
				"roles": [{"role": AGENT}],
			}
		)
		other.flags.ignore_permissions = True
		other.insert()
		if not frappe.db.exists("Call Outcome", "P502 Interested"):
			frappe.get_doc({"doctype": "Call Outcome", "outcome_name": "P502 Interested"}).insert()
		self.agents = {"agent": email("agent"), "other": OTHER, None: None}
		frappe.set_user(email("company_admin"))
		self.leads = {}
		for seed, (key, (created, source, stage, who, path, budget)) in enumerate(LEADS.items(), start=5020):
			client = crm.save_client(
				values={"client_name": f"P502 {key}", "client_type": "Buyer", "phone": phones.in_mobile(seed)}
			)
			name = crm.save_lead(
				values={"client": client["name"], "source": source, "assigned_to": self.agents[who]}
			)["lead"]["name"]
			frappe.db.set_value(
				"Lead",
				name,
				{"creation": created, "stage": stage, "budget_to": budget},
				update_modified=False,
			)
			for at, step in enumerate(path, start=1):
				raw(
					"Lead Stage Change",
					f"{name}-{at}",
					parent=name,
					parenttype="Lead",
					parentfield="stage_log",
					idx=at,
					to_stage=step,
				)
			self.leads[key] = name
		frappe.set_user("Administrator")
		self.phone_forms = [
			f for seed in range(5020, 5020 + len(LEADS)) for f in phones.forms(phones.in_mobile(seed))
		]
		for key, (started, who, state, seconds, rupees, lead, outcome) in CALLS.items():
			frappe.get_doc(
				{
					"doctype": "Call Log",
					"lead": self.leads[lead],
					"agent": self.agents[who],
					"provider": "fake",
					"call_id": f"p502-{key}",
					"purpose": "Service",
					"state": state,
					"duration": seconds,
					"cost_rupees": rupees,
					"started_on": started,
					"outcome": outcome,
				}
			).insert(ignore_permissions=True)
		client = frappe.db.get_value("Lead", self.leads["a"], "client")
		for key, (day, who, price, commission, approval, status) in DEALS.items():
			raw(
				"Deal",
				f"P502-{key}",
				client=client,
				lead=self.leads["a"],
				price=price,
				commission_amount=commission,
				deal_date=day,
				booked_by=self.agents[who],
				approval_status=approval,
				deal_status=status,
			)
		for at, (day, status, due) in enumerate(PAYOUTS):
			raw("Commission Payout", f"P502-PAY-{at}", booking_date=day, status=status, commission_due=due)
		for at, (day, asking, published) in enumerate(LISTINGS):
			raw(
				"Listing",
				f"P502-LST-{at}",
				title=f"P502 listing {at}",
				listing_type="Direct",
				asking_price=asking,
				published=published,
				creation=f"{day} 10:00:00",
			)
		for at, (day, term, status) in enumerate(MANDATES):
			raw(
				"Mandate",
				f"P502-MND-{at}",
				lead=self.leads["a"],
				mandate_type="Open",
				start_date=day,
				term_months=term,
				fee_percent=1,
				status=status,
			)
		visits = (("2021-05-10 10:00:00", "Done"), ("2021-05-11 10:00:00", "Scheduled"))
		for at, (when, status) in enumerate(visits):
			raw(
				"Site Visit",
				f"P502-SV-{at}",
				lead=self.leads["a"],
				project_name="P502",
				visit_datetime=when,
				status=status,
				agent=email("agent"),
			)
		for at, (day, status) in enumerate((("2021-05-12", "Done"), ("2021-05-13", "Open"))):
			raw(
				"Lead Task",
				f"P502-TASK-{at}",
				lead=self.leads["a"],
				title="P502",
				due_date=day,
				status=status,
				assigned_to=email("agent"),
			)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def as_user(self, who, function, **kwargs):
		frappe.set_user(email(who))
		try:
			return function(**kwargs)
		finally:
			frappe.set_user("Administrator")

	def admin(self, function, start=START, end=END):
		return self.as_user("company_admin", function, from_date=start, to_date=end)

	def groups(self, who, report, start=START, end=END):
		result = self.as_user(who, engine.run_report, report=report, from_date=start, to_date=end)
		return {r["group"]: (r["count"], r["total"]) for r in result["rows"]}, result

	def test_the_funnel_is_the_hand_calculation(self):
		result = self.admin(standard.lead_funnel)
		self.assertEqual(result["totals"], {"leads": 5, "won": 1, "lost": 1, "conversion": 20.0})
		rows = {r["stage"]: r for r in result["rows"]}
		self.assertEqual({s: rows[s]["reached"] for s in REACHED}, REACHED)
		self.assertEqual({s: rows[s]["in_stage"] for s in rows if rows[s]["in_stage"]}, NOW)
		self.assertEqual(rows["Qualified"]["conversion"], 40.0)
		self.assertEqual(rows["Qualified"]["step_conversion"], 66.7)
		self.assertIsNone(rows["Closed lost"]["reached"])
		self.assertIsNone(rows["Nurture"]["reached"])
		# what the Lead table holds, read with SQL that shares no code with the report
		count = frappe.db.sql(
			"select count(*) from `tabLead` where archived = 0 and pipeline = 'Buyer'"
			" and date(creation) between %s and %s and name in %s",
			(START, END, tuple(self.leads.values())),
		)[0][0]
		self.assertEqual(count, result["totals"]["leads"])

	def test_source_performance_is_the_hand_calculation(self):
		result = self.admin(standard.source_performance)
		rows = {r["source"]: r for r in result["rows"]}
		self.assertEqual(
			(rows["Website"]["leads"], rows["Website"]["won"], rows["Website"]["lost"]), (3, 1, 0)
		)
		self.assertEqual(rows["Website"]["conversion"], 33.3)
		self.assertEqual(
			(rows["Referral"]["leads"], rows["Referral"]["won"], rows["Referral"]["lost"]), (2, 0, 1)
		)
		self.assertEqual(rows["Referral"]["conversion"], 0.0)
		self.assertEqual(sum(r["leads"] for r in result["rows"]), result["totals"]["leads"])
		self.assertEqual(result["totals"], {"leads": 5, "won": 1, "lost": 1, "conversion": 20.0})

	def test_agent_productivity_is_the_hand_calculation(self):
		result = self.admin(standard.agent_productivity)
		rows = {r["agent"]: r for r in result["rows"]}
		mine = rows[email("agent")]
		self.assertEqual(
			(
				mine["leads"],
				mine["calls"],
				mine["connected"],
				mine["talk_seconds"],
				mine["visits_done"],
				mine["follow_ups_done"],
				mine["deals"],
			),
			(3, 2, 1, 60, 1, 1, 1),
		)
		self.assertEqual(mine["connect_rate"], 50.0)
		other = rows[OTHER]
		self.assertEqual(
			(other["leads"], other["calls"], other["connected"], other["talk_seconds"]), (2, 1, 1, 30)
		)
		self.assertEqual(other["deals"], 1)  # d2; the cancelled d3 is the agent's and counts for no one
		self.assertEqual(
			result["totals"],
			{
				"leads": 5,
				"calls": 3,
				"connected": 2,
				"talk_seconds": 90,
				"visits_done": 1,
				"follow_ups_done": 1,
				"deals": 2,
			},
		)
		self.assertEqual(
			frappe.db.sql(
				"select count(*) from `tabCall Log` where call_id like 'p502-%%' and date(started_on) between %s and %s",
				(START, END),
			)[0][0],
			result["totals"]["calls"],
		)

	def test_ageing_is_the_hand_calculation(self):
		result = self.admin(standard.ageing_report, start=WIDE_START)
		listings = {b["band"]: b for b in result["listings"]["bands"]}
		self.assertEqual(result["listings"]["total"], 4)
		self.assertEqual(
			[(b, listings[b]["count"], listings[b]["asking"]) for b in listings],
			[
				("0 to 30 days", 1, 5000000.0),
				("31 to 60 days", 1, 4000000.0),
				("61 to 90 days", 1, 3000000.0),
				("Over 90 days", 1, 2000000.0),
			],
		)
		self.assertEqual(listings["Over 90 days"]["published"], 1)
		mandates = {b["band"]: b for b in result["mandates"]["bands"]}
		self.assertEqual(result["mandates"]["total"], 3)
		self.assertEqual(
			[(b, mandates[b]["count"], mandates[b]["signed"], mandates[b]["expired"]) for b in mandates],
			[
				("0 to 30 days", 1, 1, 0),
				("31 to 60 days", 1, 0, 0),
				("61 to 90 days", 0, 0, 0),
				("Over 90 days", 1, 1, 1),
			],
		)

	def test_every_business_report_filters_by_date(self):
		empty = ("2019-01-01", "2019-01-31")
		self.assertEqual(self.admin(standard.lead_funnel, *empty)["totals"]["leads"], 0)
		self.assertEqual(self.admin(standard.source_performance, *empty)["rows"], [])
		self.assertEqual(self.admin(standard.agent_productivity, *empty)["rows"], [])
		self.assertEqual(self.admin(standard.ageing_report, *empty)["listings"]["total"], 0)
		self.assertEqual(self.admin(standard.ageing_report, *empty)["mandates"]["total"], 0)
		self.assertEqual(self.admin(standard.lead_funnel, "2021-06-01", "2021-06-30")["totals"]["leads"], 1)
		with self.assertRaises(frappe.ValidationError):
			self.admin(standard.lead_funnel, "2021-06-01", "2021-05-01")

	def test_an_agent_reads_their_own_pipeline_calls_follow_ups_and_visits(self):
		stages, result = self.groups("agent", "my-pipeline")
		self.assertEqual(
			stages, {"Booking": (1, 5000000.0), "Contacted": (1, 3000000.0), "Nurture": (1, 1000000.0)}
		)
		self.assertEqual(result["totals"], {"count": 3, "total": 9000000.0})
		self.assertEqual(result["scope"], "own")
		self.assertEqual(
			self.groups("agent", "follow-ups-by-status")[0], {"Done": (1, None), "Open": (1, None)}
		)
		self.assertEqual(
			self.groups("agent", "site-visits-by-status")[0], {"Done": (1, None), "Scheduled": (1, None)}
		)
		outcomes, _result = self.groups("agent", "calls-by-outcome")
		self.assertEqual(
			sum(count for count, _t in outcomes.values()), 2
		)  # c1 and c2, never the other agent's c3

	def test_the_admin_only_reports_are_closed_to_an_agent_and_a_sales_manager(self):
		for key in ("call-cost-by-agent", "deals-by-approval", "payouts-by-status", "listings-by-type"):
			for who in ("agent", "sales_manager"):
				with self.subTest(report=key, who=who), self.assertRaises(frappe.PermissionError):
					self.groups(who, key)
		for function in (
			standard.lead_funnel,
			standard.source_performance,
			standard.agent_productivity,
			standard.ageing_report,
		):
			for who in ("agent", "sales_manager", "channel_partner", "client", "platform_admin"):
				with (
					self.subTest(report=function.__name__, who=who),
					self.assertRaises(frappe.PermissionError),
				):
					self.as_user(who, function)

	def test_the_deal_pipeline_and_commission_are_the_hand_calculation(self):
		approval, _r = self.groups("company_admin", "deals-by-approval")
		self.assertEqual(approval, {"Approved": (1, 8000000.0), "Pending approval": (2, 6000000.0)})
		commission, _r = self.groups("company_admin", "commission-by-approval")
		self.assertEqual(commission, {"Approved": (1, 160000.0), "Pending approval": (2, 120000.0)})
		by_agent, _r = self.groups("company_admin", "deals-by-agent")
		self.assertEqual(by_agent, {email("agent"): (2, 9000000.0), OTHER: (1, 5000000.0)})
		payouts, _r = self.groups("company_admin", "payouts-by-status")
		self.assertEqual(payouts, {"Due": (2, 800.0), "Paid": (1, 50.0)})

	def test_listings_and_mandates_are_the_hand_calculation(self):
		listings, _r = self.groups("company_admin", "listings-by-type", start=WIDE_START)
		self.assertEqual(listings, {"Direct": (4, 14000000.0)})
		mandates, _r = self.groups("company_admin", "mandates-by-status", start=WIDE_START)
		self.assertEqual(mandates, {"Signed": (2, None), "Draft": (1, None)})

	def test_the_call_reports_are_definitions_that_reconcile_with_the_call_report(self):
		keys = {r["key"] for r in self.as_user("company_admin", engine.list_reports)["reports"]}
		self.assertTrue(
			{"call-cost-by-agent", "call-cost-by-purpose", "talk-time-by-agent", "calls-by-state"} <= keys
		)
		report = self.admin(calls.call_report)
		_cost, cost_result = self.groups("company_admin", "call-cost-by-agent")
		self.assertEqual(cost_result["totals"]["total"], report["totals"]["cost"])
		self.assertEqual(cost_result["totals"]["total"], float(Decimal("0.60")))
		by_purpose, _r = self.groups("company_admin", "call-cost-by-purpose")
		self.assertEqual(by_purpose, {"Service": (3, 0.6)})
		self.assertEqual(
			self.groups("company_admin", "talk-time-by-agent")[1]["totals"]["total"],
			report["totals"]["talk_seconds"],
		)
		states, _r = self.groups("company_admin", "calls-by-state")
		self.assertEqual(states, {"completed": (2, None), "no-answer": (1, None)})
		self.assertEqual(sum(c for c, _t in states.values()), report["totals"]["calls"])

	def test_every_report_in_the_task_is_a_definition_or_a_method_and_no_figure_holds_a_phone_number(self):
		listed = {
			"my pipeline": "my-pipeline",
			"calls and outcomes": "calls-by-outcome",
			"follow ups due": "follow-ups-by-status",
			"site visits": "site-visits-by-status",
			"deal pipeline": "deals-by-approval",
			"commission": "commission-by-approval",
			"call reports": "call-cost-by-agent",
			"listing ageing": "listings-by-type",
			"mandate ageing": "mandates-by-status",
			"agent productivity": "deals-by-agent",
			"source performance": "leads-by-source",
		}
		for title, key in listed.items():
			with self.subTest(report=title):
				self.assertTrue(frappe.db.exists("Report Definition", key))
		for function in (
			standard.lead_funnel,
			standard.source_performance,
			standard.agent_productivity,
			standard.ageing_report,
		):
			text = json.dumps(self.admin(function))
			for form in self.phone_forms:
				self.assertNotIn(form, text)
