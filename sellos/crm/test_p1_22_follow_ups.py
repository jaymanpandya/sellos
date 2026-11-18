"""SOS-P1-22: follow ups and reminders. Due and overdue detection with a fixed clock, the next follow up
on every lead, the list filter and sort, completing a follow up, the untouched flag, and the reminders run
as a function (never as a background job)."""

from datetime import datetime, timedelta
from unittest.mock import patch

import frappe

from sellos import hooks
from sellos.crm import api, board, call_outcomes, follow_ups, notifications, pipeline
from sellos.crm.test_crm import CrmCase, as_user, email

# The fixed clock of every test: no test reads the real time to decide what is due.
NOW = datetime(2030, 6, 10, 9, 0, 0)


def at(**delta):
	return NOW + timedelta(**delta)


class FollowUpCase(CrmCase):
	def setUp(self):
		super().setUp()
		pipeline.ensure_default_stages()
		call_outcomes.ensure_defaults()
		frappe.db.set_single_value("SellOS Settings", "untouched_days", 0)  # the default applies

	def lead_for_agent(self, name="P122 Buyer", made=None, stage=None):
		"""A lead assigned to the agent, dated `made` (default two days before the fixed clock)."""
		as_user("company_admin")
		client = api.save_client(values={"client_name": name, "client_type": "Buyer"})
		lead = api.save_lead(
			values={"client": client["name"], "source": "Website", "assigned_to": email("agent")}
		)["lead"]["name"]
		frappe.db.set_value("Lead", lead, "creation", made or at(days=-2), update_modified=False)
		if stage:
			frappe.db.set_value("Lead", lead, "stage", stage, update_modified=False)
		return lead

	def follow_up(self, lead, when=None, day=None, title="P122 call", **values):
		doc = {"doctype": "Lead Task", "lead": lead, "title": title, **values}
		if when:
			doc["due_at"] = when
		else:
			doc["due_date"] = day
		return frappe.get_doc(doc).insert(ignore_permissions=True)

	def row(self, lead, stage="New", archived=0, created=None):
		return frappe._dict(name=lead, stage=stage, archived=archived, creation=created or at(days=-2))

	def annotated(self, lead, now=NOW):
		row = frappe.db.get_value("Lead", lead, ["name", "stage", "archived", "creation"], as_dict=True)
		follow_ups.annotate([row], now=now)
		return row


class TestDueAndOverdueWithAFixedClock(FollowUpCase):
	def test_a_follow_up_with_a_time_is_due_fifteen_minutes_before_it_and_overdue_after(self):
		state = follow_ups.due_state
		self.assertIsNone(state(at(minutes=16), None, NOW))
		self.assertEqual(state(at(minutes=15), None, NOW), follow_ups.DUE)
		self.assertEqual(state(at(minutes=1), None, NOW), follow_ups.DUE)
		self.assertEqual(state(NOW, None, NOW), follow_ups.DUE)  # at its time it is due, not yet overdue
		self.assertEqual(state(at(seconds=-1), None, NOW), follow_ups.OVERDUE)
		self.assertEqual(state(at(days=-3), None, NOW), follow_ups.OVERDUE)

	def test_a_follow_up_with_only_a_day_is_due_that_day_and_overdue_after_it(self):
		state = follow_ups.due_state
		self.assertIsNone(state(None, "2030-06-11", NOW))
		self.assertEqual(state(None, "2030-06-10", NOW), follow_ups.DUE)
		self.assertEqual(state(None, "2030-06-09", NOW), follow_ups.OVERDUE)

	def test_the_due_window_is_the_one_the_reminders_use(self):
		self.assertEqual(notifications.DUE_WINDOW_MINUTES, follow_ups.DUE_WINDOW_MINUTES)
		self.assertEqual(follow_ups.DUE_WINDOW_MINUTES, 15)


