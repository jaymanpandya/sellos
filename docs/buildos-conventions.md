# BuildOS conventions

Story SOS-P0-01. Status: ready for Jayman's written approval.

This summary was written by reading the BuildOS source in the read only reference copy at `~/iespl-baseline/buildos-reference` (SOS-SETUP-21). Every path below is the BuildOS path, relative to the root of that copy. Nothing under `apps/buildos` was read. Section 10 lists what was not read in full, and section 11 lists five claims for the spot check.

## 1. Repository layout

* One Frappe app, `buildos`, on one branch (`v1`). The Python package is `buildos/`, with the module folder `buildos/buildos/` inside it. `pyproject.toml` names the project, `buildos/modules.txt` lists the one module, `buildos/hooks.py` is the hook file.
* Top level docs and scripts: `README.md`, `TASKS.md` (the backlog), `QUEUE.md` (generated from `TASKS.md`, "do not edit by hand"), `NOTES.md` (dated decisions per ticket), `MANUAL_QA_CHECKLIST.md`, `docs/`, `scripts/`, `deploy/`, `cypress/`, `frontend/`.
* Cross cutting code lives in subpackages of `buildos/`, with tests beside the code: `buildos/access/`, `buildos/accounting/`, `buildos/calling/`, `buildos/compliance/`, `buildos/documents/`, `buildos/integrations/`, `buildos/notifications/`, `buildos/onboarding/`, `buildos/security/`, `buildos/setup/`. Platform (control site) code is flat modules named `buildos/platform_*.py`, plus `buildos/control_site.py`, `buildos/provisioning.py`, `buildos/tenant_lifecycle.py`.
* Each DocType has a folder `buildos/buildos/doctype/<name>/` with `<name>.json`, `<name>.py` and `test_<name>.py`. Larger ones add helper modules in the same folder (for example `bill_allocation.py`, `bill_reading.py`; `task/task_moves.py`).
* Tests are `test_*.py` beside the code (for example `buildos/access/test_guard.py`, `buildos/security/test_mfa.py`, `buildos/setup/test_install.py`). `buildos/access/` has one test file per role group (`test_calling_roles.py`, `test_sales_roles.py`, `test_site_roles.py`, `test_portal_roles.py`, `test_every_role.py`).
* Website pages that are not the web app sit in `buildos/www/` as an `.html` plus `.py` pair (`forgot-password.html`, `forgot_password.py`, `two-step-setup.html`).
* Comments cite ticket IDs `BOS-<number>` (`buildos/spa.py`, `buildos/hooks.py`). SellOS cites story IDs such as P1.04 instead.

## 2. App structure and hooks

* **Hooks** (`buildos/hooks.py`): `app_name`, `app_title`, `app_publisher` and licence (MIT) at the top; `website_route_rules` sends `/buildos/<path:app_path>` to the `buildos` page; `get_website_user_home_page` and `website_redirects` send users to their app home; `after_install` points at `buildos/setup/install.py`; `after_migrate` runs a list of idempotent ensure functions (roles, MFA, branding, archive fields, retention, control site role); `before_tests` (`buildos.tests.legacy_role.before_tests`); `scheduler_events` use cron entries (`*/15`, `*/5` and every minute).
* **Permissions as hooks** (`buildos/hooks.py`): one `has_permission` entry for `"*"` plus per DocType entries, `permission_query_conditions`, `doc_events` for `"*"` (tier edit limits, read only support access, audit trail), `before_request`, `before_login`, `on_login` and `after_request` (`buildos.access.guard.strip_money`). Control site only DocTypes are refused on company sites by `buildos.control_site.has_permission` (`buildos/hooks.py`).
* **Access model as data** (`buildos/access/registry.py`): roles, areas, scopes (All, Own, Assigned) and actions are written once as pure data. `docs/ACCESS_MODEL.md` is generated from it by `buildos/access/document.py`, and `buildos/access/test_registry.py` fails when the two differ or when a business DocType or whitelisted endpoint belongs to no area. `buildos/access/guard.py` enforces it on every request. This is the model for SellOS's permission test matrix (P1.04, P1.05).
* **Install and seed data** (`buildos/setup/install.py`): default pipeline stages, cost structure and similar starter data, each written so it can run again.
* **Patches** (`buildos/patches.txt`, `buildos/patches/v1_0/`): `[pre_model_sync]` and `[post_model_sync]` sections, one module per patch, named for what it does (`create_default_pipeline_stages.py`, `backfill_lead_assigned_to.py`).
* **Custom bench commands** (`buildos/commands.py`): click commands such as `buildos-security-check`; the provisioning and lifecycle commands are dry runs unless `--execute` is given (`deploy/site-state/README.md`, `buildos/provisioning.py`).
* **One site per company** (`buildos/provisioning.py`, `buildos/control_site.py`, `buildos/tenant_lifecycle.py`): the Platform Admin works on a control site, which provisions, suspends, resumes and offboards each company's own site. This matches SellOS decision 1.

