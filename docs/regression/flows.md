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

## SOS-P1-15: what each buyer wants

FLOW SOS-P1-15-1 | agent | /sellos/crm/leads | Sign in as the first Regression agent. Open Regression Buyer One. | The Requirements card shows a budget range in rupees, the configurations 2 BHK and 3 BHK, the property type Apartment, the localities Andheri West and Powai, the purpose End use, the timeline Within 3 months and the possession Under construction.
FLOW SOS-P1-15-2 | agent | /sellos/crm/leads | Open Regression Buyer Two. Choose the configuration 1 BHK and the timeline Immediate, type Bandra in the locality box and a budget from that is higher than the budget to, then click Save requirements. | The card is refused with the message that the budget from cannot be above the budget to, and nothing is saved. Lower the budget from and save: the card shows what was entered.
FLOW SOS-P1-15-3 | agent | /sellos/crm/leads | On the leads list type Powai in the locality filter, then choose 3 BHK in the configuration filter, then the timeline Within 3 months, then a budget range. | Each filter narrows the list to leads that match every filter chosen. Regression Buyer One stays in the list. Clearing the filters brings the agent's other leads back.
FLOW SOS-P1-15-4 | company_admin | /sellos/crm/leads | Sign in as the Company Admin and open Regression Buyer One. Change the timeline to Over 6 months and save. | The change saves, and the change history of the lead holds the old and the new timeline.
FLOW SOS-P1-15-5 | channel_partner | /sellos/partner/leads | Sign in as the channel partner and open one of their leads. | The Requirements card shows what is recorded and has no Save requirements button.

## SOS-P1-16: duplicates

FLOW SOS-P1-16-1 | agent | /sellos/crm/leads | Sign in as the first Regression agent. Click New lead, type any name, type regression_buyer_two@example.com in the email box and click Save lead. | An amber warning says the person is already in SellOS, shows Regression Buyer Two with its lead and a masked phone, and offers Add this enquiry to Regression Buyer Two and Save as a new client anyway. No full phone number shows anywhere.
FLOW SOS-P1-16-2 | agent | /sellos/crm/leads | From that warning click Add this enquiry to Regression Buyer Two. | A new lead opens on Regression Buyer Two, and the leads list shows two leads for that client. No second client was made.
FLOW SOS-P1-16-3 | agent | /sellos/crm/leads | Click New lead, type regression_buyer_three@example.com in the email box and click Save lead. | The warning says the person belongs to another agent, shows no name, no email, no leads and only a masked phone, and offers no button to add to that client. Save as a new client anyway is still there.
FLOW SOS-P1-16-4 | agent | /sellos/crm/leads | Click New lead, type a new name and an email nobody has, and click Save lead. | No warning shows and the lead is saved.
FLOW SOS-P1-16-5 | company_admin | /sellos/crm/leads | Sign in as the Company Admin and open the lead of Regression Twin A. Under Merge a duplicate client choose Regression Twin B and click Merge into Regression Twin A. | The page says Merged with the number of leads moved. The leads list now shows both twin leads under Regression Twin A, each with its activity, and Regression Twin B is no longer in the merge choices.
FLOW SOS-P1-16-6 | agent | /sellos/crm/leads | Sign in as the agent and open any lead. | There is no Merge a duplicate client section.

## SOS-P1-20: lead sources

FLOW SOS-P1-20-1 | agent | /sellos/crm/leads | Sign in as the first Regression agent. Click New lead and open the Source box. | The box lists Website, Portal, Referral, Walk in, Channel partner, Facebook, Missed call, Bought list and Regression Roadshow. Regression Old Hoarding is not there, and there is no Add a source box.
FLOW SOS-P1-20-2 | agent | /sellos/crm/leads | Fill a new name, choose Referral as the source, type Diwali 2026 hoardings as the campaign and click Save lead. | The lead is saved and opens. The leads list shows it with Referral and Diwali 2026 hoardings under the client name.
FLOW SOS-P1-20-3 | company_admin | /sellos/crm/leads | Sign in as the Company Admin and click New lead. Type Regression Open House in Add a source to the list and click Add source. | Regression Open House is added to the Source box and is chosen at once. Saving a lead with it shows Regression Open House on the leads list, and the first agent now sees it in the box too.
FLOW SOS-P1-20-4 | company_admin | /sellos/crm/leads | Look at the leads list. | Regression Buyer Three shows Regression Roadshow and Diwali 2026 hoardings. Seller Seven shows Missed call and the two partner leads show Channel partner.

