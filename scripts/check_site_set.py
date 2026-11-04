#!/usr/bin/env python3
"""Fails when a gate run touched a site that is not SellOS's to touch (SOS-SETUP-17).

Usage:
  check_site_set.py snapshot <BENCH_DIR> <SNAPSHOT_FILE>
  check_site_set.py compare  <BENCH_DIR> <SNAPSHOT_FILE>

The bench at ~/iespl-bench holds BuildOS's and Pamaa's sites beside SellOS's. A gate run may touch
only the gate's own site (sellos_test.localhost) and the test tenant sites, which are always named
sellos_tenant_<id>.localhost (SOS-P0-06L). The gate takes a snapshot in its preflight and compares at
the end. The compare fails when:

* a site folder that is not one of those appeared or disappeared,
* the site_config.json of any other site changed,
* a tenant site that did not exist at the snapshot is still there (a test must drop what it makes),
* a tenant site's db_name is not sellos_tenant_<id> for the same <id> as its site name (SOS-SETUP-18).

SOS-SETUP-18: when SELLOS_DB_PROVISIONER_PASSWORD is set, it also lists the MariaDB databases with
the provisioner account (SHOW DATABASES, the password passed through MYSQL_PWD in the environment,
never on a command line), and the compare fails when:

* a database that is not sellos_tenant_<id> appeared or disappeared,
* a sellos_tenant_<id> database this run made is still there.

A snapshot that cannot list the databases with the account exits 3, an environment problem. With no
password set, the databases are not checked and it says so. The tenant code itself must still
refuse any other name before it runs a command (SOS-P0-06L). Tests point SELLOS_CHECK_DATABASES_FILE
at a file with one database name per line instead of a server.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TENANT_SITE = re.compile(r"^sellos_tenant_[a-z0-9_]+\.localhost$")
TENANT_DB = re.compile(r"^sellos_tenant_[a-z0-9_]+$")
# MariaDB's limit on a database name.
MAX_DB_NAME = 64
GATE_SITES = {"sellos_test", "sellos_test.localhost"}


class DatabaseListError(Exception):
	pass


def is_tenant(name):
	return bool(TENANT_SITE.match(name))


def ours(name):
	return name in GATE_SITES or is_tenant(name)


def sites(bench):
	"""{site name: sha256 of its site_config.json} for every site folder of the bench."""
	root = Path(bench) / "sites"
	found = {}
	for path in sorted(root.iterdir()) if root.is_dir() else []:
		config = path / "site_config.json"
		if path.is_dir() and config.is_file():
			found[path.name] = hashlib.sha256(config.read_bytes()).hexdigest()
	return found


def tenant_db_problems(bench, after):
	"""A tenant site whose db_name is not sellos_tenant_<id> for its own <id>."""
	out = []
	for name in sorted(after):
		if not is_tenant(name):
			continue
		expected = name.removesuffix(".localhost")
		try:
			conf = json.loads((Path(bench) / "sites" / name / "site_config.json").read_text(encoding="utf-8"))
		except (OSError, ValueError):
			conf = {}
		db_name = conf.get("db_name")
		if db_name != expected or not TENANT_DB.match(db_name) or len(db_name) > MAX_DB_NAME:
			out.append(
				f"{name} has db_name '{db_name}'. A tenant site's database is named {expected} "
				f"(sellos_tenant_<id>, at most {MAX_DB_NAME} characters)."
			)
	return out


def databases(bench):
	"""The sorted database names, or None when SELLOS_DB_PROVISIONER_PASSWORD is not set."""
	fake = os.environ.get("SELLOS_CHECK_DATABASES_FILE")
	if fake:
		return sorted(
			line.strip() for line in Path(fake).read_text(encoding="utf-8").splitlines() if line.strip()
		)
	password = os.environ.get("SELLOS_DB_PROVISIONER_PASSWORD", "")
	if not password:
		return None
	user = os.environ.get("SELLOS_DB_PROVISIONER_USER") or "sellos_provisioner"
	try:
		common = json.loads((Path(bench) / "sites" / "common_site_config.json").read_text(encoding="utf-8"))
	except (OSError, ValueError):
		common = {}
	host = str(common.get("db_host") or "127.0.0.1")
	port = str(common.get("db_port") or 3306)
	cmd = [
		"mariadb",
		"-h",
		host,
		"-P",
		port,
		"-u",
		user,
		"--batch",
		"--skip-column-names",
		"-e",
		"SHOW DATABASES",
	]
	try:
		result = subprocess.run(
			cmd, capture_output=True, text=True, timeout=30, env={**os.environ, "MYSQL_PWD": password}
		)
	except (OSError, subprocess.TimeoutExpired) as e:
		raise DatabaseListError(f"could not run the mariadb client: {type(e).__name__}") from None
	if result.returncode != 0:
		# The client's message names the user and host, never the password.
		raise DatabaseListError(result.stderr.strip().replace(password, "[provisioner password]")[:500])
	return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def database_problems(before, after):
	out = []
	if before is None or after is None:
		return out
	for name in sorted(set(before) | set(after)):
		if TENANT_DB.match(name):
			if name in after and name not in before:
				out.append(
					f"Database {name} was created by this run and is still there. Drop it in the test."
				)
			continue
		if name not in after:
			out.append(f"Database {name} was removed. Only sellos_tenant_<id> databases may be dropped.")
		elif name not in before:
			out.append(f"Database {name} was created. Tenant databases are named sellos_tenant_<id>.")
	return out


def problems(before, after):
	out = []
	for name in sorted(set(before) | set(after)):
		if ours(name):
			if is_tenant(name) and name in after and name not in before:
				out.append(f"{name} was created by this run and is still there. Drop it in the test.")
			continue
		if name not in after:
			out.append(
				f"{name} was removed. Only sellos_test.localhost and sellos_tenant_<id>.localhost may be touched."
			)
		elif name not in before:
			out.append(f"{name} was created. Test tenant sites are named sellos_tenant_<id>.localhost.")
		elif before[name] != after[name]:
			out.append(f"{name}/site_config.json changed. It is not a SellOS test site.")
	return out


def main(argv):
	if len(argv) != 3 or argv[0] not in ("snapshot", "compare"):
		print(__doc__.split("\n\n")[1])
		return 2
	action, bench, snapshot = argv
	try:
		dbs = databases(bench)
	except DatabaseListError as e:
		print(f"The provisioner account cannot list the databases: {e}")
		print("Check SELLOS_DB_PROVISIONER_USER and SELLOS_DB_PROVISIONER_PASSWORD (docs/DEV_STRATEGY.md).")
		return 3
	if action == "snapshot":
		state = {"sites": sites(bench), "databases": dbs}
		Path(snapshot).write_text(json.dumps(state, indent=1), encoding="utf-8")
		if dbs is None:
			print(
				"Databases: SELLOS_DB_PROVISIONER_PASSWORD is not set, so databases are not checked this run."
			)
		return 0
	state = json.loads(Path(snapshot).read_text(encoding="utf-8"))
	after = sites(bench)
	found = problems(state["sites"], after) + tenant_db_problems(bench, after)
	found += database_problems(state.get("databases"), dbs)
	if found:
		print(
			"This run touched sites or databases that are not SellOS test ones, or left tenant ones behind:"
		)
		for line in found:
			print(f"  {line}")
		return 1
	print("Sites: only sellos_test.localhost and test tenant sites were touched, and no tenant was left.")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
