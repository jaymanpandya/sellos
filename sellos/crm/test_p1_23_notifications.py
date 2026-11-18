"""SOS-P1-23: in-app notifications. Each event notifies the right user and nobody else."""

import itertools
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, get_datetime, now_datetime, today

from sellos import hooks
from sellos.access.roles import ensure_roles
from sellos.crm import api, notifications
from sellos.crm.test_crm import as_user, email
from sellos.testing.users import create_test_users
from sellos.tests import phones

_SEEDS = itertools.count(330)


class NotificationCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_lead(self, who="company_admin", assigned_to=None, name="P123 Buyer"):
		as_user(who)
		client = api.save_client(
			values={"client_name": name, "client_type": "Buyer", "phone": phones.in_mobile(next(_SEEDS))}
		)
		values = {"client": client["name"], "source": "Website"}
		if assigned_to:
			values["assigned_to"] = email(assigned_to)
		lead = api.save_lead(values=values)["lead"]["name"]
		frappe.set_user("Administrator")
		return lead

	def task(self, lead, assigned_to=None, **values):
		return frappe.get_doc(
			{
				"doctype": "Lead Task",
				"lead": lead,
				"title": "P123 call back",
				"due_date": values.pop("due_date", today()),
				"assigned_to": email(assigned_to) if assigned_to else None,
				**values,
			}
		).insert(ignore_permissions=True)

	def visit(self, lead, when, **values):
		return frappe.get_doc(
			{
				"doctype": "Site Visit",
				"lead": lead,
				"project_name": "P123 Tower",
				"visit_datetime": when,
				**values,
			}
		).insert(ignore_permissions=True)

	def rows(self, **filters):
		return frappe.get_all(
			"App Notification",
			filters=filters,
			fields=["name", "recipient", "event", "title", "message", "lead", "is_read"],
			order_by="creation asc",
		)

	def who(self, rows):
		return sorted(row.recipient for row in rows)


class TestAssignmentEvents(NotificationCase):
	"""SOS-P1-23: a lead assigned to me, and a lead reassigned away."""

	def test_a_lead_assigned_to_an_agent_notifies_that_agent_only(self):
		lead = self.make_lead(assigned_to="agent")
		rows = self.rows(lead=lead)
		self.assertEqual(self.who(rows), [email("agent")])
		self.assertEqual(rows[0].event, "Lead assigned")
		self.assertIn("P123 Buyer", rows[0].message)
		self.assertEqual(self.rows(recipient=email("company_admin")), [])

	def test_a_lead_with_nobody_assigned_or_assigned_to_oneself_notifies_nobody(self):
		self.make_lead()
		self.make_lead(who="agent", assigned_to="agent", name="P123 Own")
		self.assertEqual(self.rows(), [])

	def test_saving_a_lead_without_changing_its_assignee_notifies_nobody(self):
		lead = self.make_lead(assigned_to="agent")
		before = len(self.rows())
		as_user("company_admin")
		api.save_lead(name=lead, values={"notes": "P123 note"})
		self.assertEqual(len(self.rows()), before)

	def test_a_reassigned_lead_notifies_the_new_agent_and_the_old_one_and_nobody_else(self):
		lead = self.make_lead(assigned_to="agent")
		as_user("company_admin")
		api.reassign_lead(lead, email("channel_partner"))
		frappe.set_user("Administrator")
		assigned = self.rows(lead=lead, event="Lead assigned")
		self.assertEqual(self.who(assigned), [email("agent"), email("channel_partner")])
		away = self.rows(event="Lead reassigned away")
		self.assertEqual(self.who(away), [email("agent")])
		self.assertEqual(self.rows(recipient=email("company_admin")), [])
		self.assertEqual(self.rows(recipient=email("sales_manager")), [])

	def test_the_old_agent_who_can_no_longer_see_the_lead_is_told_nothing_about_it(self):
		lead = self.make_lead(assigned_to="agent", name="P123 Secret Buyer")
		as_user("company_admin")
		api.reassign_lead(lead, email("channel_partner"))
		away = self.rows(event="Lead reassigned away")[0]
		self.assertIsNone(away.lead)
		self.assertNotIn("Secret", f"{away.title} {away.message}")
		self.assertNotIn(lead, f"{away.title} {away.message}")

	def test_the_old_agent_who_still_sees_the_lead_gets_it_with_a_link(self):
		lead = self.make_lead(who="agent", assigned_to="agent", name="P123 Mine Buyer")
		as_user("company_admin")
		api.reassign_lead(lead, email("channel_partner"))
		away = self.rows(event="Lead reassigned away")[0]
		self.assertEqual((away.recipient, away.lead), (email("agent"), lead))
		self.assertIn("P123 Mine Buyer", away.message)

	def test_a_lead_whose_consent_is_opted_out_is_still_notified(self):
		lead = self.make_lead(assigned_to="agent")
		as_user("agent")
		api.record_opt_out(lead, "Phone call")
		as_user("company_admin")
		api.reassign_lead(lead, email("channel_partner"))
		self.assertEqual(len(self.rows(recipient=email("channel_partner"), lead=lead)), 1)


