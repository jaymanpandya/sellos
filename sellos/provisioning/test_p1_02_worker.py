"""SOS-P1-02: the provisioning worker.

Test criteria: provision five tenants in sequence, kill the worker during a job and confirm it
recovers, and confirm a failed job is visible. The real runs use the MariaDB provisioner account
through sellos.provisioning.tenant_sites and make real sites, which the class drops again.

The worker commits (a killed worker must leave its progress behind), so the records these tests make
are deleted by hand in tearDownClass instead of being rolled back.
"""

import ast
import contextlib
import email
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from sellos.access.roles import ensure_roles
from sellos.provisioning import site_script, tenant_setup, tenant_sites, worker
from sellos.tests.tenant_template import full_install, template_in_use

PACKAGE = Path(__file__).resolve().parents[1]
SENTINEL = "Sentinel-Not-A-Real-Password-9f3a"
PREFIX = "p102"


def make_tenant(tenant_id, **values):
	"""A Tenant and, through it, its Requested job. Returns the job's name."""
	frappe.get_doc(
		{
			"doctype": "Tenant",
			"tenant_id": tenant_id,
			"company_name": f"P102 {tenant_id} Realty",
			"admin_email": f"owner-{tenant_id}@example.com",
			"admin_name": "Owner",
			**values,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep  the worker reads it from its own transaction
	return frappe.db.get_value("Provisioning Job", {"tenant": tenant_id}, "name")


def work_until_done(job_name, limit=6, **limits):
	"""Run the worker until the job is Active or Failed with no tries left."""
	for _ in range(limit):
		worker.process_next(**limits)
		if frappe.db.get_value("Provisioning Job", job_name, "status") in ("Active", "Failed"):
			if frappe.db.get_value("Provisioning Job", job_name, "attempts") >= worker.MAX_ATTEMPTS or (
				frappe.db.get_value("Provisioning Job", job_name, "status") == "Active"
			):
				break
	return frappe.get_doc("Provisioning Job", job_name)


class TestWebProcessHasNoShell(UnitTestCase):
	"""SOS-P1-02: the web process has no shell access. Only the worker package runs commands."""

	def test_no_module_outside_the_provisioning_package_runs_commands(self):
		forbidden = {"subprocess", "pty", "pexpect"}
		for path in PACKAGE.rglob("*.py"):
			rel = path.relative_to(PACKAGE)
			if rel.parts[0] in ("provisioning", "tests", "testing") or path.name.startswith("test_"):
				continue
			tree = ast.parse(path.read_text())
			for node in ast.walk(tree):
				if isinstance(node, ast.Import):
					found = {a.name.split(".")[0] for a in node.names}
				elif isinstance(node, ast.ImportFrom):
					found = {(node.module or "").split(".")[0]}
				elif isinstance(node, ast.Call) and ast.unparse(node.func) in ("os.system", "os.popen"):
					found = {"os.system"}
				else:
					continue
				self.assertFalse(found & (forbidden | {"os.system"}), f"{rel} runs commands")

	def test_nothing_in_the_provisioning_package_is_reachable_from_the_web(self):
		for path in (PACKAGE / "provisioning").glob("*.py"):
			for node in ast.walk(ast.parse(path.read_text())):
				if isinstance(node, ast.FunctionDef):
					decorators = " ".join(ast.unparse(d) for d in node.decorator_list)
					self.assertNotIn("whitelist", decorators, f"{path.name}:{node.name}")

	def test_the_worker_is_not_a_scheduled_or_web_hook(self):
		hooks = str(frappe.get_hooks("scheduler_events")) + str(frappe.get_hooks("before_request"))
		self.assertNotIn("provisioning.worker", hooks)

	def test_the_worker_names_come_from_the_name_check(self):
		with mock.patch.object(tenant_sites, "_run_frappe") as run:
			with self.assertRaises(tenant_sites.TenantNameError):
				tenant_sites.create("../x")
		run.assert_not_called()


def visible_text(raw_message):
	"""What a reader of a queued email sees: every text part, decoded."""
	parts = email.message_from_string(raw_message).walk()
	return "\n".join(p.get_payload(decode=True).decode() for p in parts if p.get_content_maintype() == "text")


def clean_up():
	"""Delete what the tests made and the worker committed, and drop the real sites. Safe to repeat."""
	frappe.db.rollback()
	frappe.set_user("Administrator")
	for site in tenant_sites.list_sites():
		if site.startswith(f"sellos_tenant_{PREFIX}"):
			tenant_sites.drop(site[len("sellos_tenant_") : -len(".localhost")])
	jobs = frappe.get_all("Provisioning Job", filters={"tenant": ["like", f"{PREFIX}%"]}, pluck="name")
	for doctype, names in (
		("Provisioning Job", jobs),
		("Tenant", frappe.get_all("Tenant", filters={"name": ["like", f"{PREFIX}%"]}, pluck="name")),
		("Plan", frappe.get_all("Plan", filters={"name": ["like", "P102 %"]}, pluck="name")),
	):
		if names:
			frappe.db.delete("Version", {"ref_doctype": doctype, "docname": ["in", names]})
			frappe.db.delete(doctype, {"name": ["in", names]})
	if jobs:
		queued = frappe.get_all("Email Queue", filters={"reference_name": ["in", jobs]}, pluck="name")
		if queued:
			frappe.db.delete("Email Queue Recipient", {"parent": ["in", queued]})
			frappe.db.delete("Email Queue", {"name": ["in", queued]})
	frappe.db.commit()  # nosemgrep


SENDER = "p102-sender@example.com"


def ensure_outgoing_account():
	"""The control site needs a default outgoing email account to send the login email."""
	if not frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}):
		frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_account_name": "P102 Sender",
				"email_id": SENDER,
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"smtp_server": "localhost",
				"smtp_port": 25,
				"always_use_account_name_as_sender_name": 0,
			}
		).insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep


class WorkerCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()

	@classmethod
	def tearDownClass(cls):
		clean_up()
		frappe.db.delete("Email Account", {"email_id": SENDER})
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def setUp(self):
		clean_up()
		ensure_outgoing_account()
		self.addCleanup(clean_up)


class TestWorkerQueue(WorkerCase):
	"""SOS-P1-02: claiming, retrying, giving up and taking over, with the site steps faked."""

	def fake_steps(self):
		"""Fake every step that makes a real site, so these tests are quick."""
		self.created = []
		patches = [
			mock.patch.object(tenant_sites, "create", side_effect=lambda t: self.created.append(t)),
			mock.patch.object(tenant_sites, "drop"),
			mock.patch.object(
				tenant_sites,
				"list_sites",
				side_effect=lambda: [tenant_sites.names(t)[0] for t in self.created],
			),
			mock.patch.object(site_script, "_site_command", side_effect=self.fake_command),
		]
		for p in patches:
			p.start()
			self.addCleanup(p.stop)

	def fake_command(self, site, *args):
		if args[0] == "install-app":
			return ""
		function = args[1].rsplit(".", 1)[1]
		kwargs = ast.literal_eval(args[3])
		if function == "configure":
			self.configured = kwargs
			return tenant_setup.RESULT_MARK + json.dumps(
				{
					"admin": kwargs["admin_email"],
					"admin_enabled": True,
					"admin_roles": ["SellOS Company Admin"],
					"limits": {"plan": kwargs["plan"] or "", "max_users": kwargs["max_users"]},
				}
			)
		return tenant_setup.RESULT_MARK + json.dumps({"path": "/update-password?key=abc123"})

	def test_a_queued_job_becomes_a_ready_tenant_and_the_admin_is_emailed(self):
		self.fake_steps()
		frappe.get_doc({"doctype": "Plan", "plan_name": "P102 Small", "max_users": 7}).insert()
		frappe.db.commit()  # nosemgrep
		job_name = make_tenant("p102fakea", plan="P102 Small")
		job = work_until_done(job_name)
		self.assertEqual(job.status, "Active", job.log)
		self.assertEqual(job.step, "emailed")
		self.assertEqual(frappe.db.get_value("Tenant", "p102fakea", "status"), "Active")
		self.assertEqual(self.created, ["p102fakea"])
		self.assertEqual((self.configured["plan"], self.configured["max_users"]), ("P102 Small", 7))
		queued = frappe.get_all(
			"Email Queue", filters={"reference_name": job_name}, fields=["name", "message"], limit=1
		)
		self.assertEqual(len(queued), 1)
		recipients = frappe.get_all(
			"Email Queue Recipient", filters={"parent": queued[0].name}, pluck="recipient"
		)
		self.assertEqual(recipients, ["owner-p102fakea@example.com"])
		body = visible_text(queued[0].message)
		self.assertIn("/update-password?key=abc123", body)
		self.assertIn("sellos_tenant_p102fakea.localhost", body)
		self.assertNotIn("Frappe", body)
		self.assertNotIn("abc123", job.log)

	def test_a_failure_is_retried_then_the_job_is_failed_with_a_log(self):
		self.fake_steps()
		attempts = []

		def boom(tenant_id):
			attempts.append(tenant_id)
			raise tenant_sites.TenantSiteError(
				"new-site sellos_tenant_p102fail.localhost failed with exit code 1."
			)

		job_name = make_tenant("p102fail")
		with mock.patch.object(tenant_sites, "create", side_effect=boom):
			job = work_until_done(job_name, retry_delay=0)
			self.assertIsNone(worker.process_next(retry_delay=0))  # no tries left, nothing to pick up
		self.assertEqual(len(attempts), worker.MAX_ATTEMPTS)
		self.assertEqual((job.status, job.attempts), ("Failed", worker.MAX_ATTEMPTS))
		self.assertEqual(frappe.db.get_value("Tenant", "p102fail", "status"), "Failed")
		self.assertIn("exit code 1", job.log)
		self.assertIn("Giving up", job.log)
		self.assertEqual(job.log.count("Failed:"), worker.MAX_ATTEMPTS)

	def test_a_failed_job_is_visible_to_the_platform_admin(self):
		self.fake_steps()
		job_name = make_tenant("p102seen")
		with mock.patch.object(tenant_sites, "create", side_effect=tenant_sites.TenantSiteError("x failed.")):
			work_until_done(job_name, retry_delay=0)
		from sellos.testing.users import TEST_USERS, create_test_users

		create_test_users()
		frappe.set_user(TEST_USERS["platform_admin"]["email"])
		seen = frappe.get_list(
			"Provisioning Job",
			filters={"status": "Failed", "tenant": "p102seen"},
			fields=["name", "log", "attempts"],
		)
		self.assertEqual([j.name for j in seen], [job_name])
		self.assertIn("x failed.", seen[0].log)

	def test_a_job_waits_for_the_retry_delay(self):
		self.fake_steps()
		job_name = make_tenant("p102wait")
		with mock.patch.object(tenant_sites, "create", side_effect=tenant_sites.TenantSiteError("x")):
			self.assertEqual(worker.process_next(), job_name)
			self.assertIsNone(worker.process_next())  # RETRY_DELAY has not passed
			self.assertEqual(worker.process_next(retry_delay=0), job_name)
		self.assertEqual(frappe.db.get_value("Provisioning Job", job_name, "attempts"), 2)

	def test_a_job_cannot_be_claimed_twice(self):
		job_name = make_tenant("p102twice")
		self.assertTrue(worker._claim(job_name, "Requested"))
		self.assertFalse(worker._claim(job_name, "Requested"))
		self.assertEqual(frappe.db.get_value("Provisioning Job", job_name, "attempts"), 1)

	def test_a_worker_that_stopped_is_taken_over_after_the_stale_time(self):
		self.fake_steps()
		job_name = make_tenant("p102stale")
		self.assertTrue(worker._claim(job_name, "Requested"))  # a worker claimed it, then was killed
		self.created.append("p102stale")  # and left a half made site
		self.assertIsNone(worker.claim_next())  # a heartbeat inside STALE_AFTER means it is still alive
		job = work_until_done(job_name, stale_after=0)
		self.assertEqual(job.status, "Active", job.log)
		self.assertEqual(job.attempts, 2)
		self.assertIn("Taking it over", job.log)
		self.assertIn("Removing a half made site", job.log)
		tenant_sites.drop.assert_called_with("p102stale")

	def test_a_stopped_worker_on_the_last_attempt_fails_the_job(self):
		job_name = make_tenant("p102last")
		frappe.db.set_value("Provisioning Job", job_name, {"status": "Provisioning", "attempts": 3})
		frappe.db.commit()  # nosemgrep
		self.assertIsNone(worker.claim_next(stale_after=0))
		job = frappe.get_doc("Provisioning Job", job_name)
		self.assertEqual(job.status, "Failed")
		self.assertIn("Giving up", job.log)

	def test_a_configured_site_only_needs_its_email_on_retry(self):
		self.fake_steps()
		job_name = make_tenant("p102mail")
		self.created.append("p102mail")
		frappe.db.set_value(
			"Provisioning Job", job_name, {"status": "Provisioning", "step": "configured", "attempts": 1}
		)
		frappe.db.commit()  # nosemgrep
		job = work_until_done(job_name, stale_after=0)
		self.assertEqual(job.status, "Active", job.log)
		tenant_sites.drop.assert_not_called()
		self.assertIn("Only the email is left", job.log)

	def test_the_password_never_reaches_the_job_log(self):
		"""The child's output is cleaned by tenant_sites, and the log holds only what is left."""
		job_name = make_tenant("p102leak")
		noisy = CompletedProcess(
			[], 1, stdout=f"error near password {SENTINEL}\n", stderr=f"also {SENTINEL}\n"
		)
		with (
			mock.patch.dict(os.environ, {"SELLOS_DB_PROVISIONER_PASSWORD": SENTINEL}),
			mock.patch.object(tenant_sites.subprocess, "run", return_value=noisy),
			mock.patch.object(tenant_sites, "list_sites", return_value=[]),
		):
			job = work_until_done(job_name, retry_delay=0)
		self.assertEqual(job.status, "Failed")
		self.assertIn("exit code 1", job.log)
		self.assertIn("Output of the failed step", job.log)
		self.assertNotIn(SENTINEL, job.log)
		self.assertNotIn(SENTINEL, frappe.db.get_value("Provisioning Job", job_name, "log"))

	def test_a_missing_provisioner_password_fails_the_job_without_a_value(self):
		from sellos.provisioning.credentials import ProvisionerPasswordMissing

		job_name = make_tenant("p102nopw")
		with (
			mock.patch.object(tenant_sites, "list_sites", return_value=[]),
			mock.patch.object(
				tenant_sites, "get_provisioner_password", side_effect=ProvisionerPasswordMissing("not set")
			),
		):
			job = work_until_done(job_name, retry_delay=0)
		self.assertEqual(job.status, "Failed")
		self.assertIn("not set", job.log)

	def test_the_url_of_a_tenant_site_comes_from_a_setting(self):
		self.assertEqual(
			worker.tenant_url("sellos_tenant_a.localhost", "a"), "http://sellos_tenant_a.localhost:8004"
		)
		with mock.patch.object(
			frappe, "conf", frappe._dict({worker.URL_TEMPLATE_KEY: "https://{tenant_id}.example.test/"})
		):
			self.assertEqual(worker.tenant_url("s", "acme"), "https://acme.example.test")

	def test_the_command_line_needs_a_control_site(self):
		self.assertEqual(worker.main([]), 2)
		self.assertEqual(worker.main(["--once"]), 2)


