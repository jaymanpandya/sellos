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
  only. Its password comes only from `get_provisioner_password()` in
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
