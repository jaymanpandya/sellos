# SellOS permission table

Story P1.04. Every role name is created from code by `sellos/access/roles.py` on install and on
every migrate. Nothing here is set up in the Desk.

## Roles and where they work

| Role | Role name in code | Web app areas | Frappe desk |
| --- | --- | --- | --- |
| Platform Admin | `SellOS Platform Admin` | platform, home, profile | Yes, the only role, control site only |
| Company Admin | `SellOS Company Admin` | company, crm, reports, home, profile | No |
| Agent | `SellOS Agent` | crm, home, profile | No |
| Channel Partner | `SellOS Channel Partner` | partner, home, profile | No |
| Client | `SellOS Client` | client, home, profile | No |

The areas come from `frontend/src/personas.js`. The desk block is `sellos/access/desk_guard.py`.

## Data rules

Sees (CRM data, P1.06): "all" is every record on the site, "own" is the leads the user owns, is assigned, or
has a Frappe share on, plus the records that follow those leads. "None" is nothing.

| Data | Platform Admin | Company Admin | Agent | Channel Partner | Client |
| --- | --- | --- | --- | --- | --- |
| Lead | None, or read only while a support grant is active (P1.13) | All, edit, reassign, archive | Own, edit own | Own, create and edit own | None |
| Client (record) | None | All, full phone | Created by them, or on a lead they can see. Masked phone | Same as Agent | None |
| Activity, Task, Site Visit | None | All, create and edit | Follow the lead, create and edit | Follow the lead, read only | None |
| Delete | Nobody. Records are archived | | | | |
| Bulk export | Yes (`export` permission) | No | No | No | No |
| Change tracking | Every field of all five DocTypes | | | | |
| SellOS Settings | System Manager only (the wizard in P1.03 writes it for the Company Admin) | | | | |

"Own" means the lead's owner or its `assigned_to` user. Sharing uses Frappe's normal share. A shared
lead brings its timeline with it. The rules are in `sellos/access/lead_permissions.py`. Phone numbers
sit at permission level 1, so a direct read (`/api/resource/Client`) gives an Agent or Partner only
`phone_masked`. The Platform Admin's `export` and level 1 rows exist on the DocTypes but give no data
on a company site, because the data scope above is "none".

## API methods

* A method is written with `@sellos_api(<roles>)` from `sellos/access/registry.py`, never with a
  bare `@frappe.whitelist()`.
* The decorator checks the roles on every call.
* A whitelisted method in the `sellos` package that has no declaration is refused with a 403 for
  every user, before it runs (`guard_api`, a `before_request` hook).
* `undeclared_whitelisted_methods()` lists any such method, so the matrix in P1.05 can fail the
  build on it.

| Method | Roles |
| --- | --- |
| `sellos.crm.api.list_clients`, `save_client`, `list_leads`, `get_lead`, `save_lead`, `set_archived` | Company Admin, Agent, Channel Partner |
| `sellos.crm.api.add_activity`, `save_task`, `save_site_visit` | Company Admin, Agent |
| `sellos.access.support.list_support_users`, `grant_support_access`, `revoke_support_access`, `list_support_grants`, `support_access_log` (P1.13) | Company Admin |
| `sellos.access.field_history.getdoc`, `get_docinfo` (P1.06B: the record loader, with the history of fields the reader may not read left out) | Every role |

Each story that adds a method adds a row here.

## API method matrix

`sellos/access/matrix.py` lists the roles for every method. The build fails when the list and the `@sellos_api` declarations disagree, or when a sellos method is whitelisted without a declaration (P1.05).

## The permission test suite (P1.05)

`sellos/access/test_p1_05_permission_suite.py` calls every method in the matrix as each of the five roles,
as a user from another company (on a company's own site, a signed-in user with no role) and as a guest,
against one company's seeded records. It fails the build when a refused caller is not refused, when any
caller other than the Company Admin gets the company's record or a full phone number, when a method has no
matrix entry or no sample arguments, or when a sellos method is whitelisted with no declaration. It runs
in continuous integration with the rest of the backend tests (`bench run-tests --app sellos`).

## Support access grants (P1.13)

The Platform Admin sees no company data by role. A Company Admin gives one support user read access for a
chosen time, from 1 minute to 4 hours (`/sellos/company/support` in the web app, `sellos/access/support.py`).

* While the grant is active the user may read the five CRM DocTypes and nothing else: no write, create,
  share, delete or per record export. `lead_permissions` decides this from the grant, on every call.
  The user keeps the level 1 phone rows the Platform Admin role has, so a support user sees full phone numbers
  while a grant is active. Every request is logged.
* The end is checked on every use: a grant lasts to its expiry, and never more than 4 hours after it started,
  whether or not the scheduler has run. The scheduler (`expire_due_grants`, every tick) marks it Expired.
* Every request the user makes, and each grant, revoke and expiry, is a line in the Support Access Log with the
  user, the time, the method and the path. Grants and log lines are never edited or deleted. A grant's holder and
  length can not change: revoke it and make a new one.
* The Company Admin may read grants and the log (`Support Grant`, `Support Access Log`) and change them only
  through the methods above.
