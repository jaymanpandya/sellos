"""SOS-P5-01: the report engine. Leads and calls are made in 2020, a year nothing else on the site touches,
and every figure is compared with a hand calculation written beside the data (not computed from it). The
nightly table is checked row by row, a Company Admin, a Sales Manager and an Agent each read their own
scope, and every figure is reconciled with the records its drill down lists."""

import json
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from sellos.access.roles import AGENT, ensure_roles
from sellos.crm import api as crm
from sellos.reports import engine
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

START, END = "2020-03-01", "2020-03-31"
SECOND_AGENT = "p501_agent_two@example.com"

# key: (created, source, stage, agent key, archived). The hand calculation for START to END is under it.
LEADS = {
	"a": ("2020-03-02 09:00:00", "Website", "New", "agent", 0),
	"b": ("2020-03-02 17:30:00", "Website", "Contacted", "agent", 0),
	"c": ("2020-03-10 12:00:00", "Referral", "New", "agent", 0),
	"d": ("2020-03-15 10:00:00", "Website", "New", "other", 0),
	"e": ("2020-03-31 23:30:00", "Referral", "Qualified", None, 0),
	"before": ("2020-02-29 23:59:59", "Website", "New", "agent", 0),
	"after": ("2020-04-01 00:00:00", "Website", "New", "agent", 0),
	"archived": ("2020-03-05 10:00:00", "Website", "New", "agent", 1),
}
# By hand, for 1 to 31 March: five leads (a to e). Stage: New 3 (a, c, d), Contacted 1 (b), Qualified 1 (e).
# Source: Website 3 (a, b, d), Referral 2 (c, e). The agent owns a, b and c: New 2, Contacted 1.
# The second agent owns d, and e is nobody's. The days with leads are 2, 10, 15 and 31 March.
STAGES = {"New": 3, "Contacted": 1, "Qualified": 1}
SOURCES = {"Website": 3, "Referral": 2}

# key: (started, purpose, state, seconds, rupees). By hand for March: Service 0.10 + 0.20 = 0.30 over two
# calls, Transactional 1.25 over one, and 0.10 + 0.20 + 1.25 = 1.55 in all. The February call is outside.
CALLS = {
	"s1": ("2020-03-04 10:00:00", "Service", "completed", 60, "0.10"),
	"s2": ("2020-03-20 11:00:00", "Service", "completed", 30, "0.20"),
	"t1": ("2020-03-31 22:00:00", "Transactional", "no-answer", 0, "1.25"),
	"old": ("2020-02-28 10:00:00", "Service", "completed", 10, "9.99"),
}


def email(key):
	return TEST_USERS[key]["email"]


