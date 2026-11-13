# Testing SellOS

SellOS is tested the way BuildOS is: a build loop (`scripts/build-loop.sh`) gives one task at a time
to the agent, then runs the real gate (`scripts/run-tests.sh`) and commits only if it passes. Read
`docs/DEV_STRATEGY.md` for the loop and for the holes in the BuildOS strategy that this gate closes.
The agent never commits. Git hooks are not used.

## What the gate runs, in order

1. New files are marked intent-to-add (`git ls-files --others --exclude-standard -z | xargs -0 git add
   --intent-to-add`), so every check below sees them as CI does. No content is staged.
2. Preflight: the bench gate lock helper (`~/iespl-baseline/bench-gate-lock.sh`, installed from
   `scripts/shared/bench-gate-lock.sh`) exists, the bench
   serves `sellos_test.localhost`, the clean baseline and Semgrep exist. A BuildOS gate or loop may be
   running at the same time (SOS-SETUP-20).
3. Lint (`pre-commit run --all-files`) and Semgrep, CI's exact command (`semgrep ci` with the Frappe
   rules and `r/python.lang.correctness`).
4. The task guards (only when the loop sets the task): gate files untouched, no assertion removed, and
   a test that names the task.
5. Build the web app (`npm ci`, `npm run build`).
6. Take the bench gate lock (waiting for any other gate's heavy segment, and recording the wait in the
   gate log), restore the clean baseline (a clean migrated install) over `sellos_test.localhost`,
   migrate, then `prepare_clean_site` (code, on every run).
7. The test files the task changed, first. A failure stops the gate.
8. The whole backend suite, then the whole Cypress suite. A failed spec is rerun once, alone. A spec
   that needed a rerun is logged FLAKY, and one that is FLAKY three times fails the gate. The bench
   gate lock is released at the end of the Cypress run, or when the gate fails or is killed. The
   policy is `scripts/lib/ui_flaky.sh`, and CI's UI job runs Cypress through the same script, with
   its flaky log kept in the Actions cache and the run's flaky specs in the job summary
   (SOS-SETUP-27).

The gate uses only `sellos_test` and `sellos_test.localhost`. Create the site and the baseline once
with `scripts/make-baseline.sh --create`.

## Fake phone numbers

Any phone number in a backend test or a Cypress spec comes from `sellos.tests.phones` (`in_mobile`,
`au_mobile`, `ae_mobile`, `near_in_mobile`). Never write one by hand or build one with string
formatting. A Cypress spec gets its number from the backend fixture that seeds its data.
`sellos/tests/test_no_raw_phone_numbers.py` scans every test and spec and fails on a literal number.
Its allowed list is empty and stays empty.

## Backend tests

Follow the Frappe documentation: https://docs.frappe.io/framework-git/testing/overview

* `IntegrationTestCase` from `frappe.tests` for anything that touches the database, `UnitTestCase`
  for anything that does not. Create data inside the test class and let the framework roll it back.
* Tests live beside the code as `test_*.py`. Put the task ID in the class docstring.
* Anything a task creates on a site (users, roles, records, settings) comes from code that can be
  run again safely, and a test reads it back. Add test users for a new role to `TEST_USERS` in
  `sellos/testing/users.py`.

## Cypress specs

Specs are in `cypress/integration/<area>/<screen_or_flow>.cy.js`, with the task ID in `context()`.

* Select by `data-testid="sellos-<area>-<thing>"` through `cy.getByTestId("<area>-<thing>")`. Never by
  style, position or visible text.
* `cy.signInFresh(role)` signs in as `platform_admin`, `company_admin`, `agent`, `channel_partner`,
  `client` or `basic`. `cy.signOut()` ends the session.
* `cy.bench("sellos.tests.ui_fixtures.<name>", {kwargs})` runs a server side helper. Helpers are
  never exposed over HTTP.
* Make the records a spec needs inside the spec, with names unique to it.
* Three things fail a test even when its own assertions pass: an `/api/` answer of 400 or more, a
  console error, and an uncaught error. Declare an expected one with `cy.expectApiStatus(urlPart,
  status)` or `cy.expectConsoleError(text)`. Only the two ResizeObserver wordings are ignored.
* A leak spec must first show the user can read the record on at least one path, then try every path
  in `cy.genericReads` for the current value and the replaced one.

## Gate files

These decide whether a task passes, so a task may not change them unless its block says
`Gate files: allowed`, which only a human writes: `scripts/run-tests.sh`, `build-loop.sh`,
`watchdog.sh`, `select-next-task.sh`, `set-task-status.sh`, `make-baseline.sh`, `scripts/lib/*`,
`scripts/check_*.py`, `cypress.config.js`, `cypress/support/e2e.js`, `.pre-commit-config.yaml`,
`.semgrepignore`, `.eslintrc`, `.github/workflows/*`, `docs/DEV_STRATEGY.md`,
`scripts/prepare-regression.sh`, `scripts/pause-loop.sh`, `scripts/resume-loop.sh`,
`scripts/refresh-buildos-reference.sh`, `scripts/install-shared-helpers.sh`, `scripts/shared/*`,
`docs/regression/README.md` and this file. `docs/regression/flows.md`
is append only: a task adds its flows and may never remove one.

`pyproject.toml` is not protected as a whole, because tasks add dependencies to it. The guard loads it
at the base commit and in the working tree with `tomllib` and fails if the `[tool.ruff]` tables differ
in any way (rules, ignores, per file ignores, format settings). A comment or a dependency change
passes. `sellos/tests/test_check_gate_files.py` tests the guard.

## Human overrides

* `SELLOS_ALLOW_NO_BASELINE="reason"` lets one gate run go on without the baseline.
* `SELLOS_ALLOW_ASSERTION_DROP="reason"` lets one run drop assertions. The loop never sets either.
* `SELLOS_TENANT_TEMPLATE=off` makes every tenant site with the full install for one run. By default the gate, like CI, builds them from a template dump made once per run, and exactly one real provisioning test uses the full install (SOS-SETUP-32).

## Running parts by hand

From `~/iespl-bench`, with the SellOS server running on port 8004 (`cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`):

```
bench --site sellos_test.localhost run-tests --app sellos --module sellos.crm.test_crm
bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/smoke/app_shell.cy.js
apps/sellos/scripts/run-tests.sh        # the whole gate
```

Logs are in `/tmp/sellos-test-logs/` and `latest.log` is the last run.
