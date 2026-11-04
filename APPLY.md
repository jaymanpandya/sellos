# Applying the BuildOS strategy to SellOS

This folder holds the files that are new or different. Everything shared with BuildOS is copied
from `~/iespl-bench/apps/buildos/scripts`, not retyped.

## What is here

* `docs/DEV_STRATEGY.md`, `docs/TESTING.md`: the strategy and the testing rules.
* `scripts/run-tests.sh`, `scripts/make-baseline.sh`, `scripts/check_*.py`: the gate and its guards.
* `cypress.config.js`, `cypress/`: the Cypress setup, strict support file, commands and three specs.
* `sellos/tests/`: fake phone numbers, the guard against hand written numbers, and the fixtures.

## For you

1. Stop Claude Code and the current loop if one is running.
2. Copy this folder into the repository:

   ```
   cd ~/iespl-bench/apps/sellos
   git checkout 1.0 && git pull
   cp -Rn ~/Downloads/sellos_buildos_strategy/. .
   git status --short
   ```

   `-n` keeps anything that already exists. `git status` should list new files only, no changes.
3. Give Claude Code the prompt below.
4. When Claude Code says the baseline is ready to be made, run the one command it tells you
   (`scripts/make-baseline.sh --create`). It asks for the MariaDB root password.
5. Start the loop yourself, the way you start BuildOS's, with `scripts/build-loop.sh`, or under
   `scripts/watchdog.sh`.

## The prompt for Claude Code

```
Read docs/DEV_STRATEGY.md and docs/TESTING.md. We are replacing the git hook gate with the
BuildOS build loop and BuildOS's test strategy, on the same bench, with the holes in section 4
closed. Do the following in order. Commit each step yourself this once, because the loop does not
exist yet. Stop and tell me if any step cannot be done.

1. Read BuildOS first. Open ~/iespl-bench/apps/buildos and read scripts/build-loop.sh,
   scripts/run-tests.sh, scripts/lib/tasks.py, scripts/watchdog.sh, scripts/notify-telegram.sh,
   scripts/limit_wait.py, cypress/README.md, cypress/support/commands.js, cypress/support/e2e.js,
   cypress.config.js, docs/TESTING.md and .github/workflows/ci.yml. Do not rely on my summary.
   If anything in docs/DEV_STRATEGY.md disagrees with the real files, tell me and follow the
   real files except where section 4 deliberately differs.

2. Copy these from BuildOS unchanged, then change only names and paths: scripts/select-next-task.sh,
   scripts/set-task-status.sh, scripts/lib/tasks.py, scripts/watchdog.sh, scripts/notify-telegram.sh,
   scripts/limit_wait.py. Make scripts/build-loop.sh by copying BuildOS's and applying only the
   seven changes in section 5 of docs/DEV_STRATEGY.md. Do not retype it.

3. Retire what the loop replaces: remove .githooks/, scripts/test_all.sh, scripts/smoke_http.py,
   scripts/check_tests_changed.py, scripts/install_hooks.sh and scripts/setup_test_site.sh, and run
   git config --unset core.hooksPath. Keep sellos/testing/users.py, because the fixtures use it.

4. Match BuildOS's front end tooling. BuildOS uses npm with package-lock.json. Switch frontend/ from
   yarn to npm (delete yarn.lock, create package-lock.json, update the CI and any script that says
   yarn). Remove Vitest. Before deleting frontend/src/shell.test.js and the other *.test.js files,
   write a Cypress spec for every assertion in them (put the specs in cypress/integration/frontend/
   and give the elements data-testid="sellos-..." attributes), and show me the list of old
   assertion to new assertion. No coverage may be lost. Then delete the Vitest files and dependencies.

5. Convert Tasks.md to the BuildOS block format (section 3). P0.01 becomes SOS-P0-01, and so on. Keep
   every story, its acceptance criteria, its dependencies and its phase as priority (Phase 0 is P0,
   Phase 1 is P1, and so on). Done stories become Complete, the rest Not Started. Parked stories
   (the DLT ones) stay parked, with a Status of Parked. Add "- **Browser spec:** required" to every
   story that a person sees or uses. Keep the milestone and checkpoint stops from the old file.

6. Reopen the work that failed my browser test. Split P1.06 into two tasks and set both to Not Started:
   SOS-P1-06A, "CRM works on a fresh company site", with these acceptance criteria:
   a. sellos.crm.api.list_leads and save_client work for the Company Admin and the Agent on a fresh
      site made by prepare_clean_site, and are refused with a clear message for the others, as the
      permission matrix says. Quote the code that refused every user, and fix its cause without
      weakening the guard.
   b. sellos.tests.ui_fixtures: implement _configure_company_site (call the same code that
      provisioning uses), seed_agent_leads and seed_client_with_phone as their docstrings say.
   c. The Leads screens show an error when a call fails and never "No leads yet". The form shows the
      server's message. Add the data-testid attributes that cypress/integration/smoke/app_shell.cy.js
      and cypress/integration/crm/leads_by_role.cy.js use.
   d. Those two specs pass.
   e. The page uses the approved tokens (#0f4c35, #e8954a, Syne headings, DM Sans body, a filled
      --sos-brand-mid) and shows the company name, not the site name. Find what replaced the
      approved tokens and restore them.
   SOS-P1-06B, "Phone numbers do not leak", depends on SOS-P1-06A, with these acceptance criteria:
   a. cypress/integration/security/phone_masking_leaks.cy.js passes as written.
   b. A backend test for the masking and the permission rules. Reuse the approach of
      buildos.security.field_history so the change history never shows a full number to a role that
      may not see it (read BuildOS's version first).
   c. Showing a full number to a Company Admin is logged, or this task says which later task logs it.
   Mark both "Browser spec: required".

7. CI. Read https://github.com/frappe/frappe/blob/develop/.github/workflows/ui-tests.yml and add a UI
   job to .github/workflows/ci.yml modelled on it, not guessed: a fresh site, the app installed,
   prepare_clean_site run, the Cypress suite run with bench run-ui-tests. Make the Linters workflow
   run on pushes to 1.0 too. Keep every existing job.

8. Run the gate's own checks without the Cypress parts you cannot run yet: pre-commit run --all-files,
   the three scripts/check_*.py against a throw away branch, and bash -n on every script. Then stop
   and tell me exactly what I must run: scripts/make-baseline.sh --create, restarting the SellOS server
   once so it loads the SellOS hooks (`cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`), and the first scripts/run-tests.sh. Tell me
   which specs you expect to fail on that first run, and why.

Rules: never stop, start or restart the bench. Never touch buildos or its sites. Never edit a file
under apps/buildos. The gate files in docs/TESTING.md may be edited in this setup, and only in this setup.
```
