"""Create, drop, list and probe tenant sites on the local bench (SOS-P0-06L, SOS-SETUP-22).

Every code path, test and script that creates or drops a tenant site goes through this module (or
scripts/tenant-site.sh, which runs it). A tenant id matches [a-z0-9]+. The site is
sellos_tenant_<id>.localhost and the database sellos_tenant_<id>. Anything else is refused before
any command runs.

Frappe's new-site and drop-site take the root password only as --db-root-password, so it would be on
the command line, where ps shows it and the bench wrapper logs it. Instead Frappe's own command entry
(the one `bench` runs: python -m frappe.utils.bench_helper frappe ...) is started through a short
launcher that reads the password from its environment and adds it to its own argument list in
memory. The visible command line never holds it, and the bench wrapper is never used.

    python -m sellos.provisioning.tenant_sites create <id> | drop <id> | list | probe
"""

import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

from sellos.provisioning.credentials import (
	PASSWORD_ENV,
	ProvisionerPasswordMissing,
	child_env,
	get_provisioner_password,
	provisioner_user,
)

ID_RE = re.compile(r"[a-z0-9]+")
PREFIX = "sellos_tenant_"
MAX_DB_NAME = 64
PROBE_ID = "probe"
ADMIN_ENV = "SELLOS_TENANT_ADMIN_PASSWORD"

# Runs in the child. The secrets come from its environment and are added to sys.argv in memory only.
LAUNCHER = """
import os, runpy, sys
args = sys.argv[1:]
secret = os.environ.pop("SELLOS_DB_PROVISIONER_PASSWORD")
args += ["--db-root-password", secret]
admin = os.environ.pop("SELLOS_TENANT_ADMIN_PASSWORD", "")
if admin:
    args += ["--admin-password", admin]
sys.argv = ["bench_helper", "frappe", *args]  # argv[0] is replaced by runpy, as python -m does
runpy.run_module("frappe.utils.bench_helper", run_name="__main__", alter_sys=True)
"""


class TenantNameError(ValueError):
	pass


class TenantSiteError(RuntimeError):
	pass


def names(tenant_id):
	"""(site name, database name) for a tenant id, or TenantNameError."""
	if not isinstance(tenant_id, str) or not ID_RE.fullmatch(tenant_id):
		raise TenantNameError(f"A tenant id is lower case letters and digits only, not {tenant_id!r}.")
	db_name = PREFIX + tenant_id
	if len(db_name) > MAX_DB_NAME:
		raise TenantNameError(f"The database name for {tenant_id!r} is longer than {MAX_DB_NAME} characters.")
	return f"{db_name}.localhost", db_name


def bench_dir():
	return Path(os.environ.get("SELLOS_BENCH_DIR") or Path.home() / "iespl-bench")


def _run_frappe(args, extra_env=None):
	"""Run a Frappe site command with the provisioner password in the child's environment only."""
	password = get_provisioner_password()
	env = child_env(password)
	env.update(extra_env or {})
	bench = bench_dir()
	command = [str(bench / "env" / "bin" / "python"), "-c", LAUNCHER, *args]
	try:
		result = subprocess.run(
			command, cwd=bench / "sites", env=env, capture_output=True, text=True, check=False
		)
	except OSError:
		raise TenantSiteError(f"Frappe's command for {args[0]} {args[1]} could not be started.") from None
	output = (result.stdout + result.stderr).replace(password, "[provisioner password]")
	for value in (extra_env or {}).values():
		if value:
			output = output.replace(value, "[admin password]")
	if output.strip():
		print(output.rstrip("\n"))
	if result.returncode != 0:
		raise TenantSiteError(f"{args[0]} {args[1]} failed with exit code {result.returncode}.")


def create(tenant_id):
	site, db_name = names(tenant_id)
	admin = secrets.token_urlsafe(24)
	_run_frappe(
		["new-site", site, "--db-name", db_name, "--db-root-username", provisioner_user()],
		{ADMIN_ENV: admin},
	)
	return site


def drop(tenant_id):
	site, _ = names(tenant_id)
	_run_frappe(["drop-site", site, "--db-root-username", provisioner_user(), "--no-backup"])
	return site


def list_sites():
	sites = bench_dir() / "sites"
	pattern = re.compile(rf"^{PREFIX}[a-z0-9]+\.localhost$")
	return (
		sorted(p.name for p in sites.iterdir() if p.is_dir() and pattern.match(p.name))
		if sites.is_dir()
		else []
	)


def probe():
	"""Create sellos_tenant_probe.localhost and drop it again, the drop even when the create fails."""
	try:
		create(PROBE_ID)
	finally:
		drop(PROBE_ID)
	return names(PROBE_ID)[0]


USAGE = "usage: tenant_sites create <id> | drop <id> | list | probe"


def main(argv=None):
	argv = sys.argv[1:] if argv is None else argv
	if not argv or argv[0] not in ("create", "drop", "list", "probe"):
		print(USAGE, file=sys.stderr)
		return 2
	command, rest = argv[0], argv[1:]
	try:
		if command in ("create", "drop"):
			if len(rest) != 1:
				print(USAGE, file=sys.stderr)
				return 2
			site = create(rest[0]) if command == "create" else drop(rest[0])
			print(f"{'Created' if command == 'create' else 'Dropped'} {site}")
		elif command == "list":
			for site in list_sites():
				print(site)
		else:
			print(f"Probe passed: created and dropped {probe()}")
	except TenantNameError as e:
		print(str(e), file=sys.stderr)
		return 2
	except ProvisionerPasswordMissing as e:
		print(str(e), file=sys.stderr)
		return 3
	except TenantSiteError as e:
		print(str(e), file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