## 3. Python tooling

* **Packaging** (`pyproject.toml`): `flit_core` backend, `requires-python = ">=3.14"`, Frappe left to bench (a comment), one runtime dependency (`anthropic>=2.1,<3`).
* **Ruff** (`pyproject.toml`): line length 110, target `py314`, a `select` list and a long `ignore` list suited to Frappe code.
* **Editor** (`.editorconfig`): LF, final newline, tabs of size 4 for `*.py`, `*.js`, `*.vue`, `*.css`, `*.scss`, `*.html`, maximum line length 99; JSON uses one space and no final newline.
* **Pre commit** (`.pre-commit-config.yaml`): pre-commit-hooks v6.0.0 (trailing whitespace, merge conflict, AST, JSON, TOML, YAML, debug statements), then ruff v0.14.10 as import sorter, linter and formatter. `README.md` also lists eslint and prettier and `.eslintrc` exists, but the config file shown runs only the hooks above plus ruff.
* **Fake phone numbers** (`docs/TESTING.md`, `buildos/tests/phones.py`, `buildos/tests/test_no_raw_phone_numbers.py`): tests take numbers from a helper, and a test scans every test file and spec for hand written numbers. SellOS keeps this rule through `sellos.tests.phones`.

## 4. Continuous integration

* **CI** (`.github/workflows/ci.yml`): runs on pushes to `v1` and on every pull request, with a concurrency group that cancels older runs. Services: MariaDB 11.8 and two Redis containers (ports 13000 and 11000). Steps: check that a `def test` exists, Python 3.14, Node 24, pip and yarn caches, `pip install frappe-bench`, `bench init`, `bench get-app`, `bench setup requirements --dev`, `bench new-site test_site`, `bench install-app`, `bench build`, then `set-config allow_tests true` and `bench run-tests --app buildos`.
* **Linters** (`.github/workflows/linter.yml`): on pull requests, the pre commit action, then Semgrep with the Frappe rules (`frappe/semgrep-rules`) and `r/python.lang.correctness`; a second job runs `pip-audit`.
* `README.md` says CI runs on `develop`; the workflow says `v1`. The workflow is what runs.
* Neither workflow lints, tests or builds `frontend/`. `frontend/package.json` has no test or lint script.

## 5. Bench, build and deployment

* **Local gate** (`scripts/run-tests.sh`): restores a clean test site snapshot, rebuilds the web app only when `frontend/` changed (a fingerprint of the tree), runs `bench migrate`, runs the changed test modules and specs, then the affected ones, rerunning each failed spec once alone. `BUILDOS_GATE=full` (`scripts/full-gate.sh`) runs everything.
* **Build loop** (`scripts/build-loop.sh`, `scripts/select-next-task.sh`, `scripts/set-task-status.sh`, `scripts/watchdog.sh`, `scripts/notify-telegram.sh`): picks the next Not Started task from `TASKS.md`, calls `claude -p`, runs the gate, then marks Complete, commits and pushes, or marks Blocked and stops. Nothing new starts while any task is Blocked. A lock file prevents two loops.
* **Production runbook** (`docs/DEPLOY.md`): Ubuntu 24.04 droplet, MariaDB 11.8 from MariaDB's repository, Node 24 from NodeSource, `uv` Python 3.14, bench installed with `uv tool`, a read only deploy key, web app built on the server (section 11, because build output is not committed), `bench new-site` then `install-app`, `bench setup supervisor` and `bench setup nginx` by hand because `bench setup production` fails, certbot, TLS 1.3 only, the scheduler, MFA and Brevo email. The page records which framework release the tests ran on versus production.
* **Operations** (`deploy/`): `deploy/backup/` (per client backups kept 14 deep, offsite copy, restore check), `deploy/site-state/` (suspend, resume, offboard, dry run unless `--execute`), `deploy/security/` (`nginx-tls13.conf`, `mariadb-encryption.cnf`). `scripts/update-server.sh` updates a server; the rollback steps (go back to the recorded commit, restore the database taken before) are written in `docs/DEPLOY.md` section 22.3, not in the script.
* **Secrets** (`docs/DEPLOY.md` placeholders section, `deploy/backup/README.md`): never in the repository; storage keys sit in a file under `~/.config/buildos/` outside `apps` and `sites`, which the scripts refuse if other users can read it.
* **Ignored build output** (`.gitignore`): `buildos/public/frontend/`, `buildos/www/buildos.html`, `frontend/auto-imports.d.ts` and `frontend/components.d.ts` are not committed.

