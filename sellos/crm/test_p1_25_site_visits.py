"""SOS-P1-25: schedule and confirm site visits. Booking from a lead, the stage move, the agent told the day
before, the calendar and the list of tomorrow's visits by role, confirmations, and marking a visit Done with
its outcome and the stage it offers. Every date is fixed in 2030 and no test reads the real time."""

import itertools
from datetime import datetime

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import AGENT, SALES_MANAGER, ensure_roles
from sellos.crm import api, notifications, pipeline, site_visits
from sellos.crm.test_crm import as_user, email
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

_SEEDS = itertools.count(380)
NOW = datetime(2030, 6, 10, 9, 0, 0)  # a Monday
TOMORROW = "2030-06-11"
OTHER_AGENT = "p125_agent_two@example.com"
OUTSIDE_AGENT = "p125_agent_three@example.com"


def make_user(address, role):
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": address,
			"first_name": address.split("@")[0],
			"send_welcome_email": 0,
			"roles": [{"role": role}],
		}
	)
	user.flags.ignore_permissions = True
	user.insert()
	return address


class VisitCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		pipeline.ensure_default_stages()
		self.agent = email("agent")
		self.other = make_user(OTHER_AGENT, AGENT)
		self.outside = make_user(OUTSIDE_AGENT, AGENT)
		self.manager = email("sales_manager")
		frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P125 Team",
				"manager": self.manager,
				"members": [{"agent": self.agent}, {"agent": self.other}],
			}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def lead_for(self, agent, stage=None, name="P125 Buyer"):
		as_user("company_admin")
		client = api.save_client(
			values={"client_name": name, "client_type": "Buyer", "phone": phones.in_mobile(next(_SEEDS))}
		)
		lead = api.save_lead(values={"client": client["name"], "source": "Website", "assigned_to": agent})[
			"lead"
		]["name"]
		if stage:
			frappe.db.set_value("Lead", lead, "stage", stage, update_modified=False)
		return lead

	def book(self, lead, when="2030-06-11 10:00:00", who="company_admin", **values):
		as_user(who)
		return api.save_site_visit(
			values={"lead": lead, "project_name": "P125 Tower", "visit_datetime": when, **values}
		)

	def stage(self, lead):
		return frappe.db.get_value("Lead", lead, "stage")


