"""SOS-P2-11: the call reports. Calls are placed through the fake provider, then every total is
reconciled with the Call Log (read with its own SQL) and every figure with the calls it drills down to."""

import frappe
from frappe.utils import add_days, today

from sellos.crm import api as crm
from sellos.crm.test_crm import CrmCase, as_user
from sellos.reports import calls
from sellos.tests import phones
from sellos.tests.ui_fixtures import REPORT_CALL_PLAN, call_log_totals, place_report_calls

KEYS = ("soon", "months", "forever", "unknown", "opted", "dnd")


class TestCallReports(CrmCase):
	"""SOS-P2-11: cost, connect rate, talk time and consent coverage, with dates and drill downs."""

	def setUp(self):
		as_user("company_admin")
		self.leads = {}
		for seed, key in enumerate(KEYS, start=3600):
			client = crm.save_client(
				values={
					"client_name": f"P211 {key}",
					"client_type": "Buyer",
					"phone": phones.in_mobile(seed),
				}
			)
			self.leads[key] = crm.save_lead(values={"client": client["name"], "source": "Website"})["lead"][
				"name"
			]
		crm.record_consent(self.leads["soon"], "Inquiry", "https://example.com/p211")
		crm.record_consent(self.leads["months"], "Application", "https://example.com/p211")
		crm.record_consent(self.leads["forever"], "Consent", "https://example.com/p211")
		crm.record_opt_out(self.leads["opted"], "Phone call")
		crm.record_dnd_result(self.leads["dnd"], 1)
		frappe.set_user("Administrator")
		self.start, self.end = str(add_days(today(), -12)), str(today())
		self.before = self.report()
		self.calls = place_report_calls(self.leads)
		self.mine = {c["log"]: c for c in self.calls if c["day"] >= self.start}
		as_user("company_admin")

	def report(self, start=None, end=None):
		previous = frappe.session.user
		as_user("company_admin")
		try:
			return calls.call_report(start or self.start, end or self.end)
		finally:
			frappe.set_user(previous)

	def drill(self, **filters):
		return calls.call_report_calls(self.start, self.end, **filters)

	def test_totals_match_the_call_log_and_the_seeded_calls(self):
		report = self.report()
		table = call_log_totals(self.start, self.end)
		totals = report["totals"]
		self.assertEqual(
			(totals["calls"], totals["connected"], totals["talk_seconds"], totals["cost"]),
			(table["calls"], table["connected"], table["seconds"], table["rupees"]),
		)
		gained = totals["calls"] - self.before["totals"]["calls"]
		self.assertEqual(gained, len(self.mine))
		self.assertEqual(gained, 6)  # the 40 day old call is outside the range
		self.assertEqual(totals["talk_seconds"] - self.before["totals"]["talk_seconds"], 125 + 61 + 30 + 600)
		self.assertAlmostEqual(totals["cost"] - self.before["totals"]["cost"], 3 + 1.5 + 1 + 10, places=4)
		self.assertEqual(totals["connected"] - self.before["totals"]["connected"], 4)

	def test_the_groups_add_up_to_the_totals(self):
		report = self.report()
		for group in ("by_agent", "by_purpose"):
			rows = report[group]
			self.assertEqual(sum(r["calls"] for r in rows), report["totals"]["calls"])
			self.assertEqual(sum(r["connected"] for r in rows), report["totals"]["connected"])
			self.assertEqual(sum(r["talk_seconds"] for r in rows), report["totals"]["talk_seconds"])
			self.assertAlmostEqual(sum(r["cost"] for r in rows), report["totals"]["cost"], places=4)
		self.assertEqual(sum(r["calls"] for r in report["consent"]), report["totals"]["calls"])
		self.assertEqual(
			[r["status"] for r in report["consent"]],
			["Consented", "Unknown", "Opted out", "Registered DND"],
		)

	def test_every_figure_drills_down_to_exactly_its_calls(self):
		report = self.report()

		def same(found, row):
			totals = found["totals"]
			self.assertEqual(len(found["calls"]), row["calls"])
			self.assertEqual(
				(totals["calls"], totals["talk_seconds"]),
				(row["calls"], row.get("talk_seconds", totals["talk_seconds"])),
			)
			if "cost" in row:
				self.assertAlmostEqual(totals["cost"], row["cost"], places=4)

		for row in report["by_agent"]:
			same(self.drill(agent=row["agent"]), row)
		for row in report["by_purpose"]:
			same(self.drill(purpose=row["purpose"]), row)
		for row in report["consent"]:
			same(self.drill(consent_status=row["status"]), row)
		total = report["totals"]
		self.assertEqual(len(self.drill(connected="1")["calls"]), total["connected"])
		self.assertEqual(len(self.drill(connected="0")["calls"]), total["calls"] - total["connected"])
		self.assertEqual(len(self.drill()["calls"]), total["calls"])

	def test_a_drill_down_lists_the_calls_with_their_fields(self):
		rows = {r["name"]: r for r in self.drill(purpose="Service")["calls"]}
		for log, planned in self.mine.items():
			if planned["purpose"] != "Service":
				continue
			row = rows[log]
			self.assertEqual(
				(row["agent"], row["state"], row["duration"], row["cost"], row["lead"]),
				(
					planned["agent"],
					planned["state"],
					planned["seconds"],
					planned["rupees"],
					self.leads[planned["lead_key"]],
				),
			)
			self.assertEqual(row["connected"], planned["state"] == "completed" and planned["seconds"] > 0)
			self.assertEqual(row["purpose"], "Service")
			self.assertNotIn("phone", row)

	def test_consent_coverage_reads_the_consent_check_and_never_blocks_a_call(self):
		status = {
			c["log"]: frappe.db.get_value(
				"Consent Check", frappe.db.get_value("Call Log", c["log"], "consent_check"), "consent_status"
			)
			for c in self.calls
		}
		by_key = {c["lead_key"]: status[c["log"]] for c in self.calls}
		self.assertEqual(
			by_key,
			{
				"soon": "Consented",
				"months": "Consented",
				"forever": "Consented",
				"unknown": "Unknown",
				"opted": "Opted out",
				"dnd": "Registered DND",
			},
		)
		# Opted out and Registered DND leads were called all the same, and are counted.
		after, before = self.report(), self.before
		gained = {r["status"]: r["calls"] for r in after["consent"]}
		was = {r["status"]: r["calls"] for r in before["consent"]}
		self.assertEqual(gained["Consented"] - was["Consented"], 3)
		self.assertEqual(gained["Unknown"] - was["Unknown"], 2)
		self.assertEqual(gained["Registered DND"] - was["Registered DND"], 1)
		self.assertEqual(gained["Opted out"] - was["Opted out"], 0)  # that call is 40 days old
		share = after["totals"]["consent_coverage"]
		self.assertEqual(share, round(gained["Consented"] * 100 / after["totals"]["calls"], 1))

	def test_the_date_filter_keeps_both_end_days_and_nothing_else(self):
		old = next(c for c in self.calls if c["lead_key"] == "opted")
		day = old["day"]
		only = calls.call_report_calls(day, day)
		self.assertIn(old["log"], {r["name"] for r in only["calls"]})
		self.assertEqual(len(only["calls"]), call_log_totals(day, day)["calls"])
		self.assertNotIn(old["log"], {r["name"] for r in self.drill()["calls"]})
		wide = calls.call_report(day, self.end)
		self.assertEqual(wide["totals"]["calls"], call_log_totals(day, self.end)["calls"])
		self.assertEqual(wide["totals"]["calls"] - self.report()["totals"]["calls"], 1)

	def test_the_default_range_is_the_last_thirty_days_and_a_backwards_range_is_refused(self):
		report = calls.call_report()
		self.assertEqual((report["from_date"], report["to_date"]), (str(add_days(today(), -29)), today()))
		with self.assertRaises(frappe.ValidationError):
			calls.call_report(self.end, self.start)

	def test_bad_filters_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			calls.call_report_calls(purpose="International")
		with self.assertRaises(frappe.ValidationError):
			calls.call_report_calls(consent_status="Maybe")

	def test_only_a_company_admin_reads_the_reports(self):
		for key in ("agent", "channel_partner", "client", "sales_manager"):
			as_user(key)
			with self.assertRaises(frappe.PermissionError):
				calls.call_report()
			with self.assertRaises(frappe.PermissionError):
				calls.call_report_calls()

	def test_the_plan_has_every_purpose_state_and_a_call_outside_the_range(self):
		self.assertEqual(len(REPORT_CALL_PLAN), 7)
		self.assertEqual(len(self.calls), 7)
		self.assertEqual({c["state"] for c in self.calls}, {"completed", "no-answer", "busy", "failed"})


