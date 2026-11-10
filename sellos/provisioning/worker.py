"""The provisioning worker (SOS-P1-02): makes a company's site from a Provisioning Job.

It is its own process, started by the Platform Admin's operator with scripts/provisioning-worker.sh,
and never part of the web process. The web process only writes the Tenant and its Requested job; it has
no shell access and no method here is whitelisted. The worker, on the control site:

1. claims a job (Requested, a Failed job with attempts left, or a Provisioning job whose worker died);
2. creates the site and database with sellos.provisioning.tenant_sites.create, which uses the MariaDB
   provisioner account and never root, and checks the name with tenant_sites.names first;
3. installs SellOS on it, then (tenant_setup.configure) makes the Company Admin user and applies the plan
   limits;
4. emails the admin the site address and a one time link to set a password;
5. marks the job and the tenant Active.

Each step is recorded in the job's `step`, and every write to the job is committed and moves its
`modified` time, which is the worker's heartbeat. A worker that is killed leaves a Provisioning job that
stops moving. After STALE_AFTER seconds the next worker takes it over: it drops a half made site and starts
again, or, if the site was already configured, only sends the email. A failure is retried up to
MAX_ATTEMPTS times, RETRY_DELAY seconds apart, then the job stays Failed with its log.

The provisioner password is never read here. It lives in tenant_sites, which hands it to the child
process through its environment, and tenant_sites removes it from any output before this module sees it.
"""

import contextlib
import io
import json
import os
import signal
import sys
import time
from datetime import timedelta
from pathlib import Path

import frappe
from frappe.utils import add_to_date, cint, now_datetime

from sellos.provisioning import site_script, status, tenant_setup, tenant_sites
from sellos.provisioning.credentials import PASSWORD_ENV, ProvisionerPasswordMissing

MAX_ATTEMPTS = 3
RETRY_DELAY = 30  # seconds between a failure and the next try
STALE_AFTER = 600  # seconds without a heartbeat before a Provisioning job is taken over
POLL_SECONDS = 5
LOG_TAIL_LINES = 25
URL_TEMPLATE_KEY = "sellos_tenant_url_template"
DEFAULT_URL_TEMPLATE = "http://{site}:8004"

STEP_SITE = "site created"
STEP_APP = "app installed"
STEP_CONFIGURED = "configured"
STEP_EMAILED = "emailed"

JOB = "Provisioning Job"
TENANT = "Tenant"


def redact(text):
	"""Take the provisioner password out of text, if it is in this process's environment."""
	secret = os.environ.get(PASSWORD_ENV)
	if secret:
		text = text.replace(secret, "[provisioner password]")
	return text


class JobLog:
	"""Appends lines to a job's log, committing each, which is also the heartbeat."""

	def __init__(self, job_name):
		self.job_name = job_name

	def add(self, line):
		line = redact(str(line))
		current = frappe.db.get_value(JOB, self.job_name, "log") or ""
		stamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
		frappe.db.set_value(JOB, self.job_name, "log", f"{current}{stamp} {line}\n", update_modified=True)
		frappe.db.commit()  # nosemgrep  a killed worker must leave its progress behind

	def step(self, name):
		frappe.db.set_value(JOB, self.job_name, "step", name, update_modified=True)
		self.add(f"Done: {name}.")


def _claim(name, expected_status, recover=False):
	"""Move a job to Provisioning if it is still `expected_status`. True if this worker got it."""
	frappe.db.sql(
		"""update `tabProvisioning Job`
		set status = 'Provisioning', attempts = attempts + 1, started_at = %s, finished_at = null,
			modified = %s
		where name = %s and status = %s""",
		(now_datetime(), now_datetime(), name, expected_status),
	)
	claimed = frappe.db.sql("select row_count()")[0][0] == 1
	frappe.db.commit()  # nosemgrep  the claim is what stops a second worker taking the job
	return claimed


def _set_tenant(tenant_name, new_status):
	tenant = frappe.get_doc(TENANT, tenant_name)
	tenant.flags.ignore_permissions = True
	if tenant.status == status.REQUESTED and new_status != status.PROVISIONING:
		tenant.status = status.PROVISIONING  # Requested may only move to Provisioning
		tenant.save()
	if tenant.status != new_status:
		tenant.status = new_status
		tenant.save()
	frappe.db.commit()  # nosemgrep


def _finish(job_name, new_status, note):
	"""Set Failed or Active on a job we hold, through the normal status check."""
	frappe.db.rollback()
	job = frappe.get_doc(JOB, job_name)
	job.status = new_status
	job.flags.ignore_permissions = True
	job.save()
	JobLog(job_name).add(note)
	_set_tenant(job.tenant, new_status)


