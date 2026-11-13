# Continuous integration (SOS-P0-07)

Two workflows run on every pull request and on every push to `1.0`.

* `CI` (`.github/workflows/ci.yml`): jobs `Frontend` (npm ci and build), `Server` (bench install, web app build, backend tests) and `UI` (Cypress). GitHub shows each job's run time and the total on the run page.
* Runner minutes (SOS-SETUP-28). CI minutes are a budget. Each CI job ends with a summary line
  giving the runner minutes it used (wall time rounded up to whole minutes, as GitHub bills it), and
  the last job, `Runner minutes`, writes "runner minutes for this push: N" over every workflow run on
  the commit, Linters included. `scripts/lib/ci_minutes.py` counts them. A red run whose jobs never
  ran a step (a spent budget or a billing problem) is named as such in the loop's stop notice.
* Speed (SOS-SETUP-28). The `Server` and `UI` jobs cache the bench (the Frappe clone, the Python
  environment and node_modules) under a key made of the exact Python version, `pyproject.toml` and
  the ISO week. The app and the sites are never cached. The `Server` job makes one tenant site with
  the full install, dumps it (`sellos.tests.tenant_template`), and the tests build every other tenant
  site from that dump with `bench new-site --source-sql`. Exactly one real provisioning test,
  `test_plan_limits_are_applied_on_the_site`, still uses the full install on every run.
* `Linters` (`.github/workflows/linter.yml`): `scripts/check-guards.sh --all`, the gate's first step (pre-commit with ruff, prettier, eslint and gitleaks, Semgrep with the Frappe rules at the pinned version, and the code guards), and pip-audit. GitHub shows each job's run time.
* One CI (SOS-SETUP-33). Every CI step that can be the gate's step runs the gate's own script. `docs/CI_DIFFERENCES.md` lists what still differs and why. `scripts/ci-rehearsal.sh` runs CI's steps on a fresh clone of the last commit before a push.

## Blocking a merge

A failing job turns its check red. Whether red blocks the merge is a GitHub setting, not a file in the repository. Jayman sets it once, in Settings, Branches, branch protection rule for `1.0`:

1. Require a pull request before merging, with one approval.
2. Require status checks to pass before merging, and select `Frontend`, `Server`, `UI`, `Frappe Linter` and `Vulnerable Dependency Check`.
3. Require branches to be up to date before merging.
4. Do not allow bypassing the rules.

Until this rule is set, a failing check is reported but does not stop a merge. The build loop's own gate (`scripts/run-tests.sh`) runs before every push to `1.0`.
