"""SOS-P1-26: the agent's Today screen. Each list's query (follow ups due and overdue, new leads, today's
visits, tomorrow's visits), who sees which records, the counts matching the lists, the phone the role sees
and the consent warning that never blocks. Every date is fixed in 2030 and no test reads the real time."""

import itertools
from datetime import datetime

import frappe

from sellos.access.roles import AGENT
from sellos.crm import api, pipeline, today
from sellos.crm.test_crm import CrmCase, as_user, email
from sellos.crm.test_p1_25_site_visits import make_user
from sellos.tests import phones

_SEEDS = itertools.count(520)
NOW = datetime(2030, 6, 10, 9, 0, 0)  # a Monday
OTHER_AGENT = "p126_agent_two@example.com"
OUTSIDE_AGENT = "p126_agent_three@example.com"


class TodayCase(CrmCase):
	def setUp(self):
		super().setUp()
		pipeline.ensure_default_stages()
		self.agent = email("agent")
		self.manager = email("sales_manager")
		self.other = make_user(OTHER_AGENT, AGENT)
		self.outside = make_user(OUTSIDE_AGENT, AGENT)
		frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P126 Team",
				"manager": self.manager,
				"members": [{"agent": self.agent}, {"agent": self.other}],
			}
		).insert()

	def lead_for(self, agent, name, stage=None, number=None):
		as_user("company_admin")
		client = api.save_client(
			values={
				"client_name": name,
				"client_type": "Buyer",
				"phone": number or phones.in_mobile(next(_SEEDS)),
			}
		)
		lead = api.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": agent})[
			"lead"
		]["name"]
		frappe.db.set_value("Lead", lead, "stage", stage or pipeline.CONTACTED, update_modified=False)
		return lead

	def task(self, lead, agent, title, when=None, day=None, status="Open"):
		doc = {"doctype": "Lead Task", "lead": lead, "title": title, "assigned_to": agent, "status": status}
		doc["due_at" if when else "due_date"] = when or day
		return frappe.get_doc(doc).insert(ignore_permissions=True).name

	def visit(self, lead, agent, project, when, status="Scheduled"):
		doc = frappe.get_doc(
			{
				"doctype": "Site Visit",
				"lead": lead,
				"agent": agent,
				"project_name": project,
				"visit_datetime": when,
				"status": status,
			}
		)
		return doc.insert(ignore_permissions=True).name

	def view(self, who):
		as_user(who)
		return today.today_view(now=NOW)

	def titles(self, rows, field="title"):
		return [row[field] for row in rows]


class TestTodayLists(TodayCase):
	"""SOS-P1-26: the query of each list."""

	def test_follow_ups_due_and_overdue_in_time_order_for_the_agent_only(self):
		mine = self.lead_for(self.agent, "P126 Mine")
		theirs = self.lead_for(self.other, "P126 Theirs")
		self.task(mine, self.agent, "later today", when="2030-06-10 17:00:00")
		self.task(mine, self.agent, "overdue", when="2030-06-08 11:00:00")
		self.task(mine, self.agent, "day only today", day="2030-06-10")
		self.task(mine, self.agent, "tomorrow", when="2030-06-11 10:00:00")
		self.task(mine, self.agent, "done", when="2030-06-10 08:00:00", status="Done")
		self.task(theirs, self.other, "not mine", when="2030-06-10 10:00:00")
		view = self.view("agent")
		self.assertEqual(self.titles(view["follow_ups"]), ["overdue", "day only today", "later today"])
		self.assertEqual(self.titles(view["follow_ups"][:1], "state"), ["overdue"])

	def test_new_leads_are_the_agents_own_on_the_new_stage_oldest_first(self):
		first = self.lead_for(self.agent, "P126 New One", stage=pipeline.NEW)
		second = self.lead_for(self.agent, "P126 New Two", stage=pipeline.NEW)
		frappe.db.set_value("Lead", first, "creation", "2030-06-08 10:00:00", update_modified=False)
		frappe.db.set_value("Lead", second, "creation", "2030-06-07 10:00:00", update_modified=False)
		self.lead_for(self.agent, "P126 Contacted")
		self.lead_for(self.other, "P126 Other New", stage=pipeline.NEW)
		archived = self.lead_for(self.agent, "P126 Archived New", stage=pipeline.NEW)
		frappe.db.set_value("Lead", archived, "archived", 1, update_modified=False)
		view = self.view("agent")
		self.assertEqual([row.lead for row in view["new_leads"]], [second, first])

	def test_visits_today_and_tomorrow_in_time_order_without_cancelled_ones(self):
		lead = self.lead_for(self.agent, "P126 Visits")
		other = self.lead_for(self.other, "P126 Visits Other")
		self.visit(lead, self.agent, "Late", "2030-06-10 16:00:00")
		self.visit(lead, self.agent, "Early", "2030-06-10 10:00:00")
		self.visit(lead, self.agent, "Called off", "2030-06-10 12:00:00", status="Cancelled")
		self.visit(lead, self.agent, "Next two", "2030-06-11 14:00:00")
		self.visit(lead, self.agent, "Next one", "2030-06-11 09:00:00")
		self.visit(lead, self.agent, "Next off", "2030-06-11 11:00:00", status="Cancelled")
		self.visit(lead, self.agent, "Day after", "2030-06-12 09:00:00")
		self.visit(other, self.other, "Theirs", "2030-06-10 11:00:00")
		view = self.view("agent")
		self.assertEqual(self.titles(view["visits_today"], "project_name"), ["Early", "Late"])
		self.assertEqual(self.titles(view["visits_tomorrow"], "project_name"), ["Next one", "Next two"])
		self.assertEqual(view["visits_tomorrow"][0]["confirmation_status"], "Not confirmed")

	def test_counts_match_the_lists(self):
		lead = self.lead_for(self.agent, "P126 Counts", stage=pipeline.NEW)
		self.task(lead, self.agent, "one", when="2030-06-09 10:00:00")
		self.task(lead, self.agent, "two", day="2030-06-10")
		self.visit(lead, self.agent, "Today visit", "2030-06-10 10:00:00")
		view = self.view("agent")
		for key in today.SECTIONS:
			self.assertEqual(view["counts"][key], len(view[key]), key)
		self.assertEqual(view["counts"]["total"], 4)
		self.assertEqual(view["counts"]["follow_ups"], 2)
		self.assertEqual(view["counts"]["new_leads"], 1)


