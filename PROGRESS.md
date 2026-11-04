# SellOS progress

Updated in every commit. Read CLAUDE.md, TASKS.md and this file at the start of each session.

## Done

* P0.01 0045f42 (conventions summary d1f9d25)
* P0.02 9c1331b
* P0.03 ce4a3d1, 19bae4e
* P0.07 33155b2, 7adddcc, d22ba77, c8e1832, 6e3badd (CI and Linters green on 6e3badd; frontend job, smoke check in CI, Semgrep suppression approved by Jayman)
* P0.09 9fcd899 (gitleaks in pre-commit and Linters; a fake key was blocked locally)
* P0.10 be29195, 357da0f, 7a68e5f (CI fixes) (shell, sign out, session watch, branding from SellOS Settings, desk guard)
* P1.04 910ba25, e100a3e, 03cc783 (CI green on 03cc783) (five roles from code, @sellos_api registry and guard, lead permission queries, docs/permissions.md)
* P1.05 eb21d97, 67068b5 (CI green on 67068b5) (permission matrix `sellos/access/matrix.py`, `test_permission_matrix.py`)

* P1.06 (this commit) Client, Lead, Lead Activity, Lead Task and Site Visit DocTypes, `sellos/crm/api.py`, leads pages in the web app, tighter desk guard.

* P0.10 follow up: the desk guard also blocks /desk (Frappe 16's desk path), found while testing Checkpoint A.

## Working on

* Checkpoint A passed. P1.06 done. P0.11 and P1.01 are blocked on P0.06 (N18). Next ready: P1.08, P1.09.

## Blocked

* None.

## Waiting on others

* N07, N09 to N18 and the other N stories (owners Jayman, Counsel, Accountant, AMP Labs).
* P0.04, P0.05, P0.06, P0.08, P0.12 wait on N18 (DigitalOcean decisions).

## Open questions (default chosen)

* P1.05 criterion 2 (no call returns data from another company): each company is its own site and database, so a user of another company cannot sign in here at all. The matrix tests an outsider, who is signed in but holds no role here, and a guest. A real two-site check comes with P1.11 (Pandya Realtors site) and P4/E4 provisioning. The matrix is empty of production methods because none exist yet.

* P1.04 Agents' "own leads" means the lead's owner or its `assigned_to` user, plus Frappe shares. The Lead DocType is named `Lead` and has an `assigned_to` field, to be created by P1.06. Change `sellos/access/lead_permissions.py` if P1.06 names them otherwise.
* P1.04 Frappe's built in Administrator account passes the role check, as everywhere in Frappe. No SellOS role has an override.
* P1.04 permissions touched: look at `sellos/access/` and `docs/permissions.md` before Checkpoint A.

* P0.10 criterion 5 says "customer roles" without naming them. Default: Company Admin, Agent, Client and Channel Partner are redirected from /app to /sellos. Platform Admin and System Manager keep the desk. Change `CUSTOMER_ROLES` in `sellos/access/desk_guard.py` if you want otherwise.
* P0.10 criterion 4 (phone width) is built with a top bar and a bottom nav, but the manual check on a real phone has not been done.
* P0.10 added the SellOS Settings single DocType (company name, logo, brand colour), only System Manager can edit it. The wizard (P1.03) will fill it.
* P0.10 added vitest to the frontend and `yarn test` to CI.

* P0.07 criterion 2 (a failing check blocks the merge): direct pushes to 1.0 cannot be blocked by CI. Default: left as is. It needs a GitHub branch rule set by Jayman, or a decision that it no longer applies.
* The CI concurrency group is keyed on the PR number, so a push to 1.0 cancels the previous push's CI run. Default: left as is.

## P1.06 decisions (Jayman, 2026-11-04)

* Only the Platform Admin may open /desk, control site only. `desk_guard.py` now blocks everyone else, System Manager included. Administrator (the bench login) is exempt.
* The Platform Admin has no company CRM data by role. Support access is P1.13, 4 hour expiry.
* Nothing is deleted, only archived. Everything is change tracked. Only the Platform Admin may bulk export. Agents and partners see masked phones.
* The Channel Partner sees their own leads and those leads' records, read only. Earnings, potential earnings and a personal QR code went to P5.06.
* I added `crm` to the subpackage list in CLAUDE.md. Partners can create and edit their own leads and clients but cannot log activities, tasks or visits (my reading of "see their leads and its activity").
* Not done in P1.06: reveal logging for masked phones, a consent field, project or property records (site visits hold a project name as text), the pipeline stage (P1.07).
* "Callers" masking applies to Agent and Channel Partner. Company Admin sees full numbers.

## Gate waivers used

* SELLOS_NO_TEST_REASON on c8e1832 (semgrep suppression comment only) and 6e3badd (comment order only), both approved edits to scripts/check_tests_changed.py.