## SOS-P1-07: the buyer pipeline

FLOW SOS-P1-07-1 | agent | /sellos/crm/leads | Sign in as the first Regression agent. Look at the leads list, then open Regression Buyer One and open the stage box. | The list shows each lead's stage, with Regression Buyer One on Qualified and Regression Buyer Two on Site visit booked. The stage box lists the 11 stages in this order: New, Consent pending, Contacted, Qualified, Site visit booked, Site visit done, Negotiation, Booking, Closed won, Closed lost, Nurture.
FLOW SOS-P1-07-2 | agent | /sellos/crm/leads | On Regression Buyer One (status Consented, now on Qualified) choose Contacted in the stage box. | The lead moves to Contacted and no warning shows. The stage log has a line Qualified to Contacted with no warning, above the seeded lines New to Contacted and Contacted to Qualified.
FLOW SOS-P1-07-3 | agent | /sellos/crm/leads | Sign in as the second Regression agent and open Regression Investor Four (Registered DND). | Investor Four is on Contacted with an amber warning that it is on Contacted without a live Consent Record and is on the do not call list. The stage log line New to Contacted carries the same warning.
FLOW SOS-P1-07-4 | agent | /sellos/crm/leads | Sign in as the second Regression agent and open Regression Buyer Three (Opted out), then choose Negotiation and then Closed lost in the stage box. | Buyer Three starts on Contacted with a red warning. Both moves go through with no refusal, the warning goes once the lead leaves Contacted, and the stage log keeps the first Contacted warning and adds both moves.
FLOW SOS-P1-07-5 | company_admin | /sellos/company/setup | Sign in as the Company Admin, open Set up your company, click Pipeline stages and remove the Contacted row, then click Save and continue. | The stages are not saved and the message says the stage Contacted has leads and how many, and that they must be moved first. Every stage is still there.
FLOW SOS-P1-07-6 | company_admin | /sellos/company/setup | Click Pipeline stages, rename Nurture to Long term and move it up one place, then click Save and continue. Open Regression NRI Five. | The stages save with Long term in its new place, Regression NRI Five shows the stage Long term, and its stage log is unchanged.

## SOS-P2-01: Telephony Settings

FLOW SOS-P2-01-1 | company_admin | /sellos/company/telephony | Sign in. Click Telephony in the navigation. The seeded account is already saved. | The page shows "Auth ID: saved. Auth token: saved." and a 022 number that starts with +9122. The auth ID and auth token boxes are empty, and neither key is shown anywhere on the page.
FLOW SOS-P2-01-2 | company_admin | /sellos/company/telephony | Click Test connection. | A green line says "Connected. The provider accepted the keys." No key is shown.
FLOW SOS-P2-01-3 | company_admin | /sellos/company/telephony | Type a new auth ID that does not start with FAKEOK, click Save, then click Test connection. | The page says Saved, the box empties, and Test connection shows a red line saying the provider refused the keys. The new auth ID is not shown in the message.
FLOW SOS-P2-01-4 | company_admin | /sellos/company/telephony | Replace the 022 number with 012345 and click Save. | The settings are not saved and a clear message says to enter the 022 number with its area code and eight digits.
FLOW SOS-P2-01-5 | agent | /sellos/company/telephony | Sign in as an agent and type the Telephony address. | The no access page opens. No settings are shown and Telephony is not in the navigation.
FLOW SOS-P2-01-6 | platform_admin | /sellos/company/telephony | Sign in as the platform admin and type the Telephony address. | The no access page opens. No settings are shown.

## SOS-P1-21: call outcomes and logging a call by hand