class TestBooking(VisitCase):
	def test_a_visit_is_booked_for_the_lead_with_the_agent_the_project_and_the_time(self):
		lead = self.lead_for(self.agent)
		visit = self.book(lead, who="agent")
		row = frappe.db.get_value(
			"Site Visit",
			visit["name"],
			["lead", "project_name", "visit_datetime", "agent", "status", "confirmation_status"],
			as_dict=True,
		)
		self.assertEqual(row.lead, lead)
		self.assertEqual(row.project_name, "P125 Tower")
		self.assertEqual(str(row.visit_datetime), "2030-06-11 10:00:00")
		self.assertEqual(row.agent, self.agent)  # the lead's agent when none is chosen
		self.assertEqual((row.status, row.confirmation_status), ("Scheduled", "Not confirmed"))

	def test_another_agent_may_be_chosen_and_must_be_an_active_user(self):
		lead = self.lead_for(self.agent)
		visit = self.book(lead, agent=self.other)
		self.assertEqual(visit["agent"], self.other)
		frappe.db.set_value("User", self.other, "enabled", 0)
		with self.assertRaises(frappe.ValidationError):
			self.book(lead, agent=self.other)

	def test_booking_moves_a_lead_that_is_before_the_stage_to_site_visit_booked(self):
		for start in (
			pipeline.NEW,
			pipeline.CONSENT_PENDING,
			pipeline.CONTACTED,
			pipeline.QUALIFIED,
			pipeline.NURTURE,
		):
			lead = self.lead_for(self.agent, stage=start)
			visit = self.book(lead)
			self.assertTrue(visit["stage_moved"], start)
			self.assertEqual(self.stage(lead), pipeline.SITE_VISIT_BOOKED, start)
			log = frappe.get_doc("Lead", lead).stage_log[-1]
			self.assertEqual((log.from_stage, log.to_stage), (start, pipeline.SITE_VISIT_BOOKED))

	def test_booking_leaves_a_lead_that_is_already_further_on_where_it_is(self):
		for start in (
			pipeline.SITE_VISIT_BOOKED,
			pipeline.SITE_VISIT_DONE,
			pipeline.NEGOTIATION,
			pipeline.BOOKING,
			pipeline.CLOSED_WON,
			pipeline.CLOSED_LOST,
		):
			lead = self.lead_for(self.agent, stage=start)
			visit = self.book(lead)
			self.assertFalse(visit["stage_moved"], start)
			self.assertEqual(self.stage(lead), start)

	def test_changing_a_visit_does_not_move_the_stage_again(self):
		lead = self.lead_for(self.agent, stage=pipeline.NEW)
		visit = self.book(lead)
		frappe.db.set_value("Lead", lead, "stage", pipeline.NEGOTIATION, update_modified=False)
		as_user("agent")
		changed = api.save_site_visit(name=visit["name"], values={"visit_datetime": "2030-06-12 11:00:00"})
		self.assertFalse(changed["stage_moved"])
		self.assertEqual(self.stage(lead), pipeline.NEGOTIATION)

	def test_a_company_that_removed_the_stage_keeps_the_lead_where_it_is(self):
		lead = self.lead_for(self.agent, stage=pipeline.NEW)
		with self.patch_position(None):
			self.assertFalse(self.book(lead)["stage_moved"])
		self.assertEqual(self.stage(lead), pipeline.NEW)

	def patch_position(self, value):
		from unittest.mock import patch

		return patch.object(site_visits, "_position", return_value=value)

	def test_consent_never_blocks_a_booking(self):
		lead = self.lead_for(self.agent, stage=pipeline.NEW)
		as_user("agent")
		api.record_opt_out(lead, "Phone call")
		self.assertTrue(self.book(lead, who="agent")["stage_moved"])

	def test_the_agent_is_told_the_day_before_the_visit(self):
		lead = self.lead_for(self.agent)
		self.book(lead, agent=self.manager)  # a manager sees the team's leads, so may be told of the visit
		frappe.set_user("Administrator")
		self.assertEqual(notifications.notify_site_visits(now=NOW), 1)
		rows = frappe.get_all(
			"App Notification",
			filters={"lead": lead, "event": notifications.SITE_VISIT_TOMORROW},
			pluck="recipient",
		)
		self.assertEqual(rows, [self.manager])  # the visit's agent, not the lead's

	def test_a_user_who_cannot_see_the_lead_cannot_book_for_it(self):
		lead = self.lead_for(self.agent)
		with self.assertRaises(frappe.PermissionError):
			self.book(lead, who="channel_partner")
		frappe.set_user(self.outside)
		with self.assertRaises(frappe.PermissionError):
			api.save_site_visit(
				values={"lead": lead, "project_name": "x", "visit_datetime": "2030-06-11 10:00:00"}
			)


