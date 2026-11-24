"""SOS-DEMO-1: the demo environment is safe and no gate touches it.

Unit tests (no bench): the site name check, the data tables, the server's Host guard, scripts/demo.sh, and
every place the gate must ignore or protect a sellos_tenant_demo<id> site.

One real test (TestDemoSeedAndReset) builds a control site and a company site with the real provisioning
path in a subprocess, seeds twice (idempotent), resets, checks the data and the users, and drops them.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sellos.provisioning import tenant_sites
from sellos.testing import demo

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
STAGES = (
	"New", "Consent pending", "Contacted", "Qualified", "Site visit booked", "Site visit done",
	"Negotiation", "Booking", "Closed won", "Closed lost", "Nurture",
)  # fmt: skip


class TestSiteNameCheck(unittest.TestCase):
	def test_only_demo_localhost_sites_pass(self):
		for good in (
			"sellos_tenant_demo.localhost",
			"sellos_tenant_demoalpha.localhost",
			"sellos_tenant_demo2.localhost",
		):
			self.assertEqual(demo.check_demo_site(good), good)
		for bad in (
			"sellos_test.localhost", "test_site", "pamaa.localhost", "sellos_tenant_abc.localhost",
			"sellos_tenant_demo.example.com", "sellos_tenant_demo.localhost.evil.com", "sellos_tenant_demo_x.localhost",
			"sellos_tenant_Demo1.localhost", "xsellos_tenant_demo1.localhost", "", None,
		):  # fmt: skip
			with self.assertRaises(demo.DemoRefused, msg=repr(bad)):
				demo.check_demo_site(bad)

	def test_seed_functions_refuse_the_gate_site(self):
		import frappe

		# Set and restore the site by hand: patching frappe.local would unset it for the tests after this one.
		old = getattr(frappe.local, "site", None)
		try:
			frappe.local.site = "sellos_test.localhost"
			with self.assertRaises(demo.DemoRefused):
				demo.seed_company(0)
			with self.assertRaises(demo.DemoRefused):
				demo.setup_control()
		finally:
			frappe.local.site = old

	def test_ids_must_start_with_demo(self):
		for bad in ("alpha", "regressionfour", "democontrol.localhost", "demo-x", "Demo1"):
			with self.assertRaises(demo.DemoRefused):
				demo.check_demo_id(bad)
		self.assertEqual(demo.site_of("demoalpha"), "sellos_tenant_demoalpha.localhost")
		self.assertEqual(demo.main(["seed", "--company", "alpha"]), 2)
		self.assertEqual(demo.main(["bogus"]), 2)


class TestDemoData(unittest.TestCase):
	def test_every_company_has_all_stages_all_consent_states_and_duplicates(self):
		from sellos.crm.duplicates import normalise_phone

		for company in demo.COMPANIES:
			leads = company["leads"]
			self.assertEqual({row[6] for row in leads} & set(STAGES), set(STAGES), company["name"])
			self.assertEqual(
				{row[7] for row in leads}, {"unknown", "consented", "optedout", "dnd", "expired"}
			)
			phones = [normalise_phone(row[2]) for row in leads]
			self.assertTrue(len(phones) > len(set(phones)), "no duplicate phone number")
			emails = [row[3] for row in leads]
			self.assertTrue(len(emails) > len(set(emails)), "no duplicate email")
			self.assertTrue(any(row[8] is None for row in leads), "no lead owned by the partner")
			self.assertTrue({row[8] for row in leads} >= {0, 1})

	def test_every_company_has_the_listed_users(self):
		for i in range(len(demo.COMPANIES)):
			roles = [role for _e, _n, role in demo.company_users(i)]
			self.assertEqual(
				roles,
				[demo.COMPANY_ADMIN, demo.AGENT, demo.AGENT, demo.CHANNEL_PARTNER, demo.CLIENT],
			)
		emails = [e for i in range(len(demo.COMPANIES)) for e, _n, _r in demo.company_users(i)]
		self.assertEqual(len(emails), len(set(emails)))

	def test_the_doc_lists_every_sign_in(self):
		text = (REPO_ROOT / "docs" / "DEMO.md").read_text(encoding="utf-8")
		self.assertIn(demo.DEMO_PASSWORD, text)
		self.assertIn(demo.PLATFORM_ADMIN_EMAIL, text)
		self.assertIn("8006", text)
		for i in range(len(demo.COMPANIES)):
			for email, _n, _r in demo.company_users(i):
				self.assertIn(email, text)
			self.assertIn(demo.sales_manager_email(demo.COMPANIES[i]["word"]), text)

	def test_the_doc_names_update_next_to_seed_and_reset(self):
		text = (REPO_ROOT / "docs" / "DEMO.md").read_text(encoding="utf-8")
		for command in ("seed", "update", "reset"):
			self.assertIn(f"scripts/demo.sh {command}", text)

	def test_the_calls_cover_30_days_two_agents_and_two_purposes(self):
		days = [row[5] for row in demo.DEMO_CALL_PLAN]
		self.assertGreaterEqual(max(days), 25)
		self.assertLessEqual(max(days), 30)
		self.assertEqual({row[6] for row in demo.DEMO_CALL_PLAN}, {0, 1})
		self.assertGreaterEqual(len({row[1] for row in demo.DEMO_CALL_PLAN}), 2)
		self.assertTrue(demo.DEMO_TELEPHONY_ID.startswith("FAKEOK"))  # the fake provider accepts it
		self.assertIn("NOT-A-REAL-KEY", demo.DEMO_TELEPHONY_ID)

	def test_the_seed_calls_the_production_seed_functions(self):
		"""The demo's content (demo_data.py) is made by steps, each run on its own so one failure is named and
		fails the seed (SOS-DEMO-2), and each step goes through the production methods, not around them."""
		source = (REPO_ROOT / "sellos" / "testing" / "demo.py").read_text(encoding="utf-8")
		for label, name in (
			("inventory", "_seed_demo_inventory"),
			("partners", "_seed_demo_partners"),
			("enquiries", "_seed_demo_enquiries"),
			("sellers", "_seed_demo_sellers"),
			("deals and commission", "_seed_demo_deals"),
			("whatsapp", "_seed_demo_whatsapp"),
			("visits and follow ups", "_seed_demo_visits_and_follow_ups"),
		):
			self.assertIn(f'_isolated("{label}", {name},', source, name)
		for production in (
			"fx._make_partner_firm(",  # the production firm methods, with mail off
			"partner_registrations.register_buyer(",
			"deals.save_deal(",
			"deals.approve_splits(",
			"intake.take(",  # the one lead intake
			"conversations.receive(",  # the WhatsApp conversation methods, with the fake provider
			"conversations.send(",
			"conversations.hand_off(",
		):
			self.assertIn(production, source, production)


class TestDemoServer(unittest.TestCase):
	def test_only_demo_hosts_reach_frappe_and_the_site_header_is_dropped(self):
		sys.path.insert(0, str(SCRIPTS / "lib"))
		try:
			import demo_server
		finally:
			sys.path.pop(0)
		seen = []

		def app(environ, start_response):
			seen.append(environ.get("HTTP_X_FRAPPE_SITE_NAME"))
			start_response("200 OK", [])
			return [b"hello"]

		guarded = demo_server.only_demo_hosts(app)

		def call(host, extra=None):
			status = []
			environ = {
				"HTTP_HOST": host,
				"REQUEST_METHOD": "GET",
				"PATH_INFO": "/",
				"wsgi.url_scheme": "http",
			}
			environ.update(extra or {})
			body = b"".join(guarded(environ, lambda s, h, e=None: status.append(s)))
			return status[0], body

		self.assertTrue(call("sellos_tenant_demoalpha.localhost:8006")[0].startswith("200"))
		for host in (
			"localhost:8006",
			"test_site:8006",
			"sellos_test.localhost:8006",
			"127.0.0.1:8006",
			"pamaa.localhost",
			"",
		):
			self.assertTrue(call(host)[0].startswith("404"), host)
		call("sellos_tenant_demoalpha.localhost:8006", {"HTTP_X_FRAPPE_SITE_NAME": "test_site"})
		self.assertEqual(seen[-1], None)
		self.assertEqual(len(seen), 2)

	def test_the_server_binds_localhost_only_and_never_reloads(self):
		text = (SCRIPTS / "lib" / "demo_server.py").read_text(encoding="utf-8")
		self.assertIn('run_simple("127.0.0.1"', text)
		self.assertIn("use_reloader=False", text)
		self.assertNotIn("0.0.0.0", text.replace("0.0.0.0) ", ""))


class TestDemoScript(unittest.TestCase):
	def run_script(self, *args, extra=None):
		agents = tempfile.mkdtemp()
		env = {
			**os.environ,
			"SELLOS_LAUNCH_AGENTS_DIR": agents,
			"SELLOS_BASELINE_DIR": tempfile.mkdtemp(),
			"SELLOS_DEMO_WRITE_ONLY": "1",
			"SELLOS_BENCH_DIR": tempfile.mkdtemp(),
			**(extra or {}),
		}
		result = subprocess.run(
			["bash", str(SCRIPTS / "demo.sh"), *args], env=env, capture_output=True, text=True
		)
		return result, Path(agents)

	def test_usage(self):
		for args in ((), ("bogus",), ("seed", "extra")):
			self.assertEqual(self.run_script(*args)[0].returncode, 2, args)

	def test_start_writes_a_plist_for_8006_and_it_twice_is_the_same(self):
		first, agents = self.run_script("start")
		self.assertEqual(first.returncode, 0, first.stderr)
		plist = (agents / "com.sellos.demo.plist").read_text(encoding="utf-8")
		self.assertIn("scripts/lib/demo_server.py", plist)
		self.assertRegex(plist, r"<string>--port</string>\s*<string>8006</string>")
		self.assertIn("<key>KeepAlive</key><true/>", plist)
		self.assertNotIn("serve", plist.replace("demo_server", ""))
		self.assertNotRegex(plist, r"800[024]")
		second = subprocess.run(
			["bash", str(SCRIPTS / "demo.sh"), "start"],
			env={**os.environ, "SELLOS_LAUNCH_AGENTS_DIR": str(agents), "SELLOS_DEMO_WRITE_ONLY": "1"},
			capture_output=True, text=True,
		)  # fmt: skip
		self.assertEqual(second.returncode, 0)
		self.assertEqual(
			(agents / "com.sellos.demo.plist").read_text(encoding="utf-8").count("<key>Label</key>"), 1
		)

	def test_the_script_names_no_other_site(self):
		text = (SCRIPTS / "demo.sh").read_text(encoding="utf-8")
		for other in (
			"sellos_test",
			"test_site",
			"pamaa",
			" ".join(("serve", "--port")),
			"bench --site",
			"tenant-site.sh",
		):
			self.assertNotIn(other, text, other)


class TestGateIgnoresTheDemo(unittest.TestCase):
	def make_bench(self, sites):
		bench = Path(tempfile.mkdtemp())
		for name in sites:
			(bench / "sites" / name).mkdir(parents=True)
			(bench / "sites" / name / "site_config.json").write_text(
				json.dumps({"db_name": name.removesuffix(".localhost")})
			)
		return bench

	def run_check(self, *args, env=None):
		return subprocess.run(
			[sys.executable, str(SCRIPTS / "check_site_set.py"), *args],
			env={**os.environ, **(env or {})}, capture_output=True, text=True,
		)  # fmt: skip

	def test_site_check_ignores_demo_sites_made_dropped_or_changed(self):
		bench = self.make_bench(["sellos_test.localhost", "test_site"])
		snap = str(bench / "snap.json")
		dbs = bench / "dbs.txt"
		dbs.write_text("sellos_test\ntest_site\n")
		env = {"SELLOS_CHECK_DATABASES_FILE": str(dbs)}
		self.assertEqual(self.run_check("snapshot", str(bench), snap, env=env).returncode, 0)
		# A demo site and its database appear while the gate runs: not a failure.
		for name in ("sellos_tenant_democontrol.localhost", "sellos_tenant_demoalpha.localhost"):
			(bench / "sites" / name).mkdir()
			(bench / "sites" / name / "site_config.json").write_text(json.dumps({"db_name": "other"}))
		dbs.write_text("sellos_test\ntest_site\nsellos_tenant_democontrol\nsellos_tenant_demoalpha\n")
		result = self.run_check("compare", str(bench), snap, env=env)
		self.assertEqual(result.returncode, 0, result.stdout)
		# A real tenant left behind is still caught.
		(bench / "sites" / "sellos_tenant_leftover.localhost").mkdir()
		(bench / "sites" / "sellos_tenant_leftover.localhost" / "site_config.json").write_text(
			json.dumps({"db_name": "sellos_tenant_leftover"})
		)
		result = self.run_check("compare", str(bench), snap, env=env)
		self.assertEqual(result.returncode, 1)
		self.assertIn("leftover", result.stdout)
		self.assertNotIn("demo", result.stdout)

	def test_leak_check_never_reads_a_demo_site(self):
		bench = Path(tempfile.mkdtemp())
		demo_dir = bench / "sites" / "sellos_tenant_demoalpha.localhost"
		other = bench / "sites" / "sellos_tenant_other.localhost"
		for d in (demo_dir, other):
			d.mkdir(parents=True)
			(d / "site_config.json").write_text("has SECRETVALUE123 inside")
		env = {**os.environ, "BUILDOS_TELEGRAM_CHAT_ID": "SECRETVALUE123"}
		leak = [sys.executable, str(SCRIPTS / "check_no_secret_leak.py")]
		result = subprocess.run(
			[*leak, str(demo_dir), str(demo_dir / "site_config.json")],
			env=env,
			capture_output=True,
			text=True,
		)
		self.assertEqual(result.returncode, 0, result.stdout)
		result = subprocess.run([*leak, str(bench / "sites")], env=env, capture_output=True, text=True)
		self.assertEqual(result.returncode, 1)
		self.assertIn("sellos_tenant_other", result.stdout)
		self.assertNotIn("demoalpha", result.stdout)

	def test_the_baseline_restore_refuses_a_demo_site(self):
		result = subprocess.run(
			["bash", str(SCRIPTS / "lib" / "restore_baseline.sh"), "sellos_tenant_demoalpha.localhost", "/nonexistent.sql.gz"],
			capture_output=True, text=True,
		)  # fmt: skip
		self.assertEqual(result.returncode, 2)
		self.assertIn("demo site", result.stderr)

	def test_drop_refuses_a_demo_site_unless_the_demo_allows_it(self):
		with (
			mock.patch.object(tenant_sites, "_run_frappe") as run,
			mock.patch.dict(os.environ, {}, clear=False),
		):
			os.environ.pop(tenant_sites.ALLOW_DEMO_DROP_ENV, None)
			with self.assertRaises(tenant_sites.TenantSiteError):
				tenant_sites.drop("demoalpha")
			run.assert_not_called()
			tenant_sites.drop("regularone")  # an ordinary tenant is still dropped
			self.assertEqual(run.call_count, 1)
			os.environ[tenant_sites.ALLOW_DEMO_DROP_ENV] = "1"
			tenant_sites.drop("demoalpha")
			self.assertEqual(run.call_count, 2)

	def test_tenant_site_script_cannot_drop_a_demo_site(self):
		result = subprocess.run(
			[sys.executable, "-c", "import sys; from sellos.provisioning import tenant_sites as t; sys.exit(t.main(['drop','demoalpha']))"],
			env={k: v for k, v in os.environ.items() if k != tenant_sites.ALLOW_DEMO_DROP_ENV},
			capture_output=True, text=True,
		)  # fmt: skip
		self.assertNotEqual(result.returncode, 0)
		self.assertIn("demo site", result.stdout + result.stderr)


FEATURE_TABLES = (
	"Developer", "Project", "Unit", "Property", "Listing", "Channel Partner Firm", "Partner Registration",
	"Partner Share", "Sales Team", "Do Not Call Number", "Call Log", "Consent Check", "App Notification",
	"Lead Task",
)  # fmt: skip


class TestDemoSeedAndReset(unittest.TestCase):
	"""The real provisioning path: a control site and one company site, seeded, seeded again, reset, dropped."""

	CONTROL, COMPANY = "demotestctl", "demotestco"

	def demo(self, *args):
		bench = tenant_sites.bench_dir()
		return subprocess.run(
			[str(bench / "env" / "bin" / "python"), "-m", "sellos.testing.demo", *args,
			 "--control", self.CONTROL, "--company", self.COMPANY],
			cwd=bench / "sites", env={**os.environ, "SELLOS_BENCH_DIR": str(bench)}, capture_output=True, text=True,
		)  # fmt: skip

	def query(self, site, sql):
		bench = tenant_sites.bench_dir()
		code = (
			"import frappe, json; frappe.init(site=%r, sites_path='.'); frappe.connect(); "
			"print('ROWS', json.dumps(frappe.db.sql(%r, as_list=True), default=str)); frappe.destroy()"
		) % (site, sql)
		result = subprocess.run(
			[str(bench / "env" / "bin" / "python"), "-c", code],
			cwd=bench / "sites",
			capture_output=True,
			text=True,
		)
		line = next((ln for ln in result.stdout.splitlines() if ln.startswith("ROWS ")), None)
		self.assertIsNotNone(line, result.stdout + result.stderr)
		return json.loads(line[5:])

	def test_seed_is_idempotent_and_reset_rebuilds(self):
		self.addCleanup(self.demo, "drop")
		site = demo.site_of(self.COMPANY)
		first = self.demo("seed")
		self.assertEqual(first.returncode, 0, first.stdout[-1500:] + first.stderr[-1500:])
		leads = self.query(site, "select count(*) from `tabLead`")[0][0]
		self.assertGreaterEqual(leads, len(demo.COMPANIES[0]["leads"]))  # and the inbound leads
		clients = self.query(site, "select count(*) from `tabClient`")[0][0]
		stages = {r[0] for r in self.query(site, "select distinct stage from `tabLead`")}
		# Every buyer stage, and the two seller stages the demo's sellers are in (demo_data.py).
		self.assertEqual(stages, set(STAGES) | {"Seller Qualified", "Seller Valuation shared"})
		consent = {r[0] for r in self.query(site, "select distinct consent_status from `tabLead`")}
		self.assertGreaterEqual(consent, {"Unknown", "Consented", "Opted out", "Registered DND"})
		grants = {r[0] for r in self.query(site, "select status from `tabSupport Grant`")}
		self.assertEqual(grants, {"Active", "Revoked"})
		roles = self.query(
			site,
			"select u.name, r.role from `tabHas Role` r join tabUser u on u.name = r.parent where r.role like 'SellOS %'",
		)
		self.assertIn([demo.company_users(0)[0][0], demo.COMPANY_ADMIN], roles)
		self.assertIn([demo.PLATFORM_ADMIN_EMAIL, demo.PLATFORM_ADMIN], roles)
		self.assertEqual(sum(1 for _u, role in roles if role == demo.AGENT), 2)
		control = demo.site_of(self.CONTROL)
		self.assertEqual(self.query(control, "select status from `tabTenant`"), [["Active"]])

		again = self.demo("seed")
		self.assertEqual(again.returncode, 0, again.stdout[-1500:] + again.stderr[-1500:])
		self.assertEqual(self.query(site, "select count(*) from `tabLead`")[0][0], leads)
		self.assertEqual(self.query(site, "select count(*) from `tabClient`")[0][0], clients)
		counts = {
			table: self.query(site, f"select count(*) from `tab{table}`")[0][0] for table in FEATURE_TABLES
		}
		for table, count in counts.items():
			self.assertGreater(count, 0, table)
		self.assertEqual(self.query(site, "select count(*) from `tabSales Team Member`")[0][0], 2)
		purposes = {r[0] for r in self.query(site, "select distinct purpose from `tabCall Log`")}
		self.assertGreaterEqual(len(purposes), 2)
		statuses = {r[0] for r in self.query(site, "select status from `tabChannel Partner Firm`")}
		self.assertGreaterEqual(statuses, {"Invited", "Pending approval", "Approved"})

		rebuilt = self.demo("reset")
		self.assertEqual(rebuilt.returncode, 0, rebuilt.stdout[-1500:] + rebuilt.stderr[-1500:])
		self.assertEqual(self.query(site, "select count(*) from `tabLead`")[0][0], leads)

		dropped = self.demo("drop")
		self.assertEqual(dropped.returncode, 0, dropped.stdout[-800:] + dropped.stderr[-800:])
		self.assertNotIn(site, tenant_sites.list_sites())
		self.assertNotIn(demo.site_of(self.CONTROL), tenant_sites.list_sites())


if __name__ == "__main__":
	unittest.main()
