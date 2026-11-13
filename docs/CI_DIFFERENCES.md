# Where the gate and CI still differ

The gate (`scripts/run-tests.sh`) and CI (`.github/workflows/ci.yml`, `linter.yml`) run the same
scripts wherever a step can be the same (SOS-SETUP-33):

| Step | One script, used by both |
| --- | --- |
| Guards: pre-commit, Semgrep, phone numbers, commands, secrets, ratchet, stale skips | `scripts/check-guards.sh --all` (gate first step, Linters job) |
| Semgrep version and Frappe rules commit | `scripts/lib/semgrep.env` (installed by `make-baseline.sh` and the Linters job; `--all` refuses others) |
| Web app build | `scripts/build-web-app.sh` (gate, Frontend, Server and UI jobs) |
| Migrate and prepare the clean site | `scripts/lib/prepare_test_site.sh` (gate, Server and UI jobs) |
| Tenant template | `python -m sellos.tests.tenant_template make` (gate, Server job) |
| Backend suite, batch report, 1020/deadlock rerun | `run_backend` in `scripts/lib/db_conflict.sh` (gate sources it; Server job runs `scripts/lib/backend_suite.sh`) |
| Cypress suite and the flaky policy | `scripts/lib/ui_flaky.sh` (gate, UI job) |
| Frappe branch, Python minor, Node major | checked by `scripts/check_ci_parity.py` in the gate's preflight |

`scripts/ci-rehearsal.sh` runs CI's steps on a fresh clone of the last commit, so a file that is
untracked or built only locally shows up before the push. It runs the Linters job, the Frontend job, the parity check, and a check that every script the workflows call is committed and parses. It does
not run the Server and UI test runs (difference 1).

## Removed by SOS-SETUP-33

* Lint and Semgrep were two copies of the commands (the gate's own block, and `pre-commit/action`
  plus `semgrep ci` in CI). There is now one script.
* Semgrep floated in CI (`pip install semgrep`, the rules' latest commit) and was fixed locally.
  Both are now pinned in one file.
* The web app was built three ways (the gate's inline npm, the Frontend job's, the UI job's subshell). There is now one script.
* The Server job ran the backend suite on a fresh install without `prepare_clean_site`, which the
  gate always runs first. It now prepares the site with the gate's script.
* The Server job had no 1020 or deadlock rerun, so a race with the database could turn CI red where
  the gate would rerun the module. It now runs the gate's `run_backend`.
* The UI job had its own copy of the migrate and prepare commands. It now runs the gate's script.

## What still differs, and why

| # | Difference | Gate | CI | Why it stays |
| --- | --- | --- | --- | --- |
| 1 | The bench | the shared `~/iespl-bench` on macOS, also used by BuildOS and Pamaa | a fresh Ubuntu bench, cached for a week (SOS-SETUP-28) | The shared bench may never be set up or changed by SellOS (CLAUDE.md, Shared bench), so a fresh bench cannot be built locally. The parity check keeps the Frappe branch, Python minor and Node major equal. The Python patch release can differ |
| 2 | The site's starting data | the clean baseline restored over `sellos_test.localhost`, then migrated and prepared | `bench new-site test_site` and `install-app`, then migrated and prepared | The restore takes seconds and a fresh install takes minutes per run. CI is the check that a fresh install works (DEV_STRATEGY row 11) |
| 3 | The server the UI tests use | the SellOS server on port 8004, pinned to `sellos_test.localhost` (a LaunchAgent, `scripts/install-launch-agent.sh`) | `bench start` on port 8000, host `test_site` | The port rule: 8000 is BuildOS's on this machine. CI is its own machine |
| 4 | Background workers | the bench's shared worker and scheduler run | the UI job removes `watch` and `schedule` from the Procfile; the Server job runs no worker | A test never relies on a real background job (CLAUDE.md, Test rules), so neither setup may decide a result |
| 5 | The MariaDB provisioner | the real account, its password from the Keychain | made with root in the job's own MariaDB, with a fresh password each run | CI has no Keychain and a throwaway database server. The grants are the same and are tested (`test_ci_workflows.py`) |
| 6 | Changed tests first, five, three or two times by speed (SOS-SETUP-34) | yes (`scripts/lib/flake_check.sh`) | no, CI runs each suite once | The gate has already run them up to five times before the push, and repeat runs of every changed test would multiply CI minutes, which are a budget (row 32) |
| 7 | Task guards: gate files and task evidence | yes, from the task the loop sets | skipped (no task) | CI has no task block. The gate always runs them before a task's commit exists |
| 8 | End-of-run checks: sites touched, secret leaks in logs, bench files and transcripts | yes | no | They check the shared bench and the agent's transcripts, which CI does not have. CI masks its one password |
| 9 | Vulnerable Dependency Check (pip-audit) | no | yes | It depends on advisories published that day. A new advisory would block an unrelated task in the gate. `scripts/ci-rehearsal.sh` runs it when pip-audit is installed |
| 10 | Order and stop | sequential, stops at the first failing step | four jobs in parallel, each to its end | GitHub's job model. The loop waits for every CI job (row 16) |
| 11 | The flaky log | `~/iespl-baseline/sellos-flaky.log` | the Actions cache, keys `sellos-flaky-*` | Each machine keeps its own count. The policy and its limits are the same script and values |
| 12 | Database server tuning | the bench's MariaDB as configured | the UI job's MariaDB on tmpfs with `innodb_flush_log_at_trx_commit = 0` | Speed only. No test may depend on durability timing (Test rules: wait on conditions) |