class TestCalendarAndTomorrowByRole(VisitCase):
	def setUp(self):
		super().setUp()
		self.lead_a = self.lead_for(self.agent, name="P125 Alpha")
		self.lead_b = self.lead_for(self.other, name="P125 Bravo")
		self.lead_c = self.lead_for(self.outside, name="P125 Charlie")
		self.visit_a = self.book(self.lead_a, "2030-06-11 10:00:00")["name"]
		self.visit_b = self.book(self.lead_b, "2030-06-11 11:00:00")["name"]
		self.visit_c = self.book(self.lead_c, "2030-06-13 09:30:00")["name"]
		self.book(self.lead_a, "2030-06-20 09:30:00")  # another week

	def names(self, result):
		return [v["name"] for day in result["days"] for v in day["visits"]]

	def calendar(self, who, view="week", date="2030-06-12"):
		as_user(who)
		return api.site_visit_calendar(view, date)

	def test_the_week_runs_monday_to_sunday_and_lists_every_day(self):
		week = self.calendar("company_admin")
		self.assertEqual((week["start"], week["end"]), ("2030-06-10", "2030-06-16"))
		self.assertEqual([d["date"] for d in week["days"]][0::6], ["2030-06-10", "2030-06-16"])
		self.assertEqual(len(week["days"]), 7)
		by_day = {d["date"]: [v["name"] for v in d["visits"]] for d in week["days"]}
		self.assertEqual(by_day["2030-06-11"], [self.visit_a, self.visit_b])
		self.assertEqual(by_day["2030-06-13"], [self.visit_c])
		self.assertEqual(by_day["2030-06-12"], [])

	def test_the_day_view_holds_one_day(self):
		day = self.calendar("company_admin", "day", "2030-06-11")
		self.assertEqual(len(day["days"]), 1)
		self.assertEqual(self.names(day), [self.visit_a, self.visit_b])
		with self.assertRaises(frappe.ValidationError):
			self.calendar("company_admin", "month")

	def test_an_agent_sees_their_own_visits_only(self):
		self.assertEqual(self.names(self.calendar("agent")), [self.visit_a])

	def test_a_sales_manager_sees_the_visits_of_the_team_only(self):
		self.assertEqual(self.names(self.calendar("sales_manager")), [self.visit_a, self.visit_b])

	def test_a_company_admin_sees_everyones(self):
		self.assertEqual(
			self.names(self.calendar("company_admin")), [self.visit_a, self.visit_b, self.visit_c]
		)

	def test_a_visit_row_names_the_lead_and_the_agent_and_carries_no_phone_number(self):
		row = self.calendar("company_admin")["days"][1]["visits"][0]
		self.assertEqual(row["lead_title"], frappe.db.get_value("Lead", self.lead_a, "lead_title"))
		self.assertEqual(row["agent"], self.agent)
		self.assertEqual(row["confirmation_status"], "Not confirmed")
		self.assertFalse([key for key in row if "phone" in key])

	def test_tomorrows_list_has_that_days_visits_with_the_confirmation_status(self):
		as_user("company_admin")
		tomorrow = site_visits.tomorrows_visits(now=NOW)
		self.assertEqual(tomorrow["date"], TOMORROW)
		self.assertEqual([v["name"] for v in tomorrow["visits"]], [self.visit_a, self.visit_b])
		as_user("agent")
		self.assertEqual([v["name"] for v in site_visits.tomorrows_visits(now=NOW)["visits"]], [self.visit_a])
		as_user("sales_manager")
		self.assertEqual(len(site_visits.tomorrows_visits(now=NOW)["visits"]), 2)

	def test_an_archived_visit_is_off_the_calendar(self):
		frappe.db.set_value("Site Visit", self.visit_a, "archived", 1)
		self.assertNotIn(self.visit_a, self.names(self.calendar("company_admin")))

	def test_a_channel_partner_and_an_outsider_cannot_open_the_calendar(self):
		as_user("channel_partner")
		with self.assertRaises(frappe.PermissionError):
			api.site_visit_calendar("week", "2030-06-12")
		with self.assertRaises(frappe.PermissionError):
			api.tomorrows_site_visits()


