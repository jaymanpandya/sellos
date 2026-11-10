# Continuous integration (SOS-P0-07)

Two workflows run on every pull request and on every push to `1.0`.

* `CI` (`.github/workflows/ci.yml`): jobs `Frontend` (npm ci and build), `Server` (bench install, web app build, backend tests) and `UI` (Cypress). GitHub shows each job's run time and the total on the run page.
* `Linters` (`.github/workflows/linter.yml`): pre-commit (ruff, prettier, eslint, gitleaks), Semgrep with the Frappe rules, and pip-audit. GitHub shows each job's run time.

## Blocking a merge

A failing job turns its check red. Whether red blocks the merge is a GitHub setting, not a file in the repository. Jayman sets it once, in Settings, Branches, branch protection rule for `1.0`:

1. Require a pull request before merging, with one approval.
2. Require status checks to pass before merging, and select `Frontend`, `Server`, `UI`, `Frappe Linter` and `Vulnerable Dependency Check`.
3. Require branches to be up to date before merging.
4. Do not allow bypassing the rules.

Until this rule is set, a failing check is reported but does not stop a merge. The build loop's own gate (`scripts/run-tests.sh`) runs before every push to `1.0`.
