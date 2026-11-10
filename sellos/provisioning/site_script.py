"""The test site script (SOS-P0-11): one path that makes a company site, for tests and provisioning.

    python -m sellos.provisioning.site_script up <id>    # create, install SellOS, seed a test admin, check
    python -m sellos.provisioning.site_script down <id>  # drop the site and its database, check it is gone
    python -m sellos.provisioning.site_script run <id>   # up, then down even when up fails; times the run

scripts/test-site.sh runs it. <id> is [a-z0-9]+ and the site is sellos_tenant_<id>.localhost, checked by
sellos.provisioning.tenant_sites.names before anything runs. The site and database are made and dropped
only by sellos.provisioning.tenant_sites, with the MariaDB provisioner account, never root. The
provisioner password never passes through this module: the steps after the site exists (install-app,
the seed and the read back) need no MariaDB root account, so they run with the plain environment.

The seeded admin is the Company Admin test user from sellos.testing.users (a published test password,
not a secret). A site made here is for tests, never for a customer.
"""

import json
import subprocess
import sys
import time

from sellos.provisioning import tenant_sites
from sellos.provisioning.credentials import ProvisionerPasswordMissing

# The agreed time for `run`: create, install, seed, check and drop. Over it, the script exits 4.
TIME_BUDGET_SECONDS = 180
APP = "sellos"
RESULT_MARK = "SELLOS_SITE_RESULT "
ADMIN_ROLE = "SellOS Company Admin"

COMMAND_LAUNCHER = """
import runpy, sys
sys.argv = ["bench_helper", "frappe", *sys.argv[1:]]
runpy.run_module("frappe.utils.bench_helper", run_name="__main__", alter_sys=True)
"""


class SiteScriptError(RuntimeError):
	pass


def _site_command(site, *args):
	"""Run one Frappe command on a tenant site (no MariaDB root account needed). Returns its output."""
	bench = tenant_sites.bench_dir()
	command = [str(bench / "env" / "bin" / "python"), "-c", COMMAND_LAUNCHER, "--site", site, *args]
	try:
		result = subprocess.run(command, cwd=bench / "sites", capture_output=True, text=True, check=False)
	except OSError as e:
		raise SiteScriptError(f"{args[0]} on {site} could not be started: {e.strerror}.") from None
	output = result.stdout + result.stderr
	if result.returncode != 0:
		print(output.rstrip("\n"))
		raise SiteScriptError(f"{args[0]} on {site} failed with exit code {result.returncode}.")
	return result.stdout


def seed_admin():
	"""Run on the new site with bench execute (which commits): the test Company Admin, read back."""
	from sellos.testing import users

	spec = users.TEST_USERS["company_admin"]
	users._with_conflict_retry(lambda: users._ensure_user(spec, synchronous_contact=True))
	return report()


def report():
	"""What the new site holds, printed as one marked JSON line the script reads back."""
	import frappe

	from sellos.testing import users

	email = users.TEST_USERS["company_admin"]["email"]
	info = {
		"site": frappe.local.site,
		"database": frappe.local.conf.db_name,
		"apps": frappe.get_installed_apps(),
		"admin": email,
		"admin_enabled": bool(frappe.db.get_value("User", email, "enabled")),
		"admin_roles": sorted(frappe.get_roles(email)) if frappe.db.exists("User", email) else [],
	}
	print(RESULT_MARK + json.dumps(info))
	return info


def read_result(output):
	for line in reversed(output.splitlines()):
		if line.startswith(RESULT_MARK):
			return json.loads(line[len(RESULT_MARK) :])
	raise SiteScriptError("The new site did not report what it holds.")


def up(tenant_id):
	"""Create the site from nothing, install SellOS, seed the test admin and check it. Returns the report."""
	site, db_name = tenant_sites.names(tenant_id)
	if site in tenant_sites.list_sites():
		# Left by an earlier run that was killed. It is a tenant test site by name, so start clean.
		print(f"{site} already exists, dropping it first.")
		tenant_sites.drop(tenant_id)
	tenant_sites.create(tenant_id)
	_site_command(site, "install-app", APP)
	output = _site_command(site, "execute", "sellos.provisioning.site_script.seed_admin")
	info = read_result(output)
	if info["database"] != db_name or APP not in info["apps"]:
		raise SiteScriptError(f"{site} came up wrong: database {info['database']}, apps {info['apps']}.")
	if not info["admin_enabled"] or ADMIN_ROLE not in info["admin_roles"]:
		raise SiteScriptError(f"{site} has no working {ADMIN_ROLE} test admin.")
	return info


def down(tenant_id):
	"""Drop the site and its database, and check the site is gone. Safe to run when it is already gone."""
	site, _ = tenant_sites.names(tenant_id)
	if site in tenant_sites.list_sites():
		tenant_sites.drop(tenant_id)
	if site in tenant_sites.list_sites():
		raise SiteScriptError(f"{site} is still on the bench after the drop.")
	return site


def run(tenant_id, budget=TIME_BUDGET_SECONDS):
	"""up, then down in a finally. Returns (report, seconds). Raises SiteScriptError past the budget."""
	start = time.monotonic()
	try:
		info = up(tenant_id)
	finally:
		down(tenant_id)
	seconds = time.monotonic() - start
	if seconds > budget:
		raise SiteScriptError(f"The run took {seconds:.0f} seconds, over the agreed {budget}.")
	return info, seconds


USAGE = "usage: site_script up <id> | down <id> | run <id>"


def main(argv=None):
	argv = sys.argv[1:] if argv is None else argv
	if len(argv) != 2 or argv[0] not in ("up", "down", "run"):
		print(USAGE, file=sys.stderr)
		return 2
	command, tenant_id = argv
	try:
		if command == "up":
			info = up(tenant_id)
			print(f"Up: {info['site']} with {', '.join(info['apps'])}; admin {info['admin']}")
		elif command == "down":
			print(f"Down: {down(tenant_id)} is gone")
		else:
			info, seconds = run(tenant_id)
			print(f"Run passed: {info['site']} made and dropped in {seconds:.0f} seconds")
	except tenant_sites.TenantNameError as e:
		print(str(e), file=sys.stderr)
		return 2
	except ProvisionerPasswordMissing as e:
		print(str(e), file=sys.stderr)
		return 3
	except (SiteScriptError, tenant_sites.TenantSiteError) as e:
		print(str(e), file=sys.stderr)
		return 4 if "agreed" in str(e) else 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