class TestFollowUpEvents(NotificationCase):
	"""SOS-P1-23: a follow up due or overdue."""

	def test_a_follow_up_due_in_ten_minutes_notifies_its_agent_once(self):
		lead = self.make_lead(assigned_to="agent")
		now = now_datetime()
		task = self.task(lead, "agent", due_at=add_to_date(now, minutes=10))
		before = len(self.rows(event="Follow up due"))
		self.assertEqual(notifications.notify_follow_ups(now), 1)
		self.assertEqual(notifications.notify_follow_ups(now), 0)
		rows = self.rows(event="Follow up due")[before:]
		self.assertEqual((self.who(rows), rows[0].lead), ([email("agent")], lead))
		self.assertIn(task.title, rows[0].message)
		self.assertEqual(self.rows(recipient=email("company_admin"), event="Follow up due"), [])

	def test_a_follow_up_more_than_fifteen_minutes_away_is_not_yet_due(self):
		lead = self.make_lead(assigned_to="agent")
		now = now_datetime()
		self.task(lead, "agent", due_at=add_to_date(now, minutes=40))
		self.assertEqual(notifications.notify_follow_ups(now), 0)
		self.assertEqual(self.rows(event="Follow up due"), [])

	def test_a_follow_up_that_passes_its_time_becomes_overdue_and_is_told_once_more(self):
		lead = self.make_lead(assigned_to="agent")
		now = now_datetime()
		self.task(lead, "agent", due_at=add_to_date(now, minutes=5))
		notifications.notify_follow_ups(now)
		later = add_to_date(now, minutes=30)
		self.assertEqual(notifications.notify_follow_ups(later), 1)
		self.assertEqual(notifications.notify_follow_ups(later), 0)
		events = [row.event for row in self.rows(recipient=email("agent"), lead=lead)]
		self.assertEqual(events.count("Follow up due"), 1)
		self.assertEqual(events.count("Follow up overdue"), 1)

	def test_a_follow_up_with_only_a_date_is_due_that_day_and_overdue_after_it(self):
		lead = self.make_lead(assigned_to="agent")
		self.task(lead, "agent", due_date=today())
		self.task(lead, "agent", due_date=add_days(today(), -2))
		self.task(lead, "agent", due_date=add_days(today(), 3))
		self.assertEqual(notifications.notify_follow_ups(), 2)
		events = sorted(
			row.event for row in self.rows(recipient=email("agent"), lead=lead) if "Follow" in row.event
		)
		self.assertEqual(events, ["Follow up due", "Follow up overdue"])

	def test_a_done_or_archived_follow_up_or_one_on_an_archived_lead_notifies_nobody(self):
		lead = self.make_lead(assigned_to="agent")
		archived_lead = self.make_lead(assigned_to="agent", name="P123 Archived")
		self.task(lead, "agent", due_date=add_days(today(), -1), status="Done")
		self.task(lead, "agent", due_date=add_days(today(), -1), archived=1)
		self.task(archived_lead, "agent", due_date=add_days(today(), -1))
		frappe.db.set_value("Lead", archived_lead, "archived", 1)
		self.assertEqual(notifications.notify_follow_ups(), 0)

	def test_a_follow_up_with_no_assignee_goes_to_the_leads_agent(self):
		lead = self.make_lead(assigned_to="agent")
		frappe.db.set_value(
			"Lead Task", self.task(lead, "agent", due_date=add_days(today(), -1)).name, "assigned_to", None
		)
		notifications.notify_follow_ups()
		self.assertEqual(self.who(self.rows(event="Follow up overdue")), [email("agent")])

	def test_a_follow_up_assigned_to_someone_who_cannot_see_the_lead_notifies_nobody(self):
		lead = self.make_lead(assigned_to="agent")
		self.task(lead, "channel_partner", due_date=add_days(today(), -1))
		self.assertEqual(notifications.notify_follow_ups(), 0)
		self.assertEqual(self.rows(recipient=email("channel_partner")), [])