def claim_next(stale_after=STALE_AFTER, retry_delay=RETRY_DELAY, max_attempts=MAX_ATTEMPTS):
	"""Claim the next job to work on and return its name, or None."""
	now = now_datetime()
	# 1. Never tried.
	for (name,) in frappe.db.sql(
		"select name from `tabProvisioning Job` where status = 'Requested' order by creation limit 20"
	):
		if _claim(name, status.REQUESTED):
			return name
	# 2. Failed with tries left, after the delay.
	retry_before = add_to_date(now, seconds=-retry_delay)
	for (name,) in frappe.db.sql(
		"""select name from `tabProvisioning Job`
		where status = 'Failed' and attempts < %s and finished_at <= %s order by finished_at limit 20""",
		(max_attempts, retry_before),
	):
		if _claim(name, status.FAILED):
			JobLog(name).add("Trying again after a failure.")
			return name
	# 3. A worker died: Provisioning, but no heartbeat for a while.
	stale_before = add_to_date(now, seconds=-stale_after)
	for name, attempts in frappe.db.sql(
		"""select name, attempts from `tabProvisioning Job`
		where status = 'Provisioning' and modified <= %s order by modified limit 20""",
		(stale_before,),
	):
		if cint(attempts) >= max_attempts:
			_finish(
				name, status.FAILED, f"The worker stopped, and {max_attempts} attempts are used. Giving up."
			)
			continue
		# Provisioning -> Provisioning is not a status change, so count this attempt by hand.
		frappe.db.sql(
			"""update `tabProvisioning Job` set attempts = attempts + 1, started_at = %s, modified = %s
			where name = %s and status = 'Provisioning' and modified <= %s""",
			(now, now, name, stale_before),
		)
		took = frappe.db.sql("select row_count()")[0][0] == 1
		frappe.db.commit()  # nosemgrep
		if took:
			JobLog(name).add("The worker that held this job stopped. Taking it over.")
			return name
	return None


def tenant_url(site, tenant_id):
	template = frappe.conf.get(URL_TEMPLATE_KEY) or DEFAULT_URL_TEMPLATE
	return template.format(site=site, tenant_id=tenant_id).rstrip("/")


@contextlib.contextmanager
def _captured(log):
	"""Run a step; whatever it printed goes to the log's tail if it raises."""
	buffer = io.StringIO()
	try:
		with contextlib.redirect_stdout(buffer):
			yield buffer
	except Exception as e:
		tail = "\n".join(buffer.getvalue().strip().splitlines()[-LOG_TAIL_LINES:])
		if tail:
			log.add("Output of the failed step:\n" + tail)
		raise e from None


def _tenant_command(site, tenant_id, function, **kwargs):
	"""Run a function of sellos.provisioning.tenant_setup on the tenant site and return its JSON line."""
	argument = repr({"tenant_id": tenant_id, **kwargs})  # str, int and None only: a literal, no secrets
	output = site_script._site_command(
		site, "execute", f"sellos.provisioning.tenant_setup.{function}", "--kwargs", argument
	)
	for line in reversed(output.splitlines()):
		if line.startswith(tenant_setup.RESULT_MARK):
			return json.loads(line[len(tenant_setup.RESULT_MARK) :])
	raise site_script.SiteScriptError(f"{function} on {site} did not report back.")


def _send_login_email(job, tenant, site, link_path):
	url = tenant_url(site, tenant.tenant_id)
	name = frappe.utils.escape_html(tenant.admin_name or tenant.company_name)
	company = frappe.utils.escape_html(tenant.company_name)
	frappe.sendmail(
		recipients=[tenant.admin_email],
		subject=f"Your SellOS account for {tenant.company_name} is ready",
		message=(
			f"<p>Hello {name},</p>"
			f"<p>Your company, {company}, is now set up on SellOS.</p>"
			f"<p>Your address is <a href='{url}'>{url}</a>. Your login is {frappe.utils.escape_html(tenant.admin_email)}.</p>"
			f"<p>Choose your password here: <a href='{url}{link_path}'>{url}{link_path}</a>. "
			"The link works once and expires.</p>"
		),
		reference_doctype=JOB,
		reference_name=job.name,
	)
	frappe.db.commit()  # nosemgrep  the queued email must outlive this worker


