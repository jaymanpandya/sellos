"""SOS-P5-03: the Channel Partner and Platform reports. Leads and usage are made in 2020, a year nothing else
on the site touches, and every figure is compared with a hand calculation written beside the data. Each
role is tried against each method, a partner reads only their own leads, and the Platform Admin's reports
are checked to hold totals and no lead, client or call record and no phone number."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import AGENT, CHANNEL_PARTNER, ensure_roles
from sellos.crm import api as crm
from sellos.reports import panels, partner, platform
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

START, END = "2020-03-01", "2020-03-31"
OTHER_PARTNER = "p503_partner_two@example.com"
BOTH_ROLES = "p503_agent_partner@example.com"
FIRM = "Channel Partner Firm"
ALL_KEYS = ("platform_admin", "company_admin", "sales_manager", "agent", "channel_partner", "client")

# Partner one's leads. By hand for 1 to 31 March: three leads (a, b, c), New 2 (a, c) and Contacted 1 (b).
# "early" and "late" fall just outside the dates, "archived" is not counted, "agent" belongs to an agent and
# "two" to the second partner, so the first partner sees none of those three.
LEADS = {
	"a": ("2020-03-01 00:00:00", "New", "partner"),
	"b": ("2020-03-15 12:00:00", "Contacted", "partner"),
	"c": ("2020-03-31 23:59:59", "New", "partner"),
	"early": ("2020-02-29 23:59:59", "New", "partner"),
	"late": ("2020-04-01 00:00:00", "New", "partner"),
	"archived": ("2020-03-10 10:00:00", "New", "partner"),
	"agent": ("2020-03-10 10:00:00", "New", "agent"),
	"two": ("2020-03-12 10:00:00", "Qualified", "other"),
}

# Company usage by hand (tenant, month): users, new leads, calls, seconds, rupees.
USAGE = {
	("alpha", "2020-03-01"): (3, 10, 4, 300, "12.50"),
	("alpha", "2020-04-01"): (5, 7, 2, 100, "0.75"),
	("beta", "2020-03-01"): (2, 1, 0, 0, "0"),
}
# By hand, March only: alpha has 3 users, 10 leads, 4 calls, 300 seconds and Rs 12.50, beta 2, 1, 0, 0, Rs 0
# and gamma nothing. March and April: alpha has 5 users (the latest month, not 8), 17 leads, 6 calls, 400
# seconds and Rs 13.25 (12.50 and 0.75 added exactly), beta as before.
MARCH = {"alpha": [3, 10, 4, 300], "beta": [2, 1, 0, 0], "gamma": [0, 0, 0, 0]}
BOTH = {"alpha": [5, 17, 6, 400], "beta": [2, 1, 0, 0], "gamma": [0, 0, 0, 0]}


def email(key):
	return TEST_USERS[key]["email"]


def make_user(address, *roles):
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": address,
			"first_name": "P503 User",
			"send_welcome_email": 0,
			"roles": [{"role": r} for r in roles],
		}
	)
	user.flags.ignore_permissions = True
	user.insert()
	return address


class ReportCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)

	def as_user(self, who, fn, *args, **kwargs):
		frappe.set_user(who if "@" in who else email(who))
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")


class TestPartnerReport(ReportCase):
	"""SOS-P5-03: a partner sees only their own data."""

	def setUp(self):
		super().setUp()
		self.partner = email("channel_partner")
		self.second = make_user(OTHER_PARTNER, CHANNEL_PARTNER)
		self.leads = {}
		self.forms = []
		who = {"partner": self.partner, "agent": email("agent"), "other": self.second}
		for seed, (key, (created, stage, owner)) in enumerate(LEADS.items(), start=5030):
			number = phones.in_mobile(seed)
			self.forms += phones.forms(number)
			frappe.set_user(email("company_admin"))
			client = crm.save_client(
				values={"client_name": f"P503 Buyer {key}", "client_type": "Buyer", "phone": number}
			)
			name = crm.save_lead(
				values={"client": client["name"], "source": "Website", "assigned_to": who[owner]}
			)["lead"]["name"]
			frappe.set_user("Administrator")
			frappe.db.set_value(
				"Lead",
				name,
				{"creation": created, "stage": stage, "archived": 1 if key == "archived" else 0},
				update_modified=False,
			)
			self.leads[key] = name

	def report(self, who, **kwargs):
		return self.as_user(who, partner.partner_report, from_date=START, to_date=END, **kwargs)

	def make_firm(self, contact, status):
		firm = frappe.get_doc(
			{
				"doctype": FIRM,
				"firm_name": "P503 Firm",
				"contact_user": contact,
				"contact_person": "P503 Contact",
				"email": contact,
			}
		).insert(ignore_permissions=True)
		firm.db_set("status", status)
		return firm.name

	def test_a_partner_sees_their_own_leads_by_stage_as_counted_by_hand(self):
		result = self.report("channel_partner")["leads"]
		self.assertEqual(result["total"], 3)
		self.assertEqual({r["stage"]: r["count"] for r in result["by_stage"]}, {"New": 2, "Contacted": 1})
		self.assertEqual(sum(r["count"] for r in result["by_stage"]), result["total"])
		self.assertEqual(
			sorted(r["name"] for r in result["records"]),
			sorted(self.leads[k] for k in ("a", "b", "c")),
		)
		self.assertEqual(result["shown"], 3)
		self.assertFalse(result["truncated"])

	def test_both_end_days_count_and_the_days_outside_and_archived_leads_do_not(self):
		names = {r["name"] for r in self.report("channel_partner")["leads"]["records"]}
		self.assertIn(self.leads["a"], names)  # the first second of the first day
		self.assertIn(self.leads["c"], names)  # the last second of the last day
		for key in ("early", "late", "archived"):
			self.assertNotIn(self.leads[key], names)

	def test_a_partner_never_sees_another_partners_or_an_agents_lead(self):
		mine = {r["name"] for r in self.report("channel_partner")["leads"]["records"]}
		self.assertFalse(mine & {self.leads["agent"], self.leads["two"]})
		theirs = self.as_user(OTHER_PARTNER, partner.partner_report, from_date=START, to_date=END)["leads"]
		self.assertEqual([r["name"] for r in theirs["records"]], [self.leads["two"]])
		self.assertEqual({r["stage"]: r["count"] for r in theirs["by_stage"]}, {"Qualified": 1})

	def test_no_figure_or_record_holds_a_phone_number(self):
		text = json.dumps(self.report("channel_partner"))
		self.assertTrue(self.forms)
		for form in self.forms:
			self.assertNotIn(form, text)

	def test_a_partner_whose_firm_is_not_approved_sees_no_lead(self):
		self.make_firm(self.partner, "Pending approval")
		result = self.report("channel_partner")
		self.assertEqual(result["leads"]["total"], 0)
		self.assertEqual(result["leads"]["records"], [])
		self.assertEqual(result["firm"]["firm_name"], "P503 Firm")

	def test_an_approved_partner_is_named_by_their_firm(self):
		code = self.make_firm(self.partner, "Approved")
		firm = self.report("channel_partner")["firm"]
		self.assertEqual((firm["name"], firm["firm_name"]), (code, "P503 Firm"))
		self.assertEqual(self.report("channel_partner")["leads"]["total"], 3)

	def test_only_a_partner_login_may_read_it(self):
		for key in ALL_KEYS:
			if key == "channel_partner":
				continue
			with self.subTest(key), self.assertRaises(frappe.PermissionError):
				self.report(key)

	def test_a_login_that_is_also_an_agent_is_refused_so_the_wider_scope_is_never_read(self):
		make_user(BOTH_ROLES, CHANNEL_PARTNER, AGENT)
		with self.assertRaises(frappe.PermissionError):
			self.as_user(BOTH_ROLES, partner.partner_report)

	def test_deals_and_commission_wait_until_their_records_exist(self):
		with patch.object(panels, "reader", return_value=None):
			result = self.report("channel_partner")
		self.assertEqual([p["key"] for p in result["panels"]], ["deals", "commission"])
		for panel in result["panels"]:
			self.assertFalse(panel["available"])
			self.assertTrue(panel["message"])
			self.assertNotIn("rows", panel)

	def test_a_panel_that_has_a_reader_switches_on_and_is_told_only_who_is_asking(self):
		calls = []
		statement = {
			self.partner: [{"key": "d1", "label": "Deal one", "values": [100]}],
			OTHER_PARTNER: [{"key": "d2", "label": "Deal two", "values": [200]}],
		}

		def deals(start, end, firm, user):
			calls.append((str(start), str(end), firm, user))
			return {
				"columns": [{"field": "paid", "label": "Paid", "unit": "rupees"}],
				"rows": statement[user],
			}

		def find(path):
			return deals if path.endswith("partner_panels.deals") else None

		code = self.make_firm(self.partner, "Approved")
		with patch.object(panels, "reader", side_effect=find):
			mine = self.report("channel_partner")["panels"]
			theirs = self.as_user(OTHER_PARTNER, partner.partner_report, from_date=START, to_date=END)[
				"panels"
			]
		self.assertTrue(mine[0]["available"])
		self.assertEqual([r["label"] for r in mine[0]["rows"]], ["Deal one"])
		self.assertEqual([r["label"] for r in theirs[0]["rows"]], ["Deal two"])
		self.assertFalse(mine[1]["available"])
		self.assertEqual(calls, [(START, END, code, self.partner), (START, END, None, OTHER_PARTNER)])


class TestPlatformReports(ReportCase):
	"""SOS-P5-03: companies, usage and calling spend as totals per company, and no company CRM data."""

	def setUp(self):
		super().setUp()
		self.tenants = {}
		for key in ("alpha", "beta", "gamma"):
			tenant = frappe.get_doc(
				{
					"doctype": "Tenant",
					"tenant_id": f"p503{key}",
					"company_name": f"P503 {key.title()} Realty",
					"admin_email": f"p503{key}@example.com",
				}
			).insert(ignore_permissions=True)
			self.tenants[key] = tenant.name
		for (key, month), (users, leads, calls, seconds, rupees) in USAGE.items():
			platform.record_usage(
				self.tenants[key],
				{
					"month": month,
					"users": users,
					"leads": leads,
					"calls": calls,
					"call_seconds": seconds,
					"call_cost": rupees,
				},
			)

	def run_report(self, report, start=START, end=END, who="platform_admin"):
		return self.as_user(who, platform.run_platform_report, report, from_date=start, to_date=end)

	def mine(self, result):
		"""{key: values} for the three companies of this test, whatever else the site holds."""
		return {k: r["values"] for r in result["rows"] for k, t in self.tenants.items() if r["key"] == t}

	def test_usage_is_one_row_per_company_as_counted_by_hand(self):
		result = self.run_report("usage")
		self.assertEqual(self.mine(result), MARCH)
		self.assertEqual([c["field"] for c in result["columns"]], ["users", "leads", "calls", "call_seconds"])

	def test_users_are_the_latest_month_and_the_rest_are_added_up(self):
		self.assertEqual(self.mine(self.run_report("usage", START, "2020-04-30")), BOTH)

	def test_a_month_with_any_day_in_the_dates_counts_in_full(self):
		result = self.run_report("usage", "2020-03-15", "2020-03-20")
		self.assertEqual(self.mine(result), MARCH)
		self.assertEqual((result["first_month"], result["last_month"]), ("2020-03-01", "2020-03-01"))

	def test_a_company_with_no_usage_is_listed_with_zeros(self):
		self.assertEqual(self.mine(self.run_report("usage"))["gamma"], [0, 0, 0, 0])
		self.assertEqual(
			self.mine(self.run_report("usage", "2019-01-01", "2019-01-31"))["alpha"], [0, 0, 0, 0]
		)

	def test_the_stat_totals_are_the_sum_of_the_rows(self):
		result = self.run_report("usage", START, "2020-04-30")
		stats = {s["label"]: s["value"] for s in result["stats"]}
		for index, label in enumerate(("Users", "New leads", "Calls")):
			self.assertEqual(stats[label], sum(r["values"][index] for r in result["rows"]), label)
		self.assertEqual(stats["Calls"], 6)

	def test_calling_spend_is_added_exactly_per_company(self):
		march = self.run_report("calling-spend")
		self.assertEqual(self.mine(march), {"alpha": [4, 12.5], "beta": [0, 0.0], "gamma": [0, 0.0]})
		both = self.run_report("calling-spend", START, "2020-04-30")
		self.assertEqual(self.mine(both), {"alpha": [6, 13.25], "beta": [0, 0.0], "gamma": [0, 0.0]})
		stats = {s["label"]: s["value"] for s in both["stats"]}
		self.assertEqual(stats["Calling spend"], round(sum(r["values"][1] for r in both["rows"]), 2))
		self.assertEqual(stats["Calls"], sum(r["values"][0] for r in both["rows"]))

	def test_the_companies_report_lists_every_company_with_its_status_and_plan(self):
		result = self.run_report("companies")
		rows = {r["key"]: r for r in result["rows"]}
		for key, tenant in self.tenants.items():
			self.assertEqual(rows[tenant]["label"], f"P503 {key.title()} Realty")
			self.assertEqual(rows[tenant]["values"], ["Requested", ""])
		self.assertEqual({s["label"] for s in result["stats"]}, {"Companies", "Active"})
		self.assertGreaterEqual(result["stats"][0]["value"], 3)

	def test_revenue_churn_and_failed_payments_wait_until_billing_is_live(self):
		with patch.object(panels, "reader", return_value=None):
			result = self.run_report("usage")
		self.assertEqual([p["key"] for p in result["panels"]], ["revenue", "churn", "failed-payments"])
		for panel in result["panels"]:
			self.assertFalse(panel["available"])
			self.assertIn("billing is live", panel["message"])

	def test_a_billing_panel_switches_on_when_its_reader_exists(self):
		def revenue(start, end):
			return {"columns": [], "rows": [{"key": "x", "label": "Paid", "values": []}], "stats": []}

		def find(path):
			return revenue if path.endswith("report_panels.revenue") else None

		with (
			patch.object(panels, "reader", side_effect=find),
			patch.object(platform, "reader", side_effect=find),
		):
			result = self.run_report("usage")
			listed = self.as_user("platform_admin", platform.list_platform_reports)
		by_key = {p["key"]: p for p in result["panels"]}
		self.assertTrue(by_key["revenue"]["available"])
		self.assertEqual(by_key["revenue"]["rows"][0]["label"], "Paid")
		self.assertFalse(by_key["churn"]["available"])
		self.assertEqual({p["key"]: p["available"] for p in listed["panels"]}["revenue"], True)

	def test_a_reader_that_is_not_built_is_waiting_and_a_real_one_is_found(self):
		self.assertIsNone(panels.reader("sellos.billing.not_built_yet.revenue"))
		self.assertIsNone(panels.reader("sellos.reports.panels.not_a_function"))
		self.assertIs(panels.reader("sellos.reports.panels.reader"), panels.reader)

	def test_the_reports_hold_no_lead_client_or_call_record_and_no_phone_number(self):
		number = phones.in_mobile(5039)
		frappe.set_user(email("company_admin"))
		client = crm.save_client(
			values={"client_name": "P503 Platform Buyer", "client_type": "Buyer", "phone": number}
		)
		crm.save_lead(values={"client": client["name"], "source": "Website"})
		frappe.set_user("Administrator")
		forbidden = [*phones.forms(number), "P503 Platform Buyer", client["name"]]
		for report in ("companies", "usage", "calling-spend"):
			text = json.dumps(self.run_report(report))
			for value in forbidden:
				self.assertNotIn(value, text, report)
		self.assertEqual(set(platform.TOTAL_FIELDS), {"users", "leads", "calls", "call_seconds", "call_cost"})

	def test_the_company_usage_table_holds_only_totals(self):
		fields = {f.fieldname for f in frappe.get_meta("Company Usage").fields}
		self.assertEqual(fields, {"tenant", "period_start", "recorded_on", *platform.TOTAL_FIELDS})

	def test_only_the_platform_admin_reads_the_reports(self):
		for key in ALL_KEYS:
			for method, args in (
				(platform.list_platform_reports, ()),
				(platform.run_platform_report, ("usage",)),
			):
				with self.subTest(key, method=method.__name__):
					if key == "platform_admin":
						self.assertTrue(self.as_user(key, method, *args))
					else:
						with self.assertRaises(frappe.PermissionError):
							self.as_user(key, method, *args)

	def test_the_usage_table_is_read_by_the_platform_admin_only_and_never_deleted(self):
		for key in ALL_KEYS:
			allowed = frappe.has_permission("Company Usage", "read", user=email(key))
			self.assertEqual(allowed, key == "platform_admin", key)
		row = frappe.get_all("Company Usage", pluck="name", limit=1)[0]
		for key in ("platform_admin", "company_admin"):
			self.assertFalse(frappe.has_permission("Company Usage", "delete", user=email(key)))
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Company Usage", row, force=True)

	def test_an_unknown_report_is_refused(self):
		with self.assertRaises(frappe.DoesNotExistError):
			self.run_report("leads-by-stage")


class TestRecordUsage(ReportCase):
	"""SOS-P5-03: what the control site accepts from a company, and the totals a company site makes."""

	def setUp(self):
		super().setUp()
		self.tenant = (
			frappe.get_doc(
				{
					"doctype": "Tenant",
					"tenant_id": "p503gamma",
					"company_name": "P503 Gamma",
					"admin_email": "p503g@example.com",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def rows(self):
		return frappe.get_all("Company Usage", filters={"tenant": self.tenant}, fields=["*"])

	def test_recording_again_replaces_the_months_row(self):
		first = platform.record_usage(self.tenant, {"month": "2020-03-17", "leads": 4})
		second = platform.record_usage(self.tenant, {"month": "2020-03-02", "leads": 9, "call_cost": "1.005"})
		self.assertEqual(first, second)
		(row,) = self.rows()
		self.assertEqual((str(row.period_start), row.leads, row.users), ("2020-03-01", 9, 0))
		self.assertEqual(float(row.call_cost), 1.0)

	def test_anything_but_totals_is_refused(self):
		bad = (
			{"phone": phones.in_mobile(5040)},
			{"lead": "x"},
			{"leads": -1},
			{"leads": "many"},
			{"leads": True},
			{"leads": 1.5},
			{"call_cost": "nan"},
			{"call_cost": -0.01},
			{"calls": None},
		)
		for totals in bad:
			with self.subTest(totals), self.assertRaises(frappe.ValidationError):
				platform.record_usage(self.tenant, totals)
		self.assertEqual(self.rows(), [])

	def test_an_unknown_company_is_refused(self):
		for tenant in ("p503nobody", "", None):
			with self.subTest(tenant), self.assertRaises(frappe.DoesNotExistError):
				platform.record_usage(tenant, {"leads": 1})

	def test_a_company_sites_totals_for_a_month_are_counted_by_hand(self):
		# By hand for March 2020: two leads (the third, at midnight on 1 April, is April's), two calls of 60
		# and 30 seconds costing Rs 0.10 and 0.20 (the one at 1 April is April's), so 2, 90 and 0.30.
		frappe.set_user(email("company_admin"))
		names = []
		for seed, created in enumerate(
			("2020-03-01 00:00:00", "2020-03-31 23:59:59", "2020-04-01 00:00:00"), 5041
		):
			client = crm.save_client(
				values={
					"client_name": f"P503 Totals {seed}",
					"client_type": "Buyer",
					"phone": phones.in_mobile(seed),
				}
			)
			names.append(
				(
					crm.save_lead(values={"client": client["name"], "source": "Website"})["lead"]["name"],
					created,
				)
			)
		frappe.set_user("Administrator")
		for lead, created in names:
			frappe.db.set_value("Lead", lead, "creation", created, update_modified=False)
		calls = (
			("2020-03-04 10:00:00", 60, "0.10"),
			("2020-03-31 23:00:00", 30, "0.20"),
			("2020-04-01 00:00:00", 99, "5.00"),
		)
		for index, (started, seconds, rupees) in enumerate(calls):
			frappe.get_doc(
				{
					"doctype": "Call Log",
					"lead": names[0][0],
					"provider": "fake",
					"call_id": f"p503-{index}",
					"purpose": "Service",
					"state": "completed",
					"duration": seconds,
					"cost_rupees": rupees,
					"started_on": started,
				}
			).insert(ignore_permissions=True)
		totals = platform.company_totals("2020-03-17")
		self.assertEqual(
			{k: totals[k] for k in ("month", "leads", "calls", "call_seconds", "call_cost")},
			{"month": "2020-03-01", "leads": 2, "calls": 2, "call_seconds": 90, "call_cost": 0.3},
		)
		self.assertEqual(set(totals), {"month", "users", "leads", "calls", "call_seconds", "call_cost"})

	def test_users_are_the_enabled_staff_and_not_clients_partners_or_disabled_logins(self):
		before = platform.company_totals()["users"]
		make_user("p503_staff@example.com", AGENT)
		make_user("p503_client@example.com", "SellOS Client")
		make_user(OTHER_PARTNER, CHANNEL_PARTNER)
		off = make_user("p503_off@example.com", AGENT)
		frappe.db.set_value("User", off, "enabled", 0)
		self.assertEqual(platform.company_totals()["users"], before + 1)

	def test_what_a_company_site_makes_is_what_the_control_site_stores(self):
		totals = platform.company_totals("2020-03-17")
		platform.record_usage(self.tenant, totals)
		(row,) = self.rows()
		for field in platform.TOTAL_FIELDS:
			self.assertEqual(float(row[field]), float(totals[field]), field)


class TestSeeds(ReportCase):
	"""SOS-P5-03: the data the browser spec and the regression dataset add, read back."""

	def setUp(self):
		super().setUp()
		commit = patch.object(frappe.db, "commit")
		commit.start()
		self.addCleanup(commit.stop)

	def test_the_spec_fixture_makes_the_partners_leads_and_the_usage_and_removes_them(self):
		from sellos.tests import ui_fixtures

		made = ui_fixtures.seed_portal_reports()
		self.assertEqual(made["partner"], {"New": 2, "Contacted": 1})
		report = self.as_user(
			"channel_partner",
			partner.partner_report,
			from_date=made["from_date"],
			to_date=made["to_date"],
		)
		self.assertEqual({r["stage"]: r["count"] for r in report["leads"]["by_stage"]}, made["partner"])
		result = self.as_user(
			"platform_admin",
			platform.run_platform_report,
			"usage",
			from_date=made["from_date"],
			to_date=made["to_date"],
		)
		rows = {r["key"]: r["values"] for r in result["rows"]}
		for tenant, values in made["usage"].items():
			self.assertEqual(rows[tenant], values[:4], tenant)
		removed = ui_fixtures.remove_portal_reports()
		self.assertEqual(removed["leads"], 4)
		self.assertFalse(frappe.db.exists("Tenant", "portalone"))
		self.assertFalse(frappe.db.count("Company Usage", {"tenant": ["in", list(made["usage"])]}))

	def test_the_regression_dataset_gives_each_tenant_a_months_usage_and_a_second_run_adds_none(self):
		from sellos.tests import ui_fixtures

		ui_fixtures._seed_control_site()
		ui_fixtures._seed_company_usage()
		tenants = list(ui_fixtures.REGRESSION_USAGE)
		rows = {
			r.tenant: [r.users, r.leads, r.calls, r.call_seconds, float(r.call_cost)]
			for r in frappe.get_all(
				"Company Usage",
				filters={"tenant": ["in", tenants]},
				fields=["tenant", "users", "leads", "calls", "call_seconds", "call_cost"],
			)
		}
		self.assertEqual(
			rows,
			{t: [*v[:4], float(v[4])] for t, v in ui_fixtures.REGRESSION_USAGE.items()},
		)
		ui_fixtures._seed_company_usage()
		self.assertEqual(frappe.db.count("Company Usage", {"tenant": ["in", tenants]}), len(tenants))