class TestTheNextFollowUpOnEveryLead(FollowUpCase):
	def test_a_lead_shows_its_earliest_open_follow_up(self):
		lead = self.lead_for_agent()
		self.follow_up(lead, at(days=2), title="P122 later")
		soon = self.follow_up(lead, at(hours=3), title="P122 soon")
		done = self.follow_up(lead, at(hours=1), title="P122 done", status="Done")
		row = self.annotated(lead)
		self.assertEqual(row.next_follow_up_name, soon.name)
		self.assertEqual(row.next_follow_up_title, "P122 soon")
		self.assertTrue(row.next_follow_up_has_time)
		self.assertEqual(row.open_follow_ups, 2)
		self.assertEqual(row.follow_up_state, "")
		self.assertNotEqual(row.next_follow_up_name, done.name)

	def test_a_lead_with_none_open_shows_none(self):
		lead = self.lead_for_agent()
		self.follow_up(lead, at(hours=1), status="Done")
		row = self.annotated(lead)
		self.assertIsNone(row.next_follow_up)
		self.assertEqual(row.open_follow_ups, 0)
		self.assertEqual(row.follow_up_state, "")

	def test_an_overdue_follow_up_is_marked_overdue_and_a_due_one_due(self):
		overdue_lead, due_lead = self.lead_for_agent("P122 Overdue"), self.lead_for_agent("P122 Due")
		self.follow_up(overdue_lead, at(hours=-2))
		self.follow_up(due_lead, at(minutes=10))
		self.assertEqual(self.annotated(overdue_lead).follow_up_state, follow_ups.OVERDUE)
		self.assertEqual(self.annotated(due_lead).follow_up_state, follow_ups.DUE)

	def test_an_archived_follow_up_is_not_the_next_one(self):
		lead = self.lead_for_agent()
		task = self.follow_up(lead, at(hours=1))
		task.archived = 1
		task.save(ignore_permissions=True)
		self.assertEqual(self.annotated(lead).open_follow_ups, 0)

	def test_the_lead_screen_carries_it_too(self):
		lead = self.lead_for_agent()
		task = self.follow_up(lead, at(days=40))
		as_user("agent")
		view = api.get_lead(lead)["follow_up"]
		self.assertEqual(view["next_follow_up_name"], task.name)
		self.assertEqual(view["untouched_days"], 3)


class TestTheListFilterAndSort(FollowUpCase):
	def setUp(self):
		super().setUp()
		self.overdue = self.lead_for_agent("P122 Overdue")
		self.soon = self.lead_for_agent("P122 Soon")
		self.later = self.lead_for_agent("P122 Later")
		self.none = self.lead_for_agent("P122 None")
		self.follow_up(self.later, at(days=5))
		self.follow_up(self.overdue, at(days=-1))
		self.follow_up(self.soon, at(minutes=10))
		# The API reads the clock itself, so the clock it reads is the fixed one.
		clock = patch.object(follow_ups, "now_datetime", return_value=NOW)
		clock.start()
		self.addCleanup(clock.stop)
		as_user("agent")

	def mine(self, names):
		"""Only the leads this test made, so a lead another run left on the site is never counted."""
		return [name for name in names if name in self.own()]

	def own(self):
		return {self.overdue, self.soon, self.later, self.none}

	def names(self, **filters):
		return self.mine(lead.name for lead in board.visible_leads(now=NOW, **filters))

	def test_sort_puts_the_soonest_first_with_overdue_leading_and_none_last(self):
		self.assertEqual(self.names(sort="next_follow_up"), [self.overdue, self.soon, self.later, self.none])

	def test_the_overdue_filter_shows_only_overdue_ones(self):
		self.assertEqual(self.names(follow_up="overdue"), [self.overdue])

	def test_the_open_and_none_filters_split_the_leads(self):
		self.assertEqual(set(self.names(follow_up="open")), {self.overdue, self.soon, self.later})
		self.assertEqual(self.names(follow_up="none"), [self.none])

	def test_filter_and_sort_combine_with_the_other_filters(self):
		self.assertEqual(self.names(follow_up="open", search="Later"), [self.later])

	def test_a_filter_or_sort_that_does_not_exist_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			board.visible_leads(follow_up="sometimes")
		with self.assertRaises(frappe.ValidationError):
			board.visible_leads(sort="name")

	def test_the_api_takes_the_filter_and_sort_and_says_who_is_overdue(self):
		rows = [r for r in api.list_leads(follow_up="open", sort="next_follow_up") if r["name"] in self.own()]
		self.assertEqual(len(rows), 3)
		self.assertEqual(rows[0]["name"], self.overdue)
		self.assertEqual(rows[0]["follow_up_state"], follow_ups.OVERDUE)
		self.assertEqual(rows[0]["overdue_tasks"], 1)
		self.assertEqual(self.mine(r["name"] for r in api.list_leads(follow_up="none")), [self.none])
		cards = [lead.name for c in api.get_board(follow_up="none")["columns"] for lead in c["leads"]]
		self.assertEqual(self.mine(cards), [self.none])

	def test_a_user_lists_only_their_own_follow_ups_soonest_first(self):
		as_user("company_admin")
		other = self.lead_for_agent("P122 Other")
		frappe.db.set_value("Lead", other, "assigned_to", email("company_admin"))
		self.follow_up(other, at(days=-9), assigned_to=email("company_admin"))
		as_user("agent")
		rows = [r for r in api.list_follow_ups() if r["lead"] in self.own()]
		self.assertEqual([r["lead"] for r in rows], [self.overdue, self.soon, self.later])
		self.assertEqual(rows[0]["state"], follow_ups.OVERDUE)
		self.assertEqual(rows[0]["lead_title"], frappe.db.get_value("Lead", self.overdue, "lead_title"))