@contextlib.contextmanager
def templates_used():
	"""SOS-SETUP-28: the template each tenant site in the block was built from (None: full install)."""
	used = []
	real = tenant_sites.template_sql

	def record():
		used.append(real())
		return used[-1]

	with mock.patch.object(tenant_sites, "template_sql", record):
		yield used


class TestRealProvisioning(WorkerCase):
	"""SOS-P1-02: real sites, made with the provisioner account."""

	def read_back(self, tenant_id):
		site, _db_name = tenant_sites.names(tenant_id)
		self.assertIn(site, tenant_sites.list_sites())
		return site, tenant_setup_report(site, tenant_id)

	def test_five_tenants_are_provisioned_in_sequence(self):
		ids = [f"{PREFIX}seq{n}" for n in range(1, 6)]
		jobs = [make_tenant(t) for t in ids]
		for tenant_id, job_name in zip(ids, jobs, strict=True):
			with templates_used() as used:
				job = work_until_done(job_name)
			self.assertEqual(job.status, "Active", job.log)
			self.assertEqual(job.attempts, 1)
			if template_in_use():  # SOS-SETUP-28: CI builds these from its template dump
				self.assertEqual(used, [os.environ[tenant_sites.TEMPLATE_ENV]])
			site, info = self.read_back(tenant_id)
			self.assertEqual(info["site"], site)
			self.assertEqual(info["admin"], f"owner-{tenant_id}@example.com")
			self.assertTrue(info["admin_enabled"])
			self.assertIn("SellOS Company Admin", info["admin_roles"])
			self.assertEqual(info["company_name"], f"P102 {tenant_id} Realty")
			self.assertEqual(frappe.db.get_value("Tenant", tenant_id, "status"), "Active")
			self.assertEqual(
				frappe.db.count(
					"Email Queue", {"reference_doctype": "Provisioning Job", "reference_name": job_name}
				),
				1,
			)
		self.assertEqual(len({tenant_sites.names(t)[1] for t in ids}), 5)

	def test_plan_limits_are_applied_on_the_site(self):
		"""SOS-SETUP-28: the one real provisioning test. Every other test site in CI is built from
		the template dump, and this one goes through Frappe's full install, so that path is covered on
		every run. sellos/provisioning/test_tenant_template.py checks there is exactly one."""
		frappe.get_doc({"doctype": "Plan", "plan_name": "P102 Real", "max_users": 3}).insert()
		make_tenant("p102plan", plan="P102 Real")
		frappe.db.commit()  # nosemgrep
		with full_install(), templates_used() as used:
			job = work_until_done(frappe.db.get_value("Provisioning Job", {"tenant": "p102plan"}, "name"))
		self.assertEqual(job.status, "Active", job.log)
		self.assertEqual(used, [None])  # one site, made with Frappe's full install
		_site, info = self.read_back("p102plan")
		self.assertEqual(info["limits"], {"plan": "P102 Real", "max_users": 3})

	def test_a_worker_killed_during_a_job_is_recovered(self):
		tenant_id = "p102kill"
		site, _db = tenant_sites.names(tenant_id)
		job_name = make_tenant(tenant_id)
		self.assertTrue(worker._claim(job_name, "Requested"))  # the worker holds the job...
		bench = tenant_sites.bench_dir()
		child = subprocess.Popen(  # ...and is making the site when it is killed
			[
				str(bench / "env" / "bin" / "python"),
				"-m",
				"sellos.provisioning.tenant_sites",
				"create",
				tenant_id,
			],
			cwd=bench / "sites",
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			start_new_session=True,
		)
		try:
			deadline = time.monotonic() + 120
			while (
				site not in tenant_sites.list_sites() and child.poll() is None and time.monotonic() < deadline
			):
				time.sleep(0.2)
			time.sleep(1)
			if child.poll() is None:
				os.killpg(child.pid, signal.SIGKILL)
		finally:
			if child.poll() is None:
				os.killpg(child.pid, signal.SIGKILL)
			child.wait()
		self.assertEqual(frappe.db.get_value("Provisioning Job", job_name, "status"), "Provisioning")
		self.assertIsNone(worker.claim_next())  # a live heartbeat keeps the job with its worker
		job = work_until_done(job_name, stale_after=0)
		self.assertEqual(job.status, "Active", job.log)
		self.assertEqual(job.attempts, 2)
		self.assertIn("Taking it over", job.log)
		_site, info = self.read_back(tenant_id)
		self.assertIn("SellOS Company Admin", info["admin_roles"])


def tenant_setup_report(site, tenant_id):
	admin = f"owner-{tenant_id}@example.com"
	return worker._tenant_command(site, tenant_id, "report", admin_email=admin)