class TestSiteVisitEvents(NotificationCase):
	"""SOS-P1-23: a site visit tomorrow."""

	def test_a_visit_tomorrow_notifies_the_leads_agent_once_and_nobody_else(self):
		lead = self.make_lead(assigned_to="agent")
		tomorrow = add_to_date(get_datetime(add_days(today(), 1)), hours=11)
		self.visit(lead, tomorrow)
		self.assertEqual(notifications.notify_site_visits(), 1)
		self.assertEqual(notifications.notify_site_visits(), 0)
		rows = self.rows(event="Site visit tomorrow")
		self.assertEqual((self.who(rows), rows[0].lead), ([email("agent")], lead))
		self.assertIn("P123 Tower", rows[0].message)

	def test_a_visit_today_or_in_two_days_or_not_scheduled_notifies_nobody(self):
		lead = self.make_lead(assigned_to="agent")
		midnight = get_datetime(today())
		self.visit(lead, add_to_date(midnight, hours=9))
		self.visit(lead, add_to_date(midnight, days=2, hours=9))
		self.visit(lead, add_to_date(midnight, days=1, hours=9), status="Cancelled")
		self.visit(lead, add_to_date(midnight, days=1, hours=10), status="Done")
		self.assertEqual(notifications.notify_site_visits(), 0)

	def test_a_visit_on_a_lead_with_no_agent_notifies_nobody(self):
		lead = self.make_lead()
		self.visit(lead, add_to_date(get_datetime(add_days(today(), 1)), hours=9))
		self.assertEqual(notifications.notify_site_visits(), 0)

	def test_the_scheduler_runs_the_three_jobs(self):
		events = hooks.scheduler_events
		self.assertIn("sellos.crm.notifications.notify_follow_ups", events["all"])
		self.assertIn("sellos.crm.notifications.notify_site_visits", events["hourly"])