FLOW SOS-P1-21-1 | agent | /sellos/crm/leads | Sign in as the first Regression agent and open Regression Buyer Two. Look at the timeline, then under Log a call open the Outcome box. | The timeline shows a Call with the outcome Busy and 2 min, and a Follow up: Busy task for tomorrow. The Outcome box lists Interested, Call back later, Not reachable, Busy, Wrong number, Not interested, Site visit booked and Regression Sent brochure.
FLOW SOS-P1-21-2 | agent | /sellos/crm/leads | On Regression Buyer One choose Call back later, type 3 in Minutes and Ring after lunch in Notes, and click Log call without a follow up date. | The browser asks for the Follow up on date and time and nothing is logged. Fill it in, click Log call again, and the page says Call logged and follow up set. The timeline shows the call with Call back later and 3 min, and a Follow up: Call back later task at that time.
FLOW SOS-P1-21-3 | agent | /sellos/crm/leads | On Regression Buyer Two (on Site visit booked) choose the outcome Interested and look at the stage box under the form. | A line says Suggested stage: Qualified. Use it, and the box still reads Keep the stage. Click Use it and the box shows Qualified, or pick Negotiation instead. Fill in the follow up and click Log call: the lead moves only to the stage you chose.
FLOW SOS-P1-21-4 | agent | /sellos/crm/leads | Sign in as the second Regression agent and open Regression Buyer Three (Opted out). Choose the outcome Not interested, click the suggested stage Closed lost, and click Log call with no lost reason. | A Lost reason box appears and the browser asks for one. Choose Regression Price too high and click Log call: the lead moves to Closed lost, shows Lost reason: Regression Price too high, and the stage log line carries the reason. The Opted out warning never stopped the call or the move.
FLOW SOS-P1-21-5 | agent | /sellos/crm/leads | Sign in as the second Regression agent, open Regression Investor Four and choose Closed lost in the Stage box. | Nothing moves yet. A question asks why the lead is going to Closed lost, with a list of lost reasons. Click Cancel and the box returns to Contacted. Choose Closed lost again, pick Budget too low and click Move to Closed lost: the lead moves and shows the reason.
FLOW SOS-P1-21-6 | company_admin | /sellos/company/call-lists | Sign in as the Company Admin and click Call lists. Add the outcome Regression Walk in visit with Needs a follow up ticked and Contacted as its suggested stage, add the lost reason Regression Chose a rival, and untick Enabled on Regression Chose a rival. | Both lists show the new entries and each change is saved at once. Regression Sent brochure shows Needs a follow up and Contacted. The agent sees Regression Walk in visit in the Outcome box and no longer sees Regression Chose a rival when moving a lead to Closed lost.
FLOW SOS-P1-21-7 | agent | /sellos/company/call-lists | Sign in as an agent and type the Call lists address. | The no access page opens, no list is shown and Call lists is not in the navigation.

## SOS-P1-17: manage users as a Company Admin

FLOW SOS-P1-17-1 | company_admin | /sellos/company/users | Sign in as the Company Admin and click Users. Look at the list and open the Role box. | The list shows Regression New Agent (Invited, with a mobile number and the line Click to call rings this number first), Regression Agent No Mobile (Invited, with the red line No mobile number: can not use click to call) and Regression Former Agent (Deactivated, 1 open leads and 1 open tasks). The Role box offers Company Admin, Agent and Channel Partner, never Platform Admin.
FLOW SOS-P1-17-2 | company_admin | /sellos/company/users | Fill in a new email, the first name Regression Invited, the role Agent and a mobile number of +91 and ten digits, and click Send invitation. | A line says the user was added and that the invitation was not sent because email is not set up yet (real mail is SOS-P0-13). The new row shows Invited and Click to call rings this number first, and it is still there after a reload.
FLOW SOS-P1-17-3 | company_admin | /sellos/company/users | On Regression Agent No Mobile type 12345 in the mobile box and click Save number. Then type a +91 number of ten digits and click Save number again. | The first save is refused with a message that asks for +91 and ten digits and the row still says No mobile number. The second saves, the red line goes away and the number stays after a reload.
FLOW SOS-P1-17-4 | company_admin | /sellos/company/users | Click Deactivate on Regression New Agent. | The row shows Deactivated, a panel lists the agent's open leads and tasks (or says there are none), Deactivate is replaced by Turn back on, and the agent can not sign in. Click Turn back on and the row is Invited again.
FLOW SOS-P1-17-5 | company_admin | /sellos/company/users | Look at the row of the signed in Company Admin. | The row has no Deactivate button: nobody deactivates themselves.
FLOW SOS-P1-17-6 | agent | /sellos/company/users | Sign in as an agent and type the Users address. | The no access page opens, no user is shown and Users is not in the navigation.
FLOW SOS-P1-17-7 | platform_admin | /sellos/company/users | Sign in as the platform admin and type the Users address. | The no access page opens and no user is shown.

## SOS-P1-18: sales teams and the Sales Manager

