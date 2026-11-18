# Deployment (SOS-P0-08)

Code: `sellos/provisioning/deploy.py`. Commands: `deploy/deploy.sh`, `deploy/promote.sh`, `deploy/upgrade.sh`.
Running them on staging is SOS-P0-08D (AMP Labs). The build loop only runs `--dry-run` and the local
tenant-site tests.

## Commands

* `deploy/deploy.sh <tag> [--dry-run]` puts a release tag (`v1.2.3`, or `v1.2.3-rc1`) on staging.
* `deploy/promote.sh <tag> [--dry-run]` puts the same tag on production. Its first step checks the tag is
  the one checked out on staging.
* `--dry-run` prints every step as a line starting with `+ ` for staging and for production, and reaches
  no server. A real run needs `SELLOS_STAGING_HOST` or `SELLOS_PRODUCTION_HOST` (`user@host`) in the
  environment, and `SELLOS_REMOTE_BENCH_DIR` if the bench is not `~/sellos-bench`. It runs the steps over
  ssh in order and stops at the first one that fails.
* Steps: record the current tag, fetch tags, check out the tag, install requirements, build, rolling
  upgrade, restart.
* `deploy/upgrade.sh [--dry-run] [--backup] (--all-sites | --site SITE ...)` is the rolling upgrade. It backs
  up (with `--backup`) and migrates the sites one at a time, in order. At the first failure it stops, prints
  `FAILED <site>: <reason>`, lists the sites it left untouched and exits 1. Sites after the failed one are
  not backed up, migrated or changed.

## Rollback

1. Find the failed site in the upgrade output, and the previous tag in the first step's output
   (`Record the tag now deployed`).
2. Sites before the failed one are migrated. Sites after it are still on the old schema.
3. Put the old code back on the server: `git -C apps/sellos checkout --detach <previous tag>`,
   `bench build --app sellos`, `bench restart`.
4. Restore every migrated site and the failed one from the backup the upgrade made just before its
   migration (`bench --site <site> restore <backup file> --db-root-username <provisioner>`; backups are in
   `sites/<site>/private/backups`). The code is older than the schema, so a site must be restored, not left.
5. Run `deploy/upgrade.sh --backup --all-sites` on the old tag to confirm every site migrates, then run
   the smoke test of staging.
6. Fix the failing migration in a new tag. Never edit a tag that has been deployed.
