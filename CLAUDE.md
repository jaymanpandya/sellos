# SellOS

SellOS is a multitenant real estate platform for Indian agents, built on Frappe 16.x and hosted on DigitalOcean. Pandya Realtors is the first company on it. The AMP Labs builds it, Claude Code writes the code, and Jayman reviews the work on 1.0.

## Where the work is defined

* TASKS.md is the backlog. Work one story at a time, in dependency order, and follow its "Rules for Claude Code".
* KICKOFF.md says how the first week starts.
* docs/legacy/SellOS_Build_Brief_v1.md is the earlier build brief. It is reference material only. Use it for domain field lists such as Project, Unit, Lead, Booking and Payment Schedule when the matching story needs them. Do not follow its phase order, its tenant field approach, or its instruction to create DocTypes in the Desk.

## Architecture decisions

1. One Frappe site and one database per company, at a subdomain of sellos.interactivesoftwares.com, plus a separate control site for the Platform Admin. A company never shares a database with another company.
2. Frappe 16.x without ERPNext. Pin the version.
3. DocTypes, hooks and patches live in the app repositories as code. Never create DocTypes through the Desk.
4. Customers never use the Frappe desk. Every customer feature is built in the SellOS web app, which follows the BuildOS frontend stack, structure and tooling once P0.01 is approved. Only the Platform Admin may open /desk, and only to operate the control site. No customer role (Company Admin, Agent, Client or Channel Partner) ever gets it. Decided by Jayman at Checkpoint A.
5. Every API method is whitelisted, declares its allowed roles, and is covered by the permission test matrix. A method with no declaration is denied.
6. Five roles: Platform Admin, Company Admin, Agent, Client and Channel Partner.
7. Consent never blocks (Jayman, 10 November 2026). A lead's consent status (Consented, Unknown, Opted out, Registered DND when known) is recorded and shown as a warning on the lead, the caller queue and the call log. It never prevents a call, an SMS or a WhatsApp message, in code or in the screens. Enforcement lives in one function behind the company setting "Consent enforcement", which is Off by default. An explicit stop request is recorded as Opted out with a red warning, and does not block. Calling hours stay a configurable setting.
8. The 022 number is for service and transactional calls. Each call records its purpose.
9. Secrets live in encrypted settings or environment variables, never in a repository.
10. Never build captcha solving or any bypass of an access control.

## Working rules