FLOW SOS-P1-18-1 | company_admin | /sellos/company/teams | Sign in as the Company Admin and click Teams. Look at the two teams, then add the team Regression Team East with Regression Manager Two as manager and no agents. | Regression Team North (manager Gate Sales Manager) and Regression Team South (manager Regression Manager Two) are listed with their agents. Every agent is ticked and greyed out with the name of the team they are in, so no agent can be picked for a second team. Regression Team East is added with the manager and no agents.
FLOW SOS-P1-18-2 | sales_manager | /sellos/crm/leads | Sign in as the Sales Manager and click Leads. | The list holds the leads of the gate agent and Regression Agent Two (Regression Team North) and none of Regression Agent Three's leads. Teams and Users are not in the navigation, Team report is.
FLOW SOS-P1-18-3 | sales_manager | /sellos/crm/leads | Open Regression Buyer One as the Sales Manager. | The phone number is masked (stars and the last three digits), Merge a duplicate client is not shown, and the Assigned agent box offers only the agents of Regression Team North.
FLOW SOS-P1-18-4 | sales_manager | /sellos/crm/leads | On Regression Buyer One choose Regression Agent Two in the Assigned agent box. Then type the address /sellos/company/teams. | The lead is now assigned to Regression Agent Two and still in the list. The teams address opens the no access page.
FLOW SOS-P1-18-5 | sales_manager | /sellos/reports/team | Sign in as the Sales Manager and click Team report. | The report counts only the leads of Regression Team North, by agent and by stage, and names only that team.
FLOW SOS-P1-18-6 | agent | /sellos/reports/team | Sign in as the gate agent and type the Team report address. | The no access page opens and no count is shown.
FLOW SOS-P1-24-1 | agent | /sellos/crm/leads | Sign in as the gate agent, click Leads and then Board. | Eleven columns, one per stage of the buyer pipeline, in order. Each shows its lead count and the total budget. Only the gate agent's leads are on the board, none of another agent's. Regression Dormant Eight is on New with the mark No activity for 7 days.
FLOW SOS-P1-24-2 | agent | /sellos/crm/leads?view=board | Drag the card of Regression Buyer Three or Regression Investor Four, whichever is visible to this agent, or Regression Buyer Two, to the Contacted column. | The card moves, the counts and totals of both columns change, and a notice under the heading says the lead was moved to Contacted without a live Consent Record when it has none. The move is in the lead's stage log.
FLOW SOS-P1-24-3 | agent | /sellos/crm/leads?view=board | On a card choose Closed lost in its Move to stage box. | A box asks for a lost reason. Choosing one and saving moves the card to Closed lost.
FLOW SOS-P1-24-4 | agent | /sellos/crm/leads | Click Leads, then set the filters Stage, Source and Consent status one after the other, then type a date in Last contacted from, then tick No activity for 7 days. | Each filter narrows the list, and they combine. The address bar keeps every filter. Regression Dormant Eight is the only lead left when No activity is ticked. Clear filters shows every lead again.
FLOW SOS-P1-24-5 | company_admin | /sellos/crm/leads?view=board&source=Referral | Open the address as the Company Admin, then open the same address in a new tab. | Both show the Board view with Source set to Referral and only Referral leads. The Company Admin can choose an agent and a team in the filters.
FLOW SOS-P1-24-6 | sales_manager | /sellos/crm/leads?view=board | Sign in as the Sales Manager and open the Board. | Only the leads of Regression Team North's agents are on the board. The Team box offers only Regression Team North.

## SOS-P1-23: in-app notifications

FLOW SOS-P1-23-1 | agent | /sellos | Sign in as the gate agent and look at the bell in the left column (at phone width, in the top bar). Click it. | The bell shows a number of unread notifications. The panel lists them newest first, each with a title and a line naming the lead: Lead assigned for the leads the Company Admin gave the agent (Regression Dormant Eight among them), Follow up due or overdue for the agent's open tasks, and Site visit tomorrow for Regression Buyer One at Regression Tomorrow Heights. None is about another agent's lead.
FLOW SOS-P1-23-2 | agent | /sellos | Open the bell and click the Site visit tomorrow notification. | The Regression Buyer One lead opens. The bell's number is one lower, and when the bell is opened again that notification is gone.
FLOW SOS-P1-23-3 | agent | /sellos | Open the bell and click Mark all read. | The list says Nothing new, the number on the bell goes away, and after a reload the bell still shows no number.
FLOW SOS-P1-23-4 | company_admin | /sellos | Sign in as the Company Admin and open the bell. | Only notifications for the Company Admin are listed, each opening its lead. None of the agent's notifications is shown.
FLOW SOS-P1-23-5 | sales_manager | /sellos | Sign in as the Sales Manager and look for the bell. | The bell is there and lists only notifications of the Sales Manager. Opening one opens a lead of Regression Team North.
FLOW SOS-P1-23-6 | platform_admin | /sellos | Sign in as the platform admin and look at the left column. | There is no bell.

