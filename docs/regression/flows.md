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
FLOW SOS-P1-06B-1 | agent | /sellos/crm/leads | Sign in as an agent. Open a lead whose client has a phone number. | The phone shows masked (stars and the last three digits). The full number is nowhere on the page.
FLOW SOS-P1-06B-2 | company_admin | /sellos/crm/leads | Sign in as a company admin. Open the same lead. | The full phone number shows. The number is in the history of changes for no one else.

## SOS-P1-13: support access grants

FLOW SOS-P1-13-1 | company_admin | /sellos/company/support | Sign in. Open Support access. The seeded list shows an active grant for the support user and an ended one. Choose the support user, pick 1 hour, type a reason, click Give access. | A new grant appears at the top with status Active and an end time 1 hour away. The longest choice offered is 4 hours.
FLOW SOS-P1-13-2 | company_admin | /sellos/company/support | Click Show log on a grant. | Each line shows the time, the user and what was done: Granted, then Revoked or Expired, and each request the support user made, with its method and path.
FLOW SOS-P1-13-3 | company_admin | /sellos/company/support | Click End now on an active grant. | The status changes to Revoked at once, the End now button goes, and the log gains a Revoked line.
FLOW SOS-P1-13-4 | agent | /sellos/company/support | Sign in as an agent and type the Support access address. | The no access page opens. No grant is shown.

## SOS-P1-01: the control site

FLOW SOS-P1-01-1 | platform_admin | /sellos/control/tenants | Sign in. Open Companies. The seeded list shows four companies, one each Requested, Provisioning, Active and Failed. Type a tenant ID in lower case letters, a company name and an admin email, then click Create company. | The new company appears at the top with status Requested and its own site name. No error is shown.
FLOW SOS-P1-01-2 | platform_admin | /sellos/control/tenants | On the new company click Move to Provisioning, then Move to Active. | The status shows Provisioning, then Active. An Active company has no Move to button. A Failed company offers only Move to Provisioning.
FLOW SOS-P1-01-3 | platform_admin | /sellos/control/tenants | Type a tenant ID with a capital letter or a space and click Create company. | The company is not created and a clear message says the ID is lower case letters and digits only.
FLOW SOS-P1-01-4 | company_admin | /sellos/control/tenants | Sign in as a company admin and type the Companies address. | The no access page opens. No company is shown and Companies is not in the navigation.
FLOW SOS-P1-01-5 | agent | /sellos/control/tenants | Sign in as an agent and type the Companies address. | The no access page opens. No company is shown.

## SOS-P1-03: the setup wizard

FLOW SOS-P1-03-1 | company_admin | /sellos/company/setup | Sign in. Open Set up your company. The seeded wizard is half done, so it opens on First users and shows the profile, colours and stages steps ticked. Click Pipeline stages. | The default stages are listed in order with their kinds, with at least one Won and one Lost stage.
FLOW SOS-P1-03-2 | company_admin | /sellos/company/setup | On First users type a first name, an email and the role Agent, click Add person, then click Finish setup. | The person appears in the list with the role Agent, then the page says the company is set up.
FLOW SOS-P1-03-3 | company_admin | /sellos/company/setup | Click Logo and colours, choose a PNG logo, pick a brand colour and click Save and continue. Finish the setup and open Home. | The logo and company name show at the top of every screen, buttons use the new colour, and the Finish setting up banner is gone.
FLOW SOS-P1-03-4 | company_admin | /sellos/company/setup | Click Pipeline stages, remove every Won stage and click Save and continue. | The stages are not saved and a clear message says the pipeline needs one Won and one Lost stage.
FLOW SOS-P1-03-5 | agent | /sellos/company/setup | Sign in as an agent and type the setup address. | The no access page opens. No setup data is shown.

## SOS-P1-08: the Consent Record

FLOW SOS-P1-08-1 | agent | /sellos/crm/leads | Sign in as the first Regression agent. Open Regression Buyer One, then Regression Buyer Two. | Buyer One shows the status Consented with one Consent record and no warning. Buyer Two shows Consented with an Inquiry that expires 7 days after it was recorded.
FLOW SOS-P1-08-2 | company_admin | /sellos/crm/leads | Sign in. Open Regression Seller Seven, which has the status Unknown. Choose Application, type a web link as evidence and click Record basis. | An amber Unknown warning shows before, and after saving the status is Consented, the warning goes and the record shows an expiry 3 months away.
FLOW SOS-P1-08-3 | company_admin | /sellos/crm/leads | On Regression Seller Seven, with no records, click Record basis with the evidence box holding only spaces. | The record is refused with a clear message, no record is added and the status stays Unknown.
FLOW SOS-P1-08-4 | agent | /sellos/crm/leads | Sign in as the second Regression agent. Open Regression Buyer Three, then Regression Investor Four. | Buyer Three shows a red Opted out warning with the time and Phone call. Investor Four shows an amber Registered DND warning. Both still let you add a Call activity.
FLOW SOS-P1-08-5 | agent | /sellos/crm/leads | On a Consented lead choose WhatsApp and click Record stop request. | The status becomes Opted out with a red warning naming WhatsApp, and the timeline still accepts a Call, a WhatsApp and an Email.
FLOW SOS-P1-08-6 | channel_partner | /sellos/partner/leads | Sign in as the channel partner and open one of their leads. | The consent status and any warning show, and no Record basis, stop request or DND buttons are offered.