class TestTheUntouchedFlag(FollowUpCase):
	def test_the_default_is_three_days_and_the_company_admin_sets_it(self):
		self.assertEqual(follow_ups.untouched_days(), 3)
		as_user("company_admin")
		self.assertEqual(api.save_follow_up_settings(5), {"untouched_days": 5})
		self.assertEqual(api.get_follow_up_settings(), {"untouched_days": 5})
		for bad in (0, -1, 366):
			with self.assertRaises(frappe.ValidationError):
				api.save_follow_up_settings(bad)
		self.assertEqual(follow_ups.untouched_days(), 5)

	def test_an_agent_cannot_change_the_setting_but_can_read_it(self):
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			api.save_follow_up_settings(9)
		self.assertEqual(api.get_follow_up_settings()["untouched_days"], 3)

	def test_an_open_stage_lead_with_no_follow_up_is_untouched_after_the_days(self):
		fresh = self.lead_for_agent("P122 Fresh", made=at(days=-2, hours=-23))
		stale = self.lead_for_agent("P122 Stale", made=at(days=-3, minutes=-1))
		self.assertFalse(self.annotated(fresh).follow_up_untouched)
		self.assertTrue(self.annotated(stale).follow_up_untouched)

	def test_an_open_follow_up_means_the_lead_is_not_untouched(self):
		lead = self.lead_for_agent(made=at(days=-30))
		self.assertTrue(self.annotated(lead).follow_up_untouched)
		self.follow_up(lead, at(days=1))
		self.assertFalse(self.annotated(lead).follow_up_untouched)

	def test_finishing_a_follow_up_starts_the_count_again(self):
		lead = self.lead_for_agent(made=at(days=-30))
		task = self.follow_up(lead, at(days=-10), status="Done")
		frappe.db.set_value("Lead Task", task.name, "completed_on", at(days=-1))
		self.assertFalse(self.annotated(lead).follow_up_untouched)
		frappe.db.set_value("Lead Task", task.name, "completed_on", at(days=-4))
		self.assertTrue(self.annotated(lead).follow_up_untouched)

	def test_only_a_lead_in_an_open_stage_can_be_untouched(self):
		for stage, flagged in (
			("Contacted", True),
			("Booking", False),
			("Closed won", False),
			("Closed lost", False),
		):
			with self.subTest(stage=stage):
				lead = self.lead_for_agent(f"P122 {stage}", made=at(days=-30), stage=stage)
				self.assertEqual(self.annotated(lead).follow_up_untouched, flagged)

	def test_an_archived_lead_is_not_flagged(self):
		lead = self.lead_for_agent(made=at(days=-30))
		frappe.db.set_value("Lead", lead, "archived", 1)
		self.assertFalse(self.annotated(lead).follow_up_untouched)

	def flagged(self):
		return [r.name for r in board.visible_leads(now=NOW, follow_up="untouched")]

	def test_the_setting_moves_the_line_and_the_untouched_filter_uses_it(self):
		lead = self.lead_for_agent(made=at(days=-5))
		as_user("agent")
		self.assertIn(lead, self.flagged())
		as_user("company_admin")
		api.save_follow_up_settings(10)
		as_user("agent")
		self.assertNotIn(lead, self.flagged())
		self.assertEqual(api.lead_filter_options()["follow_up_untouched_days"], 10)

	def test_the_flag_never_looks_at_consent(self):
		lead = self.lead_for_agent(made=at(days=-30))
		as_user("company_admin")
		api.record_opt_out(lead, "WhatsApp")
		self.assertTrue(self.annotated(lead).follow_up_untouched)


