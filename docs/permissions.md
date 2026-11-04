# SellOS permission table

Story P1.04. Every role name is created from code by `sellos/access/roles.py` on install and on
every migrate. Nothing here is set up in the Desk.

## Roles and where they work

| Role | Role name in code | Web app areas | Frappe desk |
| --- | --- | --- | --- |
| Platform Admin | `SellOS Platform Admin` | platform, home, profile | Yes (control site) |
| Company Admin | `SellOS Company Admin` | company, crm, reports, home, profile | No |
| Agent | `SellOS Agent` | crm, home, profile | No |
| Channel Partner | `SellOS Channel Partner` | partner, home, profile | No |
| Client | `SellOS Client` | client, home, profile | No |

The areas come from `frontend/src/personas.js`. The desk block is `sellos/access/desk_guard.py`.

## Data rules

| Data | Platform Admin | Company Admin | Agent | Channel Partner | Client |
| --- | --- | --- | --- | --- | --- |
| Leads | All on the site | All | Own, assigned, or shared with them | Own, assigned, or shared with them | None |
| SellOS Settings | System Manager only (the wizard in P1.03 writes it for the Company Admin) | | | | |

Leads are the only data rule so far. Each later story that adds a DocType adds its row here and
its rules in code. "Own" means the lead's owner or its `assigned_to` user. Sharing uses Frappe's
normal share. The rules are in `sellos/access/lead_permissions.py` and apply once P1.06 creates
the Lead DocType.

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
| None yet | |

Each story that adds a method adds a row here.