## SOS-P1-22: follow ups and reminders

FLOW SOS-P1-22-1 | agent | /sellos/crm/leads | Sign in as the gate agent and look at the leads list. | Regression Buyer Two shows Next follow up with its time two hours ago and a red Follow up overdue mark. Regression Buyer One shows Next follow up with a time a few minutes ahead and no overdue mark. A lead with no open follow up shows no Next follow up line.
FLOW SOS-P1-22-2 | agent | /sellos/crm/leads | Choose Overdue follow up in the Follow up box. Then choose Next follow up first in the sort box. | Only Regression Buyer Two is listed under the filter. Under the sort, the leads with a follow up come first, the soonest first (Buyer Two, then Buyer One), and the leads with none come last. The address holds both choices.
FLOW SOS-P1-22-3 | agent | /sellos/crm/leads | Choose Untouched, no follow up for 3 days in the Follow up box. | Regression Dormant Eight is listed with the mark Untouched, no follow up for 3 days. Buyer One and Buyer Two are not, because each has an open follow up.
FLOW SOS-P1-22-4 | agent | /sellos/crm/leads | Open Regression Buyer Two. Under Next follow up it says Regression chase the site visit and Overdue. Click Mark done in the timeline. | A form asks for the call outcome or a note. Clicking Done with neither says Choose the call outcome or write a note and leaves the follow up open. Typing a note and clicking Done marks it done, the Next follow up line then says No open follow up, and the note is in the timeline.
FLOW SOS-P1-22-5 | agent | /sellos/crm/leads | Open Regression Buyer One, click Mark done on Regression ring back soon, choose the outcome Call back later. | A box for the next follow up date and time appears and is required. Entering one and clicking Done marks it done, and Next follow up shows Follow up: Call back later at that time, with the call in the timeline.
FLOW SOS-P1-22-6 | agent | /sellos | Open the bell. | Follow up due and Follow up overdue notifications are listed for Regression Buyer One and Regression Buyer Two. None is about another agent's lead.
FLOW SOS-P1-22-7 | company_admin | /sellos/company/call-lists | Under Untouched leads change the number of days and click Save days. Reload. | The new number is shown after the reload. Setting it high enough hides the Untouched mark from Regression Dormant Eight in the leads list, and setting it back to 3 shows it again.

## SOS-P1-25: schedule and confirm site visits

