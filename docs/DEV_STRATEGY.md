# How SellOS is built and tested

SellOS is built the way BuildOS is built, on the same bench, with the same tools and the same loop.
This file records what BuildOS does (read from its repository on 4 November 2026), what SellOS
copies unchanged, and every place where SellOS is stricter and why. If a rule here and a habit
disagree, the rule wins. Gate files (see below) may only be changed by a human.

## 1. The environment is the BuildOS environment

| Thing | BuildOS | SellOS |
| --- | --- | --- |
| Bench | `~/iespl-bench` | the same bench |
| Runtime | Python 3.14, Node 24, MariaDB 11.8, two Redis | the same |
| Test site | `test_site` | `sellos_test.localhost`, its own site on the same bench |
| Clean snapshot | `~/iespl-baseline/test_site_clean.sql.gz` | `~/iespl-baseline/sellos_test_clean.sql.gz` |
| Front end build | `npm ci` then `npm run build` | the same (package-lock.json, not yarn) |
| Unit tests | `bench --site test_site run-tests --app buildos` | `bench --site sellos_test.localhost run-tests --app sellos` |
| UI tests | Cypress through `bench --site test_site run-ui-tests buildos --headless` | the same command with `sellos` |
| UI fixtures | `buildos/tests/ui_fixtures.py` through `cy.bench` | `sellos/tests/ui_fixtures.py` through `cy.bench` |
| Server for UI tests | the running `bench start` on port 8000, site picked by its host name | the same |
| Lint | pre-commit: ruff, prettier 2.7.1, eslint 8.44, pyupgrade | the same |
| CI | server job (fresh site, run-tests), Linters (Semgrep, pip-audit) | the same, plus a UI job |
| Who commits | the build loop, never the agent | the same |

The SellOS gate refuses to run against any site other than `sellos_test` or `sellos_test.localhost`,
because it restores the baseline over that site and wipes it.

## 2. The loop (copied from BuildOS)

`scripts/build-loop.sh` runs one task at a time. For each task it:

1. Picks the next task from TASKS.md (`select-next-task.sh` and `lib/tasks.py`): resume an In
   Progress one, else the first Not Started task of the highest priority whose dependencies are
   all Complete. If anything is Blocked, nothing new starts.
2. Marks it In Progress and commits that, and records the commit it started from.
3. Calls `claude -p` once with the task in the prompt. The agent edits files and runs only its own
   single test module and single spec, in the foreground. It never commits, pushes, resets,
   stashes, rebases, merges or changes a status.
4. Runs the real gate, `scripts/run-tests.sh`.
5. If the gate fails, hands the failure output back to the agent to repair, up to 3 gate runs in all
   (`SELLOS_MAX_GATE_RUNS`). The repair rules forbid deleting or weakening an assertion.
6. If the gate passes: marks the task Complete, commits, pushes. If it still fails after the last
   repair: saves the attempt on a `failed/<task>-<time>` branch, hard resets the branch to the
   commit it started from, marks the task Blocked, notifies, and stops. No broken code ever stays
   on the main branch.
7. Stops on Blocked, NEEDS_INPUT (a question the agent cannot settle, never a milestone), a crashed agent or no eligible task. A Blocked task is never
   resumed by itself. A human finds the cause, checks it by hand in a browser, and resets it to
   Not Started.

Copied unchanged from `../buildos/scripts`: `select-next-task.sh`, `set-task-status.sh`,
`lib/tasks.py` (priorities now run P0 to P6, and it has a `waiting` report), `watchdog.sh`, `notify-telegram.sh`, `limit_wait.py`. Only the names, paths and
prompt text in `build-loop.sh` change (section 5).

## 3. Tasks

TASKS.md holds one block per task, in the BuildOS format that `lib/tasks.py` reads:

