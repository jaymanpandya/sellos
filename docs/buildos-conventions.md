# BuildOS conventions

Story P0.01. Status: draft for Jayman's approval.

This summary comes from a snapshot of the BuildOS repository: the first 400 file names, the configuration files, both workflow files, and the frontend entry files. Section 8 lists what was not seen. Every point names the file it comes from.

## 1. Repository layout

* A Frappe app named `buildos`. The Python package is `buildos/`, with the Frappe module folder `buildos/buildos/` inside it.
* Top level modules sit beside the packages: `buildos/adopted_settings.py`, `buildos/adoption.py`, `buildos/backups.py`.
* Cross cutting code lives in subpackages with tests beside the code: `buildos/access/` (api, audit, document, guard, registry, retired_role) and `buildos/accounting/` (connectors, invoicing, ledger, oauth, payments, payroll, testing).
* Each DocType has its own folder under `buildos/buildos/doctype/<name>/` holding `<name>.json`, `<name>.py`, an optional `<name>.js`, and `test_<name>.py`. Larger DocTypes split helpers into extra modules in the same folder, for example `bill/bill_allocation.py` and `bill/bill_reading.py`. Test fixtures sit in a `test_fixtures/` folder next to the tests.
* Tests are named `test_*.py` and live beside the code they test. The access package has one test file per role group: admin support, calling, every role, portal, sales and site.
* The frontend is a separate `frontend/` folder at the repository root, built into the app (section 4).
* Process documents sit at the root: `TASKS.md`, `QUEUE.md`, `NOTES.md` and `MANUAL_QA_CHECKLIST.md`. Comments cite ticket IDs of the form BOS followed by a number, for example BOS-276 in `pyproject.toml` and BOS-206 in `frontend/src/App.vue`.

## 2. Backend tooling

* **Packaging** (`pyproject.toml`): `flit_core` build backend, `requires-python = ">=3.14"`, Frappe installed and managed by bench, one runtime dependency, `anthropic>=2.1,<3`.
* **Ruff** (`pyproject.toml`): line length 110, target `py314`, rules F, E, W, I, UP, B and RUF, with a long list of ignores that suit Frappe code. Format with tab indentation and double quotes.
* **Editor settings** (`.editorconfig`): tabs with size 4 for Python, JavaScript, Vue, CSS, SCSS and HTML, maximum line length 99, LF endings, trailing whitespace trimmed. JSON uses one space indent and no final newline.
* **Pre commit** (`.pre-commit-config.yaml`): trailing whitespace (excluding JSON, text, CSV, Markdown and SVG), merge conflict, Python AST, JSON, TOML and YAML checks, debug statements, ruff (import sorter, linter and formatter, v0.14.10), prettier 2.7.1 for JavaScript, Vue and SCSS, and eslint 8.44.0 for JavaScript. Prettier reads `.editorconfig`, so the tab and 99 column settings apply to the frontend too.
* **ESLint** (`.eslintrc`): `eslint:recommended`, browser and Node environment, ES2022, and a long list of Frappe desk globals. Console use is a warning.

## 3. Continuous integration

* **CI** (`.github/workflows/ci.yml`): runs on pushes to the `v1` branch and on every pull request. It starts MariaDB 11.8 and two Redis containers, sets up Python 3.14 and Node 24, runs `bench init`, `bench get-app`, `bench new-site`, `bench install-app` and `bench build`, then `bench run-tests` for the app. It first checks that at least one `def test` exists.
* **Linters** (`.github/workflows/linter.yml`): on pull requests it runs the pre commit action, then Frappe's Semgrep rules, then `pip-audit` in a separate job.
* The README says CI runs on the `develop` branch, but the workflow uses `v1`. The workflow is the one that runs.
* There is no frontend lint, test or type check in either workflow. `frontend/package.json` defines only `dev`, `build` and `preview`.

## 4. Frontend