FLOW SOS-P1-25-1 | agent | /sellos/crm/visits | Sign in as the gate agent and click Site visits. Look at Tomorrow's visits to confirm. | Two visits are listed for tomorrow: Regression Tomorrow Heights on Regression Buyer One marked Not confirmed, and Regression Skyline Walkthrough on Regression Buyer Two marked Confirmed. Regression Lakeside Tour (Regression Agent Two's) is not listed.
FLOW SOS-P1-25-2 | agent | /sellos/crm/visits | On Regression Tomorrow Heights choose Confirmed in the Confirmation box. Then choose Cancelled, then Confirmed again. Then choose Rescheduled, enter a time two days ahead and click Reschedule. | Each choice is saved at once and the mark beside the visit follows it (Confirmed, Cancelled, Confirmed). Rescheduled asks for the new date and time first, and after Reschedule the visit leaves tomorrow's list.
FLOW SOS-P1-25-3 | agent | /sellos/crm/visits | In the Calendar click Day, then Next, then Week, then Today. | The Day view shows one day, Next shows tomorrow with Regression Skyline Walkthrough and Regression Tomorrow Heights at their times, the Week view shows seven days from Monday to Sunday, and Today returns to the current day or week. Regression Lakeside Tour is not shown.
FLOW SOS-P1-25-4 | agent | /sellos/crm/leads | Open Regression Dormant Eight (stage New). Under the follow up form type Regression Hilltop Visit in the site visit project box, choose a date and time, leave the agent box on The lead's agent and click Add visit. | The visit appears in the timeline as Not confirmed with the gate agent named, and the lead's stage now reads Site visit booked. Open Regression Buyer Two (already further on or at Site visit booked) and add a visit: its stage does not change.
FLOW SOS-P1-25-5 | agent | /sellos/crm/leads | Open Regression Buyer Two and click Mark visit done on Regression Skyline Walkthrough. Click Done with no outcome, then choose Liked it, type a note and click Done. | With no outcome it says Choose the outcome of the visit and stays open. With Liked it the visit shows Done with the outcome, and a line offers Next stage: Negotiation. The stage is still Site visit booked until you click Move the lead to Negotiation, and then it reads Negotiation.
FLOW SOS-P1-25-6 | sales_manager | /sellos/crm/visits | Sign in as the Sales Manager and click Site visits. | The page says Your team's site visits. Tomorrow's list holds the three visits of Regression Team North: Regression Tomorrow Heights, Regression Skyline Walkthrough and Regression Lakeside Tour. The Calendar shows them too.
FLOW SOS-P1-25-7 | company_admin | /sellos/crm/visits | Sign in as the Company Admin and click Site visits. | The page says Everyone's site visits, and tomorrow's list and the Calendar hold every agent's visits, including Regression Lakeside Tour.
FLOW SOS-P1-19-1 | company_admin | /sellos/company/assignment | Sign in as the Company Admin and click Assignment. Choose Regression Team North as the default team. Add the rule Regression Referral Rule, Assign by Source, Source Referral, Team Regression Team South. | The default team is saved and shown again after a reload. The new rule is listed as Source Referral to Regression Team South. Turn Enabled off and on, then Remove the rule, and it disappears from the list.
FLOW SOS-P1-19-2 | company_admin | /sellos/crm/leads | With the default team set to Regression Team North, click New lead, enter Regression Assigned Buyer with any source and save. Open the lead. | The lead is already assigned to one of Regression Team North's active agents, and the Assigned agent box lists the assignment in its log as Default team, from nobody to that agent.
FLOW SOS-P1-19-3 | company_admin | /sellos/crm/leads | Tick two leads in the list, choose Regression Agent Two under Give the selected leads to and click Reassign selected. | A line says how many leads were reassigned and how many follow ups and site visits moved with them. The leads now show Regression Agent Two when opened, and their assignment log ends with Bulk. Select all shown ticks every row.
FLOW SOS-P1-19-4 | sales_manager | /sellos/crm/leads | Sign in as the Sales Manager, tick a lead of Regression Team North and look at the agents offered in Give the selected leads to. | Only the agents of Regression Team North are offered. Reassigning works, and no other team's lead or agent is ever shown.
FLOW SOS-P1-19-5 | company_admin | /sellos/company/users | Click Deactivate on an agent who has open leads, such as Regression Agent No Mobile. | The row stays active and asks who takes the leads, listing them. Choosing an agent, or Share among the team's active agents, and clicking Hand over and deactivate deactivates the user, says how many leads, tasks and site visits were handed over, and the open leads list is empty. Regression Former Agent's one open lead and task now belong to Regression Agent No Mobile, not to the inactive user.

## SOS-P1-12: import the bought lead lists

FLOW SOS-P1-12-1 | company_admin | /sellos/crm/import | Sign in as the Company Admin and click Import leads. Choose a CSV file with the columns Name, Mobile, Email, City and DND Status (one person listed twice, one with DND Status Yes, one with no name). | The columns are matched without being told. The counts line says how many rows are new leads, merged with people already in SellOS, merged within the file, on the do not call list and skipped, the sample table shows the numbers masked, and the skipped row is named with its reason. Nothing is imported yet.
FLOW SOS-P1-12-2 | company_admin | /sellos/crm/import | Change a column in the mapping boxes, then click Import. | The counts follow the mapping. After Import the result says how many leads were imported, how many merged into leads already there and how many were skipped. See the imported leads opens the Leads list on the source Bought list.
FLOW SOS-P1-12-3 | company_admin | /sellos/crm/leads | Open Regression Bought One and Regression Bought Two (imported by the seed from a bought list). | Regression Bought One is Unknown with an amber warning, Regression Bought Two is Registered DND with an amber warning, both from the source Bought list and both saying You can still call and message this lead. Regression Bought Two exists once although the file listed it twice.
FLOW SOS-P1-12-4 | agent | /sellos/crm/leads | Sign in as the gate agent and look at the navigation. | There is no Import leads link, and an agent's import request is refused.
