"""SOS-P5-04: saved views, export and scheduling. Three leads are made yesterday (two of the gate agent, one of
another agent), and every figure is compared with a hand calculation: the company has 3 leads in 3 days, 2 of
them New and 1 Contacted; the gate agent has 2, both New. An export is compared with the report the screen
shows, a scheduled email is run for a Company Admin and an Agent, and each email holds only what its reader
may see."""

import base64
import csv
import io
from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime, today

from sellos.access.roles import AGENT, ensure_roles
from sellos.crm import api as crm
from sellos.reports import engine, exports
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

OTHER_AGENT = "p504_agent_two@example.com"
# By hand: yesterday has three leads. a and b are the gate agent's, c is the other agent's. Stages: New 2
# (a, c) and Contacted 1 (b), so the company's Leads by stage is New 2, Contacted 1 (3 in all) and the gate
# agent's is New 1, Contacted 1 (2 in all).
LEADS = {"a": ("New", "agent"), "b": ("Contacted", "agent"), "c": ("New", "other")}
COMPANY = {"New": 2, "Contacted": 1}
AGENT_ONLY = {"New": 1, "Contacted": 1}


def email(key):
	return TEST_USERS[key]["email"]


def decode(result) -> list[list[str]]:
	return list(csv.reader(io.StringIO(base64.b64decode(result["content"]).decode("utf-8"))))


