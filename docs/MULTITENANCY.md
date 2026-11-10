# Multitenancy on the local bench (SOS-P0-06L)

Every company is its own site and its own database. On the local bench `~/iespl-bench` the test
suite makes company sites, proves that two companies' data never mix, and drops them again.

## How tenant sites are made and dropped

* **Names.** A tenant id matches `[a-z0-9]+`. The site is `sellos_tenant_<id>.localhost` and the
  database is `sellos_tenant_<id>`, at most 64 characters (MariaDB's limit).
  `sellos.provisioning.tenant_sites.names(tenant_id)` is the one function that validates an id and
  gives both names. Every path that creates, drops or touches a tenant site calls it first. It refuses
  anything else, for example `test_site`, `sellos_test.localhost`, `sellos_tenant_A.localhost` or
  `../sellos_tenant_a.localhost`, before any command runs.
* **Account.** Sites are made with the MariaDB provisioner account, never with root. Its name is in
  `SELLOS_DB_PROVISIONER_USER` (default `sellos_provisioner`). It has `CREATE USER`, `RELOAD` and
  `SHOW DATABASES` globally and `ALL PRIVILEGES ... WITH GRANT OPTION` on `` `sellos\_tenant\_%`.* ``
  and on `` `sellos_tenant_%`.* `` only. Frappe's new-site runs `GRANT ALL ON sellos_tenant_<id>.*`, and MariaDB refuses it (1044) when the grant option comes only from the escaped pattern, while `CREATE DATABASE` still works (tested 10 November 2026, SOS-SETUP-24). Its password comes only from `get_provisioner_password()` in
  `sellos/provisioning/credentials.py` and reaches Frappe only through a child process's environment.
* **Command.** `scripts/tenant-site.sh create <id> | drop <id> | list | probe` (or the same functions in
  `sellos/provisioning/tenant_sites.py`) run Frappe's own command entry from `~/iespl-bench/sites`:
  `python -m frappe.utils.bench_helper frappe new-site <site> --db-name <name> --db-root-username <user>`
  and `drop-site <site> --db-root-username <user> --no-backup`. A short launcher adds the password
  to its argument list in memory, so it is never on a visible command line. The `bench` wrapper is
  not used. A failure names only the site and the exit code.
* **Probe.** `scripts/tenant-site.sh probe` creates and drops `sellos_tenant_probe.localhost`. It is the
  first backend test (`sellos/provisioning/test_tenant_multitenancy.py`).

## What is tested, and where

* **In process, not over HTTP.** A test creates two tenant sites, switches to each with
  `frappe.init(site=...)` and `frappe.connect()`, and checks that each sees only its own records and
  has its own `db_name`. It switches back to `sellos_test.localhost` in a `finally` block. No server
  is started for a tenant site and no HTTP request is sent to one.
* **Cleanup.** Every tenant site a test makes is dropped by the same validated code, database
  included, even when the test fails.
* **No password on disk.** After a create and a drop the password is in no file under the repository,
  the tenant site folders, the bench logs or the gate's log folder. The gate checks the same
  (`scripts/check_no_secret_leak.py`), and `scripts/check_site_set.py` fails a run that touched another
  site or database of the bench, left a tenant site or database behind, or gave a tenant site a
  `db_name` that is not `sellos_tenant_<id>`.

## Serving

The SellOS server stays pinned to `sellos_test.localhost` on port 8004:
`cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`. `bench serve` is never run
without `--site`, because it falls back to `default_site`, which is BuildOS's. Serving several company
sites from one server by host name is production routing. It belongs to SOS-P0-08 and cannot be
tested on this bench.

## The test site script (SOS-P0-11)

`scripts/test-site.sh up <id> | down <id> | run <id>` (module `sellos.provisioning.site_script`) makes
`sellos_tenant_<id>.localhost` from nothing: it creates the site with `tenant_sites.create`, runs
`install-app sellos`, seeds the Company Admin test user from `sellos.testing.users` and reads the site
back (database, apps, admin and role). `down` drops the site and database. `run` does both and drops
the site even when `up` fails. The agreed time for a run is 180 seconds (two runs took about 45 each on
this bench); over it the script exits 4. Exit 2 is a bad id and 3 a missing provisioner password.

## The control site (SOS-P1-01)

The control site is one more site of the same app, kept by the Platform Admin. Its `site_config.json` has
`"sellos_control_site": 1`. It holds the Tenant, Plan and Provisioning Job records, and nothing of any
company's data. The statuses and the allowed order are in `sellos/provisioning/status.py`, and who may open
the site is in `sellos/provisioning/control.py` (see `docs/permissions.md`). Creating a Tenant also creates its
Requested Provisioning Job, which the worker of SOS-P1-02 picks up (see below).

## The provisioning worker (SOS-P1-02)

`scripts/provisioning-worker.sh <control site> [--once]` (module `sellos.provisioning.worker`) is its own
process. The web process has no shell access: it only writes a Tenant and its Requested Provisioning Job, no
method of the worker is whitelisted, and no code outside `sellos/provisioning` imports `subprocess`
(`test_p1_02_worker.py` checks all three). The worker, on the control site:

1. claims a job: a Requested one, a Failed one with attempts left (after 30 seconds), or a Provisioning one
   whose worker died (no write for 10 minutes). The claim is one conditional update, so two workers never
   take the same job;
2. creates the site and database with `tenant_sites.create` (provisioner account, never root, name checked
   by `names` first) and installs SellOS with `site_script`;
3. runs `tenant_setup.configure` on the new site: roles, company name, the Company Admin user, and the
   plan limits in the site's `site_config.json` under `sellos_limits` (`plan`, `max_users`; the tiers
   themselves arrive with P6.02);
4. runs `tenant_setup.make_login_link` and queues the admin's email from the control site: the site
   address and a one time link to set a password. The control site therefore needs a default outgoing
   email account. The address comes from `sellos_tenant_url_template` in the control site's
   `site_config.json` (default `http://{site}:8004`, production `https://{tenant_id}.sellos.interactivesoftwares.com`);
5. marks the job and the tenant Active.

The job's `step` records how far it got and each write to the job is committed, which is the heartbeat. A
retry of a site that is only missing its email sends only the email. Any other retry drops the half made
site first. After 3 attempts the job stays Failed with its log, which the Platform Admin reads on the
Provisioning Job. The log holds messages only: the provisioner password is removed from every child's
output before the worker sees it, and the worker never reads it.
