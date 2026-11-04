# Regression flows

One block per flow, one line each, in exactly this form (five fields separated by `|`):

```
FLOW <task id>-<n> | role | start path | steps | expected result
```

Every task marked `Browser spec: required` adds its flows here. `scripts/check_task_evidence.py` fails
the task unless at least one well formed line names its ID. A task may add flows and may never remove
or change one (`scripts/check_gate_files.py`). A flow is something a person does in a browser, with
the role they would have, starting from a path under `/sellos`. The role is a key of `TEST_USERS`
(`platform_admin`, `company_admin`, `agent`, `channel_partner`, `client`, `basic`) or one of the
regression agents. The steps use the words on the screen. The expected result says what the person
sees, and what must not be there. The clickthrough regression (`docs/regression/README.md`) walks
every flow of the tasks a milestone depends on, against the data `seed_regression_data` makes.

## SOS-P0-10: the web app shell

FLOW SOS-P0-10-1 | agent | /sellos | Sign in. Open the home page. | The home page says "Welcome" and the person's name. The navigation shows Home and Leads, and a sign out button.
FLOW SOS-P0-10-2 | company_admin | /sellos | Sign in. Click Leads in the navigation. | The Leads page opens at /sellos/crm/leads. The navigation shows Home and Leads.
FLOW SOS-P0-10-3 | channel_partner | /sellos | Sign in. Click Leads in the navigation. | The partner Leads page opens at /sellos/partner/leads. The navigation shows Home and Leads.
FLOW SOS-P0-10-4 | platform_admin | /sellos | Sign in. Look at the navigation. | Only Home is shown. No CRM or partner link is shown.
FLOW SOS-P0-10-5 | client | /sellos | Sign in. Look at the navigation. | Only Home is shown. No CRM or partner link is shown.
FLOW SOS-P0-10-6 | basic | /sellos | Sign in as a user with no SellOS role. | The page says "You do not have access to this page". No navigation to the product is shown.
FLOW SOS-P0-10-7 | agent | /sellos/partner/leads | Sign in, then type the partner Leads address in the browser. | The no access page opens. No partner data is shown.
FLOW SOS-P0-10-8 | agent | /sellos | Click the sign out button. Then open /sellos again. | The person is taken to the login page both times, and the session is gone.
FLOW SOS-P0-10-9 | agent | /sellos | Make the window phone width (about 390 px). | The side navigation is replaced by a bottom navigation and a top bar with a sign out button. Nothing scrolls sideways.
FLOW SOS-P0-10-10 | company_admin | /desk | Sign in, then open /desk in the address bar. | The desk does not open. The person sees a refusal or is sent back to the app, never the Frappe desk.

## SOS-P1-06A: the CRM works on a fresh company site

FLOW SOS-P1-06A-1 | company_admin | /sellos/crm/leads | Sign in. Open Leads. Click New lead, type a client name and a phone number, save. | The form closes and the new lead appears in the Leads list. No error is shown.
FLOW SOS-P1-06A-2 | agent | /sellos/crm/leads | Sign in as an agent. Open Leads. | Only the agent's own leads are listed. The page shows the company name, not the web address, in the navigation.
FLOW SOS-P1-06A-3 | client | /sellos/crm/leads | Sign in as a client and type the Leads address. | The no access page opens and no lead is shown.
FLOW SOS-P1-06A-4 | agent | /sellos | Look at the browser tab. | The tab shows the company logo when the company has one, otherwise the SellOS icon. Headings use Syne, text uses DM Sans, and buttons are green (#0f4c35) with amber (#e8954a) for warnings.