class TestReportExports(IntegrationTestCase):
	"""SOS-P5-04"""

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
				"email": OTHER_AGENT,
				"first_name": "P504 Agent Two",
				"send_welcome_email": 0,
				"roles": [{"role": AGENT}],
			}
		)
		other.flags.ignore_permissions = True
		other.insert()
		frappe.set_user(email("company_admin"))
		self.leads = {}
		yesterday = f"{add_days(today(), -1)} 10:00:00"
		for seed, (key, (stage, who)) in enumerate(LEADS.items(), start=5040):
			client = crm.save_client(
				values={
					"client_name": f"P504 Buyer {key}",
					"client_type": "Buyer",
					"phone": phones.in_mobile(seed),
				}
			)
			assigned = OTHER_AGENT if who == "other" else email(who)
			name = crm.save_lead(
				values={"client": client["name"], "source": "Website", "assigned_to": assigned}
			)["lead"]["name"]
			frappe.db.set_value("Lead", name, {"creation": yesterday, "stage": stage}, update_modified=False)
			self.leads[key] = name
		frappe.set_user("Administrator")
		self.start, self.end = str(add_days(today(), -3)), str(add_days(today(), -1))

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def as_user(self, who, method, *args, **kwargs):
		frappe.set_user(email(who) if who in TEST_USERS else who)
		try:
			return method(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def make_schedule(self, recipients, **values):
		doc = {
			"doctype": "Report Schedule",
			"title": "P504 Weekly",
			"report": "leads-by-stage",
			"frequency": "Daily",
			"range_days": 3,
			"file_format": "CSV",
			"recipients": [{"user": r} for r in recipients],
			**values,
		}
		return frappe.get_doc(doc).insert(ignore_permissions=True)

	# ---- export ----

	def test_an_export_matches_the_report_the_screen_shows(self):
		shown = self.as_user(
			"company_admin", engine.run_report, "leads-by-stage", from_date=self.start, to_date=self.end
		)
		result = self.as_user(
			"company_admin",
			exports.export_report,
			"leads-by-stage",
			from_date=self.start,
			to_date=self.end,
			format="csv",
		)
		table = decode(result)
		self.assertEqual(table[0], ["Stage", "Records"])
		on_screen = {row["label"]: row["count"] for row in shown["rows"] if row["label"] in COMPANY}
		self.assertEqual({row[0]: int(row[1]) for row in table[1:-1] if row[0] in COMPANY}, on_screen)
		self.assertEqual(on_screen, COMPANY)
		self.assertEqual(table[-1], ["Total", str(shown["totals"]["count"])])
		self.assertEqual(
			[row["label"] for row in result["rows"]], [row["label"] for row in shown["rows"]], "same rows"
		)
		self.assertEqual(result["totals"]["count"], shown["totals"]["count"])
		self.assertTrue(result["filename"].endswith(f"{self.start}-{self.end}.csv"))

	def test_a_sum_report_exports_its_total_with_its_unit(self):
		result = self.as_user(
			"company_admin", exports.export_report, "my-pipeline", self.start, self.end, None, "csv"
		)
		table = decode(result)
		self.assertEqual(table[0], ["Stage", "Records", "Budget up to (rupees)"])
		self.assertRegex(table[-1][2], r"^\d+\.\d\d$")

	def test_an_export_can_be_a_pdf(self):
		result = self.as_user(
			"company_admin", exports.export_report, "leads-by-stage", self.start, self.end, None, "pdf"
		)
		self.assertEqual(result["mime"], "application/pdf")
		self.assertTrue(base64.b64decode(result["content"]).startswith(b"%PDF"))
		self.assertTrue(result["filename"].endswith(".pdf"))

	def test_the_plain_pdf_has_the_title_and_every_row(self):
		from sellos.inventory.plain_pdf import build_table_pdf

		data = build_table_pdf(
			"P504 Title", "From a to b.", ["Stage", "Records"], [["New", "2"], ["Total", "3"]]
		)
		self.assertTrue(data.startswith(b"%PDF"))
		for text in (b"P504 Title", b"New", b"Total"):
			self.assertIn(text, data)

	def test_every_export_is_logged(self):
		before = frappe.db.count("Report Export Log")
		result = self.as_user(
			"company_admin", exports.export_report, "leads-by-stage", self.start, self.end, None, "csv"
		)
		self.assertEqual(frappe.db.count("Report Export Log"), before + 1)
		log = frappe.get_doc("Report Export Log", result["export_log"])
		self.assertEqual(
			(log.report, log.file_format, log.via, log.exported_by, log.row_count),
			("leads-by-stage", "CSV", "Screen", email("company_admin"), len(result["rows"])),
		)
		with self.assertRaises(frappe.PermissionError):
			log.delete()
		log.row_count = 99
		with self.assertRaises(frappe.PermissionError):
			log.save()

	def test_only_a_company_admin_exports(self):
		for who in ("agent", "sales_manager", "channel_partner", "client"):
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				self.as_user(who, exports.export_report, "leads-by-stage", self.start, self.end, None, "csv")

	def test_a_phone_number_in_a_cell_is_masked_and_a_formula_is_plain_text(self):
		number = phones.in_mobile(5049)
		for form in phones.forms(number):
			self.assertNotIn(form, exports.plain_cell(f"Call {form} back"))
		self.assertIn("*", exports.mask_text(f"Call {number} back"))
		self.assertEqual(exports.plain_cell("=1+1"), "'=1+1")
		self.assertEqual(exports.plain_cell("2021-05-03"), "2021-05-03")

	def test_no_phone_number_is_in_an_export(self):
		result = self.as_user(
			"company_admin", exports.export_report, "leads-by-stage", self.start, self.end, None, "csv"
		)
		text = base64.b64decode(result["content"]).decode("utf-8")
		for seed in range(5040, 5043):
			for form in phones.forms(phones.in_mobile(seed)):
				self.assertNotIn(form, text)

	# ---- saved views ----

	def test_a_view_is_kept_and_a_shared_view_is_seen_by_others(self):
		saved = self.as_user(
			"agent",
			exports.save_report_view,
			{"title": "P504 My leads", "report": "leads-by-stage", "range_days": 7, "shared": 0},
		)
		self.assertEqual(saved["range_days"], 7)
		self.assertEqual((saved["from_date"], saved["to_date"]), (str(add_days(today(), -6)), today()))
		self.assertEqual(
			[v["name"] for v in self.as_user("agent", exports.list_report_views)["views"]], [saved["name"]]
		)
		self.assertEqual(self.as_user("sales_manager", exports.list_report_views)["views"], [])
		self.as_user("agent", exports.save_report_view, {"shared": 1}, view=saved["name"])
		seen = self.as_user("sales_manager", exports.list_report_views)["views"]
		self.assertEqual([(v["name"], v["mine"]) for v in seen], [(saved["name"], False)])

	def test_a_view_holds_filters_so_a_reader_sees_their_own_scope(self):
		saved = self.as_user(
			"company_admin",
			exports.save_report_view,
			{
				"title": "P504 Shared dates",
				"report": "leads-by-stage",
				"from_date": self.start,
				"to_date": self.end,
				"shared": 1,
			},
		)
		view = self.as_user("agent", exports.list_report_views)["views"][0]
		self.assertEqual(view["name"], saved["name"])
		shown = self.as_user(
			"agent", engine.run_report, view["report"], from_date=view["from_date"], to_date=view["to_date"]
		)
		self.assertEqual({r["label"]: r["count"] for r in shown["rows"]}, AGENT_ONLY)

	def test_only_the_owner_changes_a_view_and_only_the_owner_or_admin_deletes_it(self):
		saved = self.as_user(
			"agent",
			exports.save_report_view,
			{"title": "P504 Mine", "report": "leads-by-stage", "shared": 1},
		)
		with self.assertRaises(frappe.PermissionError):
			self.as_user("sales_manager", exports.save_report_view, {"title": "Taken"}, view=saved["name"])
		with self.assertRaises(frappe.PermissionError):
			self.as_user("sales_manager", exports.delete_report_view, saved["name"])
		self.as_user("company_admin", exports.delete_report_view, saved["name"])
		self.assertFalse(frappe.db.exists("Saved Report View", saved["name"]))

	def test_a_view_of_a_report_the_reader_may_not_read_is_refused_and_not_offered(self):
		with self.assertRaises(frappe.PermissionError):
			self.as_user(
				"agent", exports.save_report_view, {"title": "P504 Cost", "report": "call-cost-by-agent"}
			)
		saved = self.as_user(
			"company_admin",
			exports.save_report_view,
			{"title": "P504 Cost", "report": "call-cost-by-agent", "shared": 1},
		)
		self.assertNotIn(
			saved["name"], [v["name"] for v in self.as_user("agent", exports.list_report_views)["views"]]
		)

	def test_a_view_needs_a_name_and_sane_dates(self):
		for values in (
			{"title": " ", "report": "leads-by-stage"},
			{"title": "x", "report": "leads-by-stage", "from_date": self.end, "to_date": self.start},
			{"title": "x", "report": "leads-by-stage", "range_days": -1},
		):
			with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
				self.as_user("company_admin", exports.save_report_view, values)

	# ---- schedules ----

	def test_the_next_delivery_is_the_next_time_it_falls_due(self):
		doc = frappe.new_doc("Report Schedule")
		doc.update({"frequency": "Daily", "send_hour": 8})
		self.assertEqual(exports.next_run(doc, datetime(2026, 11, 23, 7, 59)), datetime(2026, 11, 23, 8, 0))
		self.assertEqual(exports.next_run(doc, datetime(2026, 11, 23, 8, 0)), datetime(2026, 11, 24, 8, 0))
		doc.update({"frequency": "Weekly", "weekday": "Monday"})  # 23 November 2026 is a Monday
		self.assertEqual(exports.next_run(doc, datetime(2026, 11, 23, 9, 0)), datetime(2026, 11, 30, 8, 0))
		doc.update({"frequency": "Monthly", "day_of_month": 5})
		self.assertEqual(exports.next_run(doc, datetime(2026, 11, 23, 9, 0)), datetime(2026, 12, 5, 8, 0))

	def test_a_schedule_gets_its_first_delivery_and_a_disabled_one_has_none(self):
		doc = self.make_schedule([email("company_admin")])
		self.assertGreater(doc.next_run, now_datetime())
		doc.enabled = 0
		doc.save(ignore_permissions=True)
		self.assertIsNone(doc.next_run)

	def test_a_schedule_cannot_name_someone_who_may_not_read_the_report(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_schedule([email("agent")], report="call-cost-by-agent")
		with self.assertRaises(frappe.ValidationError):
			self.make_schedule([email("channel_partner")])
		with self.assertRaises(frappe.ValidationError):
			self.make_schedule([])
		frappe.db.set_value("User", OTHER_AGENT, "enabled", 0)
		with self.assertRaises(frappe.ValidationError):
			self.make_schedule([OTHER_AGENT])

	def test_a_scheduled_email_holds_only_what_each_reader_may_see(self):
		doc = self.make_schedule([email("company_admin"), email("agent")])
		with patch("sellos.access.users.mail_ready", return_value=True), patch("frappe.sendmail") as send:
			done = exports.send_schedule(doc.name)
		self.assertEqual(
			done["results"], {email("company_admin"): "Sent", email("agent"): "Sent"}, "one email each"
		)
		self.assertEqual((done["from_date"], done["to_date"]), (self.start, self.end))
		sent = {call.kwargs["recipients"][0]: call.kwargs for call in send.call_args_list}
		self.assertEqual(set(sent), {email("company_admin"), email("agent")})
		for who, expected in (("company_admin", COMPANY), ("agent", AGENT_ONLY)):
			attachment = sent[email(who)]["attachments"][0]
			rows = list(csv.reader(io.StringIO(attachment["fcontent"].decode("utf-8"))))
			self.assertEqual({r[0]: int(r[1]) for r in rows[1:-1] if r[0] in expected}, expected, who)
			self.assertEqual(rows[-1], ["Total", str(sum(expected.values()))], who)
			self.assertTrue(attachment["fname"].endswith(".csv"))
		self.assertNotIn("P504 Buyer c", sent[email("agent")]["message"])

	def test_a_scheduled_email_is_logged_for_every_reader(self):
		doc = self.make_schedule([email("company_admin"), email("agent")])
		with patch("sellos.access.users.mail_ready", return_value=True), patch("frappe.sendmail"):
			exports.send_schedule(doc.name)
		logs = frappe.get_all(
			"Report Export Log", filters={"schedule": doc.name}, fields=["exported_by", "via", "row_count"]
		)
		self.assertEqual(
			{(log.exported_by, log.via) for log in logs},
			{(email("company_admin"), "Email"), (email("agent"), "Email")},
		)
		after = frappe.get_doc("Report Schedule", doc.name)
		self.assertEqual(after.last_result, "2 of 2 sent")
		self.assertEqual({r.last_status for r in after.recipients}, {"Sent"})

	def test_a_recipient_who_lost_access_is_skipped(self):
		doc = self.make_schedule([email("company_admin"), OTHER_AGENT])
		frappe.db.set_value("User", OTHER_AGENT, "enabled", 0)
		with patch("sellos.access.users.mail_ready", return_value=True), patch("frappe.sendmail") as send:
			done = exports.send_schedule(doc.name)
		self.assertEqual(done["results"][OTHER_AGENT], "Skipped: no active login")
		self.assertEqual([c.kwargs["recipients"] for c in send.call_args_list], [[email("company_admin")]])

	def test_without_an_outgoing_email_account_nothing_is_sent_and_the_schedule_says_so(self):
		doc = self.make_schedule([email("company_admin")])
		with patch("sellos.access.users.mail_ready", return_value=False), patch("frappe.sendmail") as send:
			done = exports.send_schedule(doc.name)
		send.assert_not_called()
		self.assertEqual(done["results"][email("company_admin")], "Not sent: no outgoing email account")
		self.assertEqual(frappe.get_doc("Report Schedule", doc.name).last_result, "0 of 1 sent")

	def test_a_failed_email_is_recorded_and_the_others_go_on(self):
		doc = self.make_schedule([email("company_admin"), email("agent")])
		with (
			patch("sellos.access.users.mail_ready", return_value=True),
			patch("frappe.sendmail", side_effect=[OSError("down"), None]),
			patch("frappe.log_error"),
		):
			done = exports.send_schedule(doc.name)
		self.assertEqual(sorted(done["results"].values()), ["Failed: the email could not be sent", "Sent"])

	def test_the_hourly_job_sends_what_is_due_once_and_moves_the_next_delivery_on(self):
		due = self.make_schedule([email("company_admin")], title="P504 Due")
		later = self.make_schedule([email("company_admin")], title="P504 Later")
		off = self.make_schedule([email("company_admin")], title="P504 Off")
		frappe.db.set_value("Report Schedule", due.name, "next_run", add_days(now_datetime(), -1))
		frappe.db.set_value(
			"Report Schedule", off.name, {"next_run": add_days(now_datetime(), -1), "enabled": 0}
		)
		with patch("sellos.access.users.mail_ready", return_value=True), patch("frappe.sendmail") as send:
			done = exports.send_due_schedules()
			again = exports.send_due_schedules()
		self.assertEqual([d["schedule"] for d in done], [due.name])
		self.assertEqual(again, [])
		self.assertEqual(send.call_count, 1)
		self.assertGreater(frappe.db.get_value("Report Schedule", due.name, "next_run"), now_datetime())
		self.assertIsNone(frappe.db.get_value("Report Schedule", later.name, "last_sent_on"))

	def test_the_hourly_job_is_registered(self):
		self.assertIn(
			"sellos.reports.exports.send_due_schedules", frappe.get_hooks("scheduler_events")["hourly"]
		)

	def test_the_api_makes_and_removes_a_schedule_for_a_company_admin_only(self):
		made = self.as_user(
			"company_admin",
			exports.save_report_schedule,
			{
				"title": "P504 Api",
				"report": "leads-by-stage",
				"frequency": "Weekly",
				"weekday": "Friday",
				"send_hour": 9,
				"range_days": 7,
				"file_format": "PDF",
				"recipients": [email("sales_manager"), email("agent")],
			},
		)
		self.assertEqual([r["user"] for r in made["recipients"]], [email("sales_manager"), email("agent")])
		self.assertTrue(made["next_run"])
		listed = self.as_user("company_admin", exports.list_report_schedules)
		self.assertIn(made["name"], [s["name"] for s in listed["schedules"]])
		self.assertIn(email("agent"), [p["email"] for p in listed["people"]])
		self.assertNotIn(email("channel_partner"), [p["email"] for p in listed["people"]])
		with self.assertRaises(frappe.PermissionError):
			self.as_user("agent", exports.list_report_schedules)
		with self.assertRaises(frappe.PermissionError):
			self.as_user("sales_manager", exports.delete_report_schedule, made["name"])
		self.as_user("company_admin", exports.delete_report_schedule, made["name"])
		self.assertFalse(frappe.db.exists("Report Schedule", made["name"]))

	def test_the_regression_seed_makes_a_shared_view_and_a_schedule_and_can_run_again(self):
		from sellos.tests import ui_fixtures

		ui_fixtures._seed_report_views(email("company_admin"))
		ui_fixtures._seed_report_views(email("company_admin"))
		views = frappe.get_all(
			"Saved Report View", filters={"title": "Regression Weekly leads"}, fields=["shared", "range_days"]
		)
		self.assertEqual([(v.shared, v.range_days) for v in views], [(1, 30)])
		self.assertEqual(frappe.db.count("Report Schedule", {"title": "Regression Monday report"}), 1)
		self.assertEqual(
			self.as_user("agent", exports.list_report_views)["views"][0]["title"], "Regression Weekly leads"
		)