## 6. Frontend

* **Stack** (`frontend/package.json`): Vue ^3.5, Vue Router ^4.6, `frappe-ui` ^0.1.278, `reka-ui` ^2.10, Dexie ^4.4 (offline outbox), `pdfjs-dist` 4.10.38; dev: Vite ^5.4, `@vitejs/plugin-vue`, Tailwind ^3.4, PostCSS, Autoprefixer. Plain JavaScript, ES modules, no TypeScript. Scripts: `dev`, `build`, `preview` only.
* **Build** (`frontend/vite.config.js`): the `frappe-ui/vite` plugin with `frontendRoute: "/buildos"`, `frappeProxy: true`, `jinjaBootData: true`; output to `buildos/public/frontend`, `index.html` to `buildos/www/buildos.html`, base URL `/assets/buildos/frontend/`; `@` aliases `src`. A small plugin in the same file swaps the page title and tab icons for server rendered values (`buildos/setup/tab_icons.py`).
* **Serving the page** (`buildos/www/buildos.py`, `buildos/spa.py`): `no_cache`, guests redirected to `/login?redirect-to=...`, and `get_boot()` puts `csrf_token`, `base`, `site_name` and the session on `window` before the app starts. `SPA_ROUTE` must match `frontendRoute` and `website_route_rules`. Only the Super Admin reaches `/desk`; everyone else is sent to their app home (`buildos/spa.py` module docstring). This matches SellOS decision 4.
* **API calls** (`frontend/src/api.js`): every request carries `X-Frappe-Site-Name` set from the boot data, because the browser hostname need not be the site name. `postKeepalive` sends a request that survives a page reload.
* **Session and personas** (`frontend/src/session.js`, `frontend/src/personas.js`): `session` is a reactive object filled from the boot data; `PERSONAS` holds each persona's home and nav list, and nav items carry an `area` shown only when the person's roles give it. The app only hides things; the server still decides (`buildos/spa.py` docstring).
* **Start up** (`frontend/src/main.js`): set the `frappe-ui` resource fetcher to `apiRequest`, load the session, create the app, install `FrappeUI` (sockets off) and the router, mount, then start the offline outbox.
* **Routing and pages** (`frontend/src/router.js`, `frontend/src/pages/`, `frontend/src/components/`): pages are `*Page.vue`, lazy loaded; shared pieces are in `components/` (`AppShell.vue`, `AppDialogs.vue`, `Drawer.vue`).
* **Offline** (`frontend/src/offline/outbox.js`): an IndexedDB outbox queues a fixed list of actions with a `client_ref` so a resend never makes a record twice, sends oldest first, and keeps refused actions marked Not Sent.
* **Frontend tests** (`frontend/tests/dialerProtocol.test.mjs`): one Node test file run by hand with `node --test`; it is not wired into CI.

## 7. Styling

* **Tokens** (`frontend/src/theme/tokens.js`): the single source for `colors` (ten step scales for primary, secondary, accent, warning, error, success and neutral), font families, font sizes, spacing and radii. Its header says components use these and never raw values.
* **Tailwind** (`frontend/tailwind.config.js`): the `frappe-ui` preset, content globs over `src` and `frappe-ui` components, the token objects added under `theme.extend`, and a plugin that writes the CSS variables into `:root`. `frontend/postcss.config.js` is Tailwind plus Autoprefixer.
* **Entry CSS** is `frontend/src/index.css`, imported by `frontend/src/main.js`. The sign in page has its own stylesheet, `buildos/public/css/login.css`, loaded by `web_include_css` in `buildos/hooks.py`.
* **Branding** (`buildos/setup/tab_icons.py`, `buildos/setup/branding.py`): the tab title and icons are the company's, made from its logo on save, never the framework's. The control site shows none of a company's branding.

## 8. Testing approach

* **Backend** (`.github/workflows/ci.yml`, `docs/TESTING.md`): `bench run-tests --app buildos` on a site with `allow_tests`; tests beside the code; fixtures in `buildos/tests/` (`ui_fixtures.py`, `phones.py`, `site_state.py`, `platform_flow.py`).
* **Browser** (`cypress/README.md`, `cypress.config.js`): Cypress through `bench --site <site> run-ui-tests buildos --headless [--spec ...]`; specs are `cypress/integration/<area>/<flow>.cy.js`; the task ID goes in the top level `context()` title; no test isolation; 20 second command timeout; viewport 1400 by 960.
* **Selectors** (`cypress/README.md`, `cypress/support/commands.js`): `data-testid="buildos-<area>-<thing>"` read with `cy.getByTestId("<area>-<thing>")`; never layout classes, nth-child or visible label text. User facing text must never contain internal framework names.
* **Server side helpers for specs** (`cypress/support/commands.js`, `buildos/tests/ui_fixtures.py`): `cy.bench(...)` runs a helper with `bench execute`. Helpers are not whitelisted and refuse to run without `allow_tests`. Specs create their own uniquely named records and sign in with `cy.loginAsAdmin()` and `cy.loginWithCode(...)`.
* **Regression** (`docs/regression/BOS-206.md`): a written full pass, with the commit and the log, recorded per milestone.