class TestTodayByRole(TodayCase):
	"""SOS-P1-26: a Sales Manager sees the team by agent, an agent only their own."""

	def test_sales_manager_sees_the_team_by_agent_and_not_outsiders(self):
		mine = self.lead_for(self.agent, "P126 Team One", stage=pipeline.NEW)
		theirs = self.lead_for(self.other, "P126 Team Two", stage=pipeline.NEW)
		outside = self.lead_for(self.outside, "P126 Outside", stage=pipeline.NEW)
		self.task(mine, self.agent, "a task", day="2030-06-10")
		self.task(theirs, self.other, "b task", day="2030-06-10")
		self.task(outside, self.outside, "c task", day="2030-06-10")
		self.visit(theirs, self.other, "Tower B", "2030-06-11 10:00:00")
		self.visit(outside, self.outside, "Tower C", "2030-06-11 10:00:00")
		view = self.view("sales_manager")
		self.assertEqual(view["scope"], "team")
		self.assertEqual(sorted(self.titles(view["follow_ups"])), ["a task", "b task"])
		self.assertEqual(sorted(row.lead for row in view["new_leads"]), sorted([mine, theirs]))
		self.assertEqual(self.titles(view["visits_tomorrow"], "project_name"), ["Tower B"])
		by_agent = {row["agent"]: row["counts"] for row in view["agents"]}
		self.assertEqual(by_agent[self.agent]["follow_ups"], 1)
		self.assertEqual(by_agent[self.other]["follow_ups"], 1)
		self.assertEqual(by_agent[self.other]["visits_tomorrow"], 1)
		self.assertNotIn(self.outside, by_agent)
		for key in today.SECTIONS:
			self.assertEqual(view["counts"][key], sum(c[key] for c in by_agent.values()), key)

	def test_an_agent_sees_only_their_own_records(self):
		self.lead_for(self.other, "P126 Not Mine", stage=pipeline.NEW)
		view = self.view("agent")
		self.assertEqual(view["scope"], "own")
		self.assertEqual(view["new_leads"], [])
		self.assertEqual([row["agent"] for row in view["agents"]], [self.agent])


class TestTodayApi(TodayCase):
	"""SOS-P1-26: the number each role sees and the consent warning that never blocks."""

	def test_an_agent_gets_the_masked_number_and_an_admin_the_full_one(self):
		number = phones.in_mobile(777)
		lead = self.lead_for(self.agent, "P126 Phone", stage=pipeline.NEW, number=number)
		as_user("agent")
		agent_view = api.today_screen()
		row = next(r for r in agent_view["new_leads"] if r.lead == lead)
		self.assertNotEqual(row["phone"], number)
		self.assertNotIn(number[-10:], str(agent_view))
		self.assertEqual(agent_view["full_numbers"], 0)
		as_user("company_admin")
		admin_view = api.today_screen()
		admin_row = next(r for r in admin_view["new_leads"] if r.lead == lead)
		self.assertEqual(admin_row["phone"], number)
		self.assertEqual(admin_view["full_numbers"], 1)

	def test_a_lead_that_opted_out_is_listed_with_a_red_warning_and_can_still_be_logged(self):
		lead = self.lead_for(self.agent, "P126 Opted Out", stage=pipeline.NEW)
		as_user("agent")
		api.record_opt_out(lead, "Phone call")
		row = next(r for r in api.today_screen()["new_leads"] if r.lead == lead)
		self.assertEqual(row["consent_status"], "Opted out")
		self.assertEqual(row["consent_warning"], "red")
		logged = api.log_call(lead, "Wrong number", "p126 call")
		self.assertTrue(logged["activity"])