* Ports (Jayman's rule, always): BuildOS runs on port 8000, Pamaa on 8002, SellOS on 8004. SellOS never uses 8000 or 8002, and never starts, stops or touches the servers on them. Each server is pinned to one site. The SellOS server is always started as `cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`. Never run `bench serve --port 8004` without `--site`: it falls back to default_site and serves BuildOS's site for every host name. Since SOS-SETUP-33 that command runs as the LaunchAgent `com.sellos.server` (`scripts/install-launch-agent.sh`), which starts it at login and restarts it when it exits or stops answering after sleep. Jayman starts and watches the loop with `scripts/sellos up`, `scripts/sellos status` and `scripts/sellos stop`. The agent never runs any of them. The gate and `scripts/prepare-regression.sh` refuse any port but 8004 and check that the server really is SellOS.
* The build loop makes one commit per task on the 1.0 branch, with the task ID at the start of the message, and pushes to 1.0 after the gate passes. The agent leaves its work uncommitted. Do not open pull requests, and never force push.
* Write the tests named in the story's Test criteria with the code. Continuous integration must pass.
* The loop sets a task's status in TASKS.md (In Progress, Complete, Blocked). The agent never changes one.
* Do not start a task whose dependencies are not Complete or Not Needed, and do not work on Parked or Not Needed tasks.
* Rebuild from scratch (Jayman, 10 November 2026). Every task is rebuilt from its own text. Do not assume existing code is right: read it, replace what is weak, keep what passes review, and add or refresh tests that name the task, even where code for it already exists. Do not delete the tree first. The commit before the rebuild is tagged `legacy/before-rebuild`.
* The product is called SellOS everywhere, exactly as BuildOS is called BuildOS, with no company or suite brand.
* Shared bench (SOS-SETUP-20). The BuildOS and SellOS loops run at the same time on `~/iespl-bench`. Never change the shared environment: no pip install, no npm install -g, no bench update, no bench setup, no bench get-app, and no install-app on any site except sellos_test.localhost and sellos_tenant_*.localhost. Never read, list or run anything under apps/buildos. The bench server on port 8000 and the sites pamaa and awh are not yours. The two gates share only their heavy segment, through the bench gate lock (`~/iespl-baseline/bench-gate-lock.sh`).
* Tenant sites and the provisioner password (SOS-SETUP-22): create, drop, list and probe tenant sites only with `scripts/tenant-site.sh` or `sellos.provisioning.tenant_sites`, and get the MariaDB provisioner password only from `sellos.provisioning.credentials.get_provisioner_password()` (the variable, else the macOS Keychain item `sellos_provisioner`), which hands it to bench only through a child process's environment. Never run `security find-generic-password -w` (or any command that prints a secret), and never print, log or write the password. If `get_provisioner_password()` raises, reply NEEDS_INPUT with its message.
* Multitenancy on the local bench (SOS-P0-06L): tenant sites `sellos_tenant_<id>.localhost` with databases `sellos_tenant_<id>` (`<id>` is `[a-z0-9]+`, checked by `sellos.provisioning.tenant_sites.names`) are made and dropped only with `scripts/tenant-site.sh` or `sellos.provisioning.tenant_sites`, using the MariaDB provisioner account and never root. The SellOS server stays pinned to `sellos_test.localhost` on 8004. Multitenancy is tested in process with `frappe.init(site=...)`, never over HTTP, and routing by host name is SOS-P0-08's. See `docs/MULTITENANCY.md`.
* BuildOS reference (SOS-SETUP-21). To read BuildOS code, use only the read only reference copy at `~/iespl-baseline/buildos-reference`, with ls, cat, grep and find. Never write, chmod, move or delete anything in it. Never read, list or run anything under `apps/buildos`, where the BuildOS loop is working. The loop refreshes the copy once at its start (`scripts/refresh-buildos-reference.sh`, SOS-SETUP-21).
* Regression is a scheduled pause, not a gate: `scripts/pause-loop.sh` stops the loop before its next pick and `scripts/resume-loop.sh` lets it go on (see `docs/DEV_STRATEGY.md` section 8).

## Stop and ask Jayman when

* A story needs a secret, account or access you do not have.
* An acceptance criterion is ambiguous.
* A change touches permissions, the consent check, billing or personal data.
* A dependency is blocked, or the plan and this file disagree.

## Commands

Run these from the app folder (`apps/sellos` in the bench). Never start, stop or touch the servers on port 8000 (BuildOS) or 8002 (Pamaa). The SellOS server runs on port 8004 and is always started as `cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`.

* Build the web app: `cd frontend && npm ci && npm run build`
* Build all assets through the bench: `bench build --app sellos`
* Server tests: `bench --site sellos.localhost run-tests --app sellos` (the site needs `allow_tests` set)
* Lint and format: `pre-commit run --all-files` (ruff, prettier, eslint and file checks). Run it before every push.
* Continuous integration runs the same checks on every push to 1.0.

## Frappe 16 conventions

* Python 3.14, tabs for indentation, double quotes, line length 110 (see `pyproject.toml` and `.editorconfig`).
* Code is grouped in subpackages of `sellos/`: `access`, `crm`, `telephony`, `intel`, `inventory`, `reports`, `scraper`, `whatsapp` and `billing`. Tests are named `test_*.py` and sit beside the code.
* Each DocType has its own folder under `sellos/sellos/doctype/<name>/` with its JSON, Python file and test.
* Comments cite story IDs such as P1.04, not other ticket schemes.
* The BuildOS conventions are in `docs/buildos-conventions.md`. BuildOS code itself is read only in `~/iespl-baseline/buildos-reference`, never under `apps/buildos`.

## Role model

Platform Admin, Company Admin, Agent, Client and Channel Partner. In code the role names are `SellOS Platform Admin`, `SellOS Company Admin`, `SellOS Agent`, `SellOS Client` and `SellOS Channel Partner`. The web app maps them to areas in `frontend/src/personas.js`. Any change to roles or permissions needs Jayman's approval first.

## CRM data rules (decided by Jayman, P1.06)

* Nothing is deleted. Every CRM record is archived, and `on_trash` refuses a delete for every role.
* Every field of the CRM DocTypes is change tracked.
* The Platform Admin sees no company CRM data by role. Support access is a time limited grant (P1.13, 4 hours).
* Only the Platform Admin may bulk export. No other role has the `export` permission.
* Agents and partners see masked phone numbers. Only a Company Admin sees full numbers (permission level 1 on `phone` and `overseas_phone`).
* A Channel Partner sees only their own leads and those leads' records, read only. They log nothing.

## Secrets

Keys and passwords live in `site_config.json` or environment variables, never in the repository. A gitleaks secret scan (P0.09) runs in pre-commit and in the Linters workflow. Still never commit keys, and check your diff for anything that looks like one. If a story needs a key you do not have, stop and ask Jayman.

## Frontend

See `frontend/CLAUDE.md`. The build plan is in `TASKS.md`, and the earlier brief is in `docs/legacy/`.

## Testing (the gate)

* The build loop (`scripts/build-loop.sh`) picks a task from `TASKS.md`, calls the agent, runs the
  gate `scripts/run-tests.sh` and commits and pushes only if it passes. The agent never runs
  `git commit`, `git push`, `git reset`, `git stash`, `git rebase` or `git merge`, and never changes a
  task's status. There are no git hooks.
* Run only the single backend module and the single Cypress spec you changed, in the foreground:
  `bench --site sellos_test.localhost run-tests --app sellos --module <dotted.path>` and
  `bench --site sellos_test.localhost run-ui-tests sellos --headless --spec cypress/integration/<path>`.
  Never run the whole suite, and never start, stop or restart the bench or any server.
* Read `docs/TESTING.md` and `docs/DEV_STRATEGY.md`. Write backend tests the way the Frappe
  documentation says (`IntegrationTestCase` for the database, `UnitTestCase` otherwise). Tests live
  beside the code. A task also needs a Cypress spec when its block says `Browser spec: required`.
* Never edit a gate file (listed in `docs/TESTING.md`) unless the task block says
  `Gate files: allowed`. Never remove an assertion or delete a test file. Fix a failing test in the
  code, not in the test.
* A task marked `Browser spec: required` also adds its flows to `docs/regression/flows.md`, one line per flow (`FLOW <task id>-<n> | role | start path | steps | expected result`), and adds any data a person sees to `seed_regression_data` in `sellos/tests/ui_fixtures.py` through the production API. Add flows, never remove one. The clickthrough regression milestones (SOS-REG) are run by Claude in chat, not by the loop (`docs/regression/README.md`).
* Fake phone numbers come from `sellos.tests.phones`, never a literal.
* Anything a task creates on a site (users, roles, records, settings) must come from code that can be
  run again safely, and a backend test must read it back. When a task creates a role, add a test user
  for it to `TEST_USERS` in `sellos/testing/users.py`.
* Never state that something exists or works unless a test read it back or the gate output shows it.
  When you report on a task, quote the gate summary line.
* The gate uses only `sellos_test.localhost`. It never touches the main bench or BuildOS.

## Test rules

The gate runs every new or changed test (backend module and Cypress spec) up to five times, and a failure on any run is a failure that must be fixed (SOS-SETUP-33). The runs shrink as a test gets slower: five times when its first run takes under 60 seconds, three under 3 minutes, two above, and the repeats of one gate stop at 10 minutes (SOS-SETUP-34). A slow test is checked fewer times, so keep tests fast. A test that passes four times in five is a race, and a race is fixed in the test or the code, never by a retry, a longer wait or a rerun.

* No real background jobs in tests. Never wait for the bench worker or the scheduler to pick up a job. Call the job's function directly in the test, or run it with `frappe.enqueue(..., now=True)`. The worker is shared with BuildOS, and its timing is not yours.
* Wait on conditions, never on time. No `time.sleep` in a backend test and no `cy.wait(<milliseconds>)` in a spec. Wait for the thing you need: an alias (`cy.wait("@save")`), an element's state (`.should("be.visible")`, `.should("contain", ...)`), or a polled condition with a time limit.
* No shared mutable state. Each test makes its own records, with names unique to it, and restores any setting, user or shared record it changes, even when it fails (`addCleanup`, `after`). Never depend on another test having run first, on test order, or on a record another test made. No module level mutable globals that tests change.