## 9. Changes Frappe 16 and SellOS need

1. **Branch and CI**: BuildOS uses `v1`; SellOS uses `1.0` in both workflows (CLAUDE.md). Keep Python 3.14, MariaDB 11.8, Node 24, the two Redis services and the same pre commit hooks (`.github/workflows/ci.yml`, `.pre-commit-config.yaml`).
2. **Frontend checks in CI**: BuildOS has none (`.github/workflows/ci.yml`, `frontend/package.json`). SellOS adds a frontend job for build, lint, format and unit tests.
3. **Pre commit**: `.pre-commit-config.yaml` has no prettier, eslint or secret scan, although `README.md` names them. SellOS runs ruff, prettier, eslint, file checks and gitleaks (P0.09).
4. **Tenancy**: BuildOS creates one site per client from a control site (`buildos/provisioning.py`). SellOS keeps this, with the subdomain scheme and the narrow database provisioner account (SOS-SETUP-18), never the MariaDB root account that `docs/DEPLOY.md` step 12 uses.
5. **Roles**: BuildOS has access tiers and a long list of roles (`buildos/permissions.py`, `buildos/access/registry.py`). SellOS has six roles with `SellOS` prefixed names (the Sales Manager since SOS-SETUP-35), and any change needs Jayman's approval (CLAUDE.md).
6. **Build output**: not committed in either (`.gitignore`), so the gate and the deployment build the web app (`scripts/run-tests.sh`, `docs/DEPLOY.md` section 11).
7. **Production setup**: `bench setup production` failed for BuildOS on Ubuntu 24.04 with a uv installed bench (`docs/DEPLOY.md` section 14). SellOS follows the supervisor and nginx route and records any Frappe 16 change found at P0.04. The runbook also notes the nginx `main` log format fix.
8. **Names and ports**: route `/sellos`, build to `sellos/public/frontend`, page `sellos/www/sellos.html`; SellOS runs on port 8004 with `--site sellos_test.localhost`, where BuildOS's `cypress.config.js` assumes `test_site:8000`.
9. **Test fixtures**: the SellOS equivalents are `sellos.tests.phones` and `sellos/testing/users.py` (`TEST_USERS`); the phone helper is Indian, where BuildOS's is Australian (`docs/TESTING.md`).
10. **Customer facing text**: no framework names in any label or error. BuildOS states the same rule (`cypress/README.md`), and `frontend/src/api.js` shows why the site header matters on tenant subdomains.
11. **Theming**: BuildOS colours are fixed tokens (`frontend/src/theme/tokens.js`). SellOS uses CSS variables so each company can set a brand colour.
12. **Keep out until a story needs them**: Dexie and the outbox (`frontend/src/offline/outbox.js`), `pdfjs-dist`, and the tab icon plugin (`frontend/vite.config.js`).

## 10. Not read in full

* Only the head of `buildos/hooks.py`, the hook names and the `after_migrate`, `scheduler_events` and permission blocks were read, not every entry of its 624 lines. `buildos/permissions.py`, `buildos/access/guard.py`, `frontend/src/router.js`, `AppShell.vue` and the page files were located but not read line by line.
* The `ignore` list in `pyproject.toml` was not copied here. SellOS's own `pyproject.toml` is the working copy.
* `docs/DEPLOY.md` sections 1 to 10 and 13 to 22 were read by heading and in part, not every command.

## 11. Spot check

Five claims to check against the reference copy:

1. `buildos/hooks.py` has `website_route_rules` mapping `/buildos/<path:app_path>` to `buildos` (line 95).
2. `.github/workflows/ci.yml` runs on pushes to `v1` and uses `mariadb:11.8`.
3. `frontend/package.json` has only the `dev`, `build` and `preview` scripts.
4. `cypress/README.md` says selectors use `data-testid="buildos-<area>-<thing>"` through `cy.getByTestId`.
5. `.gitignore` lists `buildos/public/frontend/` and `buildos/www/buildos.html`.

## 12. Approval

Jayman approves this summary in writing before P0.02 and the stories that depend on P0.01 go on. Items to confirm: section 9 items 2, 3 and 11, and whether any BuildOS feature in the platform modules (`buildos/platform_*.py`, `buildos/calling/`, `buildos/access/`) should be reused directly in a later story.
