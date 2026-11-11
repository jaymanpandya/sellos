"""The tenant template dump for test runs (SOS-SETUP-28).

A tenant site costs about 23 seconds to make with a full install, and CI's Server job made about
fourteen, most of its run time. CI now makes one site with the real install once per job, dumps its
database and drops it:

    cd <bench>/sites && ../env/bin/python -m sellos.tests.tenant_template make <out.sql>

and sets SELLOS_TENANT_TEMPLATE_SQL to the dump for the test step. sellos.provisioning.tenant_sites
then builds every tenant site from it (bench new-site --source-sql), except inside full_install(),
which exactly one real provisioning test uses, so the real install path is covered on every run.

The dump is made with the MariaDB provisioner account, never root, and its password reaches
mariadb-dump only through the child's environment (MYSQL_PWD).
"""

import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from sellos.provisioning import tenant_sites
from sellos.provisioning.credentials import get_provisioner_password, provisioner_user

TEMPLATE_ID = "template"


@contextmanager
def full_install():
	"""Build tenant sites with Frappe's real install inside this block, whatever the run set."""
	saved = os.environ.pop(tenant_sites.TEMPLATE_ENV, None)
	try:
		yield
	finally:
		if saved is not None:
			os.environ[tenant_sites.TEMPLATE_ENV] = saved


def template_in_use():
	return bool(os.environ.get(tenant_sites.TEMPLATE_ENV))


def _db_address(site):
	"""(host, port) the site's database is at, from the bench's and the site's config."""
	sites = tenant_sites.bench_dir() / "sites"
	conf = {}
	for path in (sites / "common_site_config.json", sites / site / "site_config.json"):
		if path.is_file():
			conf.update(json.loads(path.read_text(encoding="utf-8")))
	return str(conf.get("db_host") or "127.0.0.1"), str(conf.get("db_port") or 3306)


def _dump_once(db_name, host, port, out):
	"""Run mariadb-dump. Returns an error message instead of raising, so no frame that raises holds
	the password (Frappe's test runner prints frame locals under a traceback, SOS-SETUP-24)."""
	tool = shutil.which("mariadb-dump") or shutil.which("mysqldump")
	if not tool:
		return "Neither mariadb-dump nor mysqldump is on PATH."
	env = dict(os.environ)
	env["MYSQL_PWD"] = get_provisioner_password()
	command = [tool, "-h", host, "-P", port, "-u", provisioner_user()]
	command += ["--single-transaction", "--no-tablespaces", "--skip-triggers", db_name]
	with open(out, "w", encoding="utf-8") as f:
		result = subprocess.run(command, stdout=f, stderr=subprocess.PIPE, text=True, env=env, check=False)
	if result.returncode != 0:
		return (
			f"{Path(tool).name} {db_name} failed with exit code {result.returncode}: {result.stderr.strip()}"
		)
	return None


def make(out):
	"""Make the template site with a full install, dump its database to <out>, and drop the site."""
	out = Path(out).resolve()
	out.parent.mkdir(parents=True, exist_ok=True)
	site, db_name = tenant_sites.names(TEMPLATE_ID)
	with full_install():
		if site in tenant_sites.list_sites():
			tenant_sites.drop(TEMPLATE_ID)
		tenant_sites.create(TEMPLATE_ID)
		try:
			error = _dump_once(db_name, *_db_address(site), out)
		finally:
			tenant_sites.drop(TEMPLATE_ID)
	if error:
		raise tenant_sites.TenantSiteError(error)
	if "tabDefaultValue" not in out.read_text(encoding="utf-8"):
		raise tenant_sites.TenantSiteError(f"{out} holds no Frappe tables.")
	return out


def main(argv=None):
	argv = sys.argv[1:] if argv is None else argv
	if len(argv) != 2 or argv[0] != "make":
		print("usage: python -m sellos.tests.tenant_template make <out.sql>", file=sys.stderr)
		return 2
	print(f"Tenant template written to {make(argv[1])}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