class TestTheBell(NotificationCase):
	"""SOS-P1-23: the bell shows the signed in user's unread notifications, newest first."""

	def test_the_list_holds_only_the_signed_in_users_unread_newest_first(self):
		lead = self.make_lead(assigned_to="agent")
		mine = [
			notifications.notify(email("agent"), "Follow up due", f"P123 mine {n}", lead=lead)
			for n in range(3)
		]
		notifications.notify(email("company_admin"), "Follow up due", "P123 theirs", lead=lead)
		as_user("agent")
		result = api.list_notifications()
		titles = [row.title for row in result["items"]]
		self.assertEqual(titles[:3], ["P123 mine 2", "P123 mine 1", "P123 mine 0"])
		self.assertNotIn("P123 theirs", titles)
		self.assertEqual(result["unread"], len(result["items"]))
		self.assertEqual({row.lead for row in result["items"]}, {lead})
		self.assertEqual(set(mine) - {row.name for row in result["items"]}, set())

	def test_opening_one_marks_it_read_and_only_that_one(self):
		lead = self.make_lead(assigned_to="agent")
		first = notifications.notify(email("agent"), "Follow up due", "P123 first", lead=lead)
		notifications.notify(email("agent"), "Follow up due", "P123 second", lead=lead)
		as_user("agent")
		before = api.list_notifications()["unread"]
		self.assertEqual(api.mark_notification_read(first), {"unread": before - 1})
		self.assertNotIn(first, [row.name for row in api.list_notifications()["items"]])
		self.assertEqual(frappe.db.get_value("App Notification", first, "is_read"), 1)
		self.assertTrue(frappe.db.get_value("App Notification", first, "read_on"))

	def test_mark_all_read_clears_the_users_own_and_leaves_everyone_elses(self):
		lead = self.make_lead(assigned_to="agent")
		notifications.notify(email("agent"), "Follow up due", "P123 mine", lead=lead)
		theirs = notifications.notify(email("company_admin"), "Follow up due", "P123 theirs", lead=lead)
		as_user("agent")
		self.assertEqual(api.mark_all_notifications_read(), {"unread": 0})
		self.assertEqual(api.list_notifications(), {"unread": 0, "items": []})
		self.assertEqual(frappe.db.get_value("App Notification", theirs, "is_read"), 0)

	def test_a_user_cannot_open_or_read_another_users_notification(self):
		lead = self.make_lead(assigned_to="agent")
		theirs = notifications.notify(email("company_admin"), "Follow up due", "P123 theirs", lead=lead)
		as_user("agent")
		with self.assertRaises(frappe.DoesNotExistError):
			api.mark_notification_read(theirs)
		with self.assertRaises(frappe.DoesNotExistError):
			api.mark_notification_read("NTF-99999")
		self.assertEqual(frappe.db.get_value("App Notification", theirs, "is_read"), 0)

	def test_customer_roles_have_no_direct_read_of_notifications(self):
		lead = self.make_lead(assigned_to="agent")
		name = notifications.notify(email("agent"), "Follow up due", "P123 direct", lead=lead)
		for who in ("agent", "company_admin", "sales_manager", "channel_partner", "client"):
			as_user(who)
			self.assertFalse(frappe.has_permission("App Notification", "read", doc=name), who)
			with self.assertRaises(frappe.PermissionError):
				frappe.get_list("App Notification")

	def test_a_notification_is_never_deleted(self):
		lead = self.make_lead(assigned_to="agent")
		name = notifications.notify(email("agent"), "Follow up due", "P123 keep", lead=lead)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("App Notification", name, force=True)


class TestNobodyIsToldOfWhatTheyCannotSee(NotificationCase):
	"""SOS-P1-23: a user never receives a notification about a record they may not see."""

	def test_nothing_is_made_for_a_lead_the_recipient_cannot_read(self):
		lead = self.make_lead(assigned_to="agent")
		for who in ("channel_partner", "sales_manager", "client"):
			self.assertIsNone(
				notifications.notify(email(who), "Follow up due", "P123 hidden", lead=lead), who
			)
		self.assertIsNone(
			notifications.notify("sos_test_nobody@example.com", "Follow up due", "x", lead=lead)
		)
		self.assertEqual(self.rows(title="P123 hidden"), [])

	def test_a_disabled_user_is_told_nothing(self):
		lead = self.make_lead(assigned_to="agent")
		frappe.db.set_value("User", email("agent"), "enabled", 0)
		self.assertIsNone(notifications.notify(email("agent"), "Follow up due", "P123 off", lead=lead))

	def test_an_old_notification_disappears_when_the_user_loses_the_lead(self):
		lead = self.make_lead(assigned_to="agent")
		as_user("agent")
		self.assertTrue(any(row.lead == lead for row in api.list_notifications()["items"]))
		as_user("company_admin")
		api.reassign_lead(lead, email("channel_partner"))
		as_user("agent")
		result = api.list_notifications()
		self.assertEqual([row for row in result["items"] if row.lead == lead], [])
		# the generic notice that the lead was taken away is what is left, with no lead behind it
		self.assertEqual([row.event for row in result["items"]], ["Lead reassigned away"])
		self.assertEqual(result["unread"], 1)

	def test_a_sales_manager_is_told_of_a_team_lead_and_not_of_another_teams(self):
		from sellos.access import teams

		as_user("company_admin")
		team = teams.save_team(
			values={"team_name": "P123 Team", "manager": email("sales_manager"), "members": [email("agent")]}
		)
		lead = self.make_lead(assigned_to="agent")
		as_user("sales_manager")
		self.assertTrue(frappe.has_permission("Lead", "read", doc=lead))
		self.assertIsNotNone(team)
		frappe.set_user("Administrator")
		self.assertIsNotNone(
			notifications.notify(email("sales_manager"), "Follow up due", "P123 team", lead=lead)
		)
		other = self.make_lead(who="company_admin", assigned_to="channel_partner", name="P123 Other Team")
		self.assertIsNone(
			notifications.notify(email("sales_manager"), "Follow up due", "P123 other", lead=other)
		)


