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
7. A consent check runs before every dial. It has no override for any role.
8. Calls placed from the 022 number are service or transactional only. A promotional call purpose is refused.
9. Secrets live in encrypted settings or environment variables, never in a repository.
10. Never build captcha solving or any bypass of an access control.

## Working rules

* The build loop makes one commit per task on the 1.0 branch, with the task ID at the start of the message, and pushes to 1.0 after the gate passes. The agent leaves its work uncommitted. Do not open pull requests, and never force push.
* Write the tests named in the story's Test criteria with the code. Continuous integration must pass.
* The loop sets a task's status in TASKS.md (In Progress, Complete, Blocked). The agent never changes one.
* Do not start a task whose dependencies are not Complete, and do not work on Parked tasks.

## Stop and ask Jayman when

* A story needs a secret, account or access you do not have.
* An acceptance criterion is ambiguous.
* A change touches permissions, the consent check, billing or personal data.
* A dependency is blocked, or the plan and this file disagree.

## Commands

Run these from the app folder (`apps/sellos` in the bench). Never start, stop or restart the bench on port 8000. To run SellOS locally use only `bench --site sellos.localhost serve --port 8003`.

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
* The BuildOS conventions are in `docs/buildos-conventions.md`.

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
  Never run the whole suite, and never start, stop or restart the bench.
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
