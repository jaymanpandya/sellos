"""SOS-P7-13: response time alerts and escalation. Each limit, the escalation with and without a team, one
record per miss and its resolution time, all with a fixed clock."""

import itertools

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, get_datetime

from sellos import hooks
from sellos.access.roles import ensure_roles
from sellos.crm import api, notifications, pipeline, response_times
from sellos.crm.test_crm import as_user, email
from sellos.testing.users import create_test_users
from sellos.tests import phones

_SEEDS = itertools.count(713)
ALERT = "Response Alert"


class TestResponseAlerts(IntegrationTestCase):
	"""SOS-P7-13: the two limits, the escalation, one record per miss, the resolution."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		pipeline.ensure_default_stages()
		frappe.db.set_single_value("SellOS Settings", "default_team", None)
		frappe.db.set_single_value("SellOS Settings", "response_unassigned_minutes", 10)
		frappe.db.set_single_value("SellOS Settings", "response_contact_minutes", 120)
		self.agent, self.manager, self.admin = email("agent"), email("sales_manager"), email("company_admin")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_team(self):
		return frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P713 Team",
				"manager": self.manager,
				"members": [{"agent": self.agent}],
			}
		).insert()

	def make_lead(self, assigned_to=None):
		as_user("company_admin")
		client = api.save_client(
			values={
				"client_name": "P713 Buyer",
				"client_type": "Buyer",
				"phone": phones.in_mobile(next(_SEEDS)),
			}
		)
		values = {"client": client["name"], "source": "Website"}
		if assigned_to:
			values["assigned_to"] = assigned_to
		name = api.save_lead(values=values)["lead"]["name"]
		frappe.set_user("Administrator")
		return name

	def since(self, lead):
		"""The moment the clock starts: the lead's assignment, or its creation when it has no agent."""
		agent = frappe.db.get_value("Lead", lead, "assigned_to")
		if agent:
			return get_datetime(response_times.assigned_on(lead, agent))
		return get_datetime(frappe.db.get_value("Lead", lead, "creation"))

	def at(self, lead, minutes):
		return add_to_date(self.since(lead), minutes=minutes)

	def alerts(self, lead, **filters):
		return frappe.get_all(
			ALERT,
			filters={"lead": lead, **filters},
			fields=[
				"name",
				"limit_type",
				"agent",
				"missed_on",
				"resolved_on",
				"resolution",
				"escalation_level",
				"escalated_to",
				"counted_from",
			],
		)

	def told(self, lead, user):
		return frappe.get_all(
			"App Notification",
			filters={"lead": lead, "recipient": user, "event": notifications.RESPONSE_MISSED},
			pluck="title",
		)

	def log_activity(self, lead, when):
		return frappe.get_doc(
			{"doctype": "Lead Activity", "lead": lead, "activity_type": "Call", "activity_date": when}
		).insert(ignore_permissions=True)

	# --- the unassigned limit -------------------------------------------------------------------

	def test_an_unassigned_lead_alerts_the_company_admin_after_ten_minutes(self):
		lead = self.make_lead()
		self.assertFalse(frappe.db.get_value("Lead", lead, "assigned_to"))
		self.assertEqual(response_times.check_response_times(self.at(lead, 9))["missed"], 0)
		self.assertEqual(self.alerts(lead), [])

		self.assertEqual(response_times.check_response_times(self.at(lead, 10))["missed"], 1)
		(alert,) = self.alerts(lead)
		self.assertEqual(alert.limit_type, "Unassigned")
		self.assertIsNone(alert.agent)
		self.assertEqual(get_datetime(alert.missed_on), self.at(lead, 10))
		self.assertIsNone(alert.resolved_on)
		self.assertEqual(len(self.told(lead, self.admin)), 1)
		self.assertEqual(self.told(lead, self.agent), [])

	def test_the_unassigned_limit_follows_the_setting(self):
		frappe.db.set_single_value("SellOS Settings", "response_unassigned_minutes", 30)
		lead = self.make_lead()
		self.assertEqual(response_times.check_response_times(self.at(lead, 29))["missed"], 0)
		self.assertEqual(response_times.check_response_times(self.at(lead, 30))["missed"], 1)

	def test_giving_the_lead_an_agent_resolves_the_miss_at_that_time(self):
		lead = self.make_lead()
		response_times.check_response_times(self.at(lead, 10))
		frappe.set_user("Administrator")
		doc = frappe.get_doc("Lead", lead)
		doc.assigned_to = self.agent
		doc.save(ignore_permissions=True)
		given = get_datetime(response_times.assigned_on(lead, self.agent))
		self.assertEqual(response_times.check_response_times(self.at(lead, 14))["resolved"], 1)
		(alert,) = self.alerts(lead)
		self.assertEqual(alert.resolution, "Assigned")
		self.assertEqual(get_datetime(alert.resolved_on), given)

	def test_an_unassigned_lead_escalates_to_the_company_admin_again(self):
		lead = self.make_lead()
		response_times.check_response_times(self.at(lead, 10))
		self.assertEqual(response_times.check_response_times(self.at(lead, 19))["escalated"], 0)
		self.assertEqual(response_times.check_response_times(self.at(lead, 20))["escalated"], 1)
		(alert,) = self.alerts(lead)
		self.assertEqual(alert.escalation_level, 2)
		self.assertIn(self.admin, alert.escalated_to)
		self.assertEqual(len(self.told(lead, self.admin)), 2)
		# A third check changes nothing.
		self.assertEqual(response_times.check_response_times(self.at(lead, 60))["escalated"], 0)
		self.assertEqual(len(self.told(lead, self.admin)), 2)

	# --- the contact limit ----------------------------------------------------------------------

	def test_an_assigned_lead_with_no_contact_alerts_its_agent_after_two_hours(self):
		lead = self.make_lead(self.agent)
		self.assertEqual(response_times.check_response_times(self.at(lead, 119))["missed"], 0)
		self.assertEqual(response_times.check_response_times(self.at(lead, 120))["missed"], 1)
		(alert,) = self.alerts(lead)
		self.assertEqual((alert.limit_type, alert.agent), ("No contact", self.agent))
		self.assertEqual(get_datetime(alert.missed_on), self.at(lead, 120))
		self.assertEqual(len(self.told(lead, self.agent)), 1)
		self.assertEqual(self.told(lead, self.manager), [])

	def test_the_contact_limit_follows_the_setting(self):
		frappe.db.set_single_value("SellOS Settings", "response_contact_minutes", 45)
		lead = self.make_lead(self.agent)
		self.assertEqual(response_times.check_response_times(self.at(lead, 44))["missed"], 0)
		self.assertEqual(response_times.check_response_times(self.at(lead, 45))["missed"], 1)

	def test_an_activity_in_time_means_no_miss(self):
		lead = self.make_lead(self.agent)
		self.log_activity(lead, self.at(lead, 30))
		self.assertEqual(response_times.check_response_times(self.at(lead, 200))["missed"], 0)
		self.assertEqual(self.alerts(lead), [])

	def test_a_call_in_time_means_no_miss(self):
		lead = self.make_lead(self.agent)
		frappe.get_doc(
			{
				"doctype": "Call Log",
				"lead": lead,
				"provider": "fake",
				"call_id": "p713-call-1",
				"purpose": "Service",
				"started_on": self.at(lead, 20),
			}
		).insert(ignore_permissions=True)
		self.assertEqual(response_times.check_response_times(self.at(lead, 200))["missed"], 0)

	def test_a_late_activity_resolves_the_miss_at_the_time_it_was_logged(self):
		lead = self.make_lead(self.agent)
		response_times.check_response_times(self.at(lead, 120))
		self.log_activity(lead, self.at(lead, 130))
		self.assertEqual(response_times.check_response_times(self.at(lead, 140))["resolved"], 1)
		(alert,) = self.alerts(lead)
		self.assertEqual(alert.resolution, "Contacted")
		self.assertEqual(get_datetime(alert.resolved_on), self.at(lead, 130))
		# Resolved, so it is never escalated.
		self.assertEqual(response_times.check_response_times(self.at(lead, 300))["escalated"], 0)
		self.assertEqual(self.told(lead, self.manager), [])

	def test_a_miss_escalates_to_the_sales_manager_of_the_agents_team(self):
		self.make_team()
		lead = self.make_lead(self.agent)
		response_times.check_response_times(self.at(lead, 120))
		self.assertEqual(response_times.check_response_times(self.at(lead, 239))["escalated"], 0)
		self.assertEqual(response_times.check_response_times(self.at(lead, 240))["escalated"], 1)
		(alert,) = self.alerts(lead)
		self.assertEqual(alert.escalation_level, 2)
		self.assertEqual(alert.escalated_to, self.manager)
		self.assertEqual(len(self.told(lead, self.manager)), 1)
		self.assertEqual(len(self.told(lead, self.agent)), 1)

	def test_a_miss_escalates_to_the_company_admin_when_the_agent_has_no_team(self):
		lead = self.make_lead(self.agent)
		response_times.check_response_times(self.at(lead, 120))
		response_times.check_response_times(self.at(lead, 240))
		(alert,) = self.alerts(lead)
		self.assertEqual(alert.escalation_level, 2)
		self.assertIn(self.admin, alert.escalated_to)
		self.assertNotIn(self.manager, alert.escalated_to)
		self.assertEqual(len(self.told(lead, self.admin)), 1)
		self.assertEqual(self.told(lead, self.manager), [])

	# --- the record, and what an alert never does -----------------------------------------------

	def test_each_miss_is_recorded_once(self):
		lead = self.make_lead(self.agent)
		for minutes in (120, 121, 125, 240, 241):
			response_times.check_response_times(self.at(lead, minutes))
		self.assertEqual(len(self.alerts(lead)), 1)
		self.assertEqual(len(self.told(lead, self.agent)), 1)

	def test_a_reassigned_lead_starts_a_new_clock_and_resolves_the_old_miss(self):
		lead = self.make_lead(self.agent)
		first = self.since(lead)
		response_times.check_response_times(add_to_date(first, minutes=120))
		frappe.set_user("Administrator")
		doc = frappe.get_doc("Lead", lead)
		doc.assigned_to = self.admin
		doc.save(ignore_permissions=True)
		second = self.since(lead)
		response_times.check_response_times(add_to_date(second, minutes=10))
		(old,) = self.alerts(lead, agent=self.agent)
		self.assertEqual(old.resolution, "Reassigned")
		self.assertEqual(get_datetime(old.resolved_on), second)
		self.assertEqual(self.alerts(lead, agent=self.admin), [])
		response_times.check_response_times(add_to_date(second, minutes=120))
		(new,) = self.alerts(lead, agent=self.admin)
		self.assertEqual(new.limit_type, "No contact")
		self.assertIsNone(new.resolved_on)

	def test_an_alert_never_reassigns_or_changes_the_lead(self):
		lead = self.make_lead(self.agent)
		before = frappe.db.get_value("Lead", lead, ["assigned_to", "stage", "modified"], as_dict=True)
		for minutes in (120, 240, 600):
			response_times.check_response_times(self.at(lead, minutes))
		self.assertEqual(
			frappe.db.get_value("Lead", lead, ["assigned_to", "stage", "modified"], as_dict=True), before
		)

	def test_a_closed_or_archived_lead_is_not_counted(self):
		lost = self.make_lead(self.agent)
		frappe.db.set_value("Lead", lost, "stage", pipeline.CLOSED_LOST)
		archived = self.make_lead(self.agent)
		frappe.db.set_value("Lead", archived, "archived", 1)
		response_times.check_response_times(self.at(lost, 200))
		self.assertEqual(self.alerts(lost) + self.alerts(archived), [])

	def test_a_response_alert_is_never_deleted(self):
		lead = self.make_lead()
		response_times.check_response_times(self.at(lead, 10))
		(alert,) = self.alerts(lead)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(ALERT, alert.name, force=True)

	# --- the settings and the schedule ----------------------------------------------------------

	def test_a_company_admin_saves_both_limits_within_bounds(self):
		as_user("company_admin")
		self.assertEqual(
			response_times.get_response_limits(), {"unassigned_minutes": 10, "contact_minutes": 120}
		)
		saved = response_times.save_response_limits(unassigned_minutes=15, contact_minutes="90")
		self.assertEqual(saved, {"unassigned_minutes": 15, "contact_minutes": 90})
		self.assertEqual(response_times.limits(), (15, 90))
		for bad in (0, -5, 2881, "x"):
			with self.assertRaises(frappe.ValidationError):
				response_times.save_response_limits(unassigned_minutes=bad, contact_minutes=90)
		with self.assertRaises(frappe.ValidationError):
			response_times.save_response_limits(unassigned_minutes=15, contact_minutes=0)
		self.assertEqual(response_times.limits(), (15, 90))

	def test_an_empty_setting_falls_back_to_the_default(self):
		frappe.db.set_single_value("SellOS Settings", "response_unassigned_minutes", 0)
		frappe.db.set_single_value("SellOS Settings", "response_contact_minutes", 0)
		self.assertEqual(response_times.limits(), (10, 120))

	def test_the_scheduler_runs_the_check_every_five_minutes(self):
		self.assertEqual(
			hooks.scheduler_events["cron"]["*/5 * * * *"], ["sellos.crm.response_times.check_response_times"]
		)