class TestEmailCopies(NotificationCase):
	"""SOS-P1-23: one place to add email copies, called once for each notification made."""

	def test_send_copies_runs_once_for_each_notification_made_and_not_for_a_refused_one(self):
		lead = self.make_lead(assigned_to="agent")
		with patch.object(notifications, "send_copies") as send:
			name = notifications.notify(
				email("agent"), "Follow up due", "P123 copy", lead=lead, dedupe_key="p123-copy"
			)
			notifications.notify(
				email("agent"), "Follow up due", "P123 copy", lead=lead, dedupe_key="p123-copy"
			)
			notifications.notify(email("channel_partner"), "Follow up due", "P123 refused", lead=lead)
		send.assert_called_once()
		self.assertEqual(send.call_args.args[0].name, name)


class TestFixtures(NotificationCase):
	"""SOS-P1-23: the data the bell spec and the regression walk see, read back."""

	def test_the_spec_seed_notifies_the_agent_twice_and_the_admin_once_and_the_cleanup_removes_it(self):
		from sellos.tests import ui_fixtures

		with patch.object(frappe.db, "commit"):  # the fixtures commit for the browser. The test rolls back.
			made = ui_fixtures.seed_notifications()
			as_user("agent")
			titles = [row.message for row in api.list_notifications()["items"]]
			self.assertEqual(len(titles), 2)
			self.assertIn(made["b"]["client_name"], titles[0])
			self.assertIn(made["a"]["client_name"], titles[1])
			as_user("company_admin")
			admin_items = api.list_notifications()["items"]
			self.assertEqual([row.lead for row in admin_items], [made["c"]["lead"]])
			ui_fixtures.reassign_gate_notify_lead(made["b"]["lead"])
			as_user("agent")
			after = api.list_notifications()["items"]
			self.assertEqual([row.event for row in after], ["Lead reassigned away", "Lead assigned"])
			self.assertEqual([row.lead for row in after], [None, made["a"]["lead"]])
			ui_fixtures.remove_gate_notifications()
		self.assertEqual(self.rows(), [])

	def test_the_regression_seed_schedules_a_visit_tomorrow_and_notifies_once_however_often_it_runs(self):
		from sellos.tests import ui_fixtures

		lead = self.make_lead(who="agent", assigned_to="agent", name="Regression Buyer One")
		for _ in range(2):
			ui_fixtures._seed_notifications(email("agent"))
		visits = frappe.get_all("Site Visit", filters={"lead": lead}, pluck="project_name")
		self.assertEqual(visits, ["Regression Tomorrow Heights"])
		rows = self.rows(event="Site visit tomorrow", recipient=email("agent"))
		self.assertEqual([row.lead for row in rows], [lead])
