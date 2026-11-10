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
| Lead | None (support grant only, P1.13) | All, edit, reassign, archive | Own, edit own | Own, create and edit own | None |
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
| `sellos.access.field_history.getdoc`, `get_docinfo` (P1.06B: the record loader, with the history of fields the reader may not read left out) | Every role |

Each story that adds a method adds a row here.

## API method matrix

`sellos/access/matrix.py` lists the roles for every method. The build fails when the list and the `@sellos_api` declarations disagree, or when a sellos method is whitelisted without a declaration (P1.05).