def _provision(job_name, log):
	job = frappe.get_doc(JOB, job_name)
	tenant = frappe.get_doc(TENANT, job.tenant)
	site, db_name = tenant_sites.names(tenant.tenant_id)  # the one name check, before any command
	_set_tenant(tenant.name, status.PROVISIONING)
	log.add(f"Attempt {job.attempts} for {site} (database {db_name}).")

	exists = site in tenant_sites.list_sites()
	if exists and job.step == STEP_CONFIGURED:
		log.add("The site is already configured. Only the email is left.")
	else:
		if exists:
			log.add("Removing a half made site before starting again.")
			with _captured(log):
				tenant_sites.drop(tenant.tenant_id)
			frappe.db.set_value(JOB, job_name, "step", "", update_modified=True)
		with _captured(log):
			tenant_sites.create(tenant.tenant_id)
		log.step(STEP_SITE)
		with _captured(log):
			site_script._site_command(site, "install-app", site_script.APP)
		log.step(STEP_APP)
		plan = (
			frappe.db.get_value("Plan", tenant.plan, ["plan_name", "max_users"], as_dict=True)
			if tenant.plan
			else None
		)
		with _captured(log):
			info = _tenant_command(
				site,
				tenant.tenant_id,
				"configure",
				company_name=tenant.company_name,
				admin_email=tenant.admin_email,
				admin_name=tenant.admin_name,
				plan=plan.plan_name if plan else None,
				max_users=cint(plan.max_users) if plan else 0,
			)
		if (
			info["admin"] != tenant.admin_email
			or not info["admin_enabled"]
			or "SellOS Company Admin" not in info["admin_roles"]
		):
			raise site_script.SiteScriptError(f"{site} has no working Company Admin after the setup.")
		log.add(f"Plan limits applied: {json.dumps(info['limits'])}.")
		log.step(STEP_CONFIGURED)

	with _captured(log):
		link = _tenant_command(site, tenant.tenant_id, "make_login_link", admin_email=tenant.admin_email)
	_send_login_email(job, tenant, site, link["path"])
	log.step(STEP_EMAILED)
	_finish(job_name, status.ACTIVE, f"{site} is ready. The login email to the admin is queued.")


def _give_up_or_retry(job_name, error, max_attempts=MAX_ATTEMPTS):
	"""Record a failure. A half made site is dropped, but a configured one is kept for the email retry."""
	frappe.db.rollback()
	job = frappe.get_doc(JOB, job_name)
	log = JobLog(job_name)
	log.add(f"Failed: {error}")
	if job.step != STEP_CONFIGURED and job.step != STEP_EMAILED:
		try:
			site, _db = tenant_sites.names(frappe.db.get_value(TENANT, job.tenant, "tenant_id"))
			if site in tenant_sites.list_sites():
				with contextlib.redirect_stdout(io.StringIO()):
					tenant_sites.drop(frappe.db.get_value(TENANT, job.tenant, "tenant_id"))
				log.add(f"Dropped the half made site {site}.")
				frappe.db.set_value(JOB, job_name, "step", "", update_modified=True)
		except Exception as e:  # the cleanup must never hide the first error
			log.add(f"Could not drop the half made site: {type(e).__name__}.")
	left = max_attempts - cint(job.attempts)
	_finish(
		job_name,
		status.FAILED,
		f"Will try again in {RETRY_DELAY} seconds ({left} left)."
		if left > 0
		else "No attempts left. Giving up.",
	)


def run_job(job_name):
	"""Do one claimed job. A failure is recorded on the job, never raised."""
	log = JobLog(job_name)
	try:
		_provision(job_name, log)
	except ProvisionerPasswordMissing as e:
		_give_up_or_retry(job_name, str(e))
	except Exception as e:
		# Only the exception's own text, never a traceback: a traceback can show a frame's variables.
		_give_up_or_retry(job_name, f"{type(e).__name__}: {e}")


def process_next(**limits):
	"""Claim and run one job. Returns its name, or None when there is nothing to do."""
	name = claim_next(**limits)
	if name:
		run_job(name)
	return name


class _Stop:
	requested = False


def run_forever(poll=POLL_SECONDS):
	def stop(*_):
		_Stop.requested = True

	signal.signal(signal.SIGTERM, stop)
	signal.signal(signal.SIGINT, stop)
	print(f"SellOS provisioning worker on {frappe.local.site}. Stop it with Ctrl-C.")
	while not _Stop.requested:
		try:
			if not process_next():
				time.sleep(poll)
		except Exception as e:
			frappe.db.rollback()
			print(redact(f"Worker error: {type(e).__name__}: {e}"), file=sys.stderr)
			time.sleep(poll)
	return 0


def main(argv=None):
	argv = sys.argv[1:] if argv is None else argv
	usage = "usage: worker <control site> [--once]"
	if not argv or argv[0].startswith("-") or len(argv) > 2 or (len(argv) == 2 and argv[1] != "--once"):
		print(usage, file=sys.stderr)
		return 2
	site = argv[0]
	bench = tenant_sites.bench_dir()
	os.chdir(bench / "sites")
	frappe.init(site=site, sites_path=str(Path(bench / "sites")))
	frappe.connect()
	try:
		if not frappe.conf.get("sellos_control_site"):
			print(f"{site} is not the control site (sellos_control_site is not set).", file=sys.stderr)
			return 2
			# frappe.connect() above already runs as Administrator, P1.02.
		if len(argv) == 2:
			name = process_next()
			print(f"Ran {name}" if name else "Nothing to do.")
			return 0
		return run_forever()
	finally:
		frappe.destroy()


if __name__ == "__main__":
	sys.exit(main())