* **Stack** (`frontend/package.json`): Vue 3.5, Vue Router 4.6, `frappe-ui` 0.1.278 with `reka-ui` 2.10, Dexie 4 for offline storage, `pdfjs-dist` 4.10.38. Dev tools are Vite 5.4, `@vitejs/plugin-vue` 5.2, Tailwind 3.4, PostCSS and Autoprefixer. It is plain JavaScript with ES modules, not TypeScript.
* **Build** (`frontend/vite.config.js`): the `frappe-ui` Vite plugin with `frontendRoute` set to `/buildos`, the Frappe proxy on, and boot data passed to the page through Jinja. The build goes into `buildos/public/frontend`, served at `/assets/buildos/frontend/`, and `index.html` is copied to `buildos/www/buildos.html`, which serves every path under `/buildos`. The route must match `buildos.spa.SPA_ROUTE` and `website_route_rules` in `hooks.py`. A small plugin writes the company name and logo icons into the page title and tab icons on the server.
* **Styling** (`frontend/tailwind.config.js`, `frontend/postcss.config.js`): the `frappe-ui` Tailwind preset, with colours, fonts, font sizes, spacing and radii imported from `src/theme/tokens.js`, and CSS variables added to `:root`.
* **Start up** (`frontend/src/main.js`): set the `frappe-ui` resource fetcher to the app's `apiRequest`, load the session before mounting, install `FrappeUI` with sockets off and the router, mount, then start the offline outbox that resends queued work when the connection returns.
* **Shell** (`frontend/src/App.vue`): an `AppShell` around a router view with a page transition, plus a global `AppDialogs` component.
* **Routing** (`frontend/src/router.js`): every page is lazy loaded from `src/pages/`. Platform administration pages live in `src/pages/platform/`: clients, companies, billing, coupons, audit log, updates, health, backups, support and team. Routes use `personas.js` (`personaFor`, `routeArea`, `inAreas`, `navLabel`), so each role sees only its own areas.
* **Supporting files named in imports:** `src/api.js`, `src/session.js`, `src/personas.js`, `src/theme/tokens.js`, `src/offline/outbox.js`, `src/components/AppShell.vue` and `src/components/AppDialogs.vue`.

## 5. Platform features already in BuildOS

The file list shows BuildOS already has working versions of things SellOS needs. These are candidates to read and reuse in the matching stories (read them only in the read only copy `~/iespl-baseline/buildos-reference`, never under `apps/buildos`; SOS-SETUP-21), and none has been inspected yet:

* **Access control** (`buildos/access/`): a registry, a guard, an audit module, a retired role module, and tests per role group. This is the model for the permission matrix in P1.04 and P1.05.
* **Platform administration:** `Platform Settings`, `Platform Billing Setting` and `Platform Coupon` DocTypes, and the platform pages above. These relate to E12 and the control site in E4.
* **Calling:** `Call Log`, `Call Media Access` and `Call Note` DocTypes, plus the calling pages and calling role tests. These relate to E6.
* **Leads:** `Lead Event`, `Lead Import Batch` with a wizard, `Lead Automation`, quotations and reminders. These relate to E5.
* **Privacy and backups:** `Privacy Request`, `Privacy Compliance Setting`, `buildos/backups.py` and an `Offsite Backup Status` DocType. These relate to P1.14.
* **Help articles** shown by role.

## 6. What the SellOS shell copies

The `frontend/` folder delivered with this summary copies sections 2 and 4: the same package names and versions, the same Vite, Tailwind and PostCSS setup, the same start up order, and role based routing through `personas.js`. It differs in these ways:

* The route is `/sellos`, the build goes to `sellos/public/frontend`, and `index.html` goes to `sellos/www/sellos.html`.
* The five SellOS roles replace BuildOS's personas.
* Colours are CSS variables, so each company can set its own brand. SellOS defaults: #0f4c35 brand, #2a7a5a brand-mid, #e8954a accent, Syne headings, DM Sans body.
* Dexie, `pdfjs-dist`, the offline outbox and the tab icon plugin are left out until a story needs them.

## 7. Differences recommended for SellOS

1. Add a frontend job to CI: lint, format check and a test runner, because BuildOS has none.
2. Use SellOS story IDs where BuildOS uses ticket IDs, so comments say, for example, P1.04 instead of BOS-276.
3. Keep the SellOS branch name `1.0` in both workflows. They already use it.
4. Keep the same Python version, ruff settings, pre commit hooks and CI services, which the SellOS scaffold already matches.

## 8. Not seen

* Only the first 400 file names were captured, and 105 of those lines were hidden in the display, so the frontend `src/pages` and `src/components` folders are not listed. Files cited above come from imports and the config files.
* `buildos/hooks.py`, `buildos/spa.py`, `buildos/www/buildos.py`, `buildos/setup.py`, and the contents of `api.js`, `session.js`, `personas.js`, `tokens.js`, `AppShell.vue` and the offline outbox were not seen.
* Whether `buildos/www/buildos.html` and `buildos/public/frontend` are committed or ignored was not seen. Check `.gitignore` before committing built files in SellOS.

## 9. Approval

Jayman approves this summary before P0.02 and P0.10 continue. Items to confirm: the placeholder colours, the five role names in `personas.js`, and whether any of section 5 should be reused directly.