class TestRegressionCallSeed(CrmCase):
	"""SOS-P2-11: the regression seed's calls are made through the production API, once."""

	TITLES = ("Buyer Two", "Queue Application", "Buyer One", "Investor Four", "Buyer Three", "DND Listed")

	def test_the_seed_places_the_planned_calls_once_and_reads_back(self):
		from sellos.tests import ui_fixtures

		if frappe.db.exists("Client", {"client_name": ["like", f"{ui_fixtures.REGRESSION_PREFIX}%"]}):
			self.skipTest("this site already holds regression data")
		as_user("company_admin")
		leads = []
		for seed, title in enumerate(self.TITLES, start=3700):
			client = crm.save_client(
				values={
					"client_name": f"{ui_fixtures.REGRESSION_PREFIX}{title}",
					"client_type": "Buyer",
					"phone": phones.in_mobile(seed),
				}
			)
			leads.append(
				crm.save_lead(values={"client": client["name"], "source": "Website"})["lead"]["name"]
			)
		frappe.set_user("Administrator")
		ui_fixtures._seed_call_reports_regression()
		logs = frappe.get_all("Call Log", filters={"lead": ["in", leads]}, fields=["purpose", "state"])
		self.assertEqual(len(logs), len(REPORT_CALL_PLAN))
		self.assertEqual(
			sorted((log.purpose, log.state) for log in logs),
			sorted((row[1], row[2]) for row in REPORT_CALL_PLAN),
		)
		ui_fixtures._seed_call_reports_regression()  # again: nothing more
		self.assertEqual(frappe.db.count("Call Log", {"lead": ["in", leads]}), len(REPORT_CALL_PLAN))