class TestCompletingAFollowUp(FollowUpCase):
	def setUp(self):
		super().setUp()
		self.lead = self.lead_for_agent()
		self.task = self.follow_up(self.lead, at(days=1))
		as_user("agent")

	def status(self):
		return frappe.db.get_value("Lead Task", self.task.name, "status")

	def test_it_asks_for_the_call_outcome_or_a_note_and_stays_open_without_either(self):
		for blank in ({}, {"notes": "   "}, {"outcome": " "}):
			with self.subTest(blank=blank), self.assertRaises(frappe.MandatoryError):
				api.complete_follow_up(self.task.name, **blank)
		self.assertEqual(self.status(), "Open")

	def test_a_note_alone_completes_it_and_is_kept_on_the_lead(self):
		result = api.complete_follow_up(self.task.name, notes="Spoke to the buyer")
		self.assertEqual(self.status(), "Done")
		self.assertIsNotNone(frappe.db.get_value("Lead Task", self.task.name, "completed_on"))
		activity = frappe.get_doc("Lead Activity", result["activity"])
		self.assertEqual((activity.activity_type, activity.notes), ("Note", "Spoke to the buyer"))
		self.assertEqual(activity.lead, self.lead)

	def test_an_outcome_logs_the_call_and_completes_it(self):
		result = api.complete_follow_up(self.task.name, outcome="Wrong number", duration_seconds=45)
		self.assertEqual(self.status(), "Done")
		activity = frappe.get_doc("Lead Activity", result["activity"])
		self.assertEqual(
			(activity.activity_type, activity.outcome, activity.duration_seconds),
			("Call", "Wrong number", 45),
		)

	def test_an_outcome_that_needs_a_follow_up_makes_the_next_one(self):
		result = api.complete_follow_up(self.task.name, outcome="Call back later", follow_up_at=at(days=3))
		self.assertEqual(self.status(), "Done")
		self.assertEqual(self.annotated(self.lead).next_follow_up_name, result["follow_up"])

	def test_an_outcome_that_needs_a_follow_up_without_a_date_leaves_it_open(self):
		with self.assertRaises(frappe.MandatoryError):
			api.complete_follow_up(self.task.name, outcome="Call back later")
		self.assertEqual(self.status(), "Open")
		self.assertEqual(frappe.db.count("Lead Activity", {"lead": self.lead, "activity_type": "Call"}), 0)

	def test_a_done_follow_up_cannot_be_done_again(self):
		api.complete_follow_up(self.task.name, notes="first")
		with self.assertRaises(frappe.ValidationError):
			api.complete_follow_up(self.task.name, notes="second")

	def test_reopening_clears_when_it_was_done(self):
		api.complete_follow_up(self.task.name, notes="first")
		api.save_task(name=self.task.name, values={"status": "Open"})
		self.assertIsNone(frappe.db.get_value("Lead Task", self.task.name, "completed_on"))

	def test_another_agent_and_a_partner_cannot_complete_it(self):
		for who in ("channel_partner", "client"):
			as_user(who)
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				api.complete_follow_up(self.task.name, notes="no")
		self.assertEqual(self.status(), "Open")

	def test_consent_never_blocks_completing_it(self):
		as_user("company_admin")
		api.record_opt_out(self.lead, "WhatsApp")
		as_user("agent")
		api.complete_follow_up(self.task.name, outcome="Wrong number")
		self.assertEqual(self.status(), "Done")