class ReportCase(IntegrationTestCase):
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
				"email": SECOND_AGENT,
				"first_name": "P501 Agent Two",
				"send_welcome_email": 0,
				"roles": [{"role": AGENT}],
			}
		)
		other.flags.ignore_permissions = True
		other.insert()
		frappe.set_user(email("company_admin"))
		self.team = frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P501 Team",
				"manager": email("sales_manager"),
				"members": [{"agent": email("agent")}],
			}
		).insert()
		self.leads = {}
		for seed, (key, (created, source, stage, who, archived)) in enumerate(LEADS.items(), start=5010):
			client = crm.save_client(
				values={
					"client_name": f"P501 Buyer {key}",
					"client_type": "Buyer",
					"phone": phones.in_mobile(seed),
				}
			)
			values = {"client": client["name"], "source": source}
			if who:
				values["assigned_to"] = SECOND_AGENT if who == "other" else email(who)
			name = crm.save_lead(values=values)["lead"]["name"]
			frappe.db.set_value(
				"Lead",
				name,
				{"creation": created, "stage": stage, "archived": archived},
				update_modified=False,
			)
			self.leads[key] = name
		frappe.set_user("Administrator")
		self.calls = {}
		for key, (started, purpose, state, seconds, rupees) in CALLS.items():
			self.calls[key] = (
				frappe.get_doc(
					{
						"doctype": "Call Log",
						"lead": self.leads["a"],
						"provider": "fake",
						"call_id": f"p501-{key}",
						"purpose": purpose,
						"state": state,
						"duration": seconds,
						"cost_rupees": rupees,
						"started_on": started,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		self.phone_forms = [
			form for seed in range(5010, 5010 + len(LEADS)) for form in phones.forms(phones.in_mobile(seed))
		]

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def run_as(self, who, report, **kwargs):
		frappe.set_user(email(who))
		try:
			return engine.run_report(
				report, from_date=kwargs.pop("from_date", START), to_date=kwargs.pop("to_date", END), **kwargs
			)
		finally:
			frappe.set_user("Administrator")

	def drill_as(self, who, report, **kwargs):
		frappe.set_user(email(who))
		try:
			return engine.report_records(report, from_date=START, to_date=END, **kwargs)
		finally:
			frappe.set_user("Administrator")

	@staticmethod
	def counts(result):
		return {row["group"]: row["count"] for row in result["rows"]}

	def refresh(self, report):
		frappe.set_user(email("company_admin"))
		engine.refresh_report(report)
		frappe.set_user("Administrator")


class TestReportsAreConfiguration(ReportCase):
	"""SOS-P5-01: a report is a Report Definition, and the engine refuses configuration it cannot honour."""

	def save(self, **values):
		frappe.set_user(email("company_admin"))
		try:
			return engine.save_report_definition(
				{"report_key": "p501-own", "title": "P501 Own", "source_doctype": "Lead", **values}
			)
		finally:
			frappe.set_user("Administrator")

	def test_the_default_reports_are_definitions_and_making_them_again_changes_nothing(self):
		keys = {d["report_key"] for d in engine.DEFAULT_DEFINITIONS}
		self.assertEqual(set(frappe.get_all("Report Definition", pluck="name")) & keys, keys)
		frappe.db.set_value("Report Definition", "leads-by-stage", "title", "Our stages")
		self.assertEqual(engine.ensure_default_definitions(), [])
		self.assertEqual(frappe.db.get_value("Report Definition", "leads-by-stage", "title"), "Our stages")

	def test_a_company_admin_defines_a_report_without_code(self):
		made = self.save(group_by="assigned_to")
		self.assertEqual(made["group_label"], "Agent")
		result = self.run_as("company_admin", "p501-own")
		self.assertEqual(result["totals"]["count"], 5)
		self.assertEqual(
			{r["label"]: r["count"] for r in result["rows"]},
			{"Gate Agent": 3, "P501 Agent Two": 1, "Not set": 1},
		)

	def test_a_report_with_no_group_is_one_total(self):
		self.save()
		result = self.run_as("company_admin", "p501-own")
		self.assertEqual(result["rows"], [{"group": "", "label": "All", "count": 5, "total": None}])

	def test_fixed_filters_narrow_every_figure_and_its_records(self):
		self.save(group_by="stage", filters={"source": "Referral"})
		result = self.run_as("company_admin", "p501-own")
		self.assertEqual(self.counts(result), {"New": 1, "Qualified": 1})
		self.assertEqual(self.drill_as("company_admin", "p501-own")["total"], 2)

	def test_configuration_the_source_does_not_allow_is_refused(self):
		for values in (
			{"report_key": "Bad Key"},
			{"source_doctype": "User"},
			{"group_by": "notes"},
			{"group_by": "stage", "measure": "Sum", "measure_field": "notes"},
			{"group_by": "stage", "measure": "Sum"},
			{"filters": {"notes": "x"}},
			{"filters": "not json"},
			{"filters": ["stage"]},
		):
			with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
				self.save(**values)

	def test_changing_the_configuration_drops_the_stored_table(self):
		self.refresh("leads-by-stage")
		self.assertTrue(frappe.db.count("Report Summary", {"report": "leads-by-stage"}))
		frappe.set_user(email("company_admin"))
		engine.save_report_definition({"group_by": "source"}, report="leads-by-stage")
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.count("Report Summary", {"report": "leads-by-stage"}), 0)
		self.assertIsNone(frappe.db.get_value("Report Definition", "leads-by-stage", "summarised_to"))
		self.assertEqual(self.counts(self.run_as("company_admin", "leads-by-stage")), SOURCES)

	def test_only_a_company_admin_defines_refreshes_or_reads_the_definitions(self):
		for who in ("agent", "sales_manager"):
			frappe.set_user(email(who))
			with self.subTest(who=who):
				with self.assertRaises(frappe.PermissionError):
					engine.save_report_definition(
						{"report_key": "p501-x", "title": "X", "source_doctype": "Lead"}
					)
				with self.assertRaises(frappe.PermissionError):
					engine.refresh_report("leads-by-stage")
				self.assertFalse(frappe.has_permission("Report Definition", "read"))
		frappe.set_user("Administrator")
		meta = frappe.get_meta("Report Definition")
		self.assertEqual({p.role for p in meta.permissions}, {"SellOS Company Admin"})
		self.assertFalse(any(p.delete or p.export for p in meta.permissions))
		# No SellOS role holds a permission on the summary table. The one System Manager row is explicit and
		# read only: without it a newer Frappe adds a System Manager row with write, delete and export.
		summary = frappe.get_meta("Report Summary").permissions
		self.assertLessEqual({p.role for p in summary}, {"System Manager"})
		self.assertFalse(any(p.write or p.create or p.delete or p.export or p.share for p in summary))


class TestFiguresMatchAHandCalculation(ReportCase):
	"""SOS-P5-01: every figure against the numbers worked out by hand at the top of this file."""

	def test_leads_by_stage_and_by_source(self):
		stage = self.run_as("company_admin", "leads-by-stage")
		self.assertEqual(self.counts(stage), STAGES)
		self.assertEqual(stage["totals"]["count"], 5)
		self.assertEqual(self.counts(self.run_as("company_admin", "leads-by-source")), SOURCES)

	def test_both_end_days_are_included_and_the_days_outside_are_not(self):
		self.assertEqual(
			self.run_as("company_admin", "leads-by-stage", from_date="2020-03-31", to_date="2020-03-31")[
				"totals"
			]["count"],
			1,
		)
		self.assertEqual(
			self.run_as("company_admin", "leads-by-stage", from_date="2020-03-02", to_date="2020-03-02")[
				"totals"
			]["count"],
			2,
		)
		self.assertEqual(
			self.run_as("company_admin", "leads-by-stage", from_date="2020-02-29", to_date="2020-04-01")[
				"totals"
			]["count"],
			7,
		)
		with self.assertRaises(frappe.ValidationError):
			self.run_as("company_admin", "leads-by-stage", from_date=END, to_date=START)

	def test_an_archived_lead_is_not_counted(self):
		self.assertEqual(
			self.run_as("company_admin", "leads-by-stage", from_date="2020-03-05", to_date="2020-03-05")[
				"rows"
			],
			[],
		)

	def test_a_sum_is_exact(self):
		result = self.run_as("company_admin", "call-cost-by-purpose")
		self.assertEqual(
			{r["group"]: r["total"] for r in result["rows"]}, {"Service": 0.30, "Transactional": 1.25}
		)
		self.assertEqual(self.counts(result), {"Service": 2, "Transactional": 1})
		self.assertEqual(result["totals"]["total"], 1.55)
		self.assertEqual(result["report"]["unit"], "rupees")

	def test_the_default_range_is_the_last_thirty_days_ending_today(self):
		frappe.set_user(email("company_admin"))
		result = engine.run_report("leads-by-stage")
		frappe.set_user("Administrator")
		self.assertEqual((result["from_date"], result["to_date"]), (str(add_days(today(), -29)), today()))


class TestSummaryTables(ReportCase):
	"""SOS-P5-01: the nightly summary table holds one row per day and group, and a Company Admin's figures
	for the days it holds are added up from it."""

	def rows(self, report="leads-by-stage"):
		return {
			(str(r.summary_date), r.group_value): (r.record_count, r.total)
			for r in frappe.get_all(
				"Report Summary",
				filters={"report": report, "summary_date": ["between", [START, END]]},
				fields=["summary_date", "group_value", "record_count", "total"],
			)
		}

	def test_the_nightly_refresh_writes_one_row_per_day_and_group(self):
		self.assertEqual(self.rows(), {})
		engine.refresh_all_summaries()
		# By hand: 2 March New (a) and Contacted (b), 10 March New (c), 15 March New (d), 31 March Qualified (e).
		self.assertEqual(
			self.rows(),
			{
				("2020-03-02", "New"): (1, 0),
				("2020-03-02", "Contacted"): (1, 0),
				("2020-03-10", "New"): (1, 0),
				("2020-03-15", "New"): (1, 0),
				("2020-03-31", "Qualified"): (1, 0),
			},
		)
		self.assertEqual(
			frappe.db.get_value("Report Definition", "leads-by-stage", "summarised_to"),
			add_days(frappe.utils.getdate(today()), -1),
		)
		self.assertTrue(frappe.db.get_value("Report Definition", "leads-by-stage", "last_refreshed"))

	def test_a_refresh_replaces_the_old_rows_and_a_sum_is_stored(self):
		engine.refresh_all_summaries()
		engine.refresh_all_summaries()
		self.assertEqual(len(self.rows()), 5)
		self.assertEqual(
			self.rows("call-cost-by-purpose"),
			{
				("2020-03-04", "Service"): (1, 0.10),
				("2020-03-20", "Service"): (1, 0.20),
				("2020-03-31", "Transactional"): (1, 1.25),
			},
		)

	def test_the_summary_gives_the_same_figures_as_the_records(self):
		before = {
			k: self.run_as("company_admin", k)
			for k in ("leads-by-stage", "leads-by-source", "call-cost-by-purpose")
		}
		engine.refresh_all_summaries()
		for key, expected in before.items():
			with self.subTest(report=key):
				self.assertEqual(self.run_as("company_admin", key)["rows"], expected["rows"])
				self.assertEqual(self.run_as("company_admin", key)["totals"], expected["totals"])

	def test_a_company_admin_reads_the_table_for_the_days_it_holds(self):
		"""Proved by changing a stored row: the figure follows the table, not the records."""
		engine.refresh_all_summaries()
		row = frappe.get_all(
			"Report Summary", filters={"report": "leads-by-stage", "group_value": "Qualified"}, pluck="name"
		)[0]
		frappe.db.set_value("Report Summary", row, "record_count", 7)
		self.assertEqual(self.counts(self.run_as("company_admin", "leads-by-stage"))["Qualified"], 7)
		# A reader with a narrower scope, and a Company Admin filtering by agent, read the records.
		self.assertNotIn("Qualified", self.counts(self.run_as("agent", "leads-by-stage")))
		self.assertNotIn(
			"Qualified", self.counts(self.run_as("company_admin", "leads-by-stage", agent=email("agent")))
		)

	def test_today_is_read_from_the_records_until_the_next_refresh(self):
		engine.refresh_all_summaries()
		before = self.counts(
			self.run_as("company_admin", "leads-by-source", from_date=START, to_date=today())
		)
		frappe.set_user(email("company_admin"))
		client = crm.save_client(
			values={"client_name": "P501 Today", "client_type": "Buyer", "phone": phones.in_mobile(5099)}
		)
		crm.save_lead(values={"client": client["name"], "source": "Website"})
		frappe.set_user("Administrator")
		after = self.counts(self.run_as("company_admin", "leads-by-source", from_date=START, to_date=today()))
		self.assertEqual(after["Website"], before["Website"] + 1)  # today's lead is not in the table yet
		self.assertEqual(
			self.counts(self.run_as("company_admin", "leads-by-source", from_date=START, to_date=END)),
			SOURCES,
		)

	def test_a_night_that_was_missed_is_filled_from_the_records(self):
		engine.refresh_all_summaries()
		frappe.db.set_value("Report Definition", "leads-by-stage", "summarised_to", "2020-03-12")
		# 2020-03-15 and 2020-03-31 are past the summary's end and come from the records.
		self.assertEqual(self.counts(self.run_as("company_admin", "leads-by-stage")), STAGES)

	def test_a_disabled_report_is_not_refreshed_and_one_failure_does_not_stop_the_rest(self):
		frappe.db.set_value("Report Definition", "leads-by-source", "enabled", 0)
		done = {d["report"] for d in engine.refresh_all_summaries()}
		self.assertNotIn("leads-by-source", done)
		self.assertIn("leads-by-stage", done)
		real = engine.refresh_summary

		def flaky(name):
			if name == "leads-by-stage":
				raise RuntimeError("boom")
			return real(name)

		with patch.object(engine, "refresh_summary", flaky), patch.object(frappe, "log_error") as log:
			done = {d["report"] for d in engine.refresh_all_summaries()}
		self.assertNotIn("leads-by-stage", done)
		self.assertIn("site-visits-by-status", done)
		log.assert_called_once()

	def test_the_refresh_is_scheduled_every_night(self):
		from sellos import hooks

		self.assertIn("sellos.reports.engine.refresh_all_summaries", hooks.scheduler_events["daily"])


class TestRoleScope(ReportCase):
	"""SOS-P5-01: role scope limits the rows, the same way it limits the screens."""

	def test_an_agent_reads_only_their_own_leads(self):
		result = self.run_as("agent", "leads-by-stage")
		self.assertEqual(self.counts(result), {"New": 2, "Contacted": 1})  # a, b, c by hand
		self.assertEqual(result["scope"], "own")

	def test_a_sales_manager_reads_only_their_own_teams_leads(self):
		result = self.run_as("sales_manager", "leads-by-stage")
		self.assertEqual(
			self.counts(result), {"New": 2, "Contacted": 1}
		)  # the team is the test agent: a, b, c
		self.assertEqual(result["scope"], "team")

	def test_a_sales_manager_with_no_team_member_reads_nothing(self):
		frappe.db.delete("Sales Team Member", {"parent": self.team.name})
		self.assertEqual(self.run_as("sales_manager", "leads-by-stage")["rows"], [])

	def test_the_company_admin_reads_all_and_may_narrow_to_one_agent(self):
		self.assertEqual(self.run_as("company_admin", "leads-by-stage")["scope"], "all")
		narrowed = self.run_as("company_admin", "leads-by-stage", agent=SECOND_AGENT)
		self.assertEqual(self.counts(narrowed), {"New": 1})  # d by hand
		nobody = self.run_as("company_admin", "leads-by-stage", agent="")
		self.assertEqual(self.counts(nobody), {"Qualified": 1})  # e by hand

	def test_an_agent_cannot_widen_the_scope_by_naming_another_agent(self):
		self.assertEqual(self.run_as("agent", "leads-by-stage", agent=SECOND_AGENT)["rows"], [])

	def test_the_scope_holds_for_calls_too(self):
		# The calls are on lead a, the team's. Handed to an agent of another team, they leave the team's report.
		self.assertEqual(self.run_as("sales_manager", "call-cost-by-purpose")["totals"]["total"], 1.55)
		frappe.db.set_value("Lead", self.leads["a"], "assigned_to", SECOND_AGENT)
		self.assertEqual(self.run_as("sales_manager", "call-cost-by-purpose")["rows"], [])

	def test_each_role_lists_the_reports_made_visible_to_it(self):
		def keys(who):
			frappe.set_user(email(who))
			try:
				return {r["key"] for r in engine.list_reports()["reports"]}
			finally:
				frappe.set_user("Administrator")

		self.assertEqual(
			keys("agent"),
			{
				"leads-by-stage",
				"site-visits-by-status",
				"follow-ups-by-status",
				"my-pipeline",
				"calls-by-outcome",
			},  # SOS-P5-02 added the last two
		)
		self.assertLess(keys("agent"), keys("sales_manager"))
		self.assertLess(keys("sales_manager"), keys("company_admin"))  # SOS-P5-02: admin only reports
		frappe.db.set_value("Report Definition", "leads-by-stage", "enabled", 0)
		self.assertNotIn("leads-by-stage", keys("sales_manager"))
		self.assertIn("leads-by-stage", keys("company_admin"))  # the Company Admin sees it to switch it on

	def test_a_report_not_made_visible_to_a_role_is_refused_for_every_call(self):
		with self.assertRaises(frappe.PermissionError):
			self.run_as("agent", "leads-by-source")
		with self.assertRaises(frappe.PermissionError):
			self.drill_as("agent", "leads-by-source")
		frappe.db.set_value("Report Definition", "leads-by-stage", "enabled", 0)
		with self.assertRaises(frappe.PermissionError):
			self.run_as("sales_manager", "leads-by-stage")
		with self.assertRaises(frappe.DoesNotExistError):
			self.run_as("company_admin", "no-such-report")

	def test_a_channel_partner_and_a_client_read_no_report(self):
		for who in ("channel_partner", "client", "platform_admin"):
			frappe.set_user(email(who))
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				engine.run_report("leads-by-stage")
		frappe.set_user("Administrator")


class TestDrillDown(ReportCase):
	"""SOS-P5-01: each figure opens the records behind it, and the two always agree."""

	def test_every_figure_lists_exactly_its_records(self):
		for key in ("leads-by-stage", "leads-by-source", "call-cost-by-purpose", "site-visits-by-status"):
			for who in ("company_admin", "sales_manager", "agent"):
				frappe.set_user(email(who))
				visible = engine._reads(engine._definition(key), frappe.get_roles())
				frappe.set_user("Administrator")
				if not visible:
					continue
				with self.subTest(report=key, who=who):
					figures = self.run_as(who, key)
					for row in figures["rows"]:
						found = self.drill_as(who, key, group=row["group"])
						self.assertEqual(found["total"], row["count"])
						self.assertEqual(len(found["records"]), row["count"])
						self.assertEqual(found["sum"], row["total"])
					self.assertEqual(self.drill_as(who, key)["total"], figures["totals"]["count"])

	def test_the_records_are_the_ones_worked_out_by_hand(self):
		stage = self.drill_as("company_admin", "leads-by-stage", group="New")
		self.assertEqual({r["lead"] for r in stage["records"]}, {self.leads[k] for k in ("a", "c", "d")})
		calls = self.drill_as("company_admin", "call-cost-by-purpose", group="Service")
		self.assertEqual({r["name"] for r in calls["records"]}, {self.calls["s1"], self.calls["s2"]})
		self.assertEqual(calls["sum"], 0.30)
		self.assertEqual({r["lead"] for r in calls["records"]}, {self.leads["a"]})
		self.assertEqual([c["field"] for c in calls["columns"]][:2], ["started_on", "lead"])
		# newest first
		self.assertEqual([r["name"] for r in calls["records"]], [self.calls["s2"], self.calls["s1"]])

	def test_a_blank_group_lists_the_records_with_no_value(self):
		frappe.set_user(email("company_admin"))
		engine.save_report_definition(
			{
				"report_key": "p501-agents",
				"title": "P501 Agents",
				"source_doctype": "Lead",
				"group_by": "assigned_to",
			}
		)
		frappe.set_user("Administrator")
		found = self.drill_as("company_admin", "p501-agents", group="")
		self.assertEqual([r["lead"] for r in found["records"]], [self.leads["e"]])

	def test_a_long_list_is_cut_and_says_so(self):
		with patch.object(engine, "MAX_RECORDS", 2):
			found = self.drill_as("company_admin", "leads-by-stage")
		self.assertEqual(
			(found["total"], found["shown"], len(found["records"]), found["truncated"]), (5, 2, 2, True)
		)

	def test_an_agent_is_listed_only_their_own_records(self):
		found = self.drill_as("agent", "leads-by-stage")
		self.assertEqual({r["lead"] for r in found["records"]}, {self.leads[k] for k in ("a", "b", "c")})

	def test_no_figure_or_record_holds_a_phone_number(self):
		for who, key in (
			("company_admin", "leads-by-stage"),
			("company_admin", "call-cost-by-purpose"),
			("sales_manager", "leads-by-stage"),
			("sales_manager", "call-cost-by-purpose"),
			("agent", "leads-by-stage"),
		):
			text = json.dumps(
				[self.run_as(who, key), self.drill_as(who, key), self.drill_as(who, key, group="New")],
				default=str,
			)
			for form in self.phone_forms:
				with self.subTest(who=who, report=key):
					self.assertNotIn(form, text)

	def test_the_engine_reads_no_field_a_source_does_not_list(self):
		from sellos.reports.sources import SOURCES as ALLOWED

		for source, config in ALLOWED.items():
			listed = {f for f, _label in config["columns"]} | set(config["groups"]) | set(config["sums"])
			meta = frappe.get_meta(source)
			for field in listed - {"name", "creation"}:
				self.assertTrue(meta.has_field(field), f"{source}.{field}")
				self.assertNotIn(meta.get_field(field).fieldtype, ("Phone",), f"{source}.{field}")
			self.assertNotIn("phone", listed | {"overseas_phone"})
		self.assertEqual(Decimal("0.1") + Decimal("0.2"), Decimal("0.3"))
