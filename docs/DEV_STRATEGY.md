# How SellOS is built and tested

SellOS is built the way BuildOS is built, on the same bench, with the same tools and the same loop.
This file records what BuildOS does (read from its repository on 4 November 2026), what SellOS
copies from it and how each copy is adapted, and every place where SellOS is stricter and why. If a rule here and a habit
disagree, the rule wins. Gate files (see below) may only be changed by a human.

## 1. The environment is the BuildOS environment

| Thing | BuildOS | SellOS |
| --- | --- | --- |
| Bench | `~/iespl-bench` | the same bench, shared at the same time: the BuildOS and SellOS loops run together, and their gates take one lock only around the heavy segment (SOS-SETUP-20) |
| Runtime | Python 3.14, Node 24, MariaDB 11.8, two Redis | the same |
| Test site | `test_site` | `sellos_test.localhost`, its own site on the same bench |
| Clean snapshot | `~/iespl-baseline/test_site_clean.sql.gz` | `~/iespl-baseline/sellos_test_clean.sql.gz` |
| Front end build | `npm ci` then `npm run build` | the same (package-lock.json, not yarn) |
| Unit tests | `bench --site test_site run-tests --app buildos` | `bench --site sellos_test.localhost run-tests --app sellos` |
| UI tests | Cypress through `bench --site test_site run-ui-tests buildos --headless` | the same command with `sellos` |
| UI fixtures | `buildos/tests/ui_fixtures.py` through `cy.bench` | `sellos/tests/ui_fixtures.py` through `cy.bench` |
| Server for UI tests | the running `bench start` on port 8000, site picked by its host name | the SellOS server on port 8004, pinned to `sellos_test.localhost`: `cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004` |
| Lint | pre-commit: ruff, prettier 2.7.1, eslint 8.44, pyupgrade | the same |
| CI | server job (fresh site, run-tests), Linters (Semgrep, pip-audit) | the same, plus a UI job |
| Who commits | the build loop, never the agent | the same |

The SellOS gate refuses to run against any site other than `sellos_test` or `sellos_test.localhost`,
because it restores the baseline over that site and wipes it.