class TestConfirmation(VisitCase):
	def setUp(self):
		super().setUp()
		self.lead = self.lead_for(self.agent)
		self.visit = self.book(self.lead)["name"]

	def confirm(self, status, when=None, who="agent"):
		as_user(who)
		return api.confirm_site_visit(self.visit, status, when)

	def test_the_four_confirmation_statuses_are_the_ones_listed(self):
		self.assertEqual(
			site_visits.CONFIRMATIONS, ("Not confirmed", "Confirmed", "Rescheduled", "Cancelled")
		)
		as_user("agent")
		self.assertEqual(api.site_visit_options()["confirmations"], list(site_visits.CONFIRMATIONS))

	def test_confirmed_is_saved_and_shows_on_the_list(self):
		self.assertEqual(self.confirm("Confirmed")["confirmation_status"], "Confirmed")
		self.assertEqual(frappe.db.get_value("Site Visit", self.visit, "status"), "Scheduled")
		row = site_visits.tomorrows_visits(now=NOW)["visits"][0]
		self.assertEqual(row["confirmation_status"], "Confirmed")

	def test_rescheduled_needs_the_new_time_and_moves_the_visit(self):
		with self.assertRaises(frappe.MandatoryError):
			self.confirm("Rescheduled")
		view = self.confirm("Rescheduled", "2030-06-14 15:00:00")
		self.assertEqual(
			(view["confirmation_status"], view["visit_datetime"]), ("Rescheduled", "2030-06-14 15:00:00")
		)
		self.assertEqual(frappe.db.get_value("Site Visit", self.visit, "status"), "Scheduled")

	def test_a_rescheduled_visit_is_told_again_the_day_before_its_new_date(self):
		frappe.set_user("Administrator")
		notifications.notify_site_visits(now=NOW)
		self.confirm("Rescheduled", "2030-06-14 15:00:00")
		frappe.set_user("Administrator")
		self.assertEqual(notifications.notify_site_visits(now=NOW), 0)  # not tomorrow any more
		self.assertEqual(notifications.notify_site_visits(now=datetime(2030, 6, 13, 9, 0, 0)), 1)

	def test_cancelled_cancels_the_visit_and_stays_on_the_list(self):
		self.confirm("Cancelled")
		self.assertEqual(frappe.db.get_value("Site Visit", self.visit, "status"), "Cancelled")
		row = site_visits.tomorrows_visits(now=NOW)["visits"][0]
		self.assertEqual((row["status"], row["confirmation_status"]), ("Cancelled", "Cancelled"))
		frappe.set_user("Administrator")
		self.assertEqual(notifications.notify_site_visits(now=NOW), 0)  # a cancelled visit is not told

	def test_a_cancelled_status_set_through_the_visit_shows_as_a_cancelled_confirmation(self):
		as_user("agent")
		api.save_site_visit(name=self.visit, values={"status": "Cancelled"})
		self.assertEqual(frappe.db.get_value("Site Visit", self.visit, "confirmation_status"), "Cancelled")

	def test_a_cancelled_visit_can_be_confirmed_again(self):
		self.confirm("Cancelled")
		self.confirm("Confirmed")
		self.assertEqual(frappe.db.get_value("Site Visit", self.visit, "status"), "Scheduled")

	def test_an_unknown_status_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.confirm("Maybe")

	def test_a_done_visit_cannot_be_confirmed(self):
		as_user("agent")
		api.complete_site_visit(self.visit, "Liked it")
		with self.assertRaises(frappe.ValidationError):
			api.confirm_site_visit(self.visit, "Confirmed")

	def test_the_visits_agents_the_manager_and_the_admin_may_confirm_and_others_may_not(self):
		for who in ("sales_manager", "company_admin"):
			self.assertEqual(self.confirm("Confirmed", who=who)["confirmation_status"], "Confirmed")
		for who in ("channel_partner", "client"):
			with self.assertRaises(frappe.PermissionError):
				self.confirm("Confirmed", who=who)
		frappe.set_user(self.outside)
		with self.assertRaises(frappe.PermissionError):
			api.confirm_site_visit(self.visit, "Confirmed")


