"""SOS-P2-09: the caller queue. Leads in every consent status and with different expiries, the order, the
time left, the warnings, who sees which leads, and that consent never drops a lead or blocks a call."""

from pathlib import Path

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_days, add_to_date, now_datetime

from sellos.crm import api, consent
from sellos.crm.test_consent import make_record
from sellos.crm.test_crm import as_user, email
from sellos.crm.test_p1_26_today import TodayCase
from sellos.telephony import queue


class TestTimeLeftText(UnitTestCase):
	"""SOS-P2-09: the time left reads in the two largest units."""

	def test_text(self):
		self.assertEqual(queue.time_left_text(0), "Expired")
		self.assertEqual(queue.time_left_text(-5), "Expired")
		self.assertEqual(queue.time_left_text(30), "Less than a minute")
		self.assertEqual(queue.time_left_text(60), "1 minute")
		self.assertEqual(queue.time_left_text(2 * 86400 + 3 * 3600 + 120), "2 days 3 hours")
		self.assertEqual(queue.time_left_text(5 * 3600 + 10 * 60), "5 hours 10 minutes")


class TestCallerQueue(TodayCase):
	"""SOS-P2-09: the order and the warnings of the caller queue."""

	def build(self):
		"""One lead per case, all the agent's: two lapsing Consented (1 day and 6 days left), an Application
		(about 3 months), a Consent record (never lapses), Unknown, Registered DND and Opted out."""
		now = now_datetime()
		leads = {
			"soonest": self.lead_for(self.agent, "P209 Soonest"),
			"later": self.lead_for(self.agent, "P209 Later"),
			"months": self.lead_for(self.agent, "P209 Months"),
			"forever": self.lead_for(self.agent, "P209 Forever"),
			"unknown": self.lead_for(self.agent, "P209 Unknown"),
			"dnd": self.lead_for(self.agent, "P209 Dnd"),
			"opted": self.lead_for(self.agent, "P209 Opted"),
		}
		make_record(leads["later"], "Inquiry", add_days(now, -1))
		make_record(leads["soonest"], "Inquiry", add_to_date(now, days=-6, hours=-1))
		make_record(leads["months"], "Application", now)
		make_record(leads["forever"], "Consent", now)
		frappe.set_user("Administrator")
		consent.record_dnd_result(leads["dnd"], 1)
		consent.record_opt_out(leads["opted"], "Phone call")
		return leads

	def test_consented_first_soonest_expiry_first_then_the_rest(self):
		leads = self.build()
		as_user("agent")
		rows = queue.caller_queue()
		order = [row["lead"] for row in rows]
		self.assertEqual(
			order,
			[
				leads["soonest"],
				leads["later"],
				leads["months"],
				leads["forever"],
				leads["unknown"],
				leads["dnd"],
				leads["opted"],
			],
		)
		self.assertEqual([row["position"] for row in rows], list(range(1, 8)))

	def test_a_lapsing_lead_shows_the_time_left_and_a_lead_without_expiry_shows_none(self):
		leads = self.build()
		as_user("agent")
		by_lead = {row["lead"]: row for row in queue.caller_queue()}
		soonest, later = by_lead[leads["soonest"]], by_lead[leads["later"]]
		self.assertEqual(soonest["consent_status"], "Consented")
		self.assertTrue(0 < soonest["seconds_left"] < 86400)
		self.assertIn("hour", soonest["time_left"])
		self.assertTrue(4 * 86400 < later["seconds_left"] < 6 * 86400)
		self.assertTrue(later["time_left"].startswith("5 days"), later["time_left"])
		self.assertTrue(by_lead[leads["months"]]["seconds_left"] > 80 * 86400)
		for key in ("forever", "unknown", "dnd", "opted"):
			self.assertIsNone(by_lead[leads[key]]["seconds_left"], key)
			self.assertIsNone(by_lead[leads[key]]["time_left"], key)

	def test_every_lead_appears_whatever_its_status_with_its_warning(self):
		leads = self.build()
		as_user("agent")
		by_lead = {row["lead"]: row for row in queue.caller_queue()}
		self.assertEqual(set(by_lead), set(leads.values()))
		expected = {
			"soonest": ("Consented", None),
			"later": ("Consented", None),
			"months": ("Consented", None),
			"forever": ("Consented", None),
			"unknown": ("Unknown", "amber"),
			"dnd": ("Registered DND", "amber"),
			"opted": ("Opted out", "red"),
		}
		for key, (status, level) in expected.items():
			row = by_lead[leads[key]]
			self.assertEqual(row["consent_status"], status, key)
			self.assertEqual(row["consent_warning"], level, key)
			self.assertEqual(bool(row["consent_message"]), level is not None, key)

	def test_an_expired_record_puts_the_lead_back_among_the_rest(self):
		lead = self.lead_for(self.agent, "P209 Expired")
		make_record(lead, "Inquiry", add_days(now_datetime(), -8))
		as_user("agent")
		row = next(r for r in queue.caller_queue() if r["lead"] == lead)
		self.assertEqual(row["consent_status"], "Unknown")
		self.assertEqual(row["consent_warning"], "amber")
		self.assertIsNone(row["time_left"])

	def test_each_row_names_its_pipeline_so_the_dashboard_counts_one_population(self):
		# SOS-LOOP: the Home consent card counts the same buyer leads as the Leads tile.
		lead = self.lead_for(self.agent, "P209 Pipeline")
		as_user("agent")
		row = next(r for r in queue.caller_queue() if r["lead"] == lead)
		self.assertEqual(row["pipeline"], "Buyer")

	def test_the_longest_live_record_sets_the_window(self):
		lead = self.lead_for(self.agent, "P209 Two Records")
		make_record(lead, "Inquiry", now_datetime())
		make_record(lead, "Application", now_datetime())
		as_user("agent")
		row = next(r for r in queue.caller_queue() if r["lead"] == lead)
		self.assertTrue(row["seconds_left"] > 80 * 86400)
		make_record(lead, "Consent", now_datetime())
		row = next(r for r in queue.caller_queue() if r["lead"] == lead)
		self.assertIsNone(row["seconds_left"])
		self.assertEqual(row["consent_status"], "Consented")

	def test_the_status_matches_the_one_consent_status_rule(self):
		leads = self.build()
		as_user("agent")
		for row in queue.caller_queue():
			self.assertEqual(row["consent_status"], consent.compute_status(row["lead"]))
		self.assertEqual(len(leads), len(queue.caller_queue()))

	def test_an_agent_sees_only_their_own_leads_a_manager_the_team_and_an_admin_all(self):
		mine = self.lead_for(self.agent, "P209 Mine")
		theirs = self.lead_for(self.other, "P209 Theirs")
		outside = self.lead_for(self.outside, "P209 Outside")
		admin_lead = self.lead_for(email("company_admin"), "P209 Admin")
		as_user("agent")
		self.assertEqual({r["lead"] for r in api.caller_queue()["leads"]}, {mine})
		as_user("sales_manager")
		self.assertEqual({r["lead"] for r in api.caller_queue()["leads"]}, {mine, theirs})
		as_user("company_admin")
		seen = {r["lead"] for r in api.caller_queue()["leads"]}
		self.assertTrue({mine, theirs, outside, admin_lead} <= seen)

	def test_an_archived_lead_is_not_in_the_queue(self):
		lead = self.lead_for(self.agent, "P209 Archived")
		frappe.db.set_value("Lead", lead, "archived", 1)
		as_user("agent")
		self.assertNotIn(lead, [r["lead"] for r in queue.caller_queue()])

	def test_an_agent_gets_masked_numbers_and_an_admin_full_ones(self):
		from sellos.tests import phones

		number = phones.in_mobile(971)
		lead = self.lead_for(self.agent, "P209 Phone", number=number)
		as_user("agent")
		view = api.caller_queue()
		row = next(r for r in view["leads"] if r["lead"] == lead)
		self.assertNotEqual(row["phone"], number)
		self.assertTrue(row["phone"].endswith(number[-3:]))
		self.assertEqual(view["full_numbers"], 0)
		as_user("company_admin")
		view = api.caller_queue()
		self.assertEqual(next(r for r in view["leads"] if r["lead"] == lead)["phone"], number)
		self.assertEqual(view["full_numbers"], 1)

	def test_a_partner_and_a_client_are_refused(self):
		for key in ("channel_partner", "client"):
			as_user(key)
			with self.assertRaises(frappe.PermissionError):
				api.caller_queue()

	def test_consent_never_blocks_a_call_on_a_queued_lead(self):
		leads = self.build()
		as_user("agent")
		for lead in leads.values():
			check = consent.check_contact(lead, "Call")
			self.assertFalse(check.refused)
		as_user("agent")
		logged = api.log_call(leads["opted"], "Wrong number", "p209 call")
		self.assertTrue(logged["activity"])

	def test_the_queue_module_never_refuses_on_consent(self):
		text = Path(__file__).with_name("queue.py").read_text(encoding="utf-8")
		self.assertNotIn("frappe.throw", text)
		self.assertNotIn("PermissionError", text)


class TestQueueFixtures(TodayCase):
	"""SOS-P2-09: the regression seed's queue lead is made through the API and read back."""

	def test_the_regression_queue_lead_has_a_live_application_consent_and_is_made_once(self):
		from sellos.tests import ui_fixtures

		admin, agent = email("company_admin"), email("agent")
		ui_fixtures._seed_queue_lead(admin, agent)
		ui_fixtures._seed_queue_lead(admin, agent)  # safe to run again: still one
		clients = frappe.get_all("Client", filters={"client_name": "Regression Queue Application"})
		self.assertEqual(len(clients), 1)
		lead = frappe.db.get_value("Lead", {"client": clients[0].name}, "name")
		self.assertEqual(consent.compute_status(lead), "Consented")
		as_user("agent")
		row = next(r for r in queue.caller_queue() if r["lead"] == lead)
		self.assertTrue(row["seconds_left"] > 80 * 86400)