Ports (Jayman's rule, always): BuildOS runs on port 8000, Pamaa on 8002, SellOS on 8004. Each
server is pinned to one site with `--site`. SellOS never uses 8000 or 8002, and never starts, stops
or touches the servers on them. `bench serve --port 8004` without `--site` falls back to
`default_site` and serves BuildOS's site for every host name, so it is never used. The SellOS server
is always started as `cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`. `scripts/make-baseline.sh` sets `webserver_port` 8004 on the site
it creates. CI is not affected: it runs on its own machine, on port 8000, and is not changed.

**Multitenancy on this bench (SOS-SETUP-18).** A pinned server serves its one site for every host
name, and an unpinned `bench serve` serves `default_site`, which is BuildOS's `test_site`. So the
SellOS server stays pinned to `sellos_test.localhost` on 8004, `bench serve` is never run without
`--site`, and no server is started for a tenant site. Multitenancy is tested in the test process:
tenant sites `sellos_tenant_<id>.localhost` with databases `sellos_tenant_<id>` are created and
dropped by code, a test switches between them with `frappe.init(site=...)` and `frappe.connect()`
and checks that two tenants' data never mix, then switches back to `sellos_test.localhost`. Over
HTTP only the pinned test site is tested. Routing requests to a company's site by host name is
production routing. It belongs to SOS-P0-08 and cannot be tested on this bench.

**The MariaDB provisioner account (SOS-SETUP-18).** Tenant sites are created and dropped with a
narrow account, never with root, and no SellOS script, task or test uses a MariaDB root password.
The account has `CREATE USER`, `RELOAD` and `SHOW DATABASES` globally, and
`ALL PRIVILEGES ... WITH GRANT OPTION` on `` `sellos\_tenant\_%`.* `` and on `` `sellos_tenant_%`.* `` only.
Both are needed: Frappe's new-site runs `GRANT ALL ON sellos_tenant_<id>.*`, and MariaDB refuses it (1044) when the grant option comes only from the escaped pattern, while `CREATE DATABASE` still works (tested 10 November 2026, SOS-SETUP-24). Its name is in
`SELLOS_DB_PROVISIONER_USER` (default `sellos_provisioner`). Its password (SOS-SETUP-22) comes only
from `get_provisioner_password()` in `sellos/provisioning/credentials.py`: the variable
`SELLOS_DB_PROVISIONER_PASSWORD` if set, otherwise the macOS login Keychain item `sellos_provisioner`,
stored once with `security add-generic-password -a "$USER" -s sellos_provisioner -w`. Tenant sites
are created, dropped, listed and probed only by `sellos/provisioning/tenant_sites.py` and its wrapper
`scripts/tenant-site.sh` (create <id>, drop <id>, list, probe; `<id>` is `[a-z0-9]+`, anything else
exits 2). They run Frappe's own command entry, `python -m frappe.utils.bench_helper frappe new-site
<site> --db-name <name> --db-root-username <user>`, from `~/iespl-bench/sites`, never the `bench`
wrapper, through a short launcher that takes the password from its environment and adds
`--db-root-password` to its own argument list in memory. So the password reaches bench only through
the child process's environment, never a visible command line (`ps`, `logs/bench.log`). CI makes the
same account in its own MariaDB service with a CI-only password in the variable.

The loop runs the agent through `sellos_agent_env` (`scripts/lib/db_secrets.sh`): every exported
variable whose name looks like a credential is removed, except `SELLOS_DB_PROVISIONER_USER` and the
ones `claude` needs to sign in. The password is removed too: the agent did not see it even when it
was passed (SOS-P0-06L stopped on 10 November 2026), so its code reads the Keychain instead, and the
agent is told never to run `security find-generic-password -w` or print the password. At its start
the loop checks for the Keychain item without reading it (`security find-generic-password -s
sellos_provisioner`, no `-w`) and exits 3 with the store command when neither it nor the variable
exists. It then loads the value into its own environment (and the gate does the same on a hand run),
before its output filter starts, so that `sellos_redact` and the leak check know it. The loop's output, every saved reply, every notification and
the gate's logs go through `sellos_redact`, which replaces both values. At the end of every gate run
`scripts/check_no_secret_leak.py` fails the run if the password is in the gate's log folder, the
bench's logs, `common_site_config.json`, a tenant or archived site folder, the repository or the
agent's session transcripts, and `scripts/check_site_set.py` lists the databases with the account
and fails a run that made or dropped any database but a `sellos_tenant_<id>` one, or left one behind.

## 2. The loop (copied from BuildOS)

`scripts/build-loop.sh` runs one task at a time. For each task it:

1. Checks for the regression pause file `/tmp/sellos-loop.pause` (section 8). If it exists, it picks
   nothing, notifies "Paused for regression" and stops. Otherwise it picks the next task from
   TASKS.md (`select-next-task.sh` and `lib/tasks.py`): resume an In Progress one, else, among the Not
   Started tasks whose dependencies are all satisfied (Complete or Not Needed), the one in the
   earliest Launch tier (Dec 20, then Jan 1), and within a tier the first in file order. Priority no
   longer orders the pick (SOS-SETUP-19). A Not Needed task is never picked or reported. If anything
   is Blocked, nothing new starts.
2. Marks it In Progress and commits that, and records the commit it started from.
3. Calls `claude -p` once with the task in the prompt. The agent edits files and runs only its own
   single test module and single spec, in the foreground. It never commits, pushes, resets,
   stashes, rebases, merges or changes a status.
4. Runs the real gate, `scripts/run-tests.sh`.
5. If the gate fails, hands the failure output back to the agent to repair, up to 3 gate runs in all
   (`SELLOS_MAX_GATE_RUNS`). The repair rules forbid deleting or weakening an assertion.
6. If the gate passes: marks the task Complete, commits with the subject `<TASK ID>: <task title>`
   and the agent's summary as the body (at most 20 lines, SOS-SETUP-22), pushes, and notifies
   `<TASK ID> complete: <title>`. If it still fails after the last
   repair: saves the attempt on a `failed/<task>-<time>` branch, hard resets the branch to the
   commit it started from, marks the task Blocked, notifies, and stops. No broken code ever stays
   on the main branch.
7. Stops on Blocked, NEEDS_INPUT (a question the agent cannot settle, never a milestone), a crashed agent, a regression pause or no eligible task. A Blocked task is never
   resumed by itself. A human finds the cause, checks it by hand in a browser, and resets it to
   Not Started.

Copied from `../buildos/scripts` and adapted. Only `select-next-task.sh` is unchanged. Python files
were also reformatted to the SellOS ruff style (tabs, one statement per line), which changes no
behaviour.

* `lib/tasks.py`: the task ID pattern is the same as BuildOS's. What differs is the SellOS name in
  the docstring, priorities that run P0 to P6 (BuildOS stops at P2), an `Owner` field that is read
  from each task, the `Launch` tier that orders the pick, the `Not Needed` status that satisfies a
  dependency and is never picked or reported, the `order` command that lists the pick order, and the
  `waiting` command, a report of the Waiting tasks that hold up Not
  Started work, which the loop sends when nothing is eligible.
* `set-task-status.sh`: a SellOS task ID in the usage example.
* `limit_wait.py`: `SELLOS_LIMIT_WAIT_OVERRIDE` in place of `BUILDOS_LIMIT_WAIT_OVERRIDE`.
* `notify-telegram.sh`: the `SELLOS_TELEGRAM_*` variables and the SellOS name.
* `watchdog.sh`: the SellOS name in its message.
* `make-baseline.sh`, `run-tests.sh` and `build-loop.sh` change more, see sections 4 and 5.

## 3. Tasks

TASKS.md holds one block per task, in the BuildOS format that `lib/tasks.py` reads:

```
### SOS-P1-06: Lead, Client, Activity, Task and Site Visit records
- **Epic:** CRM
- **Description:** ...
- **Acceptance Criteria:**
  - ...
- **Priority:** P1
- **Launch:** Dec 20
- **Dependencies:** SOS-P1-04, SOS-P1-05
- **Status:** Not Started
- **Browser spec:** required
```

The ID may hold letters, digits, hyphens and underscores, never a dot. The old story P1.06 becomes
SOS-P1-06. Optional lines only a human writes: `- **Gate files:** allowed` and `- **Docs only:** yes`.

A task is done when all of these hold, and the gate checks each one:

* Its acceptance criteria are covered by tests that name the task ID (backend `test_*.py`, and a
  Cypress spec for anything a person sees or does).
* It adds assertions and removes none.
* Anything that holds personal data has the leak check in section 6.
* Lint and Semgrep are clean.
* The whole backend suite and the whole Cypress suite pass from the clean baseline.

## 4. The holes found in the BuildOS strategy, and how SellOS closes each

I read the strategy as a set of promises and asked how each one could fail without anyone noticing.
Each row says what BuildOS does, how it fails, and the SellOS fix. Row 1 and row 2 are not guesses:
on 4 November 2026 every CRM call on the SellOS test site answered 403, the Leads page showed "No
leads yet", and the whole gate was green.

| # | BuildOS today | How it fails | SellOS fix | Where it is enforced |
| --- | --- | --- | --- | --- |
| 1 | `cypress/support/e2e.js` ends with `Cypress.on("uncaught:exception", () => false)`, so every error the app throws is ignored | A page that breaks quietly passes any spec that checks the wrong thing | An uncaught error fails the spec. Only the two ResizeObserver wordings are ignored | `cypress/support/e2e.js` |
| 2 | A spec passes if its own assertions pass | An API call that answered 403 or 500, or a console error, never fails anything | After every test, any `/api/` answer of 400 or more, and any console error, fails the test unless the spec declared it with `cy.expectApiStatus` or `cy.expectConsoleError` | `cypress/support/e2e.js` |
| 3 | If the clean baseline file is missing the gate warns and carries on with whatever data is there | A result that cannot be repeated | Missing baseline stops the gate (exit 3). A human may allow one run with `SELLOS_ALLOW_NO_BASELINE` | `scripts/run-tests.sh` |
| 4 | The UI tests need `bench start` and the site at its own address, and say nothing if they are not there | Cypress times out with an unhelpful message | A preflight asks the site to answer first and says what is missing. The site's `webserver_port` (site config first, shared config second, as `frappe.get_conf` reads it) must be 8004 or the gate exits 2 | `scripts/run-tests.sh`, `scripts/prepare-regression.sh`, `scripts/lib/sellos_server.sh` |
| 5 | The agent can edit the gate, the Cypress config, the support file or CI in the same task | A failing test is "fixed" by changing what judges it | Those files are protected: `scripts/run-tests.sh`, `build-loop.sh`, `notify-telegram.sh`, `watchdog.sh`, `select-next-task.sh`, `set-task-status.sh`, `make-baseline.sh`, `prepare-regression.sh`, `pause-loop.sh`, `resume-loop.sh`, `refresh-buildos-reference.sh`, `install-shared-helpers.sh`, `scripts/shared/*`, `scripts/lib/*`, `scripts/check_*.py`, `cypress.config.js`, `cypress/support/e2e.js`, `.pre-commit-config.yaml`, `.semgrepignore`, `.eslintrc`, `.github/workflows/*`, `docs/DEV_STRATEGY.md`, `docs/TESTING.md` and `docs/regression/README.md`. `pyproject.toml` is not protected as a whole, because tasks add dependencies to it, but any change to its `[tool.ruff]` tables fails. `docs/regression/flows.md` is append only. A task changes any of these only if its block says `Gate files: allowed`, which only a human writes | `scripts/check_gate_files.py` |
| 6 | "Never weaken an assertion" is one sentence in a prompt | Nothing stops it | The number of assertions in every changed test file may not fall, and a test file may not be deleted | `scripts/check_assertion_ratchet.py` |
| 7 | A task can be marked Complete with no test that names it | Acceptance criteria nobody tests | A new or changed test that names the task ID and holds assertions is required. A task marked `Browser spec: required` also needs a Cypress spec | `scripts/check_task_evidence.py` |
| 8 | Lint and Semgrep are not in the gate, only in CI after the push | The commit lands, CI goes red afterwards. It happened three times on SellOS (ruff on PR 1, Semgrep twice on P0.07) | Pre-commit and Semgrep with the Frappe rules run inside the gate | `scripts/run-tests.sh` |
| | *Note on row 8:* BuildOS runs Semgrep (its Linters workflow) only on pull requests, and its loop pushes straight to the branch, so its direct pushes are never scanned | | | `.github/workflows/linter.yml` in BuildOS |
| 9 | A spec that fails and then passes alone is logged FLAKY and counts as a pass | A real race stays in the suite for good | The same spec flaky three times fails the gate until it is fixed | `scripts/run-tests.sh` |
| 10 | CI runs only the server tests | Browser behaviour is never checked on a clean machine | CI gets a UI job that provisions a fresh site and runs the Cypress suite (section 5) | `.github/workflows/ci.yml` |
| 11 | The gate migrates a long lived site | A fresh install is never exercised in a browser | The baseline is only a clean migrated install. The state a provisioned company site is in, and the role users, are made by code on every run: `run-tests.sh` runs `prepare_clean_site` right after the migrate and cache clear, before the changed tests, and CI builds a fresh site the same way | `scripts/run-tests.sh`, `sellos/tests/ui_fixtures.py` |
| 12 | The BuildOS gate and the SellOS gate share one bench | Two baseline restores, migrations and Cypress runs at once starve each other. Their data does not collide: Redis keys are namespaced per site and `bench clear-cache` is per site | Two loops share the heavy segment of the gate through one lock and are not serialised otherwise (SOS-SETUP-20). `~/iespl-baseline/bench-gate-lock.sh`, outside both repositories (installed from the canonical copy `scripts/shared/bench-gate-lock.sh` by `scripts/install-shared-helpers.sh`; the loop reinstalls it with a warning at start when the two differ, SOS-SETUP-21), holds the directory `/tmp/iespl-bench-heavy.lock.d` (owner, pid, start). The SellOS gate takes it from the baseline restore to the end of the Cypress run; lint, Semgrep, the task guards and the npm build stay outside it, and the wait is in the gate log. `prepare-regression.sh` takes it only for the restore and migrate. A waiter polls every 5 seconds, notifies once past 30 minutes and exits 3 after 90; a holder that is dead or older than 2 hours is stolen with a warning; release runs on EXIT, INT and TERM. The BuildOS gate takes the lock only once its own `run-tests.sh` sources the helper | `scripts/run-tests.sh`, `scripts/prepare-regression.sh`, `~/iespl-baseline/bench-gate-lock.sh`, `sellos/tests/test_bench_gate_lock.py` |
| 13 | The gate restores a baseline over its site | A wrong site name wipes real work | Only `sellos_test` and `sellos_test.localhost` are accepted | `scripts/run-tests.sh`, `scripts/make-baseline.sh` |
| 14 | Permission specs can pass because the user cannot read the record at all | A leak check that has nothing to find | A leak spec must first show the user can read the record on at least one path | `cypress/integration/security/` |
| 15 | Personal data leaks are found one at a time by a person | The change history held old and new values in BuildOS (BOS-282) | Every path in `cy.genericReads` is tried as every role for every DocType that holds personal data, for the current value and the replaced one. Reuse `buildos.security.field_history` | `cy.genericReads`, the security specs |
| 16 | After a push the loop starts the next task without looking at CI | A red CI sits unnoticed while new work piles on | After each push the loop waits for CI on that commit. If it is red the loop stops and notifies, and starts nothing new | `scripts/build-loop.sh` |
| 17 | Test data is made by hand | An invalid or real phone number breaks a test or leaks into the repository | `sellos.tests.phones` makes valid numbers, and a test fails on any hand written one. The allowed list starts empty and stays empty | `sellos/tests/test_no_raw_phone_numbers.py` |
| 18 | A human walks through the product by hand | Skipped when time is short | Regression is a scheduled pause, not a gate (SOS-SETUP-19). SOS-REG-A, B, C and L are Waiting tasks on fixed dates. `scripts/pause-loop.sh` stops the loop before its next pick, Claude in chat walks every flow in `docs/regression/flows.md` in a browser and writes a report, and `scripts/resume-loop.sh` lets it go on. A task marked `Browser spec: required` fails the gate unless it adds its flows (section 8) | `TASKS.md`, `scripts/build-loop.sh`, `scripts/pause-loop.sh`, `scripts/resume-loop.sh`, `scripts/check_task_evidence.py`, `docs/regression/` |
| 19 | The loop runs one `git push` after a task passes and assumes it worked | A loop that cannot push leaves finished work unpushed, and the next tasks pile up on top of it | At start the loop checks `git ls-remote --exit-code origin HEAD` and stops before any task if the remote does not answer, and pushes first if the branch is ahead of origin. After a passing task the push is retried after 10, 30 and 90 seconds, and GitHub's "fatal error in commit_refs" is retried, not taken as a rejection. If every try fails the commit is kept, never reset, the exact git error is sent, and the loop stops. At start the loop also stops if `gh auth status` fails, and before pushing commits that are ahead it lists them, refuses any whose message does not start with `SOS-`, and waits for CI on the pushed head before picking a task. Git never prompts (`GIT_TERMINAL_PROMPT=0`, and SSH in batch mode with a 15 second timeout when origin is an SSH remote) | `scripts/build-loop.sh` |
| 20 | The gate ran its own Semgrep command: only the Frappe rules, with its own `--exclude` list, on every file in the folder | The gate can pass while CI fails, because the two scan different files with different rules. On 6b0fade the Linters run went red on three `open()` calls in `scripts/lib/tasks.py` | The gate runs exactly CI's command, `semgrep ci --config <frappe rules> --config r/python.lang.correctness`, and both read the same `.semgrepignore` at the repo root. Any new CI check is added to the gate in the same change | `scripts/run-tests.sh`, `.semgrepignore`, `.github/workflows/linter.yml` |
| 21 | The gate lints the files git tracks, and a task's new files are untracked until the loop commits them | CI checks every file in the commit, so a new file the gate never looked at fails CI after the push. On 8d9389a a new test file passed the local pre-commit run and failed ruff-format in the Linters run | Before anything else the gate runs `git ls-files --others --exclude-standard -z \| xargs -0 git add --intent-to-add`, so pre-commit, Semgrep, the three guards and the changed tests step all see new files, without staging their content. The loop's failure path still removes them | `scripts/run-tests.sh`, `sellos/tests/test_gate_untracked_files.py` |
| 22 | A preflight asks `/api/method/ping` and takes any answer as the right server | On 4 November 2026 the server on 8004 answered ping while serving BuildOS's site, because it was started without `--site` and fell back to `default_site` | A preflight must prove it is talking to the right app, not only that something answers. A guest GET of `/sellos` must answer 301 or 302, because only SellOS's page renderer redirects a guest. Anything else exits 3 and names the pinned start command | `scripts/lib/sellos_server.sh`, used by `scripts/run-tests.sh` and `scripts/prepare-regression.sh` |
| 23 | Every failed gate run is handed to the agent to repair, and the last one Blocks the task | A server that is down, on the wrong port or serving the wrong app fails every spec. The loop spends its repair runs having the agent "fix" code that is not broken, then resets the work and Blocks the task, so a dead server costs the task | An environment failure must never consume repair runs or Block a task. The gate exits 2 or 3 only from its preflight (a command that fails with its own 2 or 3 is reported as 1). On 2 or 3 the loop does not repair, reset, salvage or Block: the task stays In Progress, the working tree is left as it is, it notifies "Environment problem, not the task" with the gate's message, and stops. After every exit 1 it runs the gate's server preflight again (port, ping, guest `/sellos` redirect) before any repair run or Block, and when the failures were nothing but connection errors to the site it says so. A failed preflight is handled the same way. Restarting the loop resumes the task | `scripts/build-loop.sh`, `scripts/run-tests.sh`, `scripts/lib/sellos_server.sh` |
| 24 | The gate runs the whole Cypress suite, and a spec can be written before the task it checks | A contract spec for a later task fails every gate until then, so the task in front of it cannot pass. On 4 November 2026 `phone_masking_leaks.cy.js`, SOS-P1-06B's contract, failed SOS-P1-06A's gate | A contract spec for a future task is skipped (`context.skip`) with its task ID in a comment above the skip, and that task removes the skip and makes the spec pass. The gate fails a skip that names no task, a task that is Complete, or the task the gate is running for | `scripts/check_no_stale_skips.py` in `scripts/run-tests.sh` |
| 25 | The gate runs on the developer's bench, and CI builds its own bench from the workflow | The two drift apart and nothing says so. On 4 November 2026 every UI spec failed in CI in 0 ms and passed locally: CI's `bench init` named no Frappe branch and got Frappe develop, which has no `cypress/support`, so `cypress/support/e2e.js` could not import Frappe's commands. The local bench is on version-16 | Every `bench init` in `ci.yml` names `--frappe-branch version-16`. The gate's preflight compares the local bench with `ci.yml` (the Frappe branch, the Python minor version and the Node major version) and exits 3 on any difference, before any test runs | `scripts/check_ci_parity.py` in `scripts/run-tests.sh`, `.github/workflows/ci.yml` |
| 26 | The loop builds and deploys from one task graph | A deployment decision that is not made (SOS-N18, the DigitalOcean region and sizes) blocks every local task after it: SOS-P0-11 waited on SOS-P0-06, which waited on SOS-P0-04 and SOS-N18 | Building and deploying are separate tasks. SOS-P0-06L sets up multitenancy on the local bench, and SOS-P0-11 and SOS-P1-01 depend on it. SOS-P0-04, SOS-P0-05, SOS-P0-06, SOS-P0-08 and SOS-P0-12 wait for SOS-N18. Since SOS-SETUP-19 SOS-N18 is Not Needed (the region is DigitalOcean Bangalore), and SOS-P0-04 and SOS-P0-12 are AMP Labs work and Waiting, so SOS-P0-05, SOS-P0-06 and SOS-P0-08 wait for SOS-P0-04. Test tenant sites are named `sellos_tenant_<id>.localhost`, and the gate fails a run that touched any other site of the bench or left a tenant site behind | `TASKS.md`, `scripts/check_site_set.py` in `scripts/run-tests.sh` |
| 27 | A task needs a database secret that is not in the agent's environment, and the plan asks for root | On 4 November 2026 SOS-P0-06L stopped with NEEDS_INPUT: the root password variable it was told to read was not set in the shell that started the loop. The loop does not empty the environment and Claude Code does not drop variables by name, so the variable never existed there. Root would also let a test drop any company's database on this bench | Tenant sites are made with a narrow MariaDB account (`CREATE USER`, `RELOAD`, `SHOW DATABASES`, and everything on `sellos\_tenant\_%` only), never root. The loop hands the agent only `SELLOS_DB_PROVISIONER_USER` and strips every other credential variable; the password comes from `get_provisioner_password()` (the variable, else the Keychain) and reaches Frappe only through a child process's environment (SOS-SETUP-22). Their values are redacted from the loop's output, replies, notifications and gate logs, and the gate fails a run whose files hold the password or that touched a database outside `sellos_tenant_<id>` | `scripts/lib/db_secrets.sh` in `scripts/build-loop.sh`, `scripts/run-tests.sh` and `scripts/notify-telegram.sh`, `sellos/provisioning/`, `scripts/tenant-site.sh`, `scripts/check_no_secret_leak.py`, `scripts/check_site_set.py` |
| 28 | The gate and CI run `bench run-tests` and the step's result is read from its last summary line | A passing summary line does not prove the command passed; the exit code does. Frappe runs the integration tests and the other tests as two batches, each with its own `Ran N tests` and `OK` or `FAILED`. On 10 November 2026 CI run 42830839891 printed `Ran 238 tests ... OK (skipped=18)` last and the step exited 1: the first batch, 43 integration tests, had ended `FAILED (errors=3)` because the tenant tests looked for the bench at `~/iespl-bench` and CI's is `~/frappe-bench`. It was read as "the tests passed and something else failed". A filter that matches no test also runs nothing and exits 0 | Every backend test command in the gate and in CI runs through `scripts/lib/report_test_exit.sh`. It prints every batch's summary and the command's exit code, names each batch that failed (`FAILED (errors=3)  <- Running 43 integration tests for sellos`), prints `tests passed but the runner returned N` when every batch passed and the code is not 0, and fails a run that exits 0 having run no test. The exit code decides. Tenant sites are made on the bench Frappe runs from (`frappe.utils.get_bench_path()`), and `SELLOS_BENCH_DIR` overrides it | `scripts/lib/report_test_exit.sh` in `scripts/run-tests.sh` and `.github/workflows/ci.yml`, `sellos/tests/test_report_test_exit.py` |
| 29 | A secret is passed through ordinary local variables | Frappe's test runner prints every frame's local variables under a traceback. CI run 42830839891 printed the provisioner password and two tenant admin passwords in its log, from `_run_frappe` and its environment dict. On the local bench that password is the real one from the Keychain | The frame that raises a tenant site error holds no secret: `_run_frappe_once` holds the password and returns an error message, and `_run_frappe` raises it. The admin password is made inline, not kept in a variable. A test formats the traceback with its locals and checks that neither secret is in it | `sellos/provisioning/tenant_sites.py`, `sellos/tests/test_tenant_sites.py` (`BenchAndTraceback`) |
| 30 | Every failed gate run is a code failure, handed to the agent to repair | A timing race with the shared bench worker looks like a code failure and wastes repair runs. On 10 November 2026 SOS-P1-06A was Blocked by MariaDB 1020 ("Record has changed since last read in table tabcontact"): a User save queued a create_contact job, the worker ran it, and `ensure_test_users()` then saved the same Contact inside a transaction whose read view was older, which MariaDB 11.8's snapshot isolation refuses | The fixture never writes an existing Contact, makes a new user's Contact in the same transaction with no job queued, and retries a Contact write 3 times on `QueryDeadlockError`. Code inside the test runner uses `create_test_users()` only. The gate treats a 1020 or a deadlock as a retryable infrastructure error: it reruns only the failing module once, alone, and a second conflict prints "database conflict (1020), not a code failure" and exits 3, so the loop stops for the environment instead of repairing or Blocking | `sellos/testing/users.py`, `sellos/tests/ui_fixtures.py`, `scripts/lib/db_conflict.sh`, `scripts/lib/db_conflict.py`, `scripts/run-tests.sh` (tests: `test_contact_race.py`, `test_db_conflict_gate.py`) |

**A job that is expected to be red.** A red job proves nothing unless it is red for the right
reason. Whenever a job is allowed to stay red (the CI UI job until SOS-P1-06A, for one), write down
the exact log line it must fail on, next to the step in the workflow file, and after every run that
is accepted as "red as expected", find that line in the job's log. If the job stops anywhere else,
it is a new failure and is fixed now. On 4 November 2026 the UI job had been taken as "red until 06A"
while it was really stopping at `bench migrate` with "Service redis_cache is not running", before
it ever reached `prepare_clean_site`. The line the UI job must fail on is
`NotImplementedError: Call the provisioning code that makes this a company site.`

## 5. Changes to `build-loop.sh`

Copy BuildOS's `scripts/build-loop.sh` and change only these things. Do not retype the script.

1. Names: `BUILDOS_` becomes `SELLOS_`, `/tmp/buildos-*` becomes `/tmp/sellos-*`, the branch default
   is `1.0`, the task ID pattern in the awk is the one in `lib/tasks.py`, commit messages use the
   SellOS ID.
2. Paths in both prompts: `bench --site sellos_test.localhost run-tests --app sellos --module ...` and
   `bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/...`.
3. The locked architecture paragraph: no ERPNext, the web app never uses the Frappe desk, five roles,
   isolation by site, consent never blocks (section 9), the 022 number is for service and
   transactional calls, the product is called SellOS with no company or suite brand, and the word
   Frappe never appears in a user facing label. The prompt also carries the rebuild rule (section 9).
4. Before calling the gate, write the task block to `/tmp/sellos-task-block.md` and export
   `SELLOS_TASK_ID`, `SELLOS_BASE_SHA` (the commit the task started from) and
   `SELLOS_TASK_BLOCK_FILE`. The gate uses them to run the three guards. Unset them for the repair
   runs only if the task changes; keep them otherwise.
5. Add the rules to the repair prompt: never edit a gate file, never remove an assertion, and a
   failing test is fixed in the code unless the task block says otherwise.
6. After `git push`, run `gh run watch` for the run on that commit. If it ends red, notify and stop
   the loop without starting a new task.
7. Run beside the BuildOS loop (SOS-SETUP-20). Nothing in the loop waits for BuildOS; only the gate's heavy segment takes the shared bench gate lock. The agent prompt says the shared environment is not the agent's to change: no pip install, no npm install -g, no bench update, no bench setup, no bench get-app, no install-app on any site but `sellos_test.localhost` and `sellos_tenant_*.localhost`, nothing under `apps/buildos` read, listed or run (BuildOS code is read only in `~/iespl-baseline/buildos-reference`, section 10), and the server on 8000 and the sites pamaa and awh left alone. At its start the loop checks the installed lock helper against `scripts/shared/bench-gate-lock.sh` and runs `scripts/refresh-buildos-reference.sh` once (SOS-SETUP-21).

## 6. Personal data

Every DocType that holds a phone number, an email address or a name of a person is tested like this
before its task is done:

* A backend test for the masking and the permission rules.
* A Cypress spec that signs in as every role and, with `cy.genericReads`, tries the form loader, the
  document info, `frappe.client.get`, `get_list`, `get_value`, the report view, link search and
  `/api/resource` for the record, and asserts the full value appears in none of them. The number is
  changed once first, so the change history holds the old value and the new one.
* The reveal of a full value is logged, or the task says which later task will log it.

## 7. What is still weak

* The Cypress code and the leak specs have not run against a real SellOS site yet. The first gate
  run is their real test, and the gate will show failures plainly.
* `testIsolation` is off, as in BuildOS, so specs share one browser state. The baseline restore and
  the rule that a spec makes its own uniquely named records limit the damage.
* The loop runs the agent with `--dangerously-skip-permissions`, as BuildOS does. The gate file
  protection and the failed branch reset are what limit the damage.
* A test the agent writes cannot be judged by the agent that wrote it. The ratchet and the evidence
  check stop the worst cases, and a human reads each milestone.
* The UI tests run on the SellOS server on port 8004, pinned to `sellos_test.localhost`
  (`cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`). Restarting it while the gate runs breaks the run. The servers on 8000
  (BuildOS) and 8002 (Pamaa) are never touched.

## 8. Waiting tasks and the regression pauses

A Waiting task is never picked by the loop. It belongs to a person (Jayman, AMP Labs, Counsel, the
Accountant) or, for a SOS-REG task, to Claude in chat. Dependants stay Not Started until it is
Complete, so when nothing else is eligible the loop stops. Its notification lists each Waiting task
that still holds up a Not Started task, what it waits on, and what it holds up. A Not Needed task
counts as satisfied for its dependants, and is never picked or reported.

To finish a Waiting task by hand, do the work, then:

```
scripts/set-task-status.sh <ID> Complete TASKS.md
git add TASKS.md            # and the report or evidence, for a regression
git commit -m "<ID> <what was done>"
git push origin 1.0
```

and start the loop again. A Waiting task stays Waiting until then, so the loop never reaches past it.

**Regression is a scheduled pause, not a gate (Jayman, 10 November 2026, SOS-SETUP-19).** No task
depends on a regression task except the last one. The regression tasks are Waiting, owned by "Claude
in chat, clickthrough regression":

| Task | About | Covers |
| --- | --- | --- |
| SOS-REG-A | 24 November 2026 | every task Complete by then |
| SOS-REG-B | 12 December 2026 | every task Complete by then |
| SOS-REG-C | 18 December 2026 | every task Complete by then, before the Dec 20 launch tier closes |
| SOS-REG-L | 29 December 2026 | the launch regression; it depends on every other task that is not Not Needed or Parked |

The pause works through one file, `/tmp/sellos-loop.pause` (`SELLOS_PAUSE_FILE` overrides the path, for
the tests only):

1. `scripts/pause-loop.sh` creates the file.
2. Before picking each task, `scripts/build-loop.sh` checks for it. If it exists the loop picks nothing,
   changes no status, notifies "Paused for regression" and stops. A task already running finishes
   first, gate and push included.
3. Claude in chat follows `docs/regression/README.md`: it walks every flow, writes the report, and
   makes every defect an SOS-FIX task in the Dec 20 tier, above the first Not Started task.
4. `scripts/resume-loop.sh` removes the file. Start the loop again; it picks the fixes first.

Both scripts are gate files. Their support files are gate files too: `docs/regression/README.md`,
`scripts/prepare-regression.sh` and the evidence check that needs each browser task's flows in
`docs/regression/flows.md` (a task may add flows, never remove one). `seed_regression_data` in
`sellos/tests/ui_fixtures.py` builds the dataset through the production API and its docstring lists the
data, which each task that adds data updates. The old milestones SOS-REG-0 to SOS-REG-6 and SOS-REG-2B
are Not Needed, and their blocks are kept.

## 9. Jayman's decisions of 10 November 2026 (SOS-SETUP-19)

* **Rebuild from scratch.** The commit before the rebuild is tagged `legacy/before-rebuild`. Every task
  was set back to Not Started, the finished ones included, and is rebuilt from its own text. The agent
  must not assume existing code is right. It reads it, replaces what is weak, keeps what passes review,
  and every task adds or refreshes tests that name it. The tree is not deleted first. The rule is in the
  loop prompt and in CLAUDE.md.
* **Launch tiers.** Everything is launch scope. Every task has a `Launch` line: Dec 20 or Jan 1, or
  `none` for a Not Needed or Parked task. The loop chooses by tier first, then dependencies, then file
  order.
* **Not Needed.** International calling is dropped, with the other enablers that are no longer needed.
  A Not Needed dependency counts as satisfied.
* **Consent never blocks.** A lead's consent status (Consented, Unknown, Opted out, Registered DND when
  known) is recorded and shown as a warning on the lead, the caller queue and the call log. It never
  prevents a call, an SMS or a WhatsApp message, in code or in the screens. Enforcement lives in one
  function (SOS-P2-04) behind the company setting "Consent enforcement", which is Off by default. An
  explicit stop request is recorded as Opted out with a red warning, and does not block. Calling hours
  stay a configurable setting. Tests show that calls and messages proceed in every consent state and
  that the warning is recorded. The earlier rules "the consent check has no override" and "the system
  refuses a promotional purpose" are withdrawn.
* **Name.** The product is called SellOS everywhere, exactly as BuildOS is called BuildOS, with no
  company or suite brand.

## 10. The BuildOS reference copy (SOS-SETUP-21)

The loop agent never reads, lists or runs anything under `apps/buildos`, because the BuildOS loop works
there at the same time. When a task needs BuildOS code (SOS-P0-01, SOS-P0-02, SOS-P0-10, SOS-P1-03,
SOS-P1-06B, SOS-P6-02 and any other that says to read or reuse it), the agent reads the read only
copy at `~/iespl-baseline/buildos-reference`, with ls, cat, grep and find only, and never writes into it.

`scripts/refresh-buildos-reference.sh` makes the copy: it makes the folder writable, rsyncs the BuildOS
working tree into it without `.git`, `node_modules`, `buildos/public/frontend`, `buildos/www/buildos.html`,
`logs`, `*.log`, `__pycache__` and `*.pyc` (excluded files already in the copy are deleted), makes it
read only again (`chmod -R a-w`), and prints the BuildOS commit it copied and whether the working tree
had uncommitted changes. The build loop runs it once at its start, not per task, and stops with an
environment problem if it fails. The copy is the BuildOS working tree as it was at that moment, so it
may hold BuildOS work in progress.