class TestMarkingAVisitDone(VisitCase):
	def setUp(self):
		super().setUp()
		self.lead = self.lead_for(self.agent)
		self.visit = self.book(self.lead)["name"]  # moves the lead to Site visit booked

	def done(self, outcome=None, notes=None, who="agent"):
		as_user(who)
		return api.complete_site_visit(self.visit, outcome, notes)

	def test_it_asks_for_the_outcome(self):
		for outcome in (None, "", "Great"):
			with self.assertRaises(frappe.MandatoryError):
				self.done(outcome)
		self.assertEqual(frappe.db.get_value("Site Visit", self.visit, "status"), "Scheduled")

	def test_it_saves_the_outcome_and_notes_and_offers_the_next_stage_without_moving_the_lead(self):
		view = self.done("Liked it", " Wants the corner unit ")
		self.assertEqual(view["status"], "Done")
		self.assertEqual((view["outcome"], view["outcome_notes"]), ("Liked it", "Wants the corner unit"))
		self.assertEqual(view["suggested_stage"], pipeline.NEGOTIATION)
		self.assertEqual(self.stage(self.lead), pipeline.SITE_VISIT_BOOKED)  # offered, never applied

	def test_the_offer_follows_the_outcome(self):
		offers = {
			"Liked it": pipeline.NEGOTIATION,
			"Undecided": pipeline.SITE_VISIT_DONE,
			"Wants a second visit": pipeline.SITE_VISIT_DONE,
			"Not interested": pipeline.CLOSED_LOST,
			"Did not come": None,
		}
		self.assertEqual(site_visits.OUTCOME_STAGES, offers)
		for outcome, stage in offers.items():
			frappe.db.set_value("Site Visit", self.visit, {"status": "Scheduled", "visit_outcome": None})
			self.assertEqual(self.done(outcome)["suggested_stage"], stage, outcome)

	def test_nothing_is_offered_when_the_lead_is_already_on_that_stage(self):
		frappe.db.set_value("Lead", self.lead, "stage", pipeline.NEGOTIATION, update_modified=False)
		self.assertIsNone(self.done("Liked it")["suggested_stage"])

	def test_the_agent_accepts_the_offer_with_move_lead_stage(self):
		offered = self.done("Undecided")["suggested_stage"]
		as_user("agent")
		api.move_lead_stage(self.lead, offered)
		self.assertEqual(self.stage(self.lead), pipeline.SITE_VISIT_DONE)

	def test_a_done_or_cancelled_visit_cannot_be_marked_done_again(self):
		self.done("Liked it")
		with self.assertRaises(frappe.ValidationError):
			self.done("Liked it")
		other = self.book(self.lead)["name"]
		as_user("agent")
		api.confirm_site_visit(other, "Cancelled")
		with self.assertRaises(frappe.ValidationError):
			api.complete_site_visit(other, "Liked it")

	def test_a_channel_partner_cannot_mark_a_visit_done(self):
		with self.assertRaises(frappe.PermissionError):
			self.done("Liked it", who="channel_partner")


class TestOptions(VisitCase):
	def test_each_role_is_offered_the_agents_it_may_book_for(self):
		def agents(who):
			as_user(who)
			return {a["name"] for a in api.site_visit_options()["agents"]}

		self.assertEqual(agents("agent"), {self.agent})
		self.assertEqual(agents("sales_manager"), {self.manager, self.agent, self.other})
		everyone = agents("company_admin")
		self.assertTrue({self.agent, self.other, self.outside, self.manager} <= everyone)
		as_user("agent")
		options = api.site_visit_options()
		self.assertEqual([o["name"] for o in options["outcomes"]], list(site_visits.OUTCOMES))
		self.assertEqual(SALES_MANAGER, "SellOS Sales Manager")
		self.assertEqual(TEST_USERS["agent"]["email"], self.agent)


class TestRegressionSeed(VisitCase):
	def test_the_seed_books_tomorrows_visits_through_the_api_and_runs_again_safely(self):
		from sellos.tests import ui_fixtures

		for who, agent in (("Buyer Two", self.agent), ("Buyer Three", self.other)):
			self.lead_for(agent, name=f"{ui_fixtures.REGRESSION_PREFIX}{who}")
		frappe.set_user("Administrator")
		ui_fixtures._seed_site_visits(self.agent, self.other)
		ui_fixtures._seed_site_visits(self.agent, self.other)
		rows = frappe.get_all(
			"Site Visit",
			filters={"project_name": ["like", "Regression %"]},
			fields=["project_name", "agent", "confirmation_status", "status"],
			order_by="project_name asc",
		)
		self.assertEqual(
			[(r.project_name, r.agent, r.confirmation_status, r.status) for r in rows],
			[
				("Regression Lakeside Tour", self.other, "Not confirmed", "Scheduled"),
				("Regression Skyline Walkthrough", self.agent, "Confirmed", "Scheduled"),
			],
		)