```
### SOS-P1-06: Lead, Client, Activity, Task and Site Visit records
- **Epic:** CRM
- **Description:** ...
- **Acceptance Criteria:**
  - ...
- **Priority:** P1
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
| 4 | The UI tests need `bench start` and the site at its own address, and say nothing if they are not there | Cypress times out with an unhelpful message | A preflight asks the site to answer first and says what is missing | `scripts/run-tests.sh` |
| 5 | The agent can edit the gate, the Cypress config, the support file or CI in the same task | A failing test is "fixed" by changing what judges it | Those files are protected. A task changes them only if its block says `Gate files: allowed`, which only a human writes | `scripts/check_gate_files.py` |
| 6 | "Never weaken an assertion" is one sentence in a prompt | Nothing stops it | The number of assertions in every changed test file may not fall, and a test file may not be deleted | `scripts/check_assertion_ratchet.py` |
| 7 | A task can be marked Complete with no test that names it | Acceptance criteria nobody tests | A new or changed test that names the task ID and holds assertions is required. A task marked `Browser spec: required` also needs a Cypress spec | `scripts/check_task_evidence.py` |
| 8 | Lint and Semgrep are not in the gate, only in CI after the push | The commit lands, CI goes red afterwards. It happened three times on SellOS (ruff on PR 1, Semgrep twice on P0.07) | Pre-commit and Semgrep with the Frappe rules run inside the gate | `scripts/run-tests.sh` |
| | *Note on row 8:* BuildOS runs Semgrep (its Linters workflow) only on pull requests, and its loop pushes straight to the branch, so its direct pushes are never scanned | | | `.github/workflows/linter.yml` in BuildOS |
| 9 | A spec that fails and then passes alone is logged FLAKY and counts as a pass | A real race stays in the suite for good | The same spec flaky three times fails the gate until it is fixed | `scripts/run-tests.sh` |
| 10 | CI runs only the server tests | Browser behaviour is never checked on a clean machine | CI gets a UI job that provisions a fresh site and runs the Cypress suite (section 5) | `.github/workflows/ci.yml` |
| 11 | The gate migrates a long lived site | A fresh install is never exercised in a browser | The baseline is only a clean migrated install. The state a provisioned company site is in, and the role users, are made by code on every run: `run-tests.sh` runs `prepare_clean_site` right after the migrate and cache clear, before the changed tests, and CI builds a fresh site the same way | `scripts/run-tests.sh`, `sellos/tests/ui_fixtures.py` |
| 12 | The BuildOS gate and the SellOS gate share one bench | Two gates restore databases and clear the cache under each other | The SellOS gate refuses to start while a BuildOS gate or loop is running | `scripts/run-tests.sh` |
| 13 | The gate restores a baseline over its site | A wrong site name wipes real work | Only `sellos_test` and `sellos_test.localhost` are accepted | `scripts/run-tests.sh`, `scripts/make-baseline.sh` |
| 14 | Permission specs can pass because the user cannot read the record at all | A leak check that has nothing to find | A leak spec must first show the user can read the record on at least one path | `cypress/integration/security/` |
| 15 | Personal data leaks are found one at a time by a person | The change history held old and new values in BuildOS (BOS-282) | Every path in `cy.genericReads` is tried as every role for every DocType that holds personal data, for the current value and the replaced one. Reuse `buildos.security.field_history` | `cy.genericReads`, the security specs |
| 16 | After a push the loop starts the next task without looking at CI | A red CI sits unnoticed while new work piles on | After each push the loop waits for CI on that commit. If it is red the loop stops and notifies, and starts nothing new | `scripts/build-loop.sh` |
| 17 | Test data is made by hand | An invalid or real phone number breaks a test or leaks into the repository | `sellos.tests.phones` makes valid numbers, and a test fails on any hand written one. The allowed list starts empty and stays empty | `sellos/tests/test_no_raw_phone_numbers.py` |
| 18 | A human walks through the product by hand | Skipped when time is short | Each milestone is a Waiting task, SOS-REG-0 to SOS-REG-6 and SOS-REG-2B, that the next phase depends on. Claude in chat walks every flow in `docs/regression/flows.md` in a browser and writes a report. A task marked `Browser spec: required` fails the gate unless it adds its flows (section 8) | `TASKS.md`, `scripts/check_task_evidence.py`, `docs/regression/` |
| 19 | The loop runs one `git push` after a task passes and assumes it worked | A loop that cannot push leaves finished work unpushed, and the next tasks pile up on top of it | At start the loop checks `git ls-remote --exit-code origin HEAD` and stops before any task if the remote does not answer, and pushes first if the branch is ahead of origin. After a passing task the push is retried after 10, 30 and 90 seconds, and GitHub's "fatal error in commit_refs" is retried, not taken as a rejection. If every try fails the commit is kept, never reset, the exact git error is sent, and the loop stops. At start the loop also stops if `gh auth status` fails, and before pushing commits that are ahead it lists them, refuses any whose message does not start with `SOS-`, and waits for CI on the pushed head before picking a task. Git never prompts (`GIT_TERMINAL_PROMPT=0`, and SSH in batch mode with a 15 second timeout when origin is an SSH remote) | `scripts/build-loop.sh` |
| 20 | The gate ran its own Semgrep command: only the Frappe rules, with its own `--exclude` list, on every file in the folder | The gate can pass while CI fails, because the two scan different files with different rules. On 6b0fade the Linters run went red on three `open()` calls in `scripts/lib/tasks.py` | The gate runs exactly CI's command, `semgrep ci --config <frappe rules> --config r/python.lang.correctness`, and both read the same `.semgrepignore` at the repo root. Any new CI check is added to the gate in the same change | `scripts/run-tests.sh`, `.semgrepignore`, `.github/workflows/linter.yml` |

## 5. Changes to `build-loop.sh`

Copy BuildOS's `scripts/build-loop.sh` and change only these things. Do not retype the script.

1. Names: `BUILDOS_` becomes `SELLOS_`, `/tmp/buildos-*` becomes `/tmp/sellos-*`, the branch default
   is `1.0`, the task ID pattern in the awk is the one in `lib/tasks.py`, commit messages use the
   SellOS ID.
2. Paths in both prompts: `bench --site sellos_test.localhost run-tests --app sellos --module ...` and
   `bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/...`.
3. The locked architecture paragraph: no ERPNext, the web app never uses the Frappe desk, five roles,
   isolation by site, the consent check has no override, calling on the 022 number is for service
   and transactional purposes only, and the word Frappe never appears in a user facing label.
4. Before calling the gate, write the task block to `/tmp/sellos-task-block.md` and export
   `SELLOS_TASK_ID`, `SELLOS_BASE_SHA` (the commit the task started from) and
   `SELLOS_TASK_BLOCK_FILE`. The gate uses them to run the three guards. Unset them for the repair
   runs only if the task changes; keep them otherwise.
5. Add the rules to the repair prompt: never edit a gate file, never remove an assertion, and a
   failing test is fixed in the code unless the task block says otherwise.
6. After `git push`, run `gh run watch` for the run on that commit. If it ends red, notify and stop
   the loop without starting a new task.
7. Refuse to start while the BuildOS loop or gate is running.

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
* The UI tests share the bench server with BuildOS development. Restarting `bench start` while the
  gate runs breaks the run.

## 8. Waiting tasks and the regression milestones

A Waiting task is never picked by the loop. It belongs to a person (Jayman, AMP Labs, Counsel, the
Accountant) or, for a SOS-REG milestone, to Claude in chat. Dependants stay Not Started until it is
Complete, so when nothing else is eligible the loop stops. Its notification lists each Waiting task
that still holds up a Not Started task, what it waits on, and what it holds up.

To finish a Waiting task by hand, do the work, then:

```
scripts/set-task-status.sh <ID> Complete TASKS.md
git add TASKS.md            # and the report or evidence, for a regression milestone
git commit -m "<ID> <what was done>"
git push origin 1.0
```

and start the loop again. A Waiting task stays Waiting until then, so the loop never reaches past it.

The regression milestones are Waiting tasks with the owner "Claude in chat, clickthrough regression".
Each depends on every task of its phase that a person sees or uses, and every task of the next phase
depends on it. SOS-REG-2B is a checkpoint inside Phase 2, after click to call. Their support files are
gate files: `docs/regression/README.md`, `scripts/prepare-regression.sh` and the evidence check that
needs each browser task's flows in `docs/regression/flows.md` (a task may add flows, never remove one).
`seed_regression_data` in `sellos/tests/ui_fixtures.py` builds the dataset through the production API and
its docstring lists the data, which each task that adds data updates.