class TestTheRemindersRunAsAFunction(FollowUpCase):
	def reminders(self, user="agent"):
		return frappe.get_all(
			"App Notification",
			filters={
				"recipient": email(user),
				"event": ["in", [notifications.FOLLOW_UP_DUE, notifications.FOLLOW_UP_OVERDUE]],
			},
			fields=["event", "lead", "message"],
		)

	def test_one_due_in_fifteen_minutes_and_one_overdue_notify_their_agent(self):
		due_lead, overdue_lead = self.lead_for_agent("P122 Due"), self.lead_for_agent("P122 Late")
		self.follow_up(due_lead, at(minutes=14), assigned_to=email("agent"))
		self.follow_up(overdue_lead, at(minutes=-5), assigned_to=email("agent"))
		self.assertEqual(notifications.notify_follow_ups(now=NOW), 2)
		events = {row.lead: row.event for row in self.reminders()}
		self.assertEqual(
			events,
			{due_lead: notifications.FOLLOW_UP_DUE, overdue_lead: notifications.FOLLOW_UP_OVERDUE},
		)
		self.assertEqual(self.reminders("company_admin"), [])

	def test_one_not_yet_due_a_done_one_and_an_archived_one_notify_nobody(self):
		lead = self.lead_for_agent()
		self.follow_up(lead, at(minutes=16), assigned_to=email("agent"))
		self.follow_up(lead, at(minutes=-5), assigned_to=email("agent"), status="Done")
		archived = self.follow_up(lead, at(minutes=-5), assigned_to=email("agent"))
		archived.archived = 1
		archived.save(ignore_permissions=True)
		self.assertEqual(notifications.notify_follow_ups(now=NOW), 0)

	def test_a_run_is_safe_to_repeat_and_a_follow_up_that_becomes_overdue_is_told_again(self):
		lead = self.lead_for_agent()
		self.follow_up(lead, at(minutes=10), assigned_to=email("agent"))
		self.assertEqual(notifications.notify_follow_ups(now=NOW), 1)
		self.assertEqual(notifications.notify_follow_ups(now=NOW), 0)
		self.assertEqual(notifications.notify_follow_ups(now=at(minutes=20)), 1)  # now overdue
		self.assertEqual(notifications.notify_follow_ups(now=at(minutes=21)), 0)
		self.assertEqual(
			sorted(row.event for row in self.reminders()),
			[notifications.FOLLOW_UP_DUE, notifications.FOLLOW_UP_OVERDUE],
		)

	def test_a_follow_up_with_only_a_day_is_due_that_day(self):
		lead = self.lead_for_agent()
		self.follow_up(lead, day="2030-06-10", assigned_to=email("agent"))
		self.assertEqual(notifications.notify_follow_ups(now=NOW), 1)
		self.assertEqual(self.reminders()[0].event, notifications.FOLLOW_UP_DUE)

	def test_the_scheduler_runs_the_reminders_every_tick(self):
		self.assertIn("sellos.crm.notifications.notify_follow_ups", hooks.scheduler_events["all"])

	def test_consent_never_blocks_a_reminder(self):
		lead = self.lead_for_agent()
		as_user("company_admin")
		api.record_opt_out(lead, "WhatsApp")
		self.follow_up(lead, at(minutes=5), assigned_to=email("agent"))
		self.assertEqual(notifications.notify_follow_ups(now=NOW), 1)


class TestTheSeededData(FollowUpCase):
	"""SOS-P1-22: the data the follow up spec and the regression walk see, read back."""

	def test_the_regression_seed_makes_an_overdue_and_a_due_follow_up_once_however_often_it_runs(self):
		from sellos.tests import ui_fixtures

		one = self.lead_for_agent("Regression Buyer One")
		two = self.lead_for_agent("Regression Buyer Two")
		for _ in range(2):
			ui_fixtures._seed_follow_ups(email("agent"))
		self.assertEqual(frappe.db.count("Lead Task", {"lead": ["in", [one, two]]}), 2)
		as_user("agent")
		rows = {row["lead"]: row for row in api.list_follow_ups()}
		self.assertEqual(rows[two]["state"], follow_ups.OVERDUE)
		self.assertEqual(rows[one]["state"], follow_ups.DUE)
		self.assertEqual(notifications.notify_follow_ups(), 2)
		self.assertEqual(
			sorted(
				row.event
				for row in frappe.get_all(
					"App Notification",
					filters={"lead": ["in", [one, two]], "event": ["like", "Follow up%"]},
					fields=["event"],
				)
			),
			[notifications.FOLLOW_UP_DUE, notifications.FOLLOW_UP_OVERDUE],
		)

	def test_the_spec_seed_has_one_untouched_lead_and_the_reset_restores_the_default(self):
		from unittest.mock import patch

		from sellos.tests import ui_fixtures

		with patch.object(frappe.db, "commit"):  # the fixtures commit for the browser. The test rolls back.
			made = ui_fixtures.seed_board_leads()
			as_user("agent")
			flagged = [lead.client_name for lead in board.visible_leads(follow_up="untouched")]
			self.assertIn(made["old"], flagged)
			self.assertNotIn(made["agent_a"], flagged)
			as_user("company_admin")
			api.save_follow_up_settings(40)
			self.assertEqual(ui_fixtures.reset_follow_up_settings(), {"untouched_days": 3})
			self.assertEqual(follow_ups.untouched_days(), 3)
