# SellOS

SellOS is a multitenant real estate platform for Indian agents, built on Frappe 16.x and hosted on DigitalOcean. Pandya Realtors is the first company on it. The AMP Labs builds it, Claude Code writes the code, and Jayman reviews the work on 1.0.

## Where the work is defined

* Tasks.md is the backlog. Work one story at a time, in dependency order, and follow its "Rules for Claude Code".
* KICKOFF.md says how the first week starts.
* docs/legacy/SellOS_Build_Brief_v1.md is the earlier build brief. It is reference material only. Use it for domain field lists such as Project, Unit, Lead, Booking and Payment Schedule when the matching story needs them. Do not follow its phase order, its tenant field approach, or its instruction to create DocTypes in the Desk.

## Architecture decisions

1. One Frappe site and one database per company, at a subdomain of sellos.interactivesoftwares.com, plus a separate control site for the Platform Admin. A company never shares a database with another company.
2. Frappe 16.x without ERPNext. Pin the version.
3. DocTypes, hooks and patches live in the app repositories as code. Never create DocTypes through the Desk.
4. Customers never use the Frappe desk. Every customer feature is built in the SellOS web app, which follows the BuildOS frontend stack, structure and tooling once P0.01 is approved.
5. Every API method is whitelisted, declares its allowed roles, and is covered by the permission test matrix. A method with no declaration is denied.
6. Five roles: Platform Admin, Company Admin, Agent, Client and Channel Partner.
7. A consent check runs before every dial. It has no override for any role.
8. Calls placed from the 022 number are service or transactional only. A promotional call purpose is refused.
9. Secrets live in encrypted settings or environment variables, never in a repository.
10. Never build captcha solving or any bypass of an access control.

## Working rules

* Make one commit per story on the 1.0 branch, with the story ID at the start of the message. Push to 1.0 directly after `pre-commit run --all-files` passes. Do not open pull requests, and never force push.
* Write the tests named in the story's Test criteria with the code. Continuous integration must pass.
* Tick the story's checkbox and update its status in the commit that completes it.
* Do not start a story whose dependencies are not ticked, and do not work on parked stories.
* Do the first story, P0.01, before anything else, and wait for Jayman's written approval of the BuildOS conventions summary.

## Stop and ask Jayman when

* A story needs a secret, account or access you do not have.
* An acceptance criterion is ambiguous.
* A change touches permissions, the consent check, billing or personal data.
* A dependency is blocked, or the plan and this file disagree.

## Commands

Run these from the app folder (`apps/sellos` in the bench). Never start, stop or restart the bench on port 8000. To run SellOS locally use only `bench --site sellos.localhost serve --port 8003`.

* Build the web app: `cd frontend && yarn install && yarn build`
* Build all assets through the bench: `bench build --app sellos`
* Server tests: `bench --site sellos.localhost run-tests --app sellos` (the site needs `allow_tests` set)
* Lint and format: `pre-commit run --all-files` (ruff, prettier, eslint and file checks). Run it before every push.
* Continuous integration runs the same checks on every push to 1.0.

## Frappe 16 conventions

* Python 3.14, tabs for indentation, double quotes, line length 110 (see `pyproject.toml` and `.editorconfig`).
* Code is grouped in subpackages of `sellos/`: `access`, `telephony`, `intel`, `inventory`, `reports`, `scraper`, `whatsapp` and `billing`. Tests are named `test_*.py` and sit beside the code.
* Each DocType has its own folder under `sellos/sellos/doctype/<name>/` with its JSON, Python file and test.
* Comments cite story IDs such as P1.04, not other ticket schemes.
* The BuildOS conventions are in `docs/buildos-conventions.md`.

## Role model

Platform Admin, Company Admin, Agent, Client and Channel Partner. In code the role names are `SellOS Platform Admin`, `SellOS Company Admin`, `SellOS Agent`, `SellOS Client` and `SellOS Channel Partner`. The web app maps them to areas in `frontend/src/personas.js`. Any change to roles or permissions needs Jayman's approval first.

## Secrets

Keys and passwords live in `site_config.json` or environment variables, never in the repository. A gitleaks secret scan (P0.09) runs in pre-commit and in the Linters workflow. Still never commit keys, and check your diff for anything that looks like one. If a story needs a key you do not have, stop and ask Jayman.

## Frontend

See `frontend/CLAUDE.md`. The build plan is in `Tasks.md`, and the earlier brief is in `docs/legacy/`.

## Testing (the gate)

* Run nothing as "done" that the gate has not passed. The git hooks run `scripts/test_all.sh`
  before every commit. Never use `--no-verify`. Never edit the hooks or the scripts to get past a
  failure. Fix the failure.
* Write backend tests the way the Frappe documentation says
  (https://docs.frappe.io/framework-git/testing/overview): `IntegrationTestCase` from
  `frappe.tests` for anything that touches the database, `UnitTestCase` for anything that does
  not, data created in the test class and rolled back by the framework. Read the documentation
  or the Frappe source before inventing a test helper.
* Tests live beside the code: `test_*.py` in the same package, `*.test.js` beside the frontend
  file. A commit that changes code needs a test change in the same commit.
* Anything a story creates on a site (users, roles, records, settings) must come from code that
  can be run again safely, and a backend test must read it back. For users, add them to
  `TEST_USERS` in `sellos/testing/users.py`. The smoke check logs in as each of them over HTTP.
* Never state that something exists or works unless a test read it back or the gate output shows
  it. When you report on a story, quote the gate summary line.
* When a story creates a role, add a test user for it in the same commit.
* The gate uses only the site `sellos_test.localhost` and port 8004. It never touches the main
  bench. `SELLOS_NO_TEST_REASON` is for renames and comments only. List every waiver you use in
  PROGRESS.md.
