# SellOS Tasks

This file is the backlog for building SellOS, in the BuildOS block format that `scripts/lib/tasks.py` reads. It was converted from the earlier `Tasks.md` on 4 November 2026 (107 stories, 523 points; the six DLT stories are Parked). The build loop (`scripts/build-loop.sh`) picks the next task from it. Read `docs/DEV_STRATEGY.md` and `docs/TESTING.md`.

## How the loop reads this file

* A task is a block that starts with `### SOS-<phase>-<number>: <title>`. Nothing else in this file may start with `### `, and prose belongs above the first block, because the loop sends everything up to the next `### ` to the agent as the task.
* Status values: Not Started, In Progress, Complete, Blocked, Waiting, Parked and Not Needed. The loop picks only Not Started tasks whose dependencies are all satisfied, choosing by Launch tier first (Dec 20 before Jan 1), then dependencies, then file order. A dependency is satisfied when it is Complete or Not Needed. It never picks Waiting, Parked or Not Needed tasks, and never reports a Not Needed one. A Blocked task stops the loop until a person resets it.
* `- **Launch:**` is the launch tier: Dec 20 or Jan 1. Everything is launch scope, and there is no "After launch". A Not Needed or Parked task says `none`.
* Priority rule (Jayman, 27 November 2026): the product working as intended matters more than polish or infrastructure, and there is no more pixel work. A task with Launch `Later` is out of the loop and never picked.
* Waiting means the task belongs to Jayman, AMP Labs, Counsel or the Accountant and is not a task for the agent. A person marks it Complete with `scripts/set-task-status.sh <ID> Complete` when the work is done.
* Priority is the phase: Phase 0 is P0, Phase 1 is P1, and so on. The N tasks (enablers owned by people) are P0. Priority no longer orders the loop (SOS-SETUP-19); the Launch tier does.
* `Browser spec: required` means a person sees or uses the result, so the task needs a Cypress spec that names it. `Docs only: yes` and `Gate files: allowed` are written only by a human.
* Regression is a scheduled pause, not a gate (Jayman, 10 November 2026). SOS-REG-A (about 24 November), SOS-REG-B (about 12 December), SOS-REG-C (about 18 December) and SOS-REG-L (about 29 December) are Waiting tasks owned by Claude in chat. No task depends on A, B or C. L depends on every other task that is not Not Needed or Parked. Claude in chat runs `scripts/pause-loop.sh`, which creates `/tmp/sellos-loop.pause`. Before picking each task the loop checks for that file, and if it exists it picks nothing, notifies "Paused for regression" and stops. After the walk and the report (`docs/regression/README.md`), `scripts/resume-loop.sh` removes the file and the loop is started again. The old milestones SOS-REG-0 to SOS-REG-6 and SOS-REG-2B are Not Needed. The old numbers map as P1.06 to SOS-P1-06 and N16 to SOS-N16.

## Done so far

* The Plivo account is created and its KYC is approved.
* The Indian number +91 22 6998 6373 is bought. It is a 022 landline series number, so it is for service and transactional calls only.
* Decisions already made: Frappe 16.x without ERPNext, DigitalOcean for DNS and servers, a custom web app for every role, one Frappe site per company at a subdomain of sellos.interactivesoftwares.com, Razorpay for India and Stripe for international billing, and the Bandra to Andheri corridor for the first five years of market data.
* Checkpoint A (Jayman, 4 November 2026) decided the desk, CRM data and masking rules in `CLAUDE.md`. The same day Jayman's browser test failed the first SOS-P1-06, so it was reopened as SOS-P1-06A and SOS-P1-06B.
* Rebuild from scratch (Jayman, 10 November 2026, SOS-SETUP-19). The commit before the rebuild is tagged `legacy/before-rebuild`. Every task was set back to Not Started, the finished ones included, and is rebuilt from its own text. The agent does not assume existing code is right: it reads it, replaces what is weak, keeps what passes review, and adds or refreshes tests that name the task. The tree is not deleted first. International calling is dropped. Consent never blocks.

## Rules for the agent

1. Work only the task you are given. Read `CLAUDE.md` first. Follow the BuildOS conventions in `docs/buildos-conventions.md`.
2. Write the tests the acceptance criteria and test criteria call for, and put the task ID in them. Run only your own test module and spec.
3. Never commit, push, reset or change a status. The loop does that after the gate passes.
4. Rebuild from scratch: build the task from its own text. Do not assume existing code is right. Read it, replace what is weak, keep what passes review, and add or refresh tests that name the task. Do not delete the tree first.
5. Stop with NEEDS_INPUT when a task needs a secret or account you do not have, when an acceptance criterion is ambiguous, or when a change touches permissions, the consent check, billing or personal data.
6. Consent never blocks. A lead's consent status (Consented, Unknown, Opted out, Registered DND when known) is recorded and shown as a warning on the lead, the caller queue and the call log, and never prevents a call or an SMS, in code or in the screens, and no consent status stops a WhatsApp reply to a message the person sent. Enforcement lives in one function behind the company setting "Consent enforcement", Off by default. An explicit stop request is recorded as Opted out with a red warning, and does not block a call or an SMS. A WhatsApp STOP is the one exception (Jayman, 24 November 2026): it always suppresses everything the bot, campaigns and partner digests send unprompted, whatever "Consent enforcement" says. It sends one confirmation reply, creates a task for the assigned advisor and records the opt out in the consent log, and the person can still write to us and get replies. Calling hours stay a configurable setting.
7. Never build captcha solving or any bypass of access controls. Never commit a secret.
8. The 022 number is for service and transactional calls. A call's purpose is recorded, and a promotional purpose is shown as a warning.
9. Customers never use the Frappe desk. Every customer feature goes into the SellOS web app.
10. The product is called SellOS everywhere, exactly as BuildOS is called BuildOS, with no company or suite brand.
11. Tenant sites and the provisioner password (SOS-SETUP-22): create, drop, list and probe tenant sites only with `scripts/tenant-site.sh` or `sellos.provisioning.tenant_sites`, and get the MariaDB provisioner password only from `sellos.provisioning.credentials.get_provisioner_password()` (the variable, else the macOS Keychain item `sellos_provisioner`), which hands it to bench only through a child process's environment. Never run `security find-generic-password -w` (or any command that prints a secret), and never print, log or write the password. If `get_provisioner_password()` raises, reply NEEDS_INPUT with its message.
12. Styling (SOS-SETUP-40): new screens follow `docs/UI_STYLE.md` once it exists. Use its tokens, components and patterns, and do not invent colors, spacing or fonts.

## Epics

* E1 Compliance, procurement and access: 12 active stories, 27 active points. Starts in week 1. SOS-N21A (the voice bake-off harness) is the one built by Claude Code.
* E2 Platform foundations and DevOps: 12 stories, 49 points. Phases 0, 1 and 6.
* E3 Web app, roles and security: 5 stories, 32 points. Phases 0, 1 and 5.
* E4 Multitenancy and provisioning: 5 stories, 27 points. Phases 0 and 1.
* E5 Core CRM and consent: 6 stories, 29 points. Phase 1.
* E6 Calling: 14 stories, 68 points. Phase 2.
* E7 Market intelligence: 13 stories, 74 points. Phase 3.
* E8 Inventory, mandates and deals: 10 stories, 53 points. Phase 4.
* E9 Reporting: 4 stories, 26 points. Phase 5.
* E10 Client and partner views: 2 stories, 16 points. Phase 5.
* E11 Voice AI pilot: 3 stories, 16 points. Phase 5.
* E12 Billing and subscriptions: 8 stories, 45 points. Phase 6.
* E13 Listing sources and WhatsApp: 6 stories, 43 points. Phase 6.
* E14 Launch readiness: 2 stories, 10 points. Phase 6.

## Phase gates and sprint plan

There are no phase gates any more: regression is the scheduled pauses SOS-REG-A, B, C and L, and the loop orders work by Launch tier (Dec 20, then Jan 1). The sprint plan below is the earlier plan, kept for reference only.

* S1, weeks 1 to 2: E1 starts. Phase 0 foundations: repositories, servers, bench.
* S2, weeks 3 to 4: Phase 0 app shell and test site script. Phase 1 starts. Velocity measured.
* S3, weeks 5 to 6: Phase 1 control site, provisioning, roles and permission tests.
* S4, weeks 7 to 8: Phase 1 CRM, consent, website endpoint, Pandya site. Regression 1.
* S5, weeks 9 to 10: Phase 2 settings, adapter, router, consent check, Call Log.
* S6, weeks 11 to 12: Phase 2 click to call, inbound opt in route, reports. Regression 2.
* S7, weeks 13 to 14: Phase 3 ingestion, normaliser, building master.
* S8, weeks 15 to 16: Phase 3 matcher, nightly jobs, comparables.
* S9, weeks 17 to 18: Phase 3 valuation and assistant. Regression 3. Phase 4 starts.
* S10, weeks 19 to 20: Phase 4 inventory, listings, mandates.
* S11, weeks 21 to 22: Phase 4 deals and website feed. Regression 4.
* S12, weeks 23 to 24: Phase 5 reporting module.
* S13, weeks 25 to 26: Phase 5 portals and voice agent service.
* S14, weeks 27 to 28: Phase 5 AI pilot review and security review. Regression 5. Phase 6 starts.
* S15, weeks 29 to 30: Phase 6 billing, listing sources, WhatsApp.
* S16, week 31: Phase 6 platform tests and the first outside agency. Regression 6.

### SOS-P1-15: Record what each buyer wants
- **Epic:** Core CRM and consent
- **Description:** As an Agent, I want each buyer's requirements on the lead, so that I call with context and can match them to inventory later. Add to Lead: budget from and to in rupees, configuration (1 RK, 1 BHK, 2 BHK, 3 BHK, 4 BHK and above, multiple allowed), property type (Apartment, Villa, Plot, Office, Shop), preferred localities (several), purpose (End use, Investment), timeline (Immediate, Within 3 months, 3 to 6 months, Over 6 months) and possession (Ready, Under construction, Any).
- **Acceptance Criteria:**
  - Every field above is on the lead, editable by the agent the lead is assigned to and by the Company Admin, and change tracked like every CRM field.
  - The lead screen shows the requirements in one card, and the leads list can filter by budget range, configuration, locality and timeline.
  - Budget from may not be above budget to; the message says so.
  - A patch adds the fields to existing company sites and changes no existing lead.
- **Test Criteria:** Backend tests for the fields, the budget check, the filters and the patch run twice; a Cypress spec in which an agent fills the card and filters the list by it.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it. A previous attempt is on branch wip/SOS-P1-15-20261113: read it for reference with git show, do not run seed_regression_data against the test site.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-06A
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-16: Find duplicates when a lead or client is entered
- **Epic:** Core CRM and consent
- **Description:** As an Agent, I want to be told when a person already exists, so that one buyer is not called by two agents. When a lead or client is entered by hand, through the website endpoint or by import, match on the phone number (normalised to +91 and ten digits), the overseas phone and the email.
- **Acceptance Criteria:**
  - Entering a phone or email that exists shows the existing client and its leads (masked as the viewer's role requires) and offers to add the new enquiry to that client instead.
  - One matching function is used by the screens, SOS-P1-09's endpoint and SOS-P1-12's import.
  - A Company Admin can merge two clients; their leads, activities, tasks and site visits move to the one kept, nothing is deleted, and the merge is logged.
  - An agent never sees the full number of a client they could not otherwise see.
- **Test Criteria:** Backend tests of matching (different spacing and prefixes of the same number from `sellos.tests.phones`), the merge and the masking; a Cypress spec of the duplicate warning.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-06A
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-20: Keep a list of lead sources
- **Epic:** Core CRM and consent
- **Description:** As a Company Admin, I want lead sources from one list, so that source performance can be reported. Replace the free text source on Lead with a Lead Source list (Website, Portal, Referral, Walk in, Channel partner, Facebook, Missed call, Bought list) that a Company Admin can extend, plus an optional campaign.
- **Acceptance Criteria:**
  - Every lead has a source from the list; the existing free text values are mapped by a patch, and a value no source matches becomes a new source.
  - SOS-P1-09, SOS-P1-12 and SOS-P2-08 set their source from the list (Website, Bought list, Missed call).
  - A source in use cannot be deleted; it can be disabled.
- **Test Criteria:** Backend tests of the list, the patch run twice and the delete refusal; a Cypress check of the source picker.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-06A
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-07: Build the buyer pipeline
- **Epic:** Core CRM and consent
- **Description:** As an Agent, I want a buyer pipeline with clear stages, so that I know where every buyer stands. Build the stages New, Consent pending, Contacted, Qualified, Site visit booked, Site visit done, Negotiation, Booking, Closed won, Closed lost and Nurture, in that order. A lead may move to any stage whatever its consent status. Consent never blocks (Jayman, 10 November 2026). Consent pending is a stage like any other: no lead is put in it or held in it because of its consent status. Moving a lead to Contacted without a live Consent Record shows a warning on the lead, writes the warning to the stage change log, and proceeds. It never refuses.
  This task supersedes the default stage list seeded by SOS-P1-03. Update that seed and its tests to the 11 stages. The number of assertions in each changed test must not fall. (Jayman, 11 November 2026, SOS-SETUP-31.)
  Existing leads are carried over by a patch that maps Site visit scheduled to Site visit booked, Booked to Booking and Lost to Closed lost, and keeps New, Contacted, Site visit done and Negotiation. The patch can be run again safely, and adds the stages the old list lacked.
  A Company Admin may rename and reorder stages and add stages within limits (at most `MAX_STAGES` in `sellos/config/setup_wizard.py`, with at least one Won and one Lost stage), but may not delete a stage that has leads.
- **Acceptance Criteria:**
  - All 11 stages exist, in the order above, on a fresh company site and on an existing one after the patch. Booking and Closed won are Won stages, Closed lost is a Lost stage, and the rest are Open.
  - The SOS-P1-03 seed and its tests (`sellos/config/test_p1_03_setup_wizard.py`, `cypress/integration/frontend/setup_wizard.cy.js`) use the 11 stages, and the number of assertions in each changed test does not fall.
  - The patch moves every lead on Site visit scheduled to Site visit booked, on Booked to Booking and on Lost to Closed lost, keeps the leads on New, Contacted, Site visit done and Negotiation where they are, and run twice changes nothing the second time.
  - A Company Admin can rename and reorder stages and add stages within the limits. Deleting a stage that has leads is refused with a message that says how many leads are on it. Deleting one with no leads succeeds.
  - A lead in any consent status (Consented, Unknown, Opted out, Registered DND) can be moved to Contacted and to every other stage. Nothing in the code or the screens refuses it.
  - Moving a lead to Contacted without a live Consent Record shows a warning on the lead, writes the warning to the stage change log, and proceeds.
  - Stage changes are logged.
- **Test Criteria:** Move a lead in each consent status to Contacted, confirm every move succeeds, and confirm the warning is shown on the lead and written to the stage change log for each status except Consented. A patch test that starts from the seven old stages with a lead on each, runs the patch twice, and checks every lead's stage. A test that a stage with leads cannot be deleted and an empty one can. A Cypress check of the 11 stages and of the warning on the lead.
- **Notes:** Updated by SOS-SETUP-31 (Jayman, 11 November 2026): the loop stopped with NEEDS_INPUT because SOS-P1-03 already seeds seven stages and its tests lock them. This task supersedes that list. FLOW SOS-P1-03-1 in `docs/regression/flows.md` no longer names the stages, so it holds for either list. Add this task's own flows.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-06B, SOS-P1-08
- **Status:** Complete
- **Browser spec:** required

### SOS-P1-21: Call outcomes and logging a call by hand
- **Epic:** Core CRM and consent
- **Description:** As an Agent, I want to record what happened on every call, including calls from my own phone before click to call exists, so that the next step is clear. Add a Call Outcome list a Company Admin edits (Interested, Call back later, Not reachable, Busy, Wrong number, Not interested, Site visit booked), each with an optional suggested stage and whether it needs a follow up date. Logging a call records the outcome, notes and duration as a Call activity on the lead.
- **Acceptance Criteria:**
  - An agent logs a call on a lead with an outcome; an outcome that needs a follow up asks for its date and time and creates the follow up (SOS-P1-22).
  - An outcome's suggested stage is offered, not forced; the agent may pick any stage, whatever the consent status.
  - Moving a lead to Closed lost asks for a lost reason from a list the Company Admin edits.
  - SOS-P2-07's outcome form and SOS-P2-05's Call Log use this outcome list; they define no outcome list of their own.
- **Test Criteria:** Backend tests of logging, the follow up rule, the suggested stage and the lost reason; a Cypress spec of logging a call by hand.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-07
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-17: Manage users as a Company Admin
- **Epic:** Core CRM and consent
- **Description:** As a Company Admin, I want to add and manage my users in the SellOS web app, so that I never need the desk. After the setup wizard, a Company Admin invites users by email with a role (Company Admin, Agent), sets each user's Indian mobile number (the number click to call rings first), and deactivates users who leave.
- **Acceptance Criteria:**
  - A Company Admin invites a user with a role; the user sets a password from the invitation and signs in to the web app.
  - Each user has an Indian mobile number, checked as +91 and ten digits; an agent without one is shown as unable to use click to call.
  - Deactivating a user stops their sign in at once and lists their open leads and tasks, which SOS-P1-19 reassigns.
  - Only a Company Admin sees this screen; nobody can give a user the Platform Admin role from it.
- **Test Criteria:** Backend tests of invite, mobile number check, deactivation and the role limits; a Cypress spec of inviting and deactivating an agent. Invitation mail is captured in tests (real mail is SOS-P0-13).
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-04
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-18: Sales teams and the Sales Manager role
- **Epic:** Core CRM and consent
- **Description:** As a Company Admin, I want agents grouped in sales teams with a manager, so that a manager runs their own team. Add Sales Team (name, manager, members), and give the sixth role, SellOS Sales Manager, its access (SOS-SETUP-35 created the role, its test user and its place in the permission suite, with no method and no data yet). A Sales Manager sees and edits the leads, activities, tasks and site visits of their team's members, reassigns leads within the team, and sees the team's reports. Phone numbers stay masked for a Sales Manager, as for an Agent; only a Company Admin sees full numbers.
- **Acceptance Criteria:**
  - A Company Admin creates teams, sets a manager and adds agents; an agent is in at most one team.
  - A Sales Manager sees exactly their team members' leads and records, and no other team's, in the list, the record API and reports.
  - A Sales Manager sees phone numbers masked.
  - The role's methods are in the permission matrix and the permission test suite (SOS-P1-05), which already list the role and its test user `sales_manager`; `scope_for` gives it a team scope; and `frontend/src/personas.js` gives it a persona with the crm, reports, home and profile areas.
- **Test Criteria:** Permission tests for every role against two teams; a Cypress spec in which a manager sees their team's leads and not another team's.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it. Approved by Jayman on 13 November 2026 (SOS-SETUP-35), as described above, and set to Not Started.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P1-17
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-24: Pipeline board and lead list views
- **Epic:** Core CRM and consent
- **Description:** As an Agent and a Sales Manager, I want to see leads by stage and find them fast, so that I work the right ones. Add a board with one column per stage of the buyer pipeline (SOS-P1-07) and drag to move, and give the leads list filters for stage, agent, team, source, consent status, requirements and last contacted.
- **Acceptance Criteria:**
  - The board shows the leads the user may see, by stage, with the count and the total budget per column.
  - Dragging a card to any stage moves it, whatever the consent status, with the warning SOS-P1-07 defines; the change is logged.
  - The list filters combine, and the URL keeps them, so a filtered view can be bookmarked.
  - A lead with no activity for the untouched period is marked on both views.
- **Test Criteria:** Cypress specs of moving a card, of each filter, and of an agent seeing only their own leads on the board; backend tests of the filter API.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P1-07, SOS-P1-15, SOS-P1-18, SOS-P1-20
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-23: In-app notifications
- **Epic:** Core CRM and consent
- **Description:** As a user, I want a notification bell in the web app, so that I see what needs me. Notify on a lead assigned to me, a follow up due or overdue, a site visit tomorrow, and a lead reassigned away.
- **Acceptance Criteria:**
  - The bell shows unread notifications for the signed in user only, newest first, each linking to its record.
  - Opening one marks it read; a user can mark all read.
  - A user never receives a notification about a record they may not see.
  - Email copies wait for SOS-P0-13; the notification code has one place to add them.
- **Test Criteria:** Backend tests that each event notifies the right user and nobody else; a Cypress spec of the bell.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-17
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-22: Follow ups and reminders
- **Epic:** Core CRM and consent
- **Description:** As an Agent, I want my follow ups listed and reminded, so that no promised call is missed. Use Lead Task as the follow up: a date and time, the lead, the agent, and Open or Done. Show the next follow up on every lead, and remind the agent when one is due.
- **Acceptance Criteria:**
  - Each lead shows its next open follow up; the leads list can sort and filter by it and show overdue ones.
  - A follow up due in the next 15 minutes, and one that becomes overdue, notifies its agent in the app (SOS-P1-23).
  - Marking a follow up done asks for the call outcome (SOS-P1-21) or a note.
  - A lead in an Open stage with no open follow up is flagged as untouched after a number of days set by the Company Admin (default 3).
- **Test Criteria:** Backend tests of due and overdue detection with a fixed clock, the untouched flag and the reminders run as a function, not a background job; a Cypress spec of completing a follow up.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-21, SOS-P1-23
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-25: Schedule and confirm site visits
- **Epic:** Core CRM and consent
- **Description:** As an Agent, I want to book site visits and confirm them the day before, so that buyers turn up. Build site visit booking from the lead (project, date and time, agent), a calendar of the agent's visits by day and week, and a list of tomorrow's visits to confirm.
- **Acceptance Criteria:**
  - Booking a visit moves the lead to Site visit booked, unless it is already further on, and the agent is notified the day before.
  - The calendar shows the user's visits (a Sales Manager sees the team's, a Company Admin everyone's).
  - Tomorrow's visits list shows each visit's confirmation status (Not confirmed, Confirmed, Rescheduled, Cancelled), set by the agent after the confirmation call.
  - Marking a visit Done asks for the outcome and offers the next stage.
- **Test Criteria:** Backend tests of booking, the stage move, confirmations and permissions; a Cypress spec of booking and confirming a visit.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-22
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-19: Assign and reassign leads
- **Epic:** Core CRM and consent
- **Description:** As a Company Admin or Sales Manager, I want every new lead to reach an agent at once and leads to move when an agent is busy or leaves, so that no lead waits uncalled. Assign new leads by a rule the Company Admin chooses: round robin across a team's active agents, or by source or locality to a named team; leads no rule matches go to a default team. Allow manual and bulk reassignment.
- **Acceptance Criteria:**
  - A lead created by hand, by the website endpoint or by import is assigned by the rules, and the assignment is logged.
  - Round robin skips deactivated agents and spreads leads evenly.
  - A Company Admin, or a Sales Manager within their team, reassigns one lead or a filtered set in bulk; open tasks and future site visits move with the lead.
  - Deactivating an agent asks where their open leads go, and nothing is left with an inactive user.
  - The new agent is notified (SOS-P1-23).
- **Test Criteria:** Backend tests of each rule, round robin over a deactivated agent, bulk reassignment and the move of tasks and visits; a Cypress spec of a bulk reassignment.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-18, SOS-P1-23
- **Browser spec:** required
- **Status:** Complete

### SOS-P1-12: Import the bought lead lists
- **Epic:** Core CRM and consent
- **Description:** As Jayman, I want the bought lead lists imported safely, so that they enter SellOS with an honest consent status. Build a CSV import that maps columns to leads, merges duplicates and gives every imported lead the consent status Unknown with the source bought list, or Registered DND when the file carries a known do not call result. Consent never blocks (Jayman, 10 November 2026). An imported lead can be called and messaged, and the warning is recorded each time.
- **Acceptance Criteria:**
  - Imported leads are Unknown, or Registered DND when the file says so, and show the warning.
  - Duplicates are merged.
  - Nothing in the import marks a lead as not to be contacted: no flag, stage or field set by the import stops a call, an SMS or a WhatsApp message. (That an imported lead is called and messaged with its warning recorded is proven by SOS-P2-04's matrix and SOS-P2-07, which are built after this task.)
- **Test Criteria:** Import a sample with duplicates and a do not call column, verify the statuses, the warnings and the merges, and check that the import sets nothing that stops contact.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): click to call, SMS and WhatsApp do not exist when this task runs (SOS-P2-07, SOS-P6-11; SMS is parked), so the criterion that they proceed moved to SOS-P2-04 and SOS-P2-07. The import sets the Lead's existing `source` field to `Bought list`, and stores a do not call result only through `record_dnd_result` in `sellos/crm/consent.py` (SOS-P1-08), never through a new field. SOS-P2-10 uses the same function. SOS-P4-10C reuses this task's CSV import code. Dependencies SOS-P1-16, SOS-P1-19, SOS-P1-20 added by SOS-SETUP-35 (13 November 2026): the core CRM comes before what uses it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-07, SOS-P1-16, SOS-P1-19, SOS-P1-20
- **Status:** Complete
- **Browser spec:** required

### SOS-P1-26: The agent's Today screen
- **Epic:** Core CRM and consent
- **Description:** As an Agent, I want one screen that tells me what to do today, so that I start working at once. Make it the agent's home page: follow ups due and overdue, new leads assigned to me, today's site visits and tomorrow's visits to confirm, each with call and log buttons.
- **Acceptance Criteria:**
  - An agent lands on Today after signing in; each section lists only their own records, in time order.
  - Each lead row can be called (click to call when SOS-P2-07 exists, otherwise the number for the agent's role) and logged in place.
  - A Sales Manager sees the same screen for their team, by agent.
  - Counts at the top match the lists.
- **Test Criteria:** Cypress specs for an agent and a Sales Manager with seeded follow ups, leads and visits; backend tests of each list's query.
- **Notes:** Added by SOS-SETUP-35 (13 November 2026): calling, the caller queue and the reports need it, and no task built it.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-19, SOS-P1-22, SOS-P1-25
- **Browser spec:** required
- **Status:** Complete

### SOS-P2-04: Build the consent status check and warnings
- **Epic:** Calling
- **Description:** As Jayman, I want every call, SMS and WhatsApp message to record the lead's consent status, so that the team sees the risk and no contact is lost to a block. Consent never blocks a call or SMS (Jayman, 10 November 2026); a WhatsApp STOP stops everything sent unprompted, with one confirmation reply, an advisor task and a consent log entry, and the person can still write to us and get replies (Jayman, 24 November 2026). Build one function, the only place consent is evaluated, which every dial, SMS send and WhatsApp send calls first. It returns the lead's consent status (Consented, Unknown, Opted out, Registered DND when known) and its warning, and the warning is written to the call log or message log. Enforcement lives only in this function, behind the company setting "Consent enforcement", which is Off by default. With it Off the function never refuses a call or an SMS, and refuses only the unprompted WhatsApp sends after a WhatsApp STOP. Calling hours are a separate setting (SOS-P2-10).
- **Acceptance Criteria:**
  - Every call, SMS and WhatsApp send goes through the one function, and no other code or screen checks consent or refuses on it.
  - With Consent enforcement Off, the default on a new company site, a call and an SMS each proceed in every consent status, and a WhatsApp reply to a message the person sent does too, and the status and warning are recorded on the log entry. A WhatsApp STOP stops everything sent unprompted, whatever the setting.
  - Consent enforcement is a company setting, Off by default, that only a Company Admin can change, and every change is logged.
  - With Consent enforcement On, the same function refuses a contact to a lead that is not Consented, logs the refusal with its reason, and the screen explains it.
  - A promotional purpose on the 022 number is recorded as a warning, not refused.
- **Test Criteria:** A matrix of the four consent statuses against call, SMS and WhatsApp with Consent enforcement Off: every contact proceeds and the warning is recorded. The same matrix with it On: only Consented proceeds. A test that no module but the one function refuses on consent.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): no Call Log or message log exists yet (there is no ERPNext, and SOS-P2-05 builds the Call Log), and sending SMS is parked with the Tata DLT stories. So this task owns one record, Consent Check (lead, channel Call, SMS or WhatsApp, consent status, warning, Consent enforcement On or Off, refused, reason, time, user, and a dynamic link to the log entry it belongs to), written by the one function on every check. SOS-P2-05's Call Log and SOS-P6-11's messages link to their Consent Check and define no consent fields of their own. The matrix calls the function for each channel directly; SMS is tested through the function only, since nothing sends SMS yet. The matrix includes a lead imported the way SOS-P1-12 imports one (source `Bought list`, Unknown or Registered DND) and shows that it proceeds.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-08
- **Status:** Complete

### SOS-N22: Write the default consent wording
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want the default consent wording written, so that the enquiry page, the website forms and the partner views show it from the start. Write the default text of the company setting "Consent wording" (SOS-P2-08), which each Company Admin can then edit. Counsel reviews it after launch.
- **Acceptance Criteria:**
  - The default consent wording is written and stored as the setting's default.
- **Test Criteria:** Backend tests in `sellos/crm/test_n22_consent_wording.py`: the default text equals the decided wording and is the default of the setting in the DocType, `{company}` is replaced with the company display name on the enquiry page and the website form, an empty company name falls back to "the company", and the settings screen gets the raw text. Verified by Jayman.
- **Notes:** Added by SOS-SETUP-34 (Jayman, 13 November 2026, question 5). Jayman's work, so it is Waiting and the loop does not pick it. Decided by Jayman, 24 November 2026: the default consent wording is "I agree that {company} and its agents may contact me about my enquiry by phone, SMS, WhatsApp and email. I can ask them to stop at any time." It is stored as the default of the company setting "Consent wording" (SellOS Settings, and `DEFAULT_WORDING` in `sellos/access/partner_registrations.py`). `{company}` is replaced with the company's display name (the setting "Company name", or "the company" while it is empty) by `render_wording`, on the enquiry page (SOS-P2-08) and the website form endpoint (SOS-P1-09), and the campaign forms (SOS-P4-11, SOS-P4-12) use the same function. The Consent Record's evidence holds the wording as shown, with the name filled in. The settings screen edits the raw text, so saving never bakes a name in. The channel partner confirmation (SOS-P7-02) no longer reads this setting: since 24 November 2026 it has its own setting, "Partner confirmation wording". Marked Complete by SOS-LOOP: written, stored and tested; counsel still reviews it after launch.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 1
- **Dependencies:** none
- **Status:** Complete

### SOS-P2-01: Build Telephony Settings
- **Epic:** Calling
- **Description:** As a Company Admin, I want to enter our Plivo details once, so that calling works for my company. Build a settings screen for the Plivo India account with encrypted keys that are never shown after saving, and a test connection button.
- **Acceptance Criteria:**
  - The India account (auth ID, auth token and the 022 number) can be configured. International calling is dropped, so there is no second account.
  - Keys are encrypted and no API returns them.
  - The test connection button reports success or the error.
  - Only Company Admins can open the screen.
- **Test Criteria:** A permission test blocks agents, a test confirms keys never appear in API responses, and tests of the test connection button against the fake provider for success and for an error.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): SOS-N09 (the second account, for international calls) is Not Needed, so this screen holds one account. It is built and tested against a fake provider behind the adapter interface, as SOS-N21A does with `--fake`. The agent never calls the real provider and never holds a real key. This task defines the telephony provider interface with `test_connection` only, and its fake; SOS-P2-02 extends the same interface and keeps this task's tests. Entering the real keys and pressing test connection against Plivo is SOS-P2-02L, owned by Jayman.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-04, SOS-N09
- **Status:** Complete
- **Browser spec:** required

### SOS-INT-1: Integrations screen in Company settings
- **Epic:** Settings
- **Description:** As a Company Admin, I want one screen where I add my own provider keys, so that each company runs on its own accounts. SellOS is sold to other agents, so nothing is hard coded to Pandya. The screen is in the SellOS web app, under Company settings, and each provider is one card with a Test connection button and a status pill (Not set, Connected, or Failed with a plain reason).
- **Acceptance Criteria:**
  - WhatsApp (Meta Cloud API) card: access token, phone number ID, WhatsApp business account ID, app secret, webhook verify token, and the webhook URL to paste into Meta. Jayman has a Meta verified number to enter here.
  - Meta Lead Ads card: app ID, app secret, page access token, page ID.
  - Email card: SMTP host, port, user, password, from name and from address, or a provider API key.
  - DocuSeal card: URL, API key, webhook secret, signer name and signer email. These exist in Company settings today and move here; the old place reads from the same record, so nothing is duplicated.
  - LegiScore card: API key, only for a company that brings its own. The platform level key stays on the control site's Market data source panel (SOS-P3-14).
  - Plivo and voice: a link to the existing Telephony settings page (SOS-P2-01), one place only, with no second copy of its fields.
  - Only a Company Admin can open the screen or call its methods. Each company has its own keys, on its own site, and no company can read or replace another's.
  - Every secret is an encrypted Password field. After saving, the browser is shown only "Saved, ending xxxx" (the last four characters), never the value. Replacing a secret is allowed, reading it is not. A secret never appears in an API response, a log line, an error message, an export, a fixture or the demo seed.
  - Test connection calls the provider's read only check through an adapter and reports success or the provider's plain reason. Existing settings pages are reused, not duplicated.
- **Test Criteria:** Permission tests (only a Company Admin; no other role; never another company's keys). A test that no API response, log or export holds a secret, using fake keys. A test that a saved secret reads back as "Saved, ending xxxx" and that replacing works. Test connection against a fake provider for Connected and for Failed with a reason. The design system checker passes (`scripts/check-guards.sh`). A Cypress spec of saving a key, seeing the masked value after a reload, and a failed test. No test calls a real provider.
- **Notes:** Added by Jayman, 27 November 2026 (priorities). Consumers read their keys from here: the WhatsApp channel (SOS-P6-11), Meta Lead Ads (SOS-P6-10), email, DocuSeal and the LegiScore adapters. UAE and Australia are out of scope for 1 January.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** none
- **Status:** Not Started
- **Browser spec:** required

### SOS-P2-02: Build the provider adapter
- **Epic:** Calling
- **Description:** As a developer, I want one adapter interface for telephony providers, so that Plivo can be replaced later. Define the interface with place call, read webhook and fetch recording, and implement it for Plivo, mapping provider errors to clear messages.
- **Acceptance Criteria:**
  - The interface is documented.
  - The Plivo adapter places a call and reads its events, proven against recorded Plivo responses and the fake provider.
  - Provider errors map to clear messages.
- **Test Criteria:** Unit tests with recorded provider responses, through a fake Plivo provider behind the same interface. The live test call is SOS-P2-02L, owned by Jayman.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): It is built and tested against a fake provider behind the adapter interface, as SOS-N21A does with `--fake`. The agent never calls the real provider and never holds a real key. The interface extends the one SOS-P2-01 defined (with `test_connection`), and SOS-P2-01's tests keep passing; the number of assertions in each changed test must not fall. Keys come only from Telephony Settings (SOS-P2-01).
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P2-01
- **Status:** Complete

### SOS-P2-03: Build the call router
- **Epic:** Calling
- **Description:** As the system, I want each call sent through the right account and number, so that calls follow the rules. Route +91 numbers through the India account and the 022 landline number, which is for service and transactional calls. International calling is dropped (Jayman, 10 November 2026), so +61, +971 and every other country code are refused with a clear message. A 140 series route is parked.
- **Acceptance Criteria:**
  - A +91 number is routed through the India account and the 022 number.
  - Each call records its purpose. A promotional purpose on the 022 number is recorded and shown as a warning on the call log. It is not refused.
  - Every other country code is refused with a clear message.
- **Test Criteria:** A table driven test of numbers and purposes against the expected account and series.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): the tests route through the fake provider of SOS-P2-02; no call reaches Plivo.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-02
- **Status:** Complete

### SOS-UI-1: Write the PAMAA style guide
- **Epic:** Web app, roles and security
- **Description:** As a developer, I want SellOS's look written down from PAMAA, so that every screen is styled the same way. Read `~/iespl-bench/apps/pamaa_erp` (read only): its Tailwind config, theme CSS, shell, sidebar, header, tables, forms, buttons, status badges, empty and error states and toasts. Write `docs/UI_STYLE.md` and a tokens file (colors, type scale, spacing, radius, shadows, with Inter) that SellOS's frontend can import. Include a screenshot of each PAMAA pattern.
- **Acceptance Criteria:**
  - `docs/UI_STYLE.md` covers the shell, sidebar, header, tables, forms, buttons, status badges, empty and error states and toasts, each with a screenshot.
  - The tokens file holds colors, type scale, spacing, radius and shadows, and the frontend can import it.
  - Starting point from PAMAA's sign in page: Inter, page background #F4F5F7, text #1D222B, a white card with a 14px radius, a 1px border and a soft two layer shadow, an indigo top accent bar, 8px inputs about 34px high at 14px, an indigo button, and a square brand tile with the company initial.
- **Notes:** Added by SOS-SETUP-40 (18 November 2026). Claude Code, interactive, not the loop: Waiting, so the loop does not pick it. A person marks it Complete with `scripts/set-task-status.sh SOS-UI-1 Complete`. PAMAA is read only.
- **Owner:** Claude Code, interactive
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** none
- **Status:** Complete

### SOS-UI-2: Apply the PAMAA style to the SellOS app shell
- **Epic:** Web app, roles and security
- **Description:** As a user, I want SellOS to look like PAMAA, so that the product feels finished. Implement the tokens in the frontend. Restyle the sign in page, the shell and navigation, the page header, cards, tables, form fields, buttons, status badges, empty and error states and toasts to match `docs/UI_STYLE.md`.
- **Acceptance Criteria:**
  - Each listed element matches `docs/UI_STYLE.md`.
  - No behaviour or permission changes, and every `data-testid` is unchanged.
  - All current Cypress specs still pass.
- **Test Criteria:** The existing Cypress specs, run unchanged; a spec that checks the tokens are applied (page background, text color, card radius).
- **Notes:** Added by SOS-SETUP-40 (18 November 2026). Placed right after SOS-P2-03 so later tasks need no restyling.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Browser spec:** required
- **Story Points:** 8
- **Dependencies:** SOS-UI-1
- **Status:** Complete

### SOS-UI-2B: Move SellOS to the Pandya palette and PAMAA's components, starting with Leads
- **Epic:** Web app, roles and security
- **Description:** As a user, I want SellOS to use the Pandya Realtors colours with PAMAA's layout and components, so that the product looks like one family and its controls are frappe-ui components. Replace the indigo tokens with the Pandya website tokens (`docs/ui-reference/pandya-website-design-tokens.md`), keeping PAMAA's Inter font and type scale. Copy PAMAA's shell, sidebar, top bar, page header, stat card, list card, filter bar, form field, badge, button, dialog, toast and empty state into SellOS (read only from PAMAA) and adapt names, routes, API calls and the menu. Convert the Leads list and the lead page first, using frappe-ui components for every control. Other pages stay as they are until SOS-UI-3.
- **Acceptance Criteria:**
  - `ui-tokens.js`, `ui-tokens.css`, `tokens.js` and `docs/UI_STYLE.md` use the Pandya palette, radius 8 (buttons, inputs) and 16 (cards), with every colour pairing's contrast ratio recorded; success, warning, danger and info tokens are listed.
  - frappe-ui's palette is remapped in the Tailwind config; CompanyBrand's per company colour override still works, with the Pandya palette as the default.
  - Inter is self hosted as WOFF2 with `font-display: swap`; no Google Fonts call.
  - Leads and the lead page use frappe-ui components for every control, every field has a label, budgets show as rupees, and the lead detail replaces the list.
  - The "You do not have permission to do this" message under Assigned agent does not show for a Company Admin.
- **Test Criteria:** Existing Leads and lead Cypress specs run unchanged; a person compares the demo with PAMAA.
- **Notes:** Added on Jayman's instruction (20 November 2026). Claude Code, interactive, not the loop. Cards and inputs use a thin teal/900 line at low opacity (Jayman's decision); links are teal/700 underlined. A person marks it Complete after comparing the demo with PAMAA at pamaa-demo.localhost:8020. Then SOS-UI-3 is rewritten as "move every other page to these components the same way". Waiting, so the loop does not pick it.
- **Owner:** Claude Code, interactive
- **Priority:** P2
- **Launch:** Dec 20
- **Browser spec:** required
- **Story Points:** 8
- **Dependencies:** SOS-UI-2
- **Status:** Complete

### SOS-P2-05: Extend the Call Log
- **Epic:** Calling
- **Description:** As an Agent and a Company Admin, I want every call recorded with its cost, so that we can review and report on calling. Extend the Call Log with provider, call ID, manual or AI mode, duration, billed duration, cost in rupees, hangup cause, recording link, outcome and consent reference, linked to the lead.
- **Acceptance Criteria:**
  - One log exists per call.
  - It links to the lead, to its Consent Check (SOS-P2-04), and to the live Consent Record when one exists.
  - Cost is stored in rupees.
- **Test Criteria:** Unit tests of cost conversion, and a test that a placed call creates a log.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): there is no Call Log DocType to extend (no ERPNext), so this task creates it in `sellos/sellos/doctype/call_log/` with the fields above, the call's purpose (SOS-P2-03) and the link to its Consent Check, which is the "consent reference". It defines no consent status field; the screens read it from the Consent Check. SOS-P5-07 adds its own fields (latency per turn, transcript) to this DocType and does not redefine these. Calls in the tests are placed through the fake provider. Dependencies SOS-P1-21 added by SOS-SETUP-35 (13 November 2026): the core CRM comes before what uses it.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-02, SOS-P2-04, SOS-P1-21
- **Status:** Complete

### SOS-P2-06: Build the webhook endpoint
- **Epic:** Calling
- **Description:** As the system, I want Plivo's call events received safely, so that the Call Log is accurate. Build a whitelisted endpoint that verifies Plivo's signature, ignores replayed events, updates the Call Log with answer, hangup, duration and recording link, and fetches the recording after the call.
- **Acceptance Criteria:**
  - Valid events update the log.
  - Invalid signatures are rejected.
  - Replayed events change nothing.
  - The recording link is stored after the call ends.
  - The endpoint is a registered provider webhook (`sellos.access.webhooks`), the one allowed exception to "every API method needs a login": the signature is checked before any database work; an invalid or missing signature writes nothing and reveals nothing; replayed and out of order events are ignored; the body size is capped; requests are rate limited per tenant; the tenant is the site the request arrives on; the signing secret is a per tenant company setting that never appears in a log.
  - `docs/permissions.md` lists it under "Provider webhooks", and `sellos/access/test_webhook_guest_guard.py` passes with it registered and declaring every check.
- **Test Criteria:** Tests for valid, invalid signature (nothing written, nothing revealed), replayed, out of order, oversized and rate limited events, and the secret never in a log.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): It is built and tested against a fake provider behind the adapter interface, as SOS-N21A does with `--fake`. The agent never calls the real provider and never holds a real key. The signature check is tested with a fake signing key and recorded Plivo event bodies. The check against Plivo's real events is SOS-P2-02L. **Decision (Jayman, 20 November 2026):** provider webhooks are the one allowed exception to "every API method needs a login", under the rules in `CLAUDE.md` ("Provider webhooks") and `docs/permissions.md`. Build the registry `sellos/access/webhooks.py` (`declared_webhooks()`, a decorator that registers the method, allows guests and records the checks `signature`, `replay`, `max_body_bytes`, `rate_limit_per_tenant` and `secret_setting`) and the shared checks once, here, so WhatsApp, email and payment webhooks (P5, P6) reuse them. `sellos/access/test_webhook_guest_guard.py` already fails the build for a guest method that is not registered. The loop stopped twice on this task (19 and 20 November 2026) for lack of this decision; the two failed branches held no work.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-05
- **Status:** Complete

### SOS-P2-07: Build click to call
- **Epic:** Calling
- **Description:** As an Agent, I want to click a lead and be connected, so that I can call without dialling. Add a click to call button that rings the agent's Indian mobile first and then the lead, shows the lead's consent status as a warning, and asks for the outcome after the call. Both call legs must stay in India.
- **Acceptance Criteria:**
  - The agent's phone rings first.
  - The lead is connected after the agent answers.
  - The lead's consent status and warning show before and during the call, and a lead in any consent status can be called. Consent never blocks (Jayman, 10 November 2026).
  - An agent number outside India shows a clear error.
  - An outcome form is required after the call.
- **Test Criteria:** An end to end test through the fake provider that plays both legs (the agent answers, the lead answers, hangup), a Cypress check of the warning and the outcome form, and a test of the media anchoring error path. The call between two real phones is SOS-P2-13, owned by Jayman.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): It is built and tested against a fake provider behind the adapter interface, as SOS-N21A does with `--fake`. The agent never calls the real provider and never holds a real key. The live check with two real phones moved to SOS-P2-13. Dependencies SOS-P1-17, SOS-P1-21 added by SOS-SETUP-35 (13 November 2026): the core CRM comes before what uses it.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P2-03, SOS-P2-04, SOS-P2-06, SOS-P1-17, SOS-P1-21
- **Status:** Complete
- **Browser spec:** required

### SOS-P2-09: Build the caller queue
- **Epic:** Calling
- **Description:** As the caller, I want a queue of leads ordered by urgency with each lead's consent status shown, so that no consent window is wasted and every risk is visible. Show every lead the caller may call: Consented leads first, soonest expiry first, with the time left, then the rest. Each lead shows its consent warning. Consent never blocks (Jayman, 10 November 2026). No lead is dropped from the queue for its consent status.
- **Acceptance Criteria:**
  - Every lead the caller may see appears, whatever its consent status.
  - Consented leads come first, soonest expiry first, with the time left shown.
  - Each lead shows its consent status: an amber warning for Unknown and Registered DND, a red warning for Opted out.
- **Test Criteria:** Seed leads in every consent status and with different expiries, and check the order and the warnings.
- **Notes:** Dependencies SOS-P1-19, SOS-P1-22 added by SOS-SETUP-35 (13 November 2026): the core CRM comes before what uses it.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P2-04, SOS-P1-19, SOS-P1-22
- **Status:** Complete
- **Browser spec:** required

### SOS-P2-08: Build the inbound opt in route
- **Epic:** Calling
- **Description:** As Jayman, I want bought leads given a way to respond, so that they can become callable leads. Give bought leads ways to come to us: a missed call to the 022 number, a link to the enquiry page shared through WhatsApp or ads, and the website forms. A missed call or form submission creates an inquiry Consent Record with a 7 day clock. An explicit stop request is recorded as Opted out with a red warning, and does not block a call or an SMS; a WhatsApp STOP stops everything sent unprompted, with one confirmation reply, an advisor task and a consent log entry, and the person can still write to us and get replies (Jayman, 24 November 2026). Consent never blocks a call or SMS (Jayman, 10 November 2026). The SMS route is parked with the Tata DLT stories.
- **Acceptance Criteria:**
  - A missed call to the 022 number is detected without the call being answered.
  - A missed call from a known lead changes no stage: it creates an inquiry Consent Record (7 days) and an activity, the lead becomes Consented, and it rises to the top of the caller queue. A missed call from an unknown number creates a new lead on the New stage, with the same record and activity.
  - The enquiry page records the consent wording.
  - A stop request, by call, form or message, is recorded as Opted out and shows a red warning on the lead, the caller queue and the call log. It does not block a later call or SMS; a WhatsApp STOP stops everything sent unprompted, with one confirmation reply, an advisor task and a consent log entry, and the person can still write to us and get replies (Jayman, 24 November 2026).
- **Test Criteria:** Feed a missed call event from a number made by `sellos.tests.phones` through the fake provider and the webhook, submit the enquiry page, and confirm the record and the lead state. Whether Plivo bills the rejected call is checked on a real call in SOS-P2-13.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): It is built and tested against a fake provider behind the adapter interface, as SOS-N21A does with `--fake`. The agent never calls the real provider and never holds a real key. A missed call arrives as a provider event through SOS-P2-06's webhook, so this task depends on it. This task builds the one lead intake function (`sellos.crm.intake`) behind the enquiry page; SOS-P1-09 and SOS-P5-06 call it and build no second path. The consent wording shown on the page is a company setting, "Consent wording", that a Company Admin edits; who writes its text is a question in `docs/BACKLOG_AUDIT.md`. A Consent Record's evidence link is the raw event or submission saved as a private file (`/private/files/...`), which SOS-P1-08's evidence rule already accepts. Which stage "moves the lead" means is a question in `docs/BACKLOG_AUDIT.md`; reply NEEDS_INPUT if it is still open when this task starts. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 5): the consent wording is the company setting "Consent wording", which each Company Admin can edit. Its default text is written by Jayman (SOS-N22); counsel reviews it after launch. Tests use their own wording. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 6): "moves the lead" means no stage change, as the criterion now says. It depends on SOS-P2-09 because the lead rises to the top of the caller queue. Dependencies SOS-P1-19, SOS-P1-20 added by SOS-SETUP-35 (13 November 2026): the core CRM comes before what uses it. Decided by Jayman (SOS-LOOP, 21 November 2026): public intake is the second exception to "every API method needs a login", only for creating or merging a lead through `sellos.crm.intake`, under the rules in CLAUDE.md ("Public intake forms") and docs/permissions.md ("Public intake forms"). This task builds the shared public intake registry (`sellos.access.public_intake`) and its checks once, with the first public form method (the enquiry page's submit); it extends `sellos/access/test_webhook_guest_guard.py` tests to cover a real registered intake method, and SOS-P1-09 reuses the registry and builds none of its own. The first intake method is the only guest method besides provider webhooks.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P2-04, SOS-P2-06, SOS-P2-09, SOS-P1-19, SOS-P1-20
- **Status:** Complete
- **Browser spec:** required

### SOS-P2-10: Make calling hours a setting and flag do not call numbers
- **Epic:** Calling
- **Description:** As Jayman, I want calling hours set by the company and do not call numbers flagged, so that callers see the rules. Calling hours stay a configurable company setting (start, end and days, India time). A do not call list can be imported and checked, and a number on it gives the lead the consent status Registered DND with a warning. Consent never blocks (Jayman, 10 November 2026). A do not call number is never refused by this task: only the one consent function of SOS-P2-04 may refuse, and only when Consent enforcement is On. International calling is dropped, so the rules are for India.
- **Acceptance Criteria:**
  - Calling hours are a company setting that a Company Admin can change, and a call outside them is refused with the hours in the message.
  - A do not call list can be imported. A listed number gives the lead Registered DND with an amber warning on the lead, the caller queue and the call log, and the call proceeds.
- **Test Criteria:** Boundary time tests for the calling hours, and a call to a listed number that proceeds with the warning recorded.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): the warning must show on the caller queue (SOS-P2-09) and the call log (SOS-P2-05), and the calling hours check sits in the dial path (SOS-P2-03), so these are dependencies. A listed number is stored only through `record_dnd_result` in `sellos/crm/consent.py` (SOS-P1-08), the same function SOS-P1-12 uses; no new do not call field is added to Lead. Refusing a call outside calling hours is a calling hours rule, not a consent check, and stays out of SOS-P2-04's function. SOS-N10 is Not Needed, and the rules are for India.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-04, SOS-N10, SOS-P2-03, SOS-P2-05, SOS-P2-09
- **Status:** Complete
- **Browser spec:** required

### SOS-UI-3A: Move Home, Call queue and Site visits to the shared components
- **Epic:** Web app, roles and security
- **Description:** As a user, I want these screens to look and work like the Leads list and the lead page, so that the product is consistent. Move Home (the Today screen and its lists), Call queue and Site visits, with `TodayRow.vue`, `VisitConfirm.vue` and `NotificationBell.vue` to the shared components. Use the shared components in `frontend/src/components` (`AppButton`, `FormField`, `MoneyField`, `AppCheckbox`, `StatusBadge`, `ListCard`, `FilterBar`, `PageHeader`, `StatCard`, `EmptyState`, `LoadError`, `LoadingSkeleton`, frappe-ui's `Dialog`) and follow the Leads list and the lead page as the pattern (`docs/UI_STYLE.md`, "Patterns" and the checklist): a page header with one primary action, content in cards, a stat row where the page has counts, filters in a `FilterBar`, two columns on a detail page, every field labelled, money in rupees with Indian grouping, status as a badge with a word and an icon, an empty state and a load error with Try again. No raw `<button>`, `<input>` or `<select>`.
- **Acceptance Criteria:**
  - Each listed page is built from the shared components and follows `docs/UI_STYLE.md`, as the Leads list and the lead page do.
  - `frontend/src/pages` files in this task come off `docs/ui-backlog.txt` (frontend/src/pages/CallQueuePage.vue, frontend/src/pages/SiteVisitsPage.vue), and `scripts/check-guards.sh` passes the controls guard.
  - `cypress/integration/frontend/ui_style.cy.js` has a case for each listed page that passes: the page background and text colour, the 24px/600 title, 16px card radius with the 1px teal line, the primary button as solid button/bg with text/button, and that every control on the page is a frappe-ui control.
  - No behaviour or permission changes, home-welcome, today-counts and every other Home, queue and visit `data-testid` are unchanged, and every current Cypress spec passes (specs that read a native `<option>` use `cy.optionTexts`).
- **Test Criteria:** The Cypress style check in `ui_style.cy.js` for each page, plus the existing specs for these pages, run unchanged apart from select helpers.
- **Notes:** Rewritten from SOS-UI-3 on Jayman's instruction (20 November 2026, after SOS-UI-2B was approved). Interactive-quality work, but it runs in the loop: build on the shared components, never a second copy of one. A page that needs a component that does not exist adds it to `frontend/src/components` and `docs/UI_STYLE.md`. frappe-ui's Select is not a native `<select>`: `cy.select()` is overwritten for it in `cypress/support/commands.js`.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Browser spec:** required
- **Story Points:** 5
- **Dependencies:** SOS-UI-2B
- **Status:** Complete

### SOS-UI-3B: Move Import leads, the pipeline Board, Call lists and Assignment to the shared components
- **Epic:** Web app, roles and security
- **Description:** As a user, I want these screens to look and work like the Leads list and the lead page, so that the product is consistent. Move Import leads, the pipeline Board (`LeadBoard.vue`, the Board view of the Leads page), Call lists and Assignment to the shared components. Use the shared components in `frontend/src/components` (`AppButton`, `FormField`, `MoneyField`, `AppCheckbox`, `StatusBadge`, `ListCard`, `FilterBar`, `PageHeader`, `StatCard`, `EmptyState`, `LoadError`, `LoadingSkeleton`, frappe-ui's `Dialog`) and follow the Leads list and the lead page as the pattern (`docs/UI_STYLE.md`, "Patterns" and the checklist): a page header with one primary action, content in cards, a stat row where the page has counts, filters in a `FilterBar`, two columns on a detail page, every field labelled, money in rupees with Indian grouping, status as a badge with a word and an icon, an empty state and a load error with Try again. No raw `<button>`, `<input>` or `<select>`.
- **Acceptance Criteria:**
  - Each listed page is built from the shared components and follows `docs/UI_STYLE.md`, as the Leads list and the lead page do.
  - `frontend/src/pages` files in this task come off `docs/ui-backlog.txt` (frontend/src/pages/ImportLeadsPage.vue, frontend/src/pages/CallListsPage.vue, frontend/src/pages/AssignmentRulesPage.vue), and `scripts/check-guards.sh` passes the controls guard.
  - `cypress/integration/frontend/ui_style.cy.js` has a case for each listed page that passes: the page background and text colour, the 24px/600 title, 16px card radius with the 1px teal line, the primary button as solid button/bg with text/button, and that every control on the page is a frappe-ui control.
  - No behaviour or permission changes, every import, board, call list and assignment `data-testid` are unchanged, and every current Cypress spec passes (specs that read a native `<option>` use `cy.optionTexts`).
- **Test Criteria:** The Cypress style check in `ui_style.cy.js` for each page, plus the existing specs for these pages, run unchanged apart from select helpers.
- **Notes:** Rewritten from SOS-UI-3 on Jayman's instruction (20 November 2026, after SOS-UI-2B was approved). Interactive-quality work, but it runs in the loop: build on the shared components, never a second copy of one. A page that needs a component that does not exist adds it to `frontend/src/components` and `docs/UI_STYLE.md`. frappe-ui's Select is not a native `<select>`: `cy.select()` is overwritten for it in `cypress/support/commands.js`.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Browser spec:** required
- **Story Points:** 5
- **Dependencies:** SOS-UI-2B
- **Status:** Complete

### SOS-UI-3C: Move Users, Teams, Team report, Support access and Telephony to the shared components
- **Epic:** Web app, roles and security
- **Description:** As a user, I want these screens to look and work like the Leads list and the lead page, so that the product is consistent. Move Users, Teams, Team report, Support access and Telephony to the shared components. Use the shared components in `frontend/src/components` (`AppButton`, `FormField`, `MoneyField`, `AppCheckbox`, `StatusBadge`, `ListCard`, `FilterBar`, `PageHeader`, `StatCard`, `EmptyState`, `LoadError`, `LoadingSkeleton`, frappe-ui's `Dialog`) and follow the Leads list and the lead page as the pattern (`docs/UI_STYLE.md`, "Patterns" and the checklist): a page header with one primary action, content in cards, a stat row where the page has counts, filters in a `FilterBar`, two columns on a detail page, every field labelled, money in rupees with Indian grouping, status as a badge with a word and an icon, an empty state and a load error with Try again. No raw `<button>`, `<input>` or `<select>`.
- **Acceptance Criteria:**
  - Each listed page is built from the shared components and follows `docs/UI_STYLE.md`, as the Leads list and the lead page do.
  - `frontend/src/pages` files in this task come off `docs/ui-backlog.txt` (frontend/src/pages/UsersPage.vue, frontend/src/pages/TeamsPage.vue, frontend/src/pages/SupportPage.vue, frontend/src/pages/TelephonyPage.vue), and `scripts/check-guards.sh` passes the controls guard.
  - `cypress/integration/frontend/ui_style.cy.js` has a case for each listed page that passes: the page background and text colour, the 24px/600 title, 16px card radius with the 1px teal line, the primary button as solid button/bg with text/button, and that every control on the page is a frappe-ui control.
  - No behaviour or permission changes, every user, team, team report, support access and telephony `data-testid` are unchanged, and every current Cypress spec passes (specs that read a native `<option>` use `cy.optionTexts`).
- **Test Criteria:** The Cypress style check in `ui_style.cy.js` for each page, plus the existing specs for these pages, run unchanged apart from select helpers.
- **Notes:** Rewritten from SOS-UI-3 on Jayman's instruction (20 November 2026, after SOS-UI-2B was approved). Interactive-quality work, but it runs in the loop: build on the shared components, never a second copy of one. A page that needs a component that does not exist adds it to `frontend/src/components` and `docs/UI_STYLE.md`. frappe-ui's Select is not a native `<select>`: `cy.select()` is overwritten for it in `cypress/support/commands.js`.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Browser spec:** required
- **Story Points:** 5
- **Dependencies:** SOS-UI-2B
- **Status:** Complete

### SOS-UI-3D: Move Companies, sign in and the setup wizard to the shared components
- **Epic:** Web app, roles and security
- **Description:** As a user, I want these screens to look and work like the Leads list and the lead page, so that the product is consistent. Move Companies (the Platform Admin list), the sign in page and the setup wizard. Sign in today is Frappe's own `/login`: give it a SellOS template (the SellOS brand tile, Inter, the Pandya tokens, a frappe-ui style form) through the app's `www` and hooks, with no change to how sign in works to the shared components. Use the shared components in `frontend/src/components` (`AppButton`, `FormField`, `MoneyField`, `AppCheckbox`, `StatusBadge`, `ListCard`, `FilterBar`, `PageHeader`, `StatCard`, `EmptyState`, `LoadError`, `LoadingSkeleton`, frappe-ui's `Dialog`) and follow the Leads list and the lead page as the pattern (`docs/UI_STYLE.md`, "Patterns" and the checklist): a page header with one primary action, content in cards, a stat row where the page has counts, filters in a `FilterBar`, two columns on a detail page, every field labelled, money in rupees with Indian grouping, status as a badge with a word and an icon, an empty state and a load error with Try again. No raw `<button>`, `<input>` or `<select>`.
- **Acceptance Criteria:**
  - Each listed page is built from the shared components and follows `docs/UI_STYLE.md`, as the Leads list and the lead page do.
  - `frontend/src/pages` files in this task come off `docs/ui-backlog.txt` (frontend/src/pages/TenantsPage.vue, frontend/src/pages/SetupWizardPage.vue), and `scripts/check-guards.sh` passes the controls guard.
  - `cypress/integration/frontend/ui_style.cy.js` has a case for each listed page that passes: the page background and text colour, the 24px/600 title, 16px card radius with the 1px teal line, the primary button as solid button/bg with text/button, and that every control on the page is a frappe-ui control.
  - No behaviour or permission changes, every companies, sign in and setup `data-testid` are unchanged, and every current Cypress spec passes (specs that read a native `<option>` use `cy.optionTexts`).
- **Test Criteria:** The Cypress style check in `ui_style.cy.js` for each page, plus the existing specs for these pages, run unchanged apart from select helpers.
- **Notes:** Rewritten from SOS-UI-3 on Jayman's instruction (20 November 2026, after SOS-UI-2B was approved). Interactive-quality work, but it runs in the loop: build on the shared components, never a second copy of one. A page that needs a component that does not exist adds it to `frontend/src/components` and `docs/UI_STYLE.md`. frappe-ui's Select is not a native `<select>`: `cy.select()` is overwritten for it in `cypress/support/commands.js`.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Browser spec:** required
- **Story Points:** 5
- **Dependencies:** SOS-UI-2B
- **Status:** Complete

### SOS-P2-11: Build call reports
- **Epic:** Calling
- **Description:** As a Company Admin, I want calling reports, so that I can see cost and performance. Build reports for cost by agent and by purpose, connect rate, talk time and consent coverage, with date filters.
- **Acceptance Criteria:**
  - Each report filters by date.
  - Totals match the Call Log.
  - Each figure drills down to calls.
- **Test Criteria:** Reconcile every total and drill down with seeded Call Logs made through the fake provider. The reconciliation with Plivo's statement for a test month is in SOS-P2-13.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): international calling is dropped, so cost by country is cost by purpose. The live reconciliation moved to SOS-P2-13.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-05
- **Status:** Complete
- **Browser spec:** required

### SOS-N21A: Build the Hinglish voice bake-off harness
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want a harness I run on my own machine that scores the voice providers on our own Hinglish phone audio, so that SOS-N21 is chosen from measurements, not vendor claims. Build `scripts/bakeoff.sh` and the package `sellos/voice/bakeoff/`. A human runs the harness locally. The agent builds and tests it with fake providers only, and never calls a real provider.
  Input: `~/iespl-baseline/bakeoff/audio/*.wav` and `~/iespl-baseline/bakeoff/reference.tsv`. The TSV has one row per recording: `file`, `reference` (the transcript in Roman Hinglish), and the key entities in three columns, `numbers`, `prices` and `localities` (each a `;` separated list, empty when there is none). Ship a template `docs/bakeoff/reference.tsv` with the 20 rows below and their entities filled in, and `docs/bakeoff/sentences.md` listing the same 20 lines for Jayman to record, one file each:
  - `01.wav`: Namaste, mujhe Bandra West mein ek 2 BHK flat dekhna hai, budget teen crore tak hai.
  - `02.wav`: Carpet area kitna hai aur parking kitni milti hai?
  - `03.wav`: Possession December 2027 ka hai, lekin RERA number kya hai?
  - `04.wav`: Andheri East mein ready to move flat chahiye, price do crore pachaas lakh ke andar.
  - `05.wav`: Main kal shaam chhe baje site visit ke liye aa sakta hoon.
  - `06.wav`: Maintenance charge har mahine kitna padega?
  - `07.wav`: Loan approval ke liye mujhe bank ka contact number chahiye.
  - `08.wav`: Aap WhatsApp pe brochure bhej dijiye, number nau aath saat chhe paanch chaar teen do ek zero hai.
  - `09.wav`: Sea facing wala flat available hai kya, ya sirf city view?
  - `10.wav`: Mera naam Rahul Mehta hai, main NRI hoon aur Dubai mein rehta hoon.
  - `11.wav`: Booking amount kitna hoga, aur payment plan kya hai?
  - `12.wav`: Resale flat hai ya developer se seedha?
  - `13.wav`: Floor rise charge alag se lagega kya?
  - `14.wav`: Mujhe abhi baat nahi karni, kal subah gyarah baje call kijiye.
  - `15.wav`: Stamp duty aur registration milake total kitna padega?
  - `16.wav`: Powai ya Goregaon, dono mein se kaunsa better rahega investment ke liye?
  - `17.wav`: Worli mein ek tower hai jahan mujhe 3 BHK chahiye.
  - `18.wav`: Kya aap AI ho ya insaan?
  - `19.wav`: Thoda dheere boliye, line mein awaaz kat rahi hai.
  - `20.wav`: Rate per square foot kitna chal raha hai is area mein, around 45 hazaar?
  Speech to text: the candidates are Sarvam (Saaras V3) and Deepgram (Nova-3, `language=multi`, with keyterms for real estate words, read from a list in the package: BHK, carpet area, RERA, possession, maintenance, floor rise, stamp duty, the localities above and the like). The harness sends each recording as 8 kHz mono audio, as a phone line carries it, converting a recording that is not 8 kHz first. For each provider and each file it records the transcript, the word error rate against the reference, entity accuracy for numbers, prices and localities scored separately, and the time to first result. Scoring normalises both sides before comparing: case and punctuation, and spoken Hindi or English numbers against digits, so "teen crore" and "3 crore", "do crore pachaas lakh" and "2.5 crore", and "nau aath saat" and "987" match.
  Text to speech: write 20 agent replies in Roman Hinglish, the first being a draft of the AI disclosure line (SOS-N21 sets the final one). Generate each at 8 kHz with each provider (Sarvam Bulbul V3 and ElevenLabs), save the audio under `~/iespl-baseline/bakeoff/out/<provider>/`, record the latency (time to first audio and total), and write a rating sheet `docs/bakeoff/rating-sheet.md` with one row per reply and provider and an empty 1 to 5 column for Jayman.
  Language model (SOS-SETUP-34): run the same 20 agent replies through two or three candidate language models of the one provider, Anthropic (Jayman, 13 November 2026), so SOS-N21 can choose the model for each of the two settings (voice agent: fast; assistant: stronger). For each of the 20 replies, the scenario is the caller's line it answers and the lead context it needs; each candidate writes its own reply in Roman Hinglish from the same system prompt. The candidate model names are not chosen by the agent: they are read from `~/iespl-baseline/bakeoff/llm-models.txt`, one per line, two or three lines, which Jayman writes before the live run, and the harness refuses fewer than two or more than three. The live adapter calls Anthropic's Messages API over HTTPS with the standard library, streaming, and records time to first token and total time per reply. Write a rating sheet `docs/bakeoff/llm-rating-sheet.md` with one row per reply and model, the reference reply beside it, and empty 1 to 5 columns for Hinglish naturalness and for correctness, and add the models' latencies to `results.md`.
  Results: write `docs/bakeoff/results.md`: one table per provider with every file's numbers, then a summary table comparing the providers (mean word error rate, entity accuracy per kind, median and slowest time to first result, text to speech latency). Ship it as "Not run yet" until Jayman runs the harness.
  Keys: they come only from the macOS Keychain items `sellos_sarvam_key`, `sellos_deepgram_key`, `sellos_elevenlabs_key` and (SOS-SETUP-34) `sellos_anthropic_key`, through one function `get_secret(name)` in `sellos/voice/bakeoff/`, built like `get_provisioner_password()` in `sellos/provisioning/credentials.py`. It accepts only those four names. A key goes only into the request to its provider: nothing prints, logs or writes one, no exception message or result holds one, and the frame that raises a provider error holds no key (`docs/DEV_STRATEGY.md` row 29). When an item is missing, the error says how to store it (`security add-generic-password -a "$USER" -s <name> -w`) without showing a value.
- **Acceptance Criteria:**
  - `scripts/bakeoff.sh --fake` runs the whole harness with fake speech to text, language model and text to speech providers on test recordings, and writes the transcripts, scores, latencies, audio, both rating sheets and `results.md` to a folder it is given.
  - Real providers run only with `scripts/bakeoff.sh --live`, which refuses to start when standard input is not a terminal, so the build loop's agent cannot run it. The agent never runs `--live`.
  - Word error rate and entity accuracy are correct on hand worked examples, including spoken numbers and prices against digits, and numbers, prices and localities are scored separately.
  - Time to first result and text to speech latency are measured and recorded per file.
  - `docs/bakeoff/reference.tsv` holds the 20 rows with their entities, `docs/bakeoff/sentences.md` lists the 20 lines, and `docs/bakeoff/results.md` says "Not run yet".
  - The language model comparison reads two or three model names from `llm-models.txt`, refuses any other count, runs the 20 replies through each, records time to first token and total time, and writes `docs/bakeoff/llm-rating-sheet.md` with one row per reply and model and empty 1 to 5 columns.
  - `get_secret` reads only the four Keychain items, and no key appears in standard output, standard error, a log, a results file or a traceback with its locals.
  - The speech to text, language model and text to speech candidates sit behind one adapter interface each, so a provider is added by writing one adapter.
- **Test Criteria:** Backend tests with fake providers: scoring on worked examples, a whole `--fake` run on two short 8 kHz test recordings, `--live` refused without a terminal, the language model comparison with a fake model (two and three model names pass, one and four are refused), `get_secret` refusing an unknown name, and a fake key that never appears in the captured output, the written files or a formatted traceback with locals. The Keychain is never read in a test: the call is replaced.
- **Notes:** Added by SOS-SETUP-30 (Jayman, 11 November 2026). Never run `security find-generic-password -w` or any command that prints a key. Add no package: the bench is shared (SOS-SETUP-20). Use the standard library and what Frappe already installs; if a provider's streaming API needs a library the bench does not have, measure its HTTP API and say so in `results.md`. The recordings and generated audio stay in `~/iespl-baseline/bakeoff/`, never in the repository. Added by SOS-SETUP-33 (13 November 2026): the 5c6a5c6 Block came from the raw phone number guard (`sellos/tests/test_no_raw_phone_numbers.py`), which recording 08's spoken number trips when a test writes it out. In tests, a spoken phone number is made from a number from `sellos.tests.phones`, spelled out in Hindi digit words by a helper; no test or spec writes a ten digit number or its spoken form by hand. The 20 sentences in `docs/bakeoff/` are not test files and stay as written. The recovered work is on the branch `wip/SOS-N21A-recovery-20261113`; a person decides whether to start from it when resetting this task. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 1): reset to Not Started by `scripts/set-task-status.sh`. Rebuild from this text; `wip/SOS-N21A-recovery-20261113` is reference only.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 6
- **Dependencies:** none
- **Status:** Complete

### SOS-N21: Choose the Hinglish voice AI providers and disclosure line
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want the building blocks of the voice agent chosen, so that SOS-P5-07 is built on settled choices. The agent calls in Hinglish: spoken Hindi with English words, on phone lines at 8 kHz (Jayman, 11 November 2026). Choose the speech to text, language model and text to speech providers, and write the AI disclosure line in Roman Hinglish. The choice is made from the bake-off results in `docs/bakeoff/results.md`, which SOS-N21A's harness writes from our own recordings, not from vendor claims (`docs/DEV_STRATEGY.md` row 33).
- **Acceptance Criteria:**
  - The speech to text, language model and text to speech providers are named, with who holds the account and key for each.
  - The language model is one Anthropic account held by Jayman, with two model settings: the voice agent's (fast) and the agent assistant's (stronger). Each model is chosen from the mean ratings in `docs/bakeoff/llm-rating-sheet.md` and the latencies in `docs/bakeoff/results.md`, and the choice cites them.
  - The speech to text choice cites its numbers in `docs/bakeoff/results.md`: word error rate, entity accuracy for numbers, prices and localities (each scored separately) and time to first result.
  - The text to speech choice cites its mean rating (1 to 5) from the rating sheet and its latency from `docs/bakeoff/results.md`.
  - The call language is Hinglish, and transcripts and prompts are in Roman script.
  - The exact AI disclosure line is written down in Roman Hinglish.
- **Test Criteria:** Verified by Jayman against `docs/bakeoff/results.md`.
- **Notes:** Record the choices here, in this block, for SOS-P5-07 to read. Speech to text candidates: Sarvam Saaras V3 and Deepgram Nova-3 (language=multi, with real estate keyterms). Text to speech candidates: Sarvam Bulbul V3 and ElevenLabs. Language model candidates: two or three Anthropic models, named by Jayman in `~/iespl-baseline/bakeoff/llm-models.txt` and compared by SOS-N21A's language model comparison. Rewritten by SOS-SETUP-30 (Jayman, 11 November 2026): the call languages are now Hinglish only, and the choice waits for the bake-off. Added by SOS-SETUP-33 (13 November 2026): this task includes Jayman's live run: record the 20 lines, store the four keys in the Keychain (`sellos_anthropic_key` added by SOS-SETUP-34), write the two or three candidate model names in `llm-models.txt`, run `scripts/bakeoff.sh --live` in a terminal, and fill in the rating sheet. The agent never runs `--live`. Decided by Jayman (SOS-SETUP-34, 13 November 2026, questions 3 and 10): one provider account for the language model, Anthropic, held by Jayman; keys in the Keychain locally and in encrypted settings in production. SOS-P5-07 builds adapters for every bake-off candidate behind the provider setting, and this task only records which ones the settings use. The model is not chosen by the agent. Decided by Jayman, 24 November 2026: Jayman chose Sarvam for speech to text (Saaras, the current recommended version: `saaras:v4`; `saaras:v3` stays available), text to speech (Bulbul; `bulbul:v4-flash` is available, and both `bulbul:v4-flash` and `bulbul:v3` are recorded as selectable, with v4 Flash the one to try first because Sarvam's documentation recommends it for new integrations) and the voice agent's language model (a Sarvam chat model, its exact model name a setting Jayman enters). The agent assistant uses Claude, default Sonnet 5.5 (`claude-sonnet-5-5`) as a changeable setting, on the Anthropic account Jayman holds. Jayman holds the Sarvam account and enters all keys (Keychain locally, encrypted settings in production; no key in the repository or in chat). This choice was made by Jayman without waiting for the bake-off numbers; the AI disclosure line, an acceptance criterion of this task, is written down in SOS-N21C (Jayman, 24 November 2026), and the Sarvam language model is compared with Claude Haiku 5.5 on the fixed disclosure line and the handover before the voice agent goes live. SOS-N21A is Complete and its harness compares Anthropic models only, so the comparison is SOS-N21B (the Sarvam adapter and the run, built by Claude Code with fakes) and SOS-N21BL (Jayman's run with his Sarvam key). The voice agent's language model is Sarvam 105B, to be confirmed against docs.sarvam.ai. SOS-P5-07 builds adapters for every candidate behind the provider setting; the settings use Sarvam for the three voice blocks and Claude for the assistant. `docs/bakeoff/results.md` stays "Not run yet" until Jayman runs the harness.
- **Owner:** Jayman
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 1
- **Dependencies:** SOS-N21A
- **Status:** Complete

### SOS-N21C: Write the default AI disclosure line
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want the AI disclosure line written and stored as the default of the company setting "AI disclosure line", so that every voice call opens with it from the start. Each Company Admin can edit it. The voice agent places no live call while the setting is empty.
- **Acceptance Criteria:**
  - The default of the setting "AI disclosure line" (Voice Agent Settings) is: "Namaste, main Nicole baat kar rahi hoon. Main {company} ka AI assistant hoon. Yeh call quality ke liye record ho rahi hai. Agar aap kisi insaan se baat karna chahein, toh bas bol dijiye."
  - `{company}` is replaced with the company's display name (the setting "Company name", or "the company" while it is empty) when the line is spoken. The settings screen edits the raw text. The persona name Nicole is part of the text.
  - While the setting is empty, the voice agent refuses to place a live call and creates no Call Log.
- **Test Criteria:** Backend tests in `sellos/voice/agent/test_p5_07_voice_agent.py`: the default text equals the decided line and is the default in the DocType, `{company}` is replaced when spoken and stays raw on the settings screen, an empty company name falls back to "the company", and an empty line places no live call.
- **Notes:** Decided by Jayman, 24 November 2026 (question 1). Marked Complete by SOS-LOOP: written, stored and tested. Counsel reviews the line before launch. SOS-N21 stays Complete.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 1
- **Dependencies:** SOS-N21
- **Status:** Complete

### SOS-N21B: Add the Sarvam voice model and compare it with Claude Haiku 5.5
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want the Sarvam chat model for the voice agent compared with Claude Haiku 5.5 on the lines that matter most, so that the voice agent's language model is confirmed from a measurement before it goes live. Add a Sarvam language model adapter behind the language model interface of the bake-off harness (SOS-N21A) and of the voice agent (SOS-P5-07), and add a comparison to the harness that runs the AI disclosure line (the default of SOS-N21C, with a test company name) and the handover cases (a caller asks for a human during the disclosure line and in the middle of a reply, and a confused caller) through the Sarvam model and Claude Haiku 5.5 (`claude-haiku-5-5`). A human runs it locally. The agent builds and tests it with fake providers only, and never calls a real provider.
- **Acceptance Criteria:**
  - A Sarvam language model adapter exists behind the same interface as the Anthropic one, with a fake. The Sarvam model name is read from `~/iespl-baseline/bakeoff/sarvam-llm-model.txt` (one line, written by Jayman) and is the voice agent's language model setting when the provider is Sarvam.
  - `scripts/bakeoff.sh --fake` runs the comparison with fake models and writes the replies, the time to first token and total time per case, and a rating sheet `docs/bakeoff/voice-llm-rating-sheet.md` with one row per case and model and empty 1 to 5 columns for Hinglish naturalness and for correctness (a handover must hand over).
  - `--live` still refuses to start when standard input is not a terminal, so the agent never runs it.
  - The Sarvam key comes only from the Keychain item `sellos_sarvam_key` through `get_secret`, and no key appears in any output, log, result file or traceback.
- **Test Criteria:** Backend tests with fake providers: the comparison on the disclosure line and the handover cases, the model name file read (and a missing or empty one refused), `--live` refused without a terminal, and a fake key that never appears in the output or the written files. The Keychain is never read in a test.
- **Notes:** Added by Jayman, 24 November 2026 (question 7). The language model named in SOS-N21 is "Sarvam 105B, to be confirmed against docs.sarvam.ai"; the agent does not choose or confirm the model name. Add no package: the bench is shared. `docs/bakeoff/results.md` stays "Not run yet" until Jayman runs the harness. SOS-N21BL is the live run. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Later
- **Story Points:** 3
- **Dependencies:** SOS-N21A, SOS-N21C, SOS-P5-07
- **Status:** In Progress

### SOS-N21BL: Run the Sarvam and Claude Haiku 5.5 comparison
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want to run the voice model comparison of SOS-N21B with my Sarvam key, so that the voice agent's language model is chosen from the result. Store the Sarvam key in the Keychain, write the Sarvam model name in `sarvam-llm-model.txt`, run `scripts/bakeoff.sh --live` in a terminal, fill in `docs/bakeoff/voice-llm-rating-sheet.md` and record the result.
- **Acceptance Criteria:**
  - The comparison is run live on the disclosure line and the handover cases.
  - The ratings and the latencies are recorded, and the chosen voice model is written in the SOS-N21 note.
- **Test Criteria:** Verified by Jayman.
- **Notes:** Added by Jayman, 24 November 2026 (question 7). Jayman holds the Sarvam account and key, so it is Waiting and the loop does not pick it. The agent never runs `--live`.
- **Owner:** Jayman
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 1
- **Dependencies:** SOS-N21B
- **Status:** Waiting

### SOS-P5-07: Build the voice agent service
- **Epic:** Voice AI pilot
- **Description:** As Jayman, I want an AI voice agent that can hold a short qualifying call in Hinglish, so that we can test AI calling safely. Build a service that receives call audio from Plivo by audio streaming, uses the speech to text, language model and text to speech providers chosen in SOS-N21, reads lead context from SellOS and writes the outcome back. The agent speaks Hinglish, and its transcripts and prompts are in Roman script (Jayman, 11 November 2026). It opens every call with the AI disclosure line chosen in SOS-N21, and a caller can ask for a human at any time.
- **Acceptance Criteria:**
  - A call connects to the agent over Plivo's audio streaming protocol, proven with a fake stream that replays recorded 8 kHz audio. The first real call is SOS-P5-07L.
  - The agent speaks Hinglish. Transcripts and prompts are in Roman script.
  - The AI disclosure line from SOS-N21 opens every call, before anything else is said.
  - The first audio of each reply starts within about one second of the caller finishing speaking. The time from the end of the caller's speech to the first audio sent is measured for every turn and recorded on the Call Log.
  - Real estate vocabulary is a per company list of keyterms, which a Company Admin edits, and it is passed to the speech to text provider on every call.
  - A caller can ask for a human at any time, including during the disclosure line or while the agent is speaking, and the call is handed over to a human. The agent also hands over on confusion.
  - The speech to text, language model and text to speech adapters each sit behind one replaceable interface, and the provider in use is a setting, so the SOS-N21 choice can change without a rebuild. There is an adapter for every bake-off candidate: Sarvam Saaras V3 and Deepgram Nova-3 for speech to text, Sarvam Bulbul V3 and ElevenLabs for text to speech, and Anthropic for the language model, whose model is the setting "Voice agent model" (the fast one SOS-N21 chooses).
  - It writes the outcome and transcript to the Call Log.
  - It runs the consent function of SOS-P2-04 before each call and records the consent status and warning on the Call Log. It never refuses a call on consent while Consent enforcement is Off. Consent never blocks (Jayman, 10 November 2026).
  - It records each call's purpose, and a promotional purpose on the 022 number is recorded as a warning.
- **Test Criteria:** Scripted test calls covering normal, interruption, silence and handover cases, including a request for a human during the disclosure line and mid reply. A latency measurement per turn from the end of caller speech to first audio, reported as median and slowest against the one second target. A test that the disclosure line is the first audio of every call, a test that the company's keyterms reach the speech to text request, and a test that switching the provider setting to a fake adapter changes the provider with no code change.
- **Notes:** Updated by SOS-SETUP-30 (Jayman, 11 November 2026): Hinglish, Roman script, the one second target, per company keyterms, handover at any time and replaceable adapters. Added by SOS-SETUP-33 (13 November 2026): It is built and tested against a fake provider behind the adapter interface, as SOS-N21A does with `--fake`. The agent never calls the real provider and never holds a real key: the Plivo audio stream, speech to text, the language model and text to speech each have a fake. The per turn latency and the transcript are fields this task adds to SOS-P2-05's Call Log, which it does not redefine; SOS-P2-05 comes before this task in the same tier. The company keyterm list starts from SOS-N21A's list. The AI disclosure line is a company setting that starts as SOS-N21's line. The live call is SOS-P5-07L. (Adding SOS-P2-05 and SOS-P5-07L to the voice chain's dependencies needs `test_the_voice_pilot_chain` changed, which is a question in `docs/BACKLOG_AUDIT.md`.) Decided by Jayman (SOS-SETUP-34, 13 November 2026, questions 3 and 10): this task starts before SOS-N21 and depends on SOS-P2-05 instead; SOS-N21 only sets the provider and model settings. The note above about `test_the_voice_pilot_chain` is resolved: SOS-SETUP-34 changed the test. Keys come from encrypted settings, never from the code.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P2-03, SOS-P2-04, SOS-P2-05
- **Status:** Complete

### SOS-P0-04: Provision DigitalOcean
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want staging and production servers, so that SellOS has somewhere to run. Provision droplets, firewall, MariaDB, Redis and a Spaces bucket, with SSH key access and nightly backups.
- **Acceptance Criteria:**
  - Staging and production exist.
  - Only required ports are open.
  - MariaDB and Redis restart automatically after a reboot.
  - A nightly backup file appears in Spaces.
- **Test Criteria:** A port scan shows only the expected ports, and a server reboot brings every service back.
- **Notes:** DigitalOcean Bangalore, target 24 November 2026. AMP Labs does this work, so it is Waiting and the loop does not pick it (Jayman, 10 November 2026). Owned outside the SellOS build (Jayman, 24 November 2026).
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-N18
- **Status:** Waiting

### SOS-N16: Give Claude Code the access it needs
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want Claude Code to have the access it needs, so that Phase 0 can start. Grant read access to the BuildOS repository, create a SellOS GitHub organisation with Claude Code access, and create a scoped DigitalOcean token.
- **Acceptance Criteria:**
  - Claude Code can read BuildOS.
  - Claude Code can create repositories and branches in the SellOS organisation.
  - The token covers only the staging and production projects, with no billing or account level rights.
- **Test Criteria:** (1) Claude Code lists BuildOS files and creates a test branch. (2) A call using the token to delete the account is refused.
- **Notes:** Decided by Jayman, 24 November 2026: Not Needed.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** none
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Not Needed

### SOS-P0-05: Create the wildcard DNS record and certificate
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want a wildcard record and certificate for the SellOS domain, so that every company subdomain works over HTTPS without manual steps. Create the wildcard record in DigitalOcean DNS and issue a wildcard certificate through the DNS API, with automatic renewal.
- **Acceptance Criteria:**
  - A script in `deploy/` creates or updates the wildcard record `*.sellos.interactivesoftwares.com` through the DigitalOcean DNS API, and a second run changes nothing.
  - It configures the wildcard certificate through the DNS challenge, with a renewal timer, and `--dry-run` prints every step and calls nothing.
  - The DigitalOcean token is read only from the environment variable `SELLOS_DO_TOKEN`. A missing token gives a clear error, and no token is ever printed, logged or written.
- **Test Criteria:** Backend tests against a fake DigitalOcean API: create, a second run that changes nothing, a dry run that makes no call, a missing token, and a fake token that never appears in output, logs or an error.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). This task is the code, owned by Claude Code. The agent never calls DigitalOcean. Running it on the real domain, and the original criteria (the record resolves, the certificate is valid for all subdomains, renewal runs), are SOS-P0-05D, owned by AMP Labs.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Complete

### SOS-P0-05D: Run the wildcard DNS and certificate setup on the real domain
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want the wildcard record and certificate live, so that every company subdomain works over HTTPS without manual steps. The deploy half of SOS-P0-05: AMP Labs runs SOS-P0-05's script with the real DigitalOcean token on the production DNS zone.
- **Acceptance Criteria:**
  - The wildcard record resolves to the server.
  - The certificate is valid for all subdomains.
  - Renewal runs automatically.
- **Test Criteria:** Two test hostnames serve valid HTTPS, and a renewal dry run succeeds.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). AMP Labs work, so it is Waiting and the loop does not pick it. Owned outside the SellOS build (Jayman, 24 November 2026).
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 1
- **Dependencies:** SOS-P0-04, SOS-P0-05
- **Status:** Waiting

### SOS-P0-06: Install the Frappe 16 bench with multitenancy
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want a Frappe 16 bench with DNS multitenancy, so that each hostname serves its own site. Install the bench pinned to Frappe 16.x, turn on DNS multitenancy and generate the nginx configuration.
- **Acceptance Criteria:**
  - `deploy/install-bench.sh` installs a bench on a fresh server pinned to one Frappe 16 version, turns on DNS multitenancy and generates the nginx configuration, and `--dry-run` prints every command and runs none.
  - The Frappe version is pinned in one place in the script, and it matches the Frappe branch in `.github/workflows/ci.yml`.
  - The script refuses, before any command runs, to touch a folder that already holds a bench, `~/iespl-bench` included.
- **Test Criteria:** Backend tests of the dry run output (the pinned version, `dns_multitenant` on, the nginx step, SellOS installed from 1.0), the version check against `ci.yml`, and the refusal for an existing bench.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). This task is the code, owned by Claude Code. The agent runs the script only in dry run inside a test, and never runs bench setup on the shared bench (SOS-SETUP-20). Installing on staging and production, and the original criteria (the bench runs on staging, two subdomains serve separate data), are SOS-P0-06D, owned by AMP Labs.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** none
- **Status:** Complete

### SOS-P0-06D: Install the bench on staging and production
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want a Frappe 16 bench with DNS multitenancy on the servers, so that each hostname serves its own site. The deploy half of SOS-P0-06: AMP Labs runs SOS-P0-06's script on staging and production. (SOS-P0-06L is the local bench, not this.)
- **Acceptance Criteria:**
  - The bench runs on staging and production.
  - Two sites on different subdomains serve separate data.
  - The Frappe version is the one pinned in the script.
- **Test Criteria:** Create different content on two sites and confirm each hostname shows only its own.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). AMP Labs work, so it is Waiting and the loop does not pick it. Owned outside the SellOS build (Jayman, 24 November 2026).
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 2
- **Dependencies:** SOS-P0-04, SOS-P0-06
- **Status:** Waiting

### SOS-P2-02L: Live test the Plivo adapter and webhook
- **Epic:** Calling
- **Description:** As Jayman, I want the Plivo adapter checked once against the real account, so that the fake provider the calling tasks are tested with behaves like Plivo. The live test of SOS-P2-01, SOS-P2-02 and SOS-P2-06: enter the real India account keys in Telephony Settings, press test connection, place one call through the adapter to a real Indian phone, and check that Plivo's real events reach the webhook, pass the signature check and update the Call Log. Plivo can reach the webhook only at a public HTTPS address (see the question in `docs/BACKLOG_AUDIT.md`).
- **Acceptance Criteria:**
  - Test connection reports success with the real keys, and no API response holds a key.
  - One call placed through the adapter rings a real Indian phone.
  - Plivo's real events for that call pass the signature check and update the Call Log, and the recording link is stored.
  - Every difference between Plivo's real answers and the fake provider's is written down and becomes an SOS-FIX task.
- **Test Criteria:** Verified by Jayman against the Call Log and Plivo's console.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman holds the Plivo account and keys. The agent never calls Plivo, so it is Waiting and the loop does not pick it. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 2): provider webhooks reach a public HTTPS address on staging, never a tunnel to the shared bench on port 8004, so this depends on SOS-P0-06D.
- **Owner:** Jayman
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 1
- **Dependencies:** SOS-P2-01, SOS-P2-02, SOS-P2-06, SOS-P0-06D
- **Status:** Waiting

### SOS-P2-13: Make and check test calls
- **Epic:** Calling
- **Description:** As Jayman, I want test calls proven end to end, so that we trust the setup before real use. The Indian number, +91 22 6998 6373, is already bought. Place test calls to Indian numbers only (international calling is dropped, Jayman, 10 November 2026) and check cost and recordings. This is the live test of the calling tasks, which are built and tested against a fake provider: click to call between two real phones (SOS-P2-07), a real missed call to the 022 number and whether Plivo bills it (SOS-P2-08), and the call reports against Plivo's statement (SOS-P2-11).
- **Acceptance Criteria:**
  - Click to call completes between two real Indian phones, and a real missed call to the 022 number creates its Consent Record.
  - Logged cost is within 2 percent of Plivo's statement.
  - Recordings play.
- **Test Criteria:** Reconcile the Call Log with the Plivo statement.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): India only, and it now holds the live checks of SOS-P2-07, SOS-P2-08 and SOS-P2-11. The agreed cost tolerance is a question in `docs/BACKLOG_AUDIT.md`. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 2): provider webhooks reach a public HTTPS address on staging, never a tunnel to the shared bench on port 8004, so this depends on SOS-P0-06D. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 9): the cost tolerance is 2 percent.
- **Owner:** Jayman
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P2-07, SOS-P2-02L, SOS-P2-08, SOS-P2-11, SOS-P0-06D, SOS-N22
- **Status:** Waiting

### SOS-P5-07L: Live test the voice agent
- **Epic:** Voice AI pilot
- **Description:** As Jayman, I want the voice agent checked on real calls with the providers chosen in SOS-N21, so that the pilot starts on something proven. The live half of SOS-P5-07: with the real keys in settings, place real calls to Jayman's own Indian phones.
- **Acceptance Criteria:**
  - A real call connects to the agent over audio streaming, and the AI disclosure line is the first thing said.
  - The agent speaks Hinglish, and the transcript is in Roman script.
  - The median and slowest time from the end of the caller's speech to the first audio are recorded on the Call Log and compared with the one second target.
  - Asking for a human, during the disclosure line and mid reply, hands the call to a real phone.
  - Every difference from the fakes becomes an SOS-FIX task.
  - At least 50 supervised end to end AI calls are completed before 20 December, each one checked for the disclosure line first, a working handover to a human when asked, and a reviewed transcript. They use only the purposes SOS-P5-08 allows on the 022 number.
- **Test Criteria:** At least 50 supervised end to end AI calls, each listened to by Jayman or a caller, with the latency figures, the handover results and every transcript reviewed and written down.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman holds the account and keys, so it is Waiting and the loop does not pick it. SOS-P5-08 does not start before this is Complete. Decided by Jayman (SOS-SETUP-34, 13 November 2026, questions 2 and 4): this is the Dec 20 test of the voice agent: at least 50 supervised end to end AI calls (the disclosure, the handover, reviewed transcripts). Plivo's audio stream reaches the agent at a public HTTPS address on staging, so it depends on SOS-P0-06D. Dependencies SOS-P1-25 added by SOS-SETUP-35 (13 November 2026): the core CRM comes before what uses it. Changed by Jayman, 24 November 2026: SOS-N21BL (the Sarvam and Claude Haiku 5.5 comparison) now blocks this task, so the voice model is chosen before the first real call.
- **Owner:** Jayman
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 2
- **Dependencies:** SOS-P5-07, SOS-N21, SOS-P2-02L, SOS-P0-06D, SOS-P1-25, SOS-N21BL
- **Status:** Waiting

### SOS-P0-08: Write the deployment scripts
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want scripted deployment and rolling upgrades, so that a release reaches every company site safely. Write one command to deploy a tagged release to staging, another to promote it to production, and a rolling upgrade that runs migrations site by site and stops on the first failure.
- **Acceptance Criteria:**
  - The deploy and promote commands take a release tag and, in `--dry-run`, print every step for staging and for production without reaching a server.
  - The rolling upgrade migrates sites one at a time, stops at the first failure, reports which site failed, and leaves the sites after it untouched.
  - Rollback steps are documented.
- **Test Criteria:** On the local bench, make two tenant sites with `sellos.provisioning.tenant_sites`, force a migration failure on the first, confirm the run stops, names it and does not migrate the second, and drop both. Dry run tests of deploy and promote.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). This task is the code, owned by Claude Code, and is tested on local tenant sites only. Deploying to staging with two sites is SOS-P0-08D, owned by AMP Labs.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P0-06, SOS-P0-06L
- **Status:** Complete

### SOS-P0-08D: Prove the deployment scripts on staging
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want the deployment scripts proven on a real server, so that a release reaches every company site safely. The deploy half of SOS-P0-08: AMP Labs deploys a tagged release to staging with SOS-P0-08's commands and checks the rolling upgrade there.
- **Acceptance Criteria:**
  - The deploy and promote commands work on staging and production.
  - On staging with two sites, a forced migration failure on one stops the run and reports it.
  - The documented rollback steps were followed once on staging and worked.
- **Test Criteria:** Deploy to staging with two sites, force a migration failure on one, and confirm the run stops and reports it.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). AMP Labs work, so it is Waiting and the loop does not pick it. Owned outside the SellOS build (Jayman, 24 November 2026).
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 2
- **Dependencies:** SOS-P0-06D, SOS-P0-08
- **Status:** Waiting

### SOS-P0-13: Set up outgoing email in production
- **Epic:** Platform foundations and DevOps
- **Description:** As Jayman, I want SellOS to send real email, so that invitations, alerts, scheduled reports and billing mail reach people. Set up a transactional mail provider for production, with SPF and DKIM on the domain.
- **Acceptance Criteria:**
  - A transactional mail provider sends from the SellOS domain.
  - SPF and DKIM pass for the domain.
  - A test email from a company site arrives and is not marked as spam.
- **Test Criteria:** Send a test email from production and check its headers.
- **Notes:** Added by SOS-SETUP-34 (Jayman, 13 November 2026, question 16). AMP Labs work, so it is Waiting and the loop does not pick it. Owned outside the SellOS build (Jayman, 24 November 2026).
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 2
- **Dependencies:** SOS-P0-04
- **Status:** Waiting

### SOS-P1-11: Create the Pandya Realtors site
- **Epic:** Multitenancy and provisioning
- **Description:** As Jayman, I want the Pandya Realtors company site live, so that the first tenant can start working. Create the Pandya site at its subdomain, apply the branding and load the users.
- **Acceptance Criteria:**
  - The site is live over HTTPS.
  - Admin and agent users exist.
  - Branding is applied.
- **Test Criteria:** Jayman signs in as each role and sees the correct screens.
- **Notes:** Dependencies added by SOS-SETUP-33 (13 November 2026): the site goes live over HTTPS only once the bench is installed on production (SOS-P0-06D) and the wildcard certificate is issued (SOS-P0-05D). Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 16): depends on SOS-P0-13, outgoing email in production.
- **Owner:** AMP Labs, Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-03, SOS-P0-05D, SOS-P0-06D, SOS-P0-13
- **Status:** Waiting

### SOS-FIX-1: An unknown path under /sellos shows a blank page
- **Epic:** Regression fixes
- **Description:** Found in a clickthrough on the SellOS test site on 4 November 2026, outside a milestone run. Opening a path under /sellos that matches no screen, for example /sellos/does/not/exist, renders the shell (navigation and top bar) with a blank body. The person should see a page not found screen with a way back to Home.
- **Acceptance Criteria:**
  - Any unknown path under /sellos, for example /sellos/does/not/exist, shows a page not found screen (data-testid `sellos-not-found`) inside the shell, with a link to Home that opens /sellos.
  - This holds for every role (every key of `TEST_USERS`: platform_admin, company_admin, agent, channel_partner, client, basic), and no console error is logged.
  - A Cypress spec that names SOS-FIX-1 signs in as each role, opens /sellos/does/not/exist, checks the not found screen and the Home link, and fails on any console error. It fails without the fix and passes with it.
  - A FLOW line for SOS-FIX-1 is added to `docs/regression/flows.md` in the five field form that file describes.
- **Test Criteria:** The Cypress spec above passes in the gate, and `scripts/check_task_evidence.py` finds the FLOW line.
- **Notes:** MUST for 1 January 2027 (Jayman, 27 November 2026). Reset from Blocked to Not Started by Jayman's authorisation, 27 November 2026; MUST, Dec 20.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 1
- **Dependencies:** SOS-P0-10
- **Status:** Not Started
- **Browser spec:** required

### SOS-P1-09: Build the website lead endpoint
- **Epic:** Core CRM and consent
- **Description:** As the website, I want a secure endpoint to send enquiries, so that leads reach SellOS with their consent wording. Build an HTTPS endpoint secured by a per company key. It creates a Lead and a Consent Record from each submission that carries consent wording. Consent never blocks (Jayman, 10 November 2026). A submission without consent wording is accepted: it creates the lead with consent status Unknown and records a warning.
- **Acceptance Criteria:**
  - A valid submission with consent wording creates a lead and a Consent Record, and the lead is Consented.
  - A bad key is rejected.
  - A submission without consent wording creates the lead with consent status Unknown and a recorded warning, and no Consent Record.
  - The endpoint is rate limited.
- **Test Criteria:** Tests for valid, bad key, missing consent wording (accepted, Unknown, warning recorded) and flood submissions.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): SOS-P2-08's enquiry page and this endpoint both turn a form submission into a Lead and a Consent Record. SOS-P2-08 builds the one lead intake function (`sellos.crm.intake`) and this endpoint calls it, adding only the per company key and the rate limit; it does not build a second intake path. The per company key is a record that holds a hash of the key and its scope (Lead intake here; SOS-P4-08 adds Listings read), shown once when it is made and never returned by an API. The Consent Record's evidence link is the raw submission saved as a private file (`/private/files/...`), which SOS-P1-08's evidence rule already accepts, so that rule is not changed. The consent wording comes from the company setting that SOS-P2-08 adds. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 5): the consent wording is the company setting "Consent wording", which each Company Admin can edit. Its default text is written by Jayman (SOS-N22); counsel reviews it after launch. Tests use their own wording. Dependencies SOS-P1-16, SOS-P1-19, SOS-P1-20 added by SOS-SETUP-35 (13 November 2026): the core CRM comes before what uses it. Decided by Jayman (SOS-LOOP, 21 November 2026): public intake is the second exception to "every API method needs a login", only for creating or merging a lead through `sellos.crm.intake`, under the rules in CLAUDE.md ("Public intake forms") and docs/permissions.md ("Public intake forms"). The website form endpoint is a registered public intake method built on SOS-P2-08's registry and checks (form key, rate limits, honeypot, size cap, validation, consent evidence file). It builds no second registry and no second check.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P1-08, SOS-P2-08, SOS-P1-16, SOS-P1-19, SOS-P1-20
- **Status:** Complete

### SOS-P1-10: Connect the Pandya website forms
- **Epic:** Core CRM and consent
- **Description:** As Jayman, I want the Pandya website forms connected to SellOS, so that enquiries arrive automatically. Point the form handlers at the endpoint, show the consent wording approved by counsel next to each form, and keep the website's own copy of each lead.
- **Acceptance Criteria:**
  - Each form posts to the endpoint.
  - The approved wording is shown.
  - Failures are retried and alerted.
  - The website still holds a copy.
- **Test Criteria:** Submit a form and see the lead in SellOS within a minute.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): SOS-N07 (counsel's review of the consent wording) is Not Needed, so "the consent wording approved by counsel" has no source yet. The wording is the company setting added by SOS-P2-08; who writes and approves its text is a question in `docs/BACKLOG_AUDIT.md`. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 5): the consent wording is the company setting "Consent wording", which each Company Admin can edit. Its default text is written by Jayman (SOS-N22); counsel reviews it after launch. Tests use their own wording.
- **Owner:** AMP Labs
- **Priority:** P1
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P1-09, SOS-N22
- **Status:** Waiting

### SOS-P7-01: Onboard and approve channel partners
- **Epic:** Channel partners
- **Description:** As a Company Admin, I want to invite channel partner firms and approve them before they work, so that only vetted partners register leads. Add Channel Partner Firm: firm name, contact person, phone, email, RERA agent registration number, PAN, the signed agreement (a private file), a status of Invited, Pending approval, Approved or Suspended, and a unique partner code. The contact person's login is made through SOS-P1-17's invitation with the SellOS Channel Partner role.
- **Acceptance Criteria:**
  - A Company Admin invites a firm by email. Its contact person gets a Channel Partner login through SOS-P1-17's invitation, completes the firm's details, and the firm moves to Pending approval.
  - Only a Company Admin approves, suspends or reinstates a firm, with a reason for a suspension. A partner whose firm is not Approved signs in to a page that says so, and can register no lead and see no inventory.
  - Each firm gets a unique partner code that is never reused; SOS-P5-06 uses it for the partner's link and QR code.
  - The RERA agent registration number and the PAN are checked for format. The PAN and the signed agreement are seen only by Company Admins, and the agreement is a private file.
  - The firm's phone number is masked for every role but the Company Admin, as a lead's is.
  - Every status change is logged with who made it and when. Nothing is deleted; a firm that leaves is Suspended.
- **Test Criteria:** Backend tests of the invitation, approval, suspension, the code's uniqueness, the format checks and the permissions (an unapproved partner is refused, an Agent cannot approve); a Cypress spec of a Company Admin inviting and approving a firm. Phone numbers come from `sellos.tests.phones`.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve'). The PAN is personal data; holding it, visible to Company Admins only, is part of what Jayman approved.
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P1-04, SOS-P1-17
- **Browser spec:** required
- **Status:** Complete

### SOS-P7-02: Register a lead as a channel partner, with a protection window
- **Epic:** Channel partners
- **Description:** As a Channel Partner, I want to register a buyer and have the lead protected in my name, so that I am paid when a buyer I brought books. Build the one whitelisted method by which a partner of an Approved firm registers a buyer (name, phone, project of interest, a note, and the confirmation wording shown to them), and the Partner Registration record with its protection window.
- **Acceptance Criteria:**
  - Only a partner of an Approved firm (SOS-P7-01) can register. The method is rate limited by the company setting "Partner lead limit", default 20 leads per partner per hour (Jayman, SOS-SETUP-34), and refuses the next one with a clear message.
  - The phone and email are checked with SOS-P1-16's matching function. A new buyer creates a Client and a Lead with the source Channel partner (SOS-P1-20), the partner recorded on the lead, on the first stage of the buyer pipeline (SOS-P1-07), and a Partner Registration in status Registered.
  - A buyer who already exists creates no second lead, and the partner is told only: "Not accepted: this buyer is already registered with the company." The reply never says who registered them, their name, their agent, their stage or anything else.
  - The registration records the confirmation wording shown (the company setting "Partner confirmation wording", not the buyer's "Consent wording"). When the partner confirms the buyer agreed, a Consent Record is made through SOS-P1-08; otherwise the lead's consent status is Unknown with a warning. Consent never blocks.
  - A Company Admin approves or rejects each registration, with a reason for a rejection. An approved registration is protected in the partner's name for the company setting "Partner protection days", default 90 days (Jayman, 13 November 2026), counted from the approval.
  - While a registration is protected, only a Company Admin can change the lead's partner, and the change is logged. Protection decides who is owed commission; it never blocks a call, a message or an agent's work on the lead.
  - The partner follows each registration through Registered, Approved, Visited, Booked, Expired and Rejected. A Site Visit marked Done on the lead moves it to Visited; SOS-P7-10's booking moves it to Booked; a protected registration whose window ends without a booking becomes Expired (run as a function the tests call with a fixed clock).
  - A partner sees only their own registrations and leads, read only after registering, logs nothing, and sees phone numbers masked. Every step is logged.
- **Test Criteria:** Backend tests of a new buyer, an existing buyer (the reply holds nothing but the sentence above), the 21st registration in an hour refused, approval and rejection, expiry with a fixed clock, the partner change refused to everyone but a Company Admin, Visited on a done site visit, and the permissions; a Cypress spec of a partner registering a buyer and a Company Admin approving it.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve'). This task owns the partner's registration method; SOS-P5-06's registration screen calls it and builds no second method. It is a permission change Jayman approved (SOS-SETUP-34 question 13, SOS-SETUP-35). Changed by Jayman, 24 November 2026: the partner confirms with its own company setting "Partner confirmation wording", default exactly "I confirm my client has agreed that {company} and its agents may contact them about this enquiry.", and no longer reads "Consent wording". {company} is replaced with the company's display name (or "the company") by the same `render_wording` as SOS-N22, the settings screen edits the raw text, and the registration keeps the wording as shown. Tests in `sellos/crm/test_n22_consent_wording.py` and `sellos/access/test_p7_02_partner_registrations.py`.
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P7-01, SOS-P1-16, SOS-P1-20, SOS-P1-07, SOS-P1-08
- **Browser spec:** required
- **Status:** Complete

### SOS-P4-01: Build Developer, Project, Unit and Property
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want developers, projects, units and properties recorded with RERA numbers, so that inventory is accurate. Build the records with RERA numbers, unit configuration, carpet area, floor and parking, and a unit status of available, held or sold, for both primary projects and secondary properties.
- **Acceptance Criteria:**
  - Records can be created and edited in the app.
  - The RERA number is stored for projects.
  - Unit status changes are logged.
  - Only permitted roles can edit.
- **Test Criteria:** Unit and permission tests, and an end to end test of creating a project with units.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P1-04
- **Status:** Complete
- **Browser spec:** required

### SOS-P7-05: Towers, wings and floors for projects
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want each project's towers, floors and units laid out, so that large projects are easy to enter and read and the unit grid has a structure. Add towers or wings to a project, each with its floors and the units on each floor, plus the project's possession date, amenities and brochure files.
- **Acceptance Criteria:**
  - A user who may edit inventory (SOS-P4-01) adds towers or wings to a project, and the floors of each, and generates the units of a floor from a pattern (for example 1201 to 1208) with their configuration and carpet area.
  - Generating again changes nothing that already exists, and unit numbers are unique within a tower.
  - A project holds its possession date, amenities (from a list the Company Admin edits) and brochure files (Media Assets).
  - Removing a tower or floor that has a unit in any status but Available is refused, with the count of such units.
- **Test Criteria:** Backend tests of the structure, the pattern generation run twice, uniqueness and the refused removal; a Cypress spec of adding a tower and generating a floor.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve').
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P4-01
- **Browser spec:** required
- **Status:** Complete

### SOS-P7-06: Unit availability grid with holds and bookings
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want to see which units are free and hold one for a buyer, so that we never double sell. Build a grid of each tower's floors and units, coloured by status, and holds that expire by themselves. This task adds Booked to SOS-P4-01's unit statuses, which become Available, Held, Booked, Sold and Blocked.
- **Acceptance Criteria:**
  - The grid shows each tower's floors and units coloured by status (Available, Held, Booked, Sold, Blocked) with a legend, and filters by configuration and status. A patch adds Booked and Blocked and changes no existing unit.
  - An agent holds an Available unit for one of their leads. A hold lasts the company setting "Unit hold hours", default 48 hours (Jayman, 13 November 2026), and is released when it expires (run as a function the tests call with a fixed clock).
  - Two holds on one unit can never both succeed: the second is refused with who holds it and until when, even when both arrive at the same moment.
  - The holding agent or a Company Admin releases a hold. A Company Admin blocks a unit from sale, or unblocks it, with a reason.
  - Booked and Sold are set only by SOS-P7-10's booking and its completion, never from the grid.
  - A held unit shows its agent; the lead's name shows only to users who may see that lead. Every status change is logged with who made it and when.
- **Test Criteria:** Backend tests of each status change, expiry with a fixed clock, and two concurrent holds on one unit from two database connections (exactly one succeeds); a Cypress spec of holding and releasing a unit on the grid.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve').
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P7-05
- **Browser spec:** required
- **Status:** Complete

### SOS-P7-07: Price lists, payment plans and cost sheets
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want a price, a payment plan and a cost sheet for any unit, so that a buyer sees exactly what they will pay. Add dated price lists and payment plan templates to projects, and a cost sheet made from a unit.
- **Acceptance Criteria:**
  - A project has dated price lists: a base rate per square foot of carpet area, a floor rise per floor above a set floor, preferred location charges, parking and other charges (each an amount or a rate). One price list is in force at a time, and earlier ones are kept.
  - Payment plan templates (construction linked, time linked, down payment) list instalments as percentages that must add up to 100.
  - From a unit, an agent makes a cost sheet: the price from the price list in force, the charges, stamp duty, registration and GST at percentages the Company Admin sets as company settings, the total, and the chosen payment plan's schedule, on screen and as a PDF with the company's branding.
  - A cost sheet records the price list and the percentages it used, so a later change never alters one already made.
  - Amounts are in rupees, rounded to the rupee, and match hand worked examples.
- **Test Criteria:** Backend tests of the price and the cost sheet on hand worked examples, the 100 percent rule and an issued cost sheet unchanged after a price change; a Cypress spec of making a cost sheet from a unit.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve').
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P7-05
- **Browser spec:** required
- **Status:** Complete

### SOS-P4-02: Build Listing
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want listings typed as primary, Direct or Partner, so that the website shows the right sections. Build Listing linked to a unit or property, with a type, a publish flag and a change history.
- **Acceptance Criteria:**
  - Each listing has a type.
  - Publishing needs the required fields.
  - Changes are audited.
- **Test Criteria:** An end to end create and publish, and a test that an incomplete listing cannot publish.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P4-01
- **Status:** Complete
- **Browser spec:** required

### SOS-P4-03: Build Media Asset
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want photos and videos linked to listings, so that listings look complete. Link media from the asset library to listings, with size and type checks and an order.
- **Acceptance Criteria:**
  - Media attaches to a listing.
  - Invalid files are rejected.
  - The order can be changed.
- **Test Criteria:** Upload valid and invalid files.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 11): the asset library is the company's uploaded files.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P4-02
- **Status:** Complete
- **Browser spec:** required

### SOS-P7-03: Share projects, units and collateral with channel partners
- **Epic:** Channel partners
- **Description:** As a Company Admin, I want to choose what each channel partner may see, so that partners sell only what we share with them. A Company Admin shares a project, with all or chosen units, its price list and chosen brochures, with one partner firm, several, or every Approved firm.
- **Acceptance Criteria:**
  - A Company Admin shares a project (all units or chosen ones), its price list in force (SOS-P7-07) and chosen brochures (Media Assets, SOS-P4-03) with chosen Approved firms or with all of them, and can withdraw a share.
  - A partner sees only what is shared with their firm: no other project, unit, price or file, and nothing about other partners or their registrations.
  - A withdrawn share, or a firm that is Suspended, stops showing at once.
  - Every share and withdrawal is logged.
- **Test Criteria:** Permission tests: a partner of each of two firms sees exactly what is shared with their firm, through every list and record method; a Cypress spec of sharing a project and withdrawing it.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve'). SOS-SETUP-35 added SOS-P7-07 to the dependencies on the sheet, because this task shares price lists, which SOS-P7-07 builds.
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P7-01, SOS-P4-01, SOS-P4-03, SOS-P7-07
- **Browser spec:** required
- **Status:** Complete

### SOS-P7-08: Match buyers to inventory
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want SellOS to suggest units and listings that suit a buyer, and buyers that suit a unit, so that I offer the right homes quickly. Score published listings and Available units against a lead's requirements (SOS-P1-15).
- **Acceptance Criteria:**
  - From a lead, SellOS lists matching published listings and Available units, scored 0 to 100 on budget, configuration, locality and property type, with each part of the score and a reason shown (for example "2 BHK matches, 5 percent over budget").
  - The weights of the four parts are company settings, 25 each by default.
  - A unit that is not Available, or a listing that is not published, is never suggested.
  - From a listing or a unit, SellOS lists the leads it suits that the user may see: an agent only their own leads, a Sales Manager their team's, with phone numbers masked as the role requires.
  - Matching one lead against 5,000 units and listings answers within 2 seconds on the test site.
- **Test Criteria:** Backend tests of the score on hand worked examples, of what is never suggested, of the permissions in both directions, and the 5,000 record timing with generated records; a Cypress spec of an agent opening a lead's matches.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve').
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P1-15, SOS-P4-02, SOS-P7-06
- **Browser spec:** required
- **Status:** Complete

### SOS-P7-09: Shortlists and sharing with buyers
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want to build a shortlist for a buyer and share it, so that the buyer reviews homes in one place. A shortlist is a list of listings and units for one client, made by the agent and seen by the client (Jayman, SOS-SETUP-34 question 11).
- **Acceptance Criteria:**
  - An agent makes a shortlist for one client from listings and units, orders the items and adds a note to each. SOS-P7-08's matches get an Add to shortlist button.
  - Sharing sends the client a link to their own client view (SOS-P5-05), which they open after signing in, or a PDF with the company's branding, the photos (Media Assets) and the prices. Neither holds another client's data or any phone number but the agent's.
  - The agent sees which items the client opened, and when.
  - An item whose listing is unpublished, or whose unit is no longer Available, is marked so on the shortlist.
- **Test Criteria:** Backend tests of the shortlist, the opened marks, the marking of unavailable items and the permissions (a client sees only their own shortlist); a Cypress spec of building and sharing a shortlist.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve').
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P7-08, SOS-P4-03
- **Browser spec:** required
- **Status:** Complete

### SOS-P4-08: Build the listings endpoint
- **Epic:** Inventory, mandates and deals
- **Description:** As the website, I want a read only listings endpoint, so that listings appear without manual entry. Build an endpoint, keyed per company, that returns published listings, plus a webhook that announces changes, with caching.
- **Acceptance Criteria:**
  - Only published listings are returned.
  - Changes trigger the webhook.
  - A bad key is rejected.
- **Test Criteria:** Contract tests and a change push test.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): SOS-P1-09 defines the per company key record with a scope. This endpoint adds the Listings read scope to that record and builds no second key store, so SOS-P1-09 is a dependency. A Lead intake key never reads listings, and a Listings read key never creates leads. Decided by Jayman (SOS-LOOP, 22 November 2026): a public listings feed is the third allowed guest kind, only for the website reading published listings with the Listings read key, under the rules in CLAUDE.md ("Public listings feed") and docs/permissions.md ("Public listings feed"): read only, published only, an explicit field allowlist (no owner or seller data, phone numbers, mandate or dossier files, internal notes or unpublished media), the key in a header never in the URL, one short answer for a bad key, rate limits per key and per tenant, a page size cap, ETag caching, the tenant from the site, no cookies. The outbound change webhook is signed with a per tenant secret that never appears in a log, retried, HTTPS only, refuses private addresses and carries no personal data. This task builds the registry (`sellos.access.public_listings`) and its shared checks once, and extends the `sellos/access/test_webhook_guest_guard.py` tests to cover a real registered feed method.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P4-02, SOS-P1-09
- **Status:** Complete

### SOS-P4-09: Switch the website to read listings from SellOS
- **Epic:** Inventory, mandates and deals
- **Description:** As Jayman, I want the Pandya website to show listings from SellOS, so that nothing is entered twice. Render the listing pages from the endpoint, remove unpublished listings within 15 minutes, and fall back safely if the endpoint is down.
- **Acceptance Criteria:**
  - Pages render from the endpoint.
  - Unpublishing removes a listing within 15 minutes.
  - An outage shows the last good copy.
- **Test Criteria:** Toggle a listing and check the site, and simulate an outage.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 9): 15 minutes. Decided by Jayman, 24 November 2026: the Pandya website is built in WordPress. Pages render from the SellOS endpoint inside WordPress (a theme or plugin snippet), with the last good copy kept for an outage. Campaign forms on the same site are SOS-P4-11 and SOS-P4-12.
- **Owner:** AMP Labs
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P4-08
- **Status:** Waiting

### SOS-P4-11: Build campaign forms in the web app
- **Epic:** Inventory, mandates and deals
- **Description:** As a Company Admin, I want to build a form for each campaign and copy it onto my website, so that every campaign's leads arrive tagged. Build a Campaign Form record and its builder screen in the SellOS web app.
- **Acceptance Criteria:**
  - A Company Admin makes a form per campaign: its fields (from the fields the website form endpoint accepts: name, phone, email, message, and the requirement fields that endpoint allows), its consent wording (default from the company setting "Consent wording", `{company}` replaced with the company's display name as in SOS-N22), and a campaign tag.
  - The screen shows two things to copy: an embed snippet (a div and one script tag) and an optional WordPress shortcode with the few lines of code that register it in the WordPress theme.
  - The form renders in the host page, not in an iframe, and carries no styling of its own, so it inherits the site's design (plain elements with stable class names the site can style).
  - A form is Active or Off; an Off form submits nothing. Each form lists the allowed website domains it may be used on.
  - The snippet carries the company's Lead intake key (SOS-P1-09) and no other key; rotating the key shows a warning that embedded snippets must be updated.
  - Only a Company Admin builds forms. Nothing is deleted: a form is archived.
- **Test Criteria:** Backend tests of the record, the permission check, the snippet and shortcode text (no key other than the Lead intake key, no styling, no iframe) and the wording substitution; a Cypress spec of building a form and copying the snippet.
- **Notes:** Decided by Jayman, 24 November 2026. The website is built in WordPress (SOS-P4-09). A campaign form is not a new kind of guest method: it is the existing public intake method of SOS-P1-09 (scope Lead intake) with extra known fields, built in SOS-P4-12; CLAUDE.md's "Public intake forms" rules apply unchanged. Split with SOS-P4-12 to keep each story within 8 points. Expected flow (Jayman, 24 November 2026; the builder adds it to `docs/regression/flows.md` when building the feature, one `FLOW` line each, and does not add flows in advance): 1. As company_admin, from `/sellos/campaign-forms`: Sign in. Make a campaign form with a name, a phone, a campaign tag and the default consent wording. Open the embed snippet and the WordPress shortcode. Expected: The wording shows the company name instead of the placeholder, the snippet is a div and a script tag with no iframe and no styling, and it holds the Lead intake key and no other key. 2. As company_admin, from `/sellos/campaign-forms`: Add an allowed website domain, then turn the form Off and archive it. Expected: The domain is listed, an Off form is marked Off, and an archived form is kept in the archive, never deleted. 3. As agent, from `/sellos/campaign-forms`: Sign in as the gate agent and type the address of the campaign forms page. Expected: The page says there is no access. MUST for 1 January 2027 (Jayman, 27 November 2026). Integrates with the Pandya website forms (WordPress, SOS-P4-09); MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P1-09, SOS-N22
- **Status:** Not Started
- **Browser spec:** required

### SOS-P4-12: Submit campaign forms into SellOS
- **Epic:** Inventory, mandates and deals
- **Description:** As a Company Admin, I want a campaign form on my website to create a tagged lead in SellOS, so that I see which campaign each lead came from. Extend the website lead endpoint of SOS-P1-09 for campaign forms, and ship the script that renders a form in the host page.
- **Acceptance Criteria:**
  - The script, served as a static file by SellOS, renders the Campaign Form's fields into the host page and submits straight to `sellos.crm.website_form.submit_website_lead` with the company's Lead intake key. It sets no cookie and reads no record.
  - The endpoint accepts new known fields only: the campaign form id and the UTM details (source, medium, campaign, term, content). They are length checked, unknown fields are still refused, and a form id of an Off or archived form is refused with the same short answer as a bad key.
  - The lead carries the campaign (the Lead `campaign` field is set from the form's campaign tag) and the UTM details, in new Lead fields, change tracked like every CRM field.
  - Allowed website domains per form: a submission from a page whose Origin or Referer is not in the form's list is refused with the same short answer, before any write.
  - The honeypot, rate limit, size cap, strict validation, consent evidence file (the wording shown with `{company}` filled in, its version, the time and the address) and tenant rules of CLAUDE.md apply unchanged, and `sellos/access/test_webhook_guest_guard.py` still passes with no new guest method.
  - The answer is only a thank you and a reference code.
- **Test Criteria:** Backend tests: a valid submission makes a lead with the campaign and UTM details and a Consent Record with the filled in wording; a wrong domain, an Off form, a bad key, a filled honeypot, an unknown field, an oversized body and a flood are each refused or ignored as the rules say; the guard test passes. A Cypress spec of submitting an embedded form on a page served from an allowed domain.
- **Notes:** Decided by Jayman, 24 November 2026. Reuses SOS-P1-09's per company key endpoint and SOS-P2-08's public intake registry; it adds no registry, no check of its own and no new kind of guest method. The domain check is a declared check of the same registered method. Expected flow (Jayman, 24 November 2026; the builder adds it to `docs/regression/flows.md` when building the feature, one `FLOW` line each, and does not add flows in advance): 1. As company_admin, from `/sellos/campaign-forms`: Open the test page for a form on an allowed domain, fill it in with UTM details in the address and submit. Then open the new lead. Expected: The form thanks the visitor with a reference, and the lead shows the campaign tag and the UTM details and a Consent Record with the wording as shown. 2. As company_admin, from `/sellos/campaign-forms`: Submit the same form from a page on a domain that is not in the form's list. Expected: The submit gets the same short answer as any refusal and no lead is made. MUST for 1 January 2027 (Jayman, 27 November 2026). Integrates with the Pandya website forms (WordPress, SOS-P4-09); MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P4-11, SOS-P1-09
- **Status:** Not Started
- **Browser spec:** required

### SOS-P4-04: Build the seller pipeline
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want a seller pipeline, so that owners are tracked to a signed mandate and a sale. Build the stages New owner enquiry, Qualified, Valuation shared, Mandate proposed, Mandate signed, Listed, Offers received, Sold, Closed lost and Nurture.
- **Acceptance Criteria:**
  - All stages exist.
  - Stage rules are enforced. The rule that a seller cannot reach Listed without a signed mandate is added by SOS-P4-05, which builds Mandate.
  - Changes are logged.
- **Test Criteria:** Stage rule tests.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): Pipeline Stage (SOS-P1-03, SOS-P1-07) has no pipeline field, so the seller stages would mix with the buyer stages. This task supersedes the single stage list: it adds a `pipeline` field (Buyer or Seller) to Pipeline Stage, a patch that can be run again safely sets every existing stage to Buyer, and the seller stages above are seeded as Seller (Sold a Won stage, Closed lost a Lost stage, the rest Open). `MAX_STAGES`, the rule of at least one Won and one Lost stage, and the rule that a stage with leads cannot be deleted (SOS-P1-07) apply to each pipeline on its own. The buyer screens and SOS-P1-03's and SOS-P1-07's tests filter on Buyer and keep every assertion; the number of assertions in each changed test must not fall. The no Listed without a signed mandate rule moved to SOS-P4-05, because Mandate does not exist before it. Whether a seller is a Lead on the Seller pipeline or a record of its own is a question in `docs/BACKLOG_AUDIT.md`; reply NEEDS_INPUT if it is still open when this task starts. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 11): a seller is a Lead on the Seller pipeline, linked to a Client.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P4-02
- **Status:** Complete
- **Browser spec:** required

### SOS-P4-05: Build Mandate
- **Epic:** Inventory, mandates and deals
- **Description:** As an owner and an Agent, I want a mandate recorded, so that the Private Sale Dossier is shared only against a signed agreement. Build Mandate as exclusive or open with term, fee and a signed document upload. The Dossier is released only when the mandate is signed, and each view is audited.
- **Acceptance Criteria:**
  - Mandates carry type, term and fee.
  - The signed document is required.
  - The Dossier is hidden until signed.
  - Each Dossier view is logged.
  - A seller cannot be moved to the Listed stage without a signed mandate (the stage rule from SOS-P4-04).
  - The Private Sale Dossier (the files and notes attached to a Mandate) is released only when the Mandate is signed.
- **Test Criteria:** Try to open the Dossier without a signed mandate and confirm it fails.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): the Listed stage rule moved here from SOS-P4-04. What the Private Sale Dossier holds is not defined anywhere; it is a question in `docs/BACKLOG_AUDIT.md`. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 11): the Private Sale Dossier is the files and notes attached to a Mandate, released only when the Mandate is signed.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P4-04
- **Status:** Complete
- **Browser spec:** required

### SOS-P4-10C: Build the listings and mandates import
- **Epic:** Inventory, mandates and deals
- **Description:** As a Company Admin, I want to import my current developers, projects, units, properties, listings and mandates from a spreadsheet in the SellOS web app, so that a company starts with its real business without the desk. Reuse SOS-P1-12's CSV import code. A mandate imported without its signed document stays unsigned, so its Dossier stays hidden (SOS-P4-05).
- **Acceptance Criteria:**
  - A Company Admin downloads a template per record type and uploads a filled file in the web app.
  - A dry run shows the counts, the rows that would fail and why, and writes nothing.
  - Duplicates are matched on RERA number for projects and on project and unit number for units, and are updated, not doubled.
  - A run writes a reconciliation report with the counts per record type, and running the same file again changes nothing.
- **Test Criteria:** Backend tests with a sample file holding duplicates and bad rows, a second run that changes nothing, and a permission test. A Cypress check of the dry run and the import.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): SOS-P4-10 needs an import, and no task built one.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P4-05, SOS-P1-12
- **Status:** Complete
- **Browser spec:** required

### SOS-P4-10: Import current listings and mandates
- **Epic:** Inventory, mandates and deals
- **Description:** As Jayman, I want current listings and mandates imported, so that SellOS holds the real business. Import Pandya's current listings and mandates and reconcile the counts with the source sheet.
- **Acceptance Criteria:**
  - Imports complete.
  - Counts reconcile.
  - Duplicates are resolved.
- **Test Criteria:** A reconciliation report signed off by Jayman.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): customers never use the desk, and Frappe's Data Import is a desk tool, so the import is built in the web app as SOS-P4-10C, and this task runs it on Pandya's data. Decided by Jayman, 24 November 2026: Not Needed. SOS-P4-10C is the importer, and Jayman uploads the sheet when needed.
- **Owner:** AMP Labs, Jayman
- **Priority:** P4
- **Launch:** none
- **Story Points:** 3
- **Dependencies:** SOS-P4-05, SOS-P4-10C
- **Status:** Not Needed

### SOS-P4-06: Build Deal and Commission Split
- **Epic:** Inventory, mandates and deals
- **Description:** As a Company Admin, I want deals and commission splits recorded, so that we know who earns what. Build Deal linking client, unit or property and price, and Commission Split among agent, channel partner and company with percentages that sum to 100, approved by a Company Admin.
- **Acceptance Criteria:**
  - Deals link client and property.
  - Splits must sum to 100 percent.
  - A Company Admin approves splits.
  - Channel Partner shares are supported.
- **Test Criteria:** Validation tests and worked split examples.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P4-05
- **Status:** Complete
- **Browser spec:** required

### SOS-P7-04: Commission rules and payout tracking
- **Epic:** Channel partners
- **Description:** As a Company Admin, I want commission rates per project and partner and each payout tracked to payment, so that partners are paid correctly and on time. Add Commission Rate and Commission Payout on top of SOS-P4-06's Deal and Commission Split.
- **Acceptance Criteria:**
  - A Company Admin sets a commission rate per project, as a percentage of the agreement value or a fixed amount, with an optional rate for a partner firm that overrides it, each with a start date. Earlier rates are kept.
  - When a deal with a channel partner share is approved (SOS-P4-06), the commission due is worked out from the rate in force on the booking date and the partner's share of the split, and a Commission Payout is made in status Due.
  - A Company Admin moves a payout through Due, Approved and Paid, recording the payment reference and date at Paid, or puts it On hold with a reason. Nothing is deleted.
  - A partner sees their own payouts and a statement for a date range, and nobody else's.
  - A Company Admin exports a partner's statement as a report result under the SOS-P5-04 rule: only what they may see, phone numbers masked, every export logged. Raw DocType export stays Platform Admin only.
  - Amounts are in rupees to two decimals, and every change is logged.
- **Test Criteria:** Backend tests of the calculation on hand worked examples (a project rate, a firm override, a rate changed after the booking date), each status change and the permissions; a Cypress spec of approving and paying a payout and of a partner reading their statement.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve').
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P7-01, SOS-P4-06
- **Browser spec:** required
- **Status:** Complete

### SOS-P5-06: Build the Channel Partner views
- **Epic:** Client and partner views
- **Description:** As a Channel Partner, I want to register leads and track my deals, so that I can work with the company. Build partner views to register leads with consent, see shared inventory, and track their own deals and commission status. Added at SOS-P1-06 (Jayman): the partner also sees earnings so far, potential future earnings, and a QR code specific to them for sharing sales materials. SOS-P1-06 already gives partners their own leads and the timeline of those leads, read only.
- **Acceptance Criteria:**
  - Leads can be registered with consent wording. A lead registered without it is saved with consent status Unknown and a warning. Consent never blocks (Jayman, 10 November 2026).
  - Shared inventory is visible.
  - Deals and commission status show only the partner's own, with earnings so far, potential earnings and the partner's QR code.
  - Partners cannot see other partners' leads.
  - A partner creates a lead only through one whitelisted method, which records them as its partner. The method is rate limited per partner by the company setting "Partner lead limit", default 20 leads per partner per hour, and refuses the next lead with a clear message. After that the lead is read only to the partner, who logs nothing, and a partner only ever sees their own leads.
- **Test Criteria:** Permission tests, and an end to end test of registering a lead.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): the product names no company, so "work with Pandya" reads "work with the company". A registered lead goes through SOS-P2-08's lead intake function, so it is a dependency. CLAUDE.md says a Channel Partner's access is read only; whether a partner may create a lead is a question in `docs/BACKLOG_AUDIT.md`, and a change to permissions needs Jayman's approval. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 5): the consent wording is the company setting "Consent wording", which each Company Admin can edit. Its default text is written by Jayman (SOS-N22); counsel reviews it after launch. Tests use their own wording. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 13): partners may create leads, as the criterion above says; the limit is 20 leads per partner per hour (Jayman, 13 November 2026). This permission change is approved. Changed by SOS-SETUP-35 (13 November 2026): it depends on SOS-P7-01 to SOS-P7-04. SOS-P7-02 owns the registration method, with the rate limit and the 90 day protection window; this task's registration screen calls it and builds no second method. Shared inventory is SOS-P7-03's sharing, and commission status is SOS-P7-04's payouts. Public intake note (SOS-LOOP, 21 November 2026): a partner registering a lead is signed in and goes through SOS-P7-02's whitelisted method with a login, so it is not a public intake method and allows no guests. If a partner's link or QR code ever opens a public form, that form is a registered public intake method under CLAUDE.md ("Public intake forms").
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P4-06, SOS-P2-08, SOS-P7-01, SOS-P7-02, SOS-P7-03, SOS-P7-04
- **Status:** Complete
- **Browser spec:** required

### SOS-P7-10: Book a unit from the pipeline
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want to book a unit for a buyer from the lead, so that the pipeline, the inventory and the deal stay in step. Booking picks the unit, records the price and booking amount, and in one step creates the deal, marks the unit Booked and moves the lead to Booking.
- **Acceptance Criteria:**
  - From a lead, an agent books an Available unit, or one held for this lead, recording the agreed price and the booking amount (and the cost sheet, when one exists).
  - Confirming creates the Deal (SOS-P4-06) linking the client, the unit and the price, marks the unit Booked (SOS-P7-06) and moves the lead to the Booking stage (SOS-P1-07), all in one transaction, so a failure leaves nothing half done.
  - A unit that is Booked, Sold, Blocked, or held for another lead cannot be booked, and two bookings of one unit at the same moment cannot both succeed.
  - Cancelling a booking needs a reason, returns the unit to Available, marks the Deal Cancelled (never deleted) and logs who and why. The lead's stage is left for the agent to choose.
  - When the lead has a protected channel partner registration (SOS-P7-02), the booking moves it to Booked and the Deal's commission split includes that partner.
  - Moving to Booking is never refused because of consent; the consent warning shows as everywhere else.
- **Test Criteria:** Backend tests of a booking, a cancellation, each refused unit status, two concurrent bookings of one unit (exactly one succeeds), the rollback of a failed booking and the partner registration moving to Booked; a Cypress spec of booking a unit from a lead.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve'). SOS-SETUP-35 added SOS-P7-02 to the dependencies on the sheet, because this task moves a partner's registration to Booked.
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P7-06, SOS-P1-07, SOS-P4-06, SOS-P7-02
- **Browser spec:** required
- **Status:** Complete

### SOS-P7-12: Notification preferences and email alerts
- **Epic:** Alerts and notifications
- **Description:** As a user, I want to choose which alerts reach me in the app and by email, so that I get what matters without noise. Add per user preferences for every alert type, quiet hours, and the email copies that SOS-P1-23's notifications were built to receive.
- **Acceptance Criteria:**
  - Each user chooses, for each alert type, in the app, by email, both or off, and sets quiet hours (India time) during which no email is sent; an email due in quiet hours goes when they end.
  - A Company Admin sets the company's defaults, and a user's own choice overrides them. With no choice made, an alert is in the app only.
  - Emails go through Frappe's email queue with the company's branding, name the record without any phone number, and link to it in the web app.
  - A user never gets an email about a record they may not see.
- **Test Criteria:** Backend tests of each preference, quiet hours with a fixed clock and the record visibility check, with the email captured in the email queue (no real email is sent); a Cypress spec of setting preferences.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve'). Changed by Jayman, 24 November 2026: this task is built and tested against the email queue with captured mail (no real email is sent), so it no longer waits for SOS-P0-13. The real email test is SOS-P7-12L (AMP Labs), which depends on this task and on SOS-P0-13. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Later
- **Story Points:** 5
- **Dependencies:** SOS-P1-23
- **Browser spec:** required
- **Status:** Not Started

### SOS-P7-12L: Send a real alert email from a company site
- **Epic:** Alerts and notifications
- **Description:** As Jayman, I want an alert email from a company site checked on real mail, so that the email queue of SOS-P7-12 is proven with the production mail provider of SOS-P0-13. AMP Labs sends an alert email from a company site once outgoing email is set up.
- **Acceptance Criteria:**
  - An alert email sent from a company site through the email queue arrives, is branded for the company, links to the record in the web app and is not marked as spam.
  - Quiet hours hold an email until they end, checked on the real mail.
  - Every difference from the captured mail becomes an SOS-FIX task.
- **Test Criteria:** Verified by AMP Labs, with the message headers.
- **Notes:** Added by Jayman, 24 November 2026 (question 5): the real email test split out of SOS-P7-12 so the build is not held by SOS-P0-13. AMP Labs' work, so it is Waiting and the loop does not pick it.
- **Owner:** AMP Labs
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** SOS-P7-12, SOS-P0-13
- **Status:** Waiting

### SOS-P7-13: Response time alerts and escalation
- **Epic:** Alerts and notifications
- **Description:** As a Company Admin, I want to know when a lead waits too long, so that leads are not lost. A Company Admin sets how fast new leads must be assigned and contacted; a miss alerts the agent, then the Sales Manager.
- **Acceptance Criteria:**
  - A Company Admin sets two limits as company settings: a new lead unassigned for more than N minutes (default 10), and an assigned lead with no call or activity logged within N minutes of assignment (default 120).
  - When a limit is missed, the lead's agent is alerted (for an unassigned lead, the Company Admin). If it is still missed after the same period again, the Sales Manager of the agent's team is alerted, or the Company Admin when the agent has no team.
  - Each miss is recorded once, with the lead, the limit, the agent, when it was missed and when it was resolved, for SOS-P5-02's reports.
  - The check runs as a function the tests call with a fixed clock; the scheduler calls it every 5 minutes. An alert never reassigns or blocks anything.
- **Test Criteria:** Backend tests of each limit, the escalation with and without a team, one record per miss and the resolution time, with a fixed clock; a Cypress check of the settings screen.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve').
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P1-19, SOS-P1-22, SOS-P1-23
- **Browser spec:** required
- **Status:** Complete

### SOS-P7-11: Mandate renewal and expiry tracking
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want to know before a mandate ends and renew it, so that we never lose a listing by letting its mandate lapse. Each mandate (SOS-P4-05) gets an end date and a status worked out from it.
- **Acceptance Criteria:**
  - Each mandate has a start and an end date, and a status worked out from them: Active, Expiring (within 30 days of the end) or Expired.
  - A list shows the mandates expiring in the next 30 days and those expired, filterable by agent.
  - The mandate's agent and the Company Admin are alerted 30, 15 and 7 days before the end date, in the app and by email. Email goes to the mandate's agent and the Company Admin by default; per user preferences (SOS-P7-12, taken out of the loop) apply when it is built. The seller is never messaged automatically.
  - Renewing records a new end date and attaches the new signed document; the earlier terms and documents are kept.
- **Test Criteria:** Backend tests of the status at each boundary with a fixed clock, the alerts on the right days only once each, and renewal keeping the history; a Cypress spec of renewing a mandate from the expiring list.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve'). MUST for 1 January 2027 (Jayman, 27 November 2026). SOS-P7-12 is no longer a dependency (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P4-05, SOS-P7-13
- **Browser spec:** required
- **Status:** Not Started

### SOS-P7-14: Daily digest for agents and managers
- **Epic:** Alerts and notifications
- **Description:** As an Agent or a Sales Manager, I want a morning summary by email, so that I start the day knowing what is due. Send each agent their day, and each manager their team's numbers.
- **Acceptance Criteria:**
  - Every morning at a time the Company Admin sets (default 08:00 India time), each active agent gets an email of their follow ups due today and overdue, new leads assigned to them since the last digest, and today's site visits.
  - Each Sales Manager gets their team's numbers by agent (leads waiting for first contact, overdue follow ups, visits booked today), and each Company Admin the company's.
  - The numbers match the Today screen (SOS-P1-26) at the same moment.
  - A user with nothing to report gets no email, a user who turned the digest off gets none (a simple per user digest on and off switch, built here; SOS-P7-12's full preferences are out of the loop), and no phone number appears.
  - The digest obeys the WhatsApp STOP rule (CLAUDE.md decision 7): a person who sent STOP on WhatsApp gets no digest over WhatsApp, whatever "Consent enforcement" says, and the email digest is unaffected.
- **Test Criteria:** A test against the STOP rule: a user with a WhatsApp STOP in the consent log receives nothing on WhatsApp and still receives email, and a user without one is not suppressed. Backend tests of each digest's content against seeded records and the Today screen's queries, the skip rules, with a fixed clock and the email captured in the email queue.
- **Notes:** Added by SOS-SETUP-35 (Jayman approved, 13 November 2026, from the sheet 'New tasks to approve'). MUST for 1 January 2027 (Jayman, 27 November 2026). Dependency SOS-P6-11 added by Jayman's priorities, 27 November 2026, because it records the WhatsApp STOP. SOS-P7-12 is no longer a dependency (Jayman, 27 November 2026). Must obey the WhatsApp STOP rule and is tested against it: a person with a WhatsApp STOP gets no digest on WhatsApp.
- **Owner:** Claude Code
- **Priority:** P7
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P1-26, SOS-P6-11
- **Status:** Not Started

### SOS-P2-14: Onboard the first caller and start the baseline
- **Epic:** Calling
- **Description:** As Jayman, I want the first caller trained and a baseline measured, so that the AI pilot has something to beat. Train the caller on the app and script, have them work from the caller queue, which shows each lead's consent warning, and track the four week baseline metrics.
- **Acceptance Criteria:**
  - The caller completes training.
  - The caller works from the caller queue and reads each lead's consent warning before calling.
  - Baseline metrics are tracked weekly.
- **Test Criteria:** A weekly baseline report is produced for four weeks.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 4): moved to the Jan 1 tier; the four week baseline cannot end by 20 December.
- **Owner:** Jayman
- **Priority:** P2
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P2-13
- **Status:** Waiting

### SOS-P5-09: Compare AI with the human baseline
- **Epic:** Voice AI pilot
- **Description:** As Jayman, I want AI and human calling compared fairly, so that we decide whether to scale. Compare connect rate, qualified lead rate, site visits booked, cost per qualified lead, handover rate and complaints, using the four week human baseline.
- **Acceptance Criteria:**
  - A comparison report covers all six measures.
  - The data reconciles with the Call Log.
  - The report runs for any date range, and is tested on seeded AI and human Call Logs.
- **Test Criteria:** Reconcile the report with the raw data.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026): this task builds the comparison report, owned by Claude Code. Jayman's go or no go decision on the pilot data is SOS-P5-09A. The report needs only the Call Log, so it could start before the pilot ends; that dependency change needs `test_the_voice_pilot_chain` changed (question in `docs/BACKLOG_AUDIT.md`). Decided by Jayman (SOS-SETUP-34, 13 November 2026, questions 3 and 4): it needs only the Call Log, so it depends on SOS-P5-07 and SOS-P2-11 instead of SOS-P5-08, and it is in the Jan 1 tier.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P5-07, SOS-P2-11
- **Status:** Complete

### SOS-P5-08: Run the AI pilot
- **Epic:** Voice AI pilot
- **Description:** As Jayman, I want a controlled AI pilot, so that we learn before scaling. Run 400 AI calls over about four weeks in Hinglish, reviewing transcripts weekly. While only the 022 number exists, the calls are limited to service and transactional purposes, such as site visit confirmations and follow ups for existing clients, so the pilot design may change or wait until the number series question is settled. Any complaint stops the pilot for review.
- **Acceptance Criteria:**
  - 400 calls are completed, or the pilot is stopped with a recorded reason.
  - Transcripts are reviewed weekly.
  - Complaints are logged, and zero are required to continue.
  - Every pilot call is a site visit confirmation or a follow up for an existing client, the only purposes allowed on the 022 number.
- **Test Criteria:** A weekly review log is kept.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): the call language is Hinglish (SOS-SETUP-30). Do not start before SOS-P5-07L is Complete. Its dependencies are not changed here because `test_the_voice_pilot_chain` locks them (question in `docs/BACKLOG_AUDIT.md`). Which purposes the pilot may use on the 022 number, and whether a four week baseline and a four week pilot fit the Dec 20 tier, are questions in the same file. Decided by Jayman (SOS-SETUP-34, 13 November 2026, questions 3 and 4): moved to the Jan 1 tier, because a four week baseline and a four week pilot cannot end by 20 December. It depends on SOS-P5-07L. The pilot is limited to site visit confirmations and follow ups for existing clients.
- **Owner:** Jayman
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P5-07L, SOS-P2-14
- **Status:** Waiting

### SOS-P5-09A: Record the AI go or no go decision
- **Epic:** Voice AI pilot
- **Description:** As Jayman, I want a go or no go decision on AI calling made from the pilot, so that we decide whether to scale. The acceptance half of SOS-P5-09: run its comparison report on the pilot and the human baseline, and record the decision.
- **Acceptance Criteria:**
  - The comparison report is run on the pilot and the four week baseline, and reconciles with the Call Log.
  - A go or no go decision is recorded, with its reasons.
- **Test Criteria:** Verified by the recorded decision.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman's decision, so it is Waiting and the loop does not pick it. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 4): Jan 1 tier. It depends on SOS-P5-08 too, because SOS-P5-09 no longer does and the decision needs the pilot's data.
- **Owner:** Jayman
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** SOS-P5-09, SOS-P5-08
- **Status:** Waiting

### SOS-P6-11: Build the WhatsApp channel foundation
- **Epic:** Listing sources and WhatsApp
- **Description:** As Jayman, I want WhatsApp working per company, so that each agency has its own number and templates. Build the WhatsApp channel foundation in SellOS: a per company number and templates, inbound and outbound messages, Leads and Consent Records created from conversations, and handoff to a human agent.
- **Acceptance Criteria:**
  - A company can connect its own number through the WhatsApp provider adapter. In the tests the number is a fake provider's.
  - Messages create or update leads.
  - An opt in creates a consent record.
  - A WhatsApp STOP in a conversation is recorded as Opted out with a red warning and a Consent Record, and from then on nothing unprompted is sent to that person (the bot, campaigns and partner digests). It sends one confirmation reply and creates a task for the assigned advisor. The person can still write to us, and replies to their messages are still sent, until they opt in again.
  - Every send goes through the consent function of SOS-P2-04 and records the consent status and warning. Apart from the unprompted sends after a WhatsApp STOP, none is refused while Consent enforcement is Off. Consent never blocks calls or SMS (Jayman, 10 November 2026; restated 24 November 2026).
  - A conversation can be handed to a human.
- **Test Criteria:** An end to end test through a fake WhatsApp provider behind the adapter interface, with signed webhook bodies, covering inbound, outbound, an opt in, a stop request (the confirmation, the advisor task, the consent log entry, an unprompted send suppressed and a reply to the person still sent) and handoff. The test on a real number is SOS-P6-11L, owned by Jayman.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): It is built and tested against a fake provider behind the adapter interface, as SOS-N21A does with `--fake`. The agent never calls the real provider and never holds a real key. Every send goes through SOS-P2-04's consent function, so it is a dependency, and each message links to its Consent Check and defines no consent fields of its own. A Consent Record made from a conversation has the message saved as a private file as its evidence link. Which WhatsApp provider is used is a question in `docs/BACKLOG_AUDIT.md`. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 14): Meta's Cloud API directly, behind the adapter; Jayman holds the Meta business account and does the business verification; Jayman puts the flow designs and the list of the ten flows in `docs/whatsapp/` (SOS-N23); "the agent's calendar" means Site Visit records. Restated by Jayman, 24 November 2026: consent never blocks calls or SMS, but a WhatsApp STOP always suppresses everything the bot, campaigns and partner digests send unprompted (one confirmation reply, a task for the assigned advisor, an entry in the consent log); the person can still write to us and get replies. This is the one place consent stops a send, and it does not depend on Consent enforcement. The send function refuses an unprompted message to an opted out person; a reply inside a conversation the person started is not unprompted. Code and tests that still carry the old rule ("a stop blocks nothing" or "WhatsApp is never refused") and must change in this build, with their comments, docstrings and test names: `sellos/crm/lead_import.py`; `sellos/crm/api.py` (lines 813 and 839); `sellos/crm/intake.py`; `sellos/crm/enquiry.py`; `sellos/crm/consent.py` (lines 258 to 260); `sellos/whatsapp/base.py`; `sellos/sellos/doctype/lead/lead.json` (line 197, the field description); `cypress/integration/crm/whatsapp.cy.js` (line 51); `sellos/crm/test_p2_08_inbound_opt_in.py` (line 279).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P1-08, SOS-P2-04
- **Status:** Complete
- **Browser spec:** required

### SOS-N23: Put the WhatsApp flow designs and the ten flows in docs/whatsapp
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want the WhatsApp flow designs in the repository, so that SOS-P6-16 and SOS-P6-17 are built from them. Put the existing WhatsApp CRM designs and the list of the ten flows in `docs/whatsapp/`. Meta's business verification is SOS-N23V.
- **Acceptance Criteria:**
  - `docs/whatsapp/` holds the flow designs and names the ten flows, split into group one (SOS-P6-16) and group two (SOS-P6-17).
- **Test Criteria:** Verified by Jayman.
- **Notes:** Added by SOS-SETUP-34 (Jayman, 13 November 2026, question 14). Jayman's work, so it is Waiting and the loop does not pick it. Split by Jayman, 24 November 2026 (question 6): this task is the designs only, SOS-P6-16 and SOS-P6-17 depend only on it, and Meta business verification is SOS-N23V, which SOS-P6-11L depends on. Claude in chat wrote the files in `docs/whatsapp/` on 24 November 2026 (ten flows, a README, a backlog of the other workflows); Jayman reviews them and marks this task Complete. Flows 1 to 5 are group one (SOS-P6-16) and flows 6 to 10 are group two (SOS-P6-17), as `docs/whatsapp/README.md` lists them.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** none
- **Status:** Waiting

### SOS-N23V: Complete Meta business verification
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want Meta's business verification completed on the Meta business account I hold, so that the WhatsApp channel can be connected to a real number. Split out of SOS-N23.
- **Acceptance Criteria:**
  - The Meta business account is verified.
- **Test Criteria:** Verified by Jayman.
- **Notes:** Split out of SOS-N23 by Jayman, 24 November 2026 (question 6). Jayman's work, so it is Waiting and the loop does not pick it. SOS-P6-11L depends on it.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** none
- **Status:** Waiting

### SOS-P6-11L: Live test WhatsApp on a real number
- **Epic:** Listing sources and WhatsApp
- **Description:** As Jayman, I want the WhatsApp channel checked on a real number, so that the fake provider it was built with behaves like the real one. The live half of SOS-P6-11: connect a real test number, then send and receive messages from Jayman's own phone.
- **Acceptance Criteria:**
  - A real number is connected for a company.
  - An inbound message creates a lead, an outbound message arrives, an opt in creates a Consent Record, and a stop request is recorded as Opted out, gets one confirmation reply and an advisor task, stops everything unprompted, and still gets replies when Jayman writes to the number.
  - A conversation is handed to a human.
  - Every difference from the fake provider becomes an SOS-FIX task.
- **Test Criteria:** Verified by Jayman on his own phone.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman holds the account and keys, so it is Waiting and the loop does not pick it. The provider's webhooks need a public HTTPS address (question in `docs/BACKLOG_AUDIT.md`). Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 2): provider webhooks reach a public HTTPS address on staging, never a tunnel to the shared bench on port 8004, so this depends on SOS-P0-06D. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 14): Meta's Cloud API directly, behind the adapter; Jayman holds the Meta business account and does the business verification; Jayman puts the flow designs and the list of the ten flows in `docs/whatsapp/` (SOS-N23); "the agent's calendar" means Site Visit records. Changed by Jayman, 24 November 2026: Meta business verification is now SOS-N23V, and this task depends on it. Restated by Jayman, 24 November 2026: a WhatsApp STOP suppresses everything unprompted but never replies to the person (see SOS-P6-11).
- **Owner:** Jayman
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** SOS-P6-11, SOS-P0-06D, SOS-N23V
- **Status:** Waiting

### SOS-P6-16: Rebuild WhatsApp flows, group one
- **Epic:** Listing sources and WhatsApp
- **Description:** As an Agent, I want the lead qualification, NRI buyer and investor flows, so that WhatsApp enquiries are qualified automatically. Rebuild these flows from the existing WhatsApp CRM designs inside SellOS. Each flow asks its questions, scores the lead and hands over to an agent when needed. This story and SOS-P6-17 were split out of the original rebuild task to keep each within 8 points.
- **Acceptance Criteria:**
  - Each flow runs end to end.
  - Answers are stored on the lead.
  - Handoff works from each flow.
  - Each flow records the lead's consent status and shows its warning to the agent, and never stops a call or an SMS on consent. Consent never blocks a call or SMS (Jayman, 10 November 2026); a WhatsApp STOP stops everything sent unprompted, with one confirmation reply, an advisor task and a consent log entry, and the person can still write to us and get replies (Jayman, 24 November 2026).
- **Test Criteria:** Scripted conversations through each flow with the fake WhatsApp provider of SOS-P6-11.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): tested with SOS-P6-11's fake provider; the real number is SOS-P6-11L. Where "the existing WhatsApp CRM designs" are is a question in `docs/BACKLOG_AUDIT.md`; reply NEEDS_INPUT if they are not in the repository when this task starts. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 14): Meta's Cloud API directly, behind the adapter; Jayman holds the Meta business account and does the business verification; Jayman puts the flow designs and the list of the ten flows in `docs/whatsapp/` (SOS-N23); "the agent's calendar" means Site Visit records. Changed by Jayman, 24 November 2026: depends only on SOS-N23 (the designs), not on business verification. The flows of this group are flows 1 to 5 in `docs/whatsapp/README.md`.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P6-11, SOS-N23
- **Status:** Not Started

### SOS-P6-17: Rebuild WhatsApp flows, group two
- **Epic:** Listing sources and WhatsApp
- **Description:** As an Agent, I want the site visit booking, cold lead nurture, human handoff and remaining flows, so that WhatsApp supports the whole journey. Rebuild the remaining flows from the existing designs, including booking site visits into the agent's calendar and nurture messages for cold leads recording each lead's consent status.
- **Acceptance Criteria:**
  - Site visits are booked from WhatsApp.
  - Nurture messages go through the consent function of SOS-P2-04 and record each lead's consent status and warning. A WhatsApp STOP is recorded as Opted out with a red warning and suppresses every nurture message, and anything else unprompted, until the person opts in again; the person can still write to us and get replies. Consent never blocks calls or SMS (Jayman, 10 November 2026; restated 24 November 2026).
  - Handoff passes the full conversation.
  - All ten flows are live.
- **Test Criteria:** Scripted conversations through each flow with the fake WhatsApp provider of SOS-P6-11, including an opt out (no nurture message after a STOP, a reply to the person's own message still sent).
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): tested with SOS-P6-11's fake provider. The "remaining flows" and the ten flows are not listed anywhere, and "the agent's calendar" is taken to be the Site Visit record; both are in the WhatsApp question in `docs/BACKLOG_AUDIT.md`. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 14): Meta's Cloud API directly, behind the adapter; Jayman holds the Meta business account and does the business verification; Jayman puts the flow designs and the list of the ten flows in `docs/whatsapp/` (SOS-N23); "the agent's calendar" means Site Visit records. Dependencies SOS-P1-25 added by SOS-SETUP-35 (13 November 2026): the core CRM comes before what uses it. Changed by Jayman, 24 November 2026: depends only on SOS-N23 (the designs), not on business verification. The flows of this group are flows 6 to 10 in `docs/whatsapp/README.md`. Site visit booking is flow 5, in SOS-P6-16's group, which differs from the wording of this task's description; the README lists the split. Restated by Jayman, 24 November 2026: after a WhatsApp STOP no nurture or other unprompted message is sent (see SOS-P6-11).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P6-11, SOS-N23, SOS-P1-25
- **Status:** Not Started

### SOS-P5-01: Build the report engine
- **Epic:** Reporting
- **Description:** As a Company Admin, I want a report engine, so that every report shares filters, scoping and drill down. Build Report Definition with filters, grouping and role scope, backed by nightly summary tables, with drill down to the underlying records.
- **Acceptance Criteria:**
  - Reports are defined by configuration.
  - Role scope limits the rows.
  - Each figure drills down to records.
  - Summary tables refresh nightly.
- **Test Criteria:** Compare results with a hand calculation.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P1-06B
- **Status:** Complete
- **Browser spec:** required

### SOS-P5-02: Build the agent and Company Admin reports
- **Epic:** Reporting
- **Description:** As an Agent and a Company Admin, I want the standard reports, so that I can run the business from data. For agents: my pipeline, calls and outcomes, follow ups due and site visits. For Company Admins: lead funnel and conversion by stage, source performance, agent productivity, call reports, listing and mandate ageing, and deal pipeline and commission.
- **Acceptance Criteria:**
  - Every listed report exists.
  - Each filters by date.
  - Each reconciles with its raw data.
- **Test Criteria:** Reconcile every report against raw data.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): the call reports for Company Admins are SOS-P2-11's. This task registers them as report definitions on the engine and does not rebuild them, and SOS-P2-11's tests keep passing; the number of assertions in each changed test must not fall. Dependencies SOS-P1-18, SOS-P1-20, SOS-P1-22 added by SOS-SETUP-35 (13 November 2026): the core CRM comes before what uses it.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P5-01, SOS-P4-06, SOS-P2-11, SOS-P1-18, SOS-P1-20, SOS-P1-22
- **Status:** Complete
- **Browser spec:** required

### SOS-P5-03: Build the Channel Partner and Platform reports
- **Epic:** Reporting
- **Description:** As a Channel Partner and a Platform Admin, I want my reports, so that I can track results. Build Channel Partner reports for own leads, deals and commission statements, and Platform Admin reports for companies, usage and calling spend. The revenue, churn and failed payment panels switch on once billing data exists.
- **Acceptance Criteria:**
  - Partners see only their own data.
  - Platform reports cover companies, usage and calling spend as totals per company. They hold no lead, client or call record and no phone number (the Platform Admin sees no company CRM data by role, CLAUDE.md).
  - Revenue panels activate after billing is live.
- **Test Criteria:** Permission tests, and a check of the totals.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): calling spend comes from the Call Log of SOS-P2-05, so it is a dependency.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P5-01, SOS-P2-05
- **Status:** Complete
- **Browser spec:** required

### SOS-P5-04: Build saved views, export and scheduling
- **Epic:** Reporting
- **Description:** As a Company Admin, I want to save, export and schedule reports, so that results reach the right people. Add saved filters, CSV and PDF export, and scheduled email delivery with recipients, all scoped by role.
- **Acceptance Criteria:**
  - Views can be saved and shared.
  - Exports match the screen.
  - Scheduled emails arrive on time.
  - Recipients only get data they may see.
  - A Company Admin may export report results only: the rows and figures they can already see, with phone numbers masked, and every export logged. Raw DocType export stays Platform Admin only.
- **Test Criteria:** Compare an export with the screen, and run a scheduled email.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): CLAUDE.md says only the Platform Admin may bulk export, and this task gives Company Admins CSV and PDF export. Which exports a Company Admin may make is a question in `docs/BACKLOG_AUDIT.md`; reply NEEDS_INPUT if it is still open when this task starts. Scheduled email needs an outgoing mail account on production, which no task sets up yet (same file). Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 12): this permission change is approved as the criterion above says.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P5-01
- **Status:** Complete
- **Browser spec:** required

### SOS-P5-05: Build the client views
- **Epic:** Client and partner views
- **Description:** As a Client, I want to see my shortlist, visits and deal status, so that I stay informed. Buyers see their shortlist, site visits and deal status. Sellers see mandate status and enquiries on their property. The Dossier appears only after a signed mandate.
- **Acceptance Criteria:**
  - Buyers see shortlist, visits and status.
  - Sellers see mandate status and enquiries.
  - The Dossier is hidden until a mandate is signed.
  - Clients see only their own data.
- **Test Criteria:** Permission tests, and an end to end walk through for a buyer and a seller.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): no task defines a shortlist record. What a shortlist is (a list of listings per client, made by the agent) is a question in `docs/BACKLOG_AUDIT.md`. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 11): a shortlist is a list of listings per client, made by the agent and seen by the client. Changed by SOS-SETUP-35 (13 November 2026): the shortlist is SOS-P7-09's, so it depends on SOS-P7-09. Decided by Jayman (SOS-LOOP, 23 November 2026): a seller sees the enquiries on their own property as plain rows and nothing else, under the rules in CLAUDE.md ("Client views") and docs/permissions.md ("Client views"). SOS-LOOP adds the field `Lead.property` (Link to Property, optional; on a Seller lead the property being sold, on a Buyer lead the property enquired about; existing leads are not backfilled) and its patch `p5_05_lead_property`; this task builds the rest. The seller's rows are the Buyer pipeline leads with the same `property` as the seller's own Seller lead(s), reached by the signed in user's email, then the Client record, then its Seller leads, never the seller's own lead. The server returns exactly four fields per row: a label (Enquiry 1, Enquiry 2 and so on, numbered per property in the order the leads were created), the stage, the time stamp of when the lead reached that stage (from the lead's stage log, the creation time for the first stage) and an SLA badge (In SLA or Outside SLA). Never a name, phone, email, message text, source, consent status or agent notes, and no lead, client or property id. The SLA is the response SLA that SOS-P7-13 already records (first assignment and first contact): Outside SLA means the lead has at least one Response Alert, resolved or not, otherwise In SLA; the badge is labelled as a response SLA and there is no per stage SLA. A seller lead with no property shows an empty state telling the seller their agent is linking it. Tests: a test that fails if any field other than the four is returned; permission tests that another seller, a buyer and a Channel Partner see none of the rows; a Cypress spec; FLOW lines.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P4-05, SOS-P7-09
- **Status:** Complete
- **Browser spec:** required

### SOS-P3-01: Build the source adapter
- **Epic:** Market intelligence
- **Description:** As a developer, I want one adapter interface for registration data sources, so that SellOS works with whichever source we secure. Define the interface with fetch batch and map fields, and build the adapter for the source chosen through SOS-N11 or SOS-N12, running on a schedule with failure alerts.
- **Acceptance Criteria:**
  - The interface is documented.
  - A file adapter ingests a batch from an export file (CSV or JSON) in the documented shape, and a fake source adapter feeds the tests. The adapter for the real source is added when it is known, and its first real batch is SOS-P3-01L.
  - Runs are scheduled and failures raise alerts.
  - The adapter never solves captchas or bypasses access controls.
- **Test Criteria:** Contract tests with sample payloads, and a test that a failed run raises an alert.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026): SOS-N11 (bought data) is Not Needed and SOS-N12 (the Department of Registration and Stamps) is Waiting with an uncertain outcome, so the interface, the file adapter, the schedule and the alerts are built now with a fake source, and the real source's first batch is SOS-P3-01L. Which site holds the market data, and where it comes from, are questions in `docs/BACKLOG_AUDIT.md`. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 8): Market data lives on the control site and reaches company sites through a role checked API. It is loaded from export files Jayman supplies (Index II or DoRS) through SOS-P3-01's file adapter, ready reckoner rates are loaded from a file Jayman supplies, and the data licence switch is a platform setting, On by default for data SellOS owns.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** none
- **Status:** Complete

### SOS-P3-02: Create the raw transaction table
- **Epic:** Market intelligence
- **Description:** As a data engineer, I want every record stored untouched, so that cleaning can always be repeated from the original. Store each record exactly as received, with its source, fetch time and a hash.
- **Acceptance Criteria:**
  - Original fields are unchanged.
  - Source, fetch time and hash are stored.
  - Re runs do not create duplicates.
  - The raw transaction table is on the control site, and company sites read it only through a role checked API.
- **Test Criteria:** Ingest the same batch twice and confirm there are no duplicates.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 8): Market data lives on the control site and reaches company sites through a role checked API. It is loaded from export files Jayman supplies (Index II or DoRS) through SOS-P3-01's file adapter, ready reckoner rates are loaded from a file Jayman supplies, and the data licence switch is a platform setting, On by default for data SellOS owns.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P3-01
- **Status:** Complete

### SOS-P3-03: Build the normaliser
- **Epic:** Market intelligence
- **Description:** As an Agent, I want clean, comparable figures, so that rates mean the same thing across records. Translate or transliterate Marathi names and property text into English, standardise dates, parse consideration and market value, and convert areas to carpet area in square feet, recording the rule used.
- **Acceptance Criteria:**
  - English fields are filled and the original is kept.
  - Dates are standard.
  - Areas are in carpet square feet with the conversion rule recorded.
  - Unparseable records go to a review list.
- **Test Criteria:** A golden file of 100 verified records, with at least 95 percent of fields correct.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 9): at least 95 percent of fields correct. The gate uses a synthetic golden file Claude Code writes; the check on real data is SOS-P3-13.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-02
- **Status:** Complete

### SOS-P3-04: Build the building and micro market master
- **Epic:** Market intelligence
- **Description:** As an Agent, I want buildings and micro markets defined, so that transactions roll up the way agents think. Micro markets are configurable data, never hard coded: a named area with an optional boundary, a country and a parent (city or region), which a Company Admin can add, rename, split, merge and archive. Buildings and projects carry the identifiers where known, editable by admins, and are reviewed by a person before they count.
- **Acceptance Criteria:**
  - Micro markets are a DocType, not a list in code: name, country, parent (city or region), optional boundary (GeoJSON), status (Active or Archived). No micro market name, city or country appears in code outside the sample file and the tests.
  - A Company Admin can add, rename, split (one market into two, its buildings assigned to the parts) and merge (two into one) micro markets, and archive one. Nothing is deleted (CRM data rule); a rename, split and merge keep the history of which market a building belonged to.
  - Micro markets and their boundaries can be loaded from a file and edited. The sample file `sellos/intel/fixtures/corridor_bandra_andheri.json` ships with the code for the tests and as Pandya's first set; it is a sample, not a rule. The Ahmedabad demo company is a dummy test company and loads nothing real.
  - Building record is flexible: name, micro market, optional project. India identifiers: CTS numbers (several), village, tahsil, district, RERA number. Optional identifiers for other countries, stored and shown but with no data adapter built now: UAE community and DLD number, Australian lot and plan. Which identifiers are shown follows the building's country. Data adapters stay pluggable by country (SOS-P3-01's interface); only India's is built for 1 January.
  - Where the master lives (decided by Jayman's request of 27 November 2026, design below): a platform master on the control site plus each company's own layer on its site.
  - Seed list load: a CSV or list of building and project names (from a RERA project search, a file or an agent's list) creates buildings with status "Needs review". SOS-P3-14 to SOS-P3-16 enrich them through LegiScore later; this task never calls LegiScore.
  - A building review screen in the SellOS web app lists the system built buildings with name, CTS, RERA and micro market. A reviewer (any Company Admin or Agent) can correct each field or confirm the building; every correction is saved with who, when and the old value, and a confirmed building is marked Confirmed. Only Confirmed buildings reach the Property Matcher and market data roll ups.
  - Admins can edit buildings and micro markets; the permissions are in the permission test matrix.
- **Test Criteria:** Backend tests of the load, the edits (rename, split, merge, archive) and the permissions with the sample file, of the optional foreign identifiers (stored, not required), of the seed list load, and of the review (a correction is saved with the old value, confirm marks Confirmed, an unconfirmed building is not returned to the matcher). A Cypress check of editing a building and of correcting then confirming one on the review screen, with its flow in `docs/regression/flows.md`.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026): the code is this task, owned by Claude Code; supplying the real corridor boundaries and buildings and the agents' check of twenty buildings is SOS-P3-04A, owned by Jayman. Decided by Jayman, 27 November 2026: micro markets are configurable, SellOS is sold across India, UAE and Australia, and valuation, comparables and the market data panel for the UAE and Australia are out of scope for 1 January (India only, structure open). **Master design:** (1) the control site holds a platform master of buildings and projects (with the LegiScore data, SOS-P3-01), seeded from the corridor file and curated by the Platform Admin; (2) each company site holds its own micro markets and its own building records, each building optionally linked to a platform building by a `platform_building` id. A company's micro market is a grouping of its buildings, so a company can split, merge, rename and archive freely without touching another company or the platform master; (3) a building a company adds that is not on the platform master stays the company's own, with no market data until the Platform Admin links it; (4) company sites receive building level figures only, by role checked API, joined on `platform_building`, and parties' names stay on the control site (SOS-P3-12). LegiScore has no bulk or area listing (`docs/LEGISCORE.md`), so buildings come from seed lists and are enriched one by one. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P3-02
- **Status:** Not Started

### SOS-P3-05: Build the matcher
- **Epic:** Market intelligence
- **Description:** As an Agent, I want each transaction tied to the right building, so that comparables are trustworthy. Match using CTS or survey number, address and RERA number, give each match a confidence score, and send low confidence records to a review queue.
- **Acceptance Criteria:**
  - Each record gets a match or a review status.
  - Confidence is stored.
  - Reviewer decisions are saved and reused.
- **Test Criteria:** Precision and recall are measured on 200 hand matched records: precision at least 95 percent and recall at least 85 percent.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 9): precision at least 95 percent, recall at least 85 percent. The gate uses a synthetic golden file Claude Code writes; the check on real data is SOS-P3-13. Decided by Jayman, 24 November 2026: the matcher's inputs include building level transaction figures and project level sold inventory from the market data tasks (SOS-P3-14 to SOS-P3-17), only after the review queue approves them, and never parties' names. Dependencies unchanged: SOS-P3-03 and SOS-P3-04 (Blocked) stay; the market data tasks do not need to be dependencies, because the matcher is built against synthetic files and SOS-P3-17's approved figures arrive later through the same record shape. UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-03, SOS-P3-04
- **Status:** Not Started

### SOS-P3-06: Flag outliers
- **Epic:** Market intelligence
- **Description:** As an Agent, I want unusual deals flagged, so that they do not distort comparables. Flag related party sales, token prices, bundled units and parking sold separately. Exclude flagged records from comparables by default and show the reason.
- **Acceptance Criteria:**
  - Each flag type is detected.
  - Flagged records are excluded by default.
  - The reason is visible.
- **Test Criteria:** Seeded examples of each flag type.
- **Notes:** UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-05
- **Status:** Not Started

### SOS-P3-07: Build the nightly jobs
- **Epic:** Market intelligence
- **Description:** As an Agent, I want up to date rates and trends, so that guidance reflects the market. Compute rate per square foot, rolling 3, 6 and 12 month trends and building statistics every night.
- **Acceptance Criteria:**
  - Jobs run nightly and are repeatable.
  - They finish within 2 hours.
  - Failures raise alerts.
- **Test Criteria:** Recompute a known sample by hand and compare.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 9): the window is 2 hours. UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-05
- **Status:** Not Started

### SOS-P3-11: Build alerts for watched buildings
- **Epic:** Market intelligence
- **Description:** As an Agent, I want alerts on watched buildings, so that I hear about new sales first. Let agents watch buildings, and send an in app and email alert when a new registration appears, with a frequency cap.
- **Acceptance Criteria:**
  - Agents can watch and unwatch buildings.
  - New registrations create alerts.
  - The cap limits repeats.
- **Test Criteria:** Ingest a test record in a watched building.
- **Notes:** UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P3-07
- **Status:** Not Started
- **Browser spec:** required

### SOS-P3-08: Build the comparables API and profiles
- **Epic:** Market intelligence
- **Description:** As an Agent, I want comparables and building profiles, so that I can price and advise with evidence. Build an API that returns comparables for a building, project or micro market with filters, and screens for building and project profiles showing five year trend, volume, resale against primary, and price against the ready reckoner.
- **Acceptance Criteria:**
  - The API filters by area, floor, date and type.
  - Profiles show trend, volume and price against the ready reckoner.
  - Every figure links to its records.
  - Role permissions apply.
  - Ready reckoner rates are loaded from a file through the file adapter; the tests use a sample file.
- **Test Criteria:** API tests, and an end to end view of a known building.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 8): Market data lives on the control site and reaches company sites through a role checked API. It is loaded from export files Jayman supplies (Index II or DoRS) through SOS-P3-01's file adapter, ready reckoner rates are loaded from a file Jayman supplies, and the data licence switch is a platform setting, On by default for data SellOS owns. UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-07
- **Status:** Not Started
- **Browser spec:** required

### SOS-P3-09: Build the valuation range
- **Epic:** Market intelligence
- **Description:** As an Agent, I want a valuation range for a property, so that I can advise sellers confidently. Produce a low, middle and high range with the number of comparables, the method and the comparables used, and refuse to answer when too few comparables exist.
- **Acceptance Criteria:**
  - A range is returned with its comparables.
  - The method is shown.
  - Too few comparables returns a clear refusal.
- **Test Criteria:** Back test against 50 known sales and report the error: median error at most 10 percent.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 9): median error at most 10 percent. The gate uses a synthetic golden file Claude Code writes; the check on real data is SOS-P3-13. UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-08
- **Status:** Not Started
- **Browser spec:** required

### SOS-P4-07: Attach comparables to listings and mandates
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want comparables and a valuation range on listing and mandate screens, so that I can advise with evidence. Show comparables and the valuation range with links to the underlying records, hidden when the data licence does not allow it.
- **Acceptance Criteria:**
  - Comparables appear on both screens.
  - Each links to its records.
  - They are hidden if the licence forbids showing them.
  - The data licence switch is a platform setting, On by default; when it is Off, comparables are hidden.
- **Test Criteria:** An end to end check on a known building, and a test of the licence switch.
- **Notes:** Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 8): Market data lives on the control site and reaches company sites through a role checked API. It is loaded from export files Jayman supplies (Index II or DoRS) through SOS-P3-01's file adapter, ready reckoner rates are loaded from a file Jayman supplies, and the data licence switch is a platform setting, On by default for data SellOS owns. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-09, SOS-P4-05
- **Status:** Not Started
- **Browser spec:** required

### SOS-P3-12: Apply the party name rules
- **Epic:** Market intelligence
- **Description:** As Jayman, I want party names handled as counsel advises, so that we stay lawful. Apply the storage, access and retention rules from SOS-N13, hide names from roles that do not need them, disable search by name unless allowed, and log every access.
- **Acceptance Criteria:**
  - Names are visible only to allowed roles.
  - Name search is off unless allowed.
  - Access is logged.
  - Retention follows the advice.
  - Index II buyer and seller names are visible only to Company Admins, are never searchable, every view is logged, and they are kept five years. A Facebook poster's name and number are kept only on the draft listing, masked like a lead's phone, and deleted when the draft is rejected.
- **Test Criteria:** Permission tests for each role.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): SOS-N13 (counsel's advice on party names) is Not Needed, so "the rules from SOS-N13" have no source. The rules to apply are a question in `docs/BACKLOG_AUDIT.md`; reply NEEDS_INPUT if it is still open when this task starts. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 7): these rules replace "the rules from SOS-N13". Index II buyer and seller names are visible only to Company Admins, are never searchable, every view is logged, and they are kept five years. A Facebook poster's name and number are kept only on the draft listing, masked like a lead's phone, and deleted when the draft is rejected.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-N13, SOS-P3-02
- **Status:** Complete
- **Browser spec:** required

### SOS-P3-10: Build the agent assistant
- **Epic:** Market intelligence
- **Description:** As an Agent, I want to ask market questions in plain language, so that I get answers grounded in records. Build an assistant that answers only through query tools, lists the records behind every answer, refuses to guess, logs questions and respects role limits on party names.
- **Acceptance Criteria:**
  - Answers cite records.
  - Unknown buildings get a clear refusal.
  - Party names are hidden where the role forbids them.
  - Questions are logged.
  - The language model sits behind one adapter, Anthropic, with a fake that scripts tool calls for the tests; the model is the setting "Assistant model" (the stronger one SOS-N21 chooses), and its key comes from encrypted settings.
- **Test Criteria:** A scripted question set with expected tool calls, and a test with an unknown building to confirm it does not invent figures.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): the party name limits come from SOS-P3-12, so it is a dependency. The language model sits behind one adapter interface, and the tests use a fake model that returns scripted tool calls. The agent never calls a real model and never holds its key, which lives in encrypted settings or an environment variable. Which model and whose account is a question in `docs/BACKLOG_AUDIT.md`. The run with the real model is SOS-P3-10L. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 7): the party name limits are SOS-P3-12's: only a Company Admin sees party names, and every view is logged. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 10): one Anthropic account held by Jayman for the assistant and the voice agent, with two model settings; the agent never chooses the model and never calls the real API. UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-08, SOS-P3-12
- **Status:** Not Started
- **Browser spec:** required

### SOS-N12: Request bulk or API access from the Department of Registration and Stamps
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want a formal request sent to the Department of Registration and Stamps, so that we know whether bulk or API access exists. Ask about bulk data, API access and licence terms. The outcome is uncertain, so this runs beside SOS-N11.
- **Acceptance Criteria:**
  - The request is sent and acknowledged.
  - The reply, or the absence of one after 30 days, is recorded.
- **Test Criteria:** Verified by the acknowledgement.
- **Notes:** Decided by Jayman, 24 November 2026: Not Needed. The registration data source is now LegiScore (SOS-P3-14 to SOS-P3-17), a per property lookup service, not a bulk feed.
- **Owner:** Jayman, Counsel
- **Priority:** P0
- **Launch:** none
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Not Needed

### SOS-P3-01L: Ingest the first real batch from the chosen source
- **Epic:** Market intelligence
- **Description:** As Jayman, I want the first small batch of real registration data ingested, so that we know the source works and what it costs before five years are loaded. The live half of SOS-P3-01 and of the LegiScore adapters (SOS-P3-15, SOS-P3-16): Jayman adds the LegiScore API key in the Market data source panel (SOS-P3-14), runs a first small batch, and records the credit price and LegiScore's written answers.
- **Acceptance Criteria:**
  - Jayman has added the key in the panel and run a first small batch, and the records are in the raw transaction table.
  - The credit price of a year of an Index II search and of a RERA check is recorded, from the panel's balance before and after.
  - LegiScore's written confirmation is recorded on four questions: (1) permanent storage of the results, (2) use in derived analytics and matching, (3) showing derived figures to several customer companies, and (4) the terms of its upstream sources.
  - The ready reckoner rates file is supplied and loaded.
  - Nothing solves a captcha or bypasses an access control.
- **Test Criteria:** Verified by Jayman against the panel's credit ledger and LegiScore's written reply.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman holds the source and its terms, so it is Waiting and the loop does not pick it. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 8): Market data lives on the control site and reaches company sites through a role checked API. It is loaded from export files Jayman supplies (Index II or DoRS) through SOS-P3-01's file adapter, ready reckoner rates are loaded from a file Jayman supplies, and the data licence switch is a platform setting, On by default for data SellOS owns. Decided by Jayman, 24 November 2026: SOS-N12 is Not Needed and is no longer a dependency. The acceptance above replaces the earlier one (a count that matches the source's, and the source's licence terms).
- **Owner:** Jayman
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** SOS-P3-01
- **Status:** Waiting

### SOS-P3-14: Build the market data source panel for the Platform Admin
- **Epic:** Market intelligence
- **Description:** As the Platform Admin, I want a panel on the control site where I enter the market data source's API key and control what it may spend, so that no search spends credits I did not allow. Build a Market data source panel in the SellOS web app (control site, Platform Admin only) for LegiScore, with the client that every LegiScore adapter uses (`sellos/intel/legiscore/client.py`).
- **Acceptance Criteria:**
  - The Platform Admin enters the API key. It is stored encrypted in a password field of a control site setting, shown only as a masked value (the last four characters), never returned by any API, and never in code, a log, an error message, a fixture or this chat.
  - The panel shows the credit balance, read with `GET /api/v1/search/credits` (the `data.balance` and `data.spendable` fields), with the time it was read.
  - The panel holds a monthly credit budget and a per run cap. A run that would take the month's spend over the budget, or its own spend over the cap, is refused before anything is submitted, and says why.
  - Before any search is submitted the panel shows the estimated credits and asks for confirmation; nothing is spent without it. A scheduled run uses the same budget and cap and spends nothing the settings do not allow.
  - The client sends `Authorization: Bearer <key>` and an `Idempotency-Key` header on every submit (1 to 255 printable characters, no spaces, derived from the search's own parameters so the same search always has the same key), polls `GET /api/v1/search/{id}` every 5 to 10 seconds for up to 20 minutes, and adds no callback endpoint and sends no `callback_url`. A search still running after 20 minutes is recorded as timed out, not as failed or empty, and is polled again on the next run.
  - The district, tahsil and village of a property are resolved by name through `GET /api/v1/search/lookups` (at most 10 matches, name of at least 2 characters), never enumerated; an ambiguous name asks the Platform Admin to choose.
  - Only the Platform Admin can open the panel or call its methods, and every method is declared and in the permission test matrix.
  - The real transport is refused under the test runner, so no test calls LegiScore.
- **Test Criteria:** Backend tests with saved responses and a fake transport: the key is stored encrypted and masked in every answer and never appears in a captured log, error, fixture or file (a fake key); balance read; budget and per run cap refuse before submit; no spend without confirmation; the Idempotency-Key is sent and is the same for the same search; polling stops at 20 minutes and marks the search timed out; no callback is sent; a permission test for every role. A Cypress spec of entering a key, reading the balance, setting the budget and confirming a spend.
- **Notes:** Decided by Jayman, 24 November 2026. Source: LegiScore, https://legiscore.in/docs, base https://legiscore.in/api/v1, Bearer key (the docs read on 24 November 2026: every answer is `{"data": ...}` or `{"error": {...}}`). LegiScore is a per property or per project lookup service, not a bulk feed. No test and no loop run calls LegiScore: tests use saved responses in `sellos/intel/fixtures/legiscore/` through a fake transport, and the real transport refuses to run under the test runner. Market data lives on the control site (SOS-P3-01); parties' names stay on the control site under SOS-P3-12's rules, and company sites and the Property Matcher get building level and project level figures only. Discovery of new projects stays with SOS-P6-08. This task does not depend on SOS-P3-04 (Blocked): it builds against a fixture list of buildings, and reads the real list once SOS-P3-04A supplies it. Added by SOS-LOOP. Expected flow (Jayman, 24 November 2026; the builder adds it to `docs/regression/flows.md` when building the feature, one `FLOW` line each, and does not add flows in advance): 1. As platform_admin, from `/sellos/control/market-data`: Sign in. Open the Market data source panel. Enter a fake API key and save. Expected: The panel shows the key only as a masked value (its last four characters) and never shows the full key, before or after a reload. 2. As platform_admin, from `/sellos/control/market-data`: In the panel read the credit balance, set a monthly credit budget and a per run cap, then try a run whose estimate is over the cap. Expected: The balance and the time it was read are shown, the run is refused before anything is submitted, and the message says the cap is the reason. 3. As platform_admin, from `/sellos/control/market-data`: Start a run that is inside the budget and the cap and look at the confirmation. Cancel it, then start it again and confirm. Expected: The confirmation shows the estimated credits, cancelling spends nothing, and only the confirmed run is submitted. 4. As company_admin, from `/sellos/control/market-data`: Sign in as the gate company admin and type the address of the panel. Expected: The page says there is no access and no key, balance or setting is shown. UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-01, SOS-P1-01
- **Status:** Not Started
- **Browser spec:** required

### SOS-P3-15: Build the LegiScore adapter for Maharashtra Index II
- **Epic:** Market intelligence
- **Description:** As an Agent, I want the registered transactions of a building, so that comparables rest on real documents. Build the LegiScore adapter behind SOS-P3-01's source adapter interface for the search type `index2_property` (Maharashtra), run per building from the building's CTS numbers, one year at a time.
- **Acceptance Criteria:**
  - The adapter reads the buildings to search from a fixture list of buildings in the shape SOS-P3-04 defines (building, CTS numbers, village, tahsil, district); once SOS-P3-04A supplies the real list, it reads that, and the task needs no change.
  - For each building, CTS number and year, it submits one `index2_property` search with `property_no` (the CTS number, at most 40 characters), `year_from`, and the district, tahsil and village resolved by name through the lookups (never enumerated). For a Mumbai property it uses the Mumbai tab with `area_name` (English, at most 80 characters), and `mumbai_district` Mumbai Suburban where it applies. The exact parameter names are read from the saved responses and the docs page, and a change in them raises an alert, not bad data.
  - Every submit goes through SOS-P3-14's client and guard: Idempotency-Key, confirmation, budget and per run cap.
  - One raw transaction row is stored per registered document, in the shape of SOS-P3-02, with the building, CTS number, year and search id. A re-run of the same year changes nothing.
  - Each result PDF (the Index II abstract) is fetched with `GET /api/v1/search/{id}/documents/{filename}` and stored as a private file linked to its row. A withheld document (410) is recorded as withheld.
  - A year that timed out is marked not searched, never zero documents. A search that returned the 25 PDF cap is marked truncated, never complete, and its building and year are queued for a narrower search or a manual look.
  - Parties' names are stored only on the control site, under SOS-P3-12's rules, and are never in the building level data the company sites receive.
  - The adapter never solves a captcha and never bypasses an access control; an `awaiting_otp` search is recorded and not answered by SellOS.
- **Test Criteria:** Contract tests with saved responses for: a normal year, a year with no documents (found false), a timed out year (not searched), a result at the 25 PDF cap (truncated), a withheld PDF, a failed search (each failure kind) and a changed response shape (alert). A test that a re-run is idempotent, that a Mumbai Suburban building uses the Mumbai tab and `area_name`, and that a party name never reaches a company site's data. No test calls LegiScore.
- **Notes:** Decided by Jayman, 24 November 2026. Source: LegiScore, https://legiscore.in/docs, base https://legiscore.in/api/v1, Bearer key (the docs read on 24 November 2026: every answer is `{"data": ...}` or `{"error": {...}}`). LegiScore is a per property or per project lookup service, not a bulk feed. No test and no loop run calls LegiScore: tests use saved responses in `sellos/intel/fixtures/legiscore/` through a fake transport, and the real transport refuses to run under the test runner. Market data lives on the control site (SOS-P3-01); parties' names stay on the control site under SOS-P3-12's rules, and company sites and the Property Matcher get building level and project level figures only. Discovery of new projects stays with SOS-P6-08. This task does not depend on SOS-P3-04 (Blocked): it builds against a fixture list of buildings, and reads the real list once SOS-P3-04A supplies it. The docs do not name a field for a timed out year or for the cap, so the adapter infers them from the result (`record_count`, `documents`, `note`) and the saved responses; if a real response differs, that is found in SOS-P3-01L and fixed as an SOS-FIX. The docs price an Index II search at 20 credits per year. Cost, limits and the corridor worked example are in `docs/LEGISCORE.md` (27 November 2026): LegiScore has no bulk or area listing, so the building list comes from seed lists reviewed by a person (SOS-P3-04), and the stated 25 document cap is not in the general docs and is confirmed in SOS-P3-01L. Reading the consideration and stamp duty from the abstract PDF is SOS-P3-17. Expected flow (Jayman, 24 November 2026; the builder adds it to `docs/regression/flows.md` when building the feature, one `FLOW` line each, and does not add flows in advance): 1. As platform_admin, from `/sellos/control/market-data`: Open the Index II searches list after a fixture run. Find a building with a timed out year and a building at the 25 document cap. Expected: The timed out year says Not searched, never zero, and the capped search says Truncated, never complete. UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-14, SOS-P3-02, SOS-P3-03
- **Status:** Not Started

### SOS-P3-16: Build the LegiScore adapter for Maharashtra RERA projects and sold inventory snapshots
- **Epic:** Market intelligence
- **Description:** As an Agent, I want each project's sold and booked inventory over time, so that I know how a project is selling. Build the LegiScore adapter for the search type `rera_check` (Maharashtra) for every Project record that has a RERA number, on a schedule Jayman sets, and keep a dated snapshot of the parsed figures each run. `rera_single` is replaced by `rera_check` and is not used.
- **Acceptance Criteria:**
  - A schedule (Off by default; daily, weekly or monthly, set by Jayman in the panel) runs one `rera_check` per Project with a RERA number (`rera_number`, at most 20 characters), through SOS-P3-14's client and guard (Idempotency-Key, confirmation or a standing approval within the budget and per run cap).
  - The summary PDF and the latest sold and booked inventory disclosure PDF (the document named "Disclosure of Sold-Booked Inventory" in the result) are stored as private files.
  - Each run takes a dated snapshot of the parsed sold and booked figures for the project, so a time series builds up; a snapshot is never edited or deleted, and a run that finds no new disclosure records that it changed nothing.
  - A name that matches several projects returns a list and charges nothing; the adapter records it for a person to choose, and never guesses.
  - The figures are extracted by SOS-P3-17 and go through its review queue; nothing from this adapter feeds the Property Matcher or any published view before approval.
  - The adapter never solves a captcha and never bypasses an access control.
- **Test Criteria:** Contract tests with saved responses for a project with a disclosure, one without, several matching projects, a failed search and a changed response shape; a test that two runs make two dated snapshots and that an unchanged disclosure makes none new; a test that a snapshot cannot be edited; a test that nothing unapproved reaches the matcher or a published view. No test calls LegiScore.
- **Notes:** Decided by Jayman, 24 November 2026. Source: LegiScore, https://legiscore.in/docs, base https://legiscore.in/api/v1, Bearer key (the docs read on 24 November 2026: every answer is `{"data": ...}` or `{"error": {...}}`). LegiScore is a per property or per project lookup service, not a bulk feed. No test and no loop run calls LegiScore: tests use saved responses in `sellos/intel/fixtures/legiscore/` through a fake transport, and the real transport refuses to run under the test runner. Market data lives on the control site (SOS-P3-01); parties' names stay on the control site under SOS-P3-12's rules, and company sites and the Property Matcher get building level and project level figures only. Discovery of new projects stays with SOS-P6-08. This task does not depend on SOS-P3-04 (Blocked): it builds against a fixture list of buildings, and reads the real list once SOS-P3-04A supplies it. The Projects come from SOS-P6-08 (discovery) and from Jayman's list; this task only checks the ones that carry a RERA number. The docs do not state a credit price for `rera_check`; SOS-P3-01L records it. Expected flow (Jayman, 24 November 2026; the builder adds it to `docs/regression/flows.md` when building the feature, one `FLOW` line each, and does not add flows in advance): 1. As platform_admin, from `/sellos/control/market-data`: Open the RERA check schedule, set it to weekly and look at a project with two runs. Expected: The schedule is saved, the project shows two dated snapshots of its sold and booked figures, and neither can be edited. UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-14, SOS-P3-02, SOS-P4-01
- **Status:** Not Started

### SOS-P3-17: Extract figures from LegiScore PDFs and approve them in a review queue
- **Epic:** Market intelligence
- **Description:** As the Platform Admin, I want the consideration, stamp duty and sold and booked inventory read from the PDFs and approved by a person before anyone relies on them, so that no wrong figure reaches an agent. Build the extraction behind one interface, a review queue, and the approved building level and project level figures.
- **Acceptance Criteria:**
  - The extractor interface has a fake extractor for tests and a manual entry path; a real reader (the SOS-P3-03 normaliser for the text it can parse, and Sarvam Vision for PDF pages) is added behind it only after the live check SOS-P3-17L passes on real PDFs. The task decides nothing about the reader from claims: SOS-P3-03 parses text fields and does not read PDFs.
  - For an Index II abstract the extractor produces consideration, stamp duty and registration date, in the canonical shape of SOS-P3-01; for a disclosure PDF it produces the sold and booked inventory numbers.
  - Every extracted figure goes to a review queue with its source PDF beside it, the confidence and the extractor used. Approve, correct and reject are saved, a correction is reused, and each action is logged.
  - Nothing feeds the Property Matcher (SOS-P3-05) or any published view before approval.
  - Approved figures are rolled up to building level (transactions) and project level (sold and booked inventory, with the dated snapshots of SOS-P3-16) and are the only data company sites receive, through the role checked API of SOS-P3-01's decision; parties' names never leave the control site.
  - Only the Platform Admin works the queue.
- **Test Criteria:** Backend tests with the fake extractor: figures wait in the queue, approval releases them to the roll up, a rejected figure never does, a correction is saved and reused, the roll ups carry no party name, and the permission test for every role. A Cypress spec of approving and correcting a figure.
- **Notes:** Decided by Jayman, 24 November 2026. Source: LegiScore, https://legiscore.in/docs, base https://legiscore.in/api/v1, Bearer key (the docs read on 24 November 2026: every answer is `{"data": ...}` or `{"error": {...}}`). LegiScore is a per property or per project lookup service, not a bulk feed. No test and no loop run calls LegiScore: tests use saved responses in `sellos/intel/fixtures/legiscore/` through a fake transport, and the real transport refuses to run under the test runner. Market data lives on the control site (SOS-P3-01); parties' names stay on the control site under SOS-P3-12's rules, and company sites and the Property Matcher get building level and project level figures only. Discovery of new projects stays with SOS-P6-08. This task does not depend on SOS-P3-04 (Blocked): it builds against a fixture list of buildings, and reads the real list once SOS-P3-04A supplies it. The check Jayman asked for before choosing a reader (24 November 2026): `sellos/intel/normaliser.py` parses text and numbers, dates, Marathi names and areas and reads no PDF, and `sellos/voice/` is the only code that holds Sarvam keys; so whether Sarvam Vision or the normaliser reads a real Index II abstract and a real disclosure PDF is not known from the code, and is measured on real files in SOS-P3-17L. Expected flow (Jayman, 24 November 2026; the builder adds it to `docs/regression/flows.md` when building the feature, one `FLOW` line each, and does not add flows in advance): 1. As platform_admin, from `/sellos/control/market-data/review`: Open the review queue. Correct one figure, approve another and reject a third. Expected: Each action is saved and logged with the source PDF beside the figure, and only the approved figure appears in the building roll up. 2. As agent, from `/sellos/control/market-data/review`: Sign in as the gate agent and type the address of the queue. Expected: The page says there is no access. UAE and Australia are out of scope for 1 January. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-15, SOS-P3-16, SOS-P3-03
- **Status:** Not Started
- **Browser spec:** required

### SOS-P3-17L: Check the PDF reader on a real Index II abstract and a real disclosure PDF
- **Epic:** Market intelligence
- **Description:** As Jayman, I want the PDF reader tried on real files before it is switched on, so that no figure is trusted on a guess. The live half of SOS-P3-17: Jayman runs one real Index II abstract and one real sold and booked inventory disclosure PDF through the normaliser and Sarvam Vision, and records which reader got the consideration, stamp duty and sold and booked numbers right.
- **Acceptance Criteria:**
  - The result for each reader and each file is recorded in `docs/MARKET_DATA.md`, with the figures read against the figures on the page.
  - The reader to switch on is chosen from that result, or manual entry stays the only path.
- **Test Criteria:** Verified by Jayman against the PDFs.
- **Notes:** Decided by Jayman, 24 November 2026. Jayman holds the files and the Sarvam key, so it is Waiting and the loop does not pick it.
- **Owner:** Jayman
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** SOS-P3-17
- **Status:** Waiting

### SOS-P3-04A: Supply and verify the corridor micro markets and buildings
- **Epic:** Market intelligence
- **Description:** As Jayman, I want the real Bandra to Andheri micro markets and buildings loaded and checked, so that transactions roll up the way agents think. The acceptance half of SOS-P3-04: Jayman supplies the boundaries and the seed list of buildings in SOS-P3-04's file format, they are loaded into Pandya's company layer, and people review them on SOS-P3-04's review screen.
- **Acceptance Criteria:**
  - The corridor's micro markets and boundaries are loaded for Pandya Realtors.
  - The review screen lists the system built buildings with their name, CTS, RERA and micro market.
  - A reviewer can correct or confirm each building, and every correction is saved.
  - Twenty buildings are confirmed. That completes the task.
- **Test Criteria:** Twenty buildings are confirmed on the review screen, and the corrections are in each building's change history.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman's work, so it is Waiting and the loop does not pick it. Decided by Jayman, 27 November 2026: any Company Admin or Agent can be the reviewer, so who reviews is not decided now. The Bandra to Andheri corridor is Pandya's first set, not a built in rule.
- **Owner:** Jayman
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 2
- **Dependencies:** SOS-P3-04
- **Status:** Waiting

### SOS-P3-10L: Live test the agent assistant with the real language model
- **Epic:** Market intelligence
- **Description:** As Jayman, I want the assistant checked once with the real language model, so that the fake model it was built with behaves like the real one. The live half of SOS-P3-10: with the real key in settings, run the scripted question set and the unknown building question.
- **Acceptance Criteria:**
  - Every answer cites its records.
  - An unknown building gets a clear refusal and no invented figure.
  - Party names stay hidden where the role forbids them.
  - Every difference from the fake model's behaviour becomes an SOS-FIX task.
- **Test Criteria:** Verified by Jayman against the scripted question set.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman holds the account and keys, so it is Waiting and the loop does not pick it. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 10): Anthropic, with the assistant model SOS-N21 chooses; Jayman enters the key.
- **Owner:** Jayman
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** SOS-P3-10
- **Status:** Waiting

### SOS-P3-13: Load and verify five years of data
- **Epic:** Market intelligence
- **Description:** As Jayman, I want five years of corridor data loaded and checked, so that agents can trust it. Load five years of Bandra to Andheri data and check 50 records against Index II.
- **Acceptance Criteria:**
  - Five years are loaded.
  - 50 records are checked against Index II.
  - The accuracy is reported and discrepancies are logged.
- **Test Criteria:** An audit report with the sample and the results.
- **Notes:** Dependencies added by SOS-SETUP-33 (13 November 2026): loading five years needs the real source (SOS-P3-01L) and the verified buildings (SOS-P3-04A). Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 8): Market data lives on the control site and reaches company sites through a role checked API. It is loaded from export files Jayman supplies (Index II or DoRS) through SOS-P3-01's file adapter, ready reckoner rates are loaded from a file Jayman supplies, and the data licence switch is a platform setting, On by default for data SellOS owns.
- **Owner:** Jayman
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-05, SOS-P3-01L, SOS-P3-04A
- **Status:** Waiting

### SOS-P6-08: Build the listing scraper for property portals
- **Epic:** Listing sources and WhatsApp
- **Description:** As an Agent, I want listings from the property portals collected automatically, so that I start with inventory I did not type by hand. P6-08 is a scraper that browses the portals itself: it is not a file importer. One source adapter per portal, starting with 99acres, MagicBricks, Housing.com and NoBroker, and adding others as they are found. Each adapter drives a headless browser over public search and listing pages, scoped by the company's micro markets and buildings (SOS-P3-04), and sends what it reads to a review queue of candidate listings.
- **Acceptance Criteria:**
  - One source adapter per portal, one extraction file per adapter, behind one interface, so a new portal is a new adapter. Each reads: title, price, area, BHK and type, locality, building or project, floor, furnishing, posted date, poster type, listing URL and photo URLs.
  - Searches are scoped by the company's micro markets and buildings (SOS-P3-04); nothing outside them is searched.
  - Rate limiting per source, from the source's settings: a delay between page loads with random jitter (default 6 to 12 seconds), a cap per run and a cap per day, one session per source at a time, a quiet window, exponential backoff on 429 or 403, and an automatic pause of the source with an alert when it starts blocking.
  - Runs are scheduled (nightly by default) on the worker, never in a web request.
  - Per company settings, ordinary settings a Company Admin changes: each source on or off, search areas, schedule, and an optional proxy URL.
  - Public pages only. If a portal shows a captcha or a login wall, the source stops and is reported as "blocked by the portal", and the run moves on to the next source. SellOS never solves a captcha and never logs in or bypasses an access control (CLAUDE.md rule 10). Owner phone numbers are behind logins on most portals, so a listing without a phone is still a listing.
  - Results go to a review queue of candidate listings, deduplicated across portals and runs (the same building, the same floor, and area and price each within a few percent is one property), linked to the building master (SOS-P3-04) where it matches, with the source URL kept. A person approves a candidate, and it becomes a draft listing or a seller lead to call. Nothing publishes by itself.
  - A health check per adapter fails loudly, and alerts, when a page yields no fields (a changed layout), and loads no bad data.
- **Test Criteria:** For each adapter, saved sample HTML pages in fixtures and a test of the extraction against them; a test that a page with no fields fails the health check and raises an alert; the rate limit (jitter inside the range, per run and per day caps, one session per source, quiet window, backoff on 429 and 403, pause with alert); a captcha page and a login wall each stop the source with "blocked by the portal" and the run goes on; deduplication across portals and runs; the scope by micro market; the per company switches; nothing publishes without approval. No test or loop run calls a live portal, and the headless browser is driven against saved pages only.
- **Notes:** Final decision by Jayman, 27 November 2026: a scraper, not a CSV or XLS importer (the import, and "a sample export from an agent" as something Jayman supplies, are dropped). SOS-P6-09 (the portal terms review) is no longer a gate or a dependency; it stays only as a note. The live run of one adapter against a real portal is SOS-P6-08L (Jayman). The headless browser must already be on the machine: the agent never installs one on the shared bench (SOS-SETUP-20), and replies NEEDS_INPUT if none is available. MUST for 1 January 2027. UAE and Australia are out of scope for 1 January.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P4-02, SOS-P3-04
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-08L: Run one scraper adapter against a real portal
- **Epic:** Listing sources and WhatsApp
- **Description:** As Jayman, I want a small live run of one adapter against a real portal, so that we know the extraction works on the real pages before it is switched on for a company. Run one adapter over one micro market, check the candidates in the review queue against the portal's own pages, and record what each field read correctly and what it missed.
- **Acceptance Criteria:**
  - One adapter ran once, within its per run cap.
  - The candidates were compared with the portal's pages and the result is recorded.
  - A captcha, a login wall or a block, if it happened, is recorded.
- **Test Criteria:** Verified by Jayman against the review queue and the source's last run log.
- **Notes:** Added by Jayman's decision, 27 November 2026. Jayman's work, so it is Waiting and the loop does not pick it.
- **Owner:** Jayman
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 2
- **Dependencies:** SOS-P6-08
- **Status:** Waiting
### SOS-P6-09: Review each portal's terms
- **Epic:** Listing sources and WhatsApp
- **Description:** As Jayman, I want each listing portal's terms reviewed, so that we only use sources we are allowed to use. Review each portal's terms and any official feed or partner access, and switch on only the sources that pass.
- **Acceptance Criteria:**
  - A decision is recorded for each portal.
  - Only approved sources are enabled.
  - Rejected sources stay off.
- **Test Criteria:** Verified by the decision log and the source switches.
- **Notes:** Decided by Jayman, 24 November 2026: SOS-P6-08 is the scraper. Every source starts Off, the legal review and switching sources on are Jayman's, and SOS-P6-08's criteria (rate limits, access rules, no captcha solving, no login bypass) are unchanged. Decided by Jayman, 27 November 2026: no longer a dependency of SOS-P6-08 or SOS-P6-10, and no gate on switching a source on. Final decision, 27 November 2026: a note only. It is not a gate and not a dependency, and no source waits for it.
- **Owner:** Jayman, Counsel
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P6-08
- **Status:** Waiting

### SOS-P6-10: Build the Facebook capture assist
- **Epic:** Listing sources and WhatsApp
- **Description:** As an Agent, I want to save a property post from a Facebook group to SellOS myself, so that group posts build our starting inventory without automated collection. The main job is the share target and paste flow: an agent signed in as themselves shares or pastes a post, and it is parsed into a draft listing in the review queue. Meta Lead Ads (below) is a secondary, optional part that does not block this.
- **Acceptance Criteria:**
  - An agent can save a post in two taps or clicks.
  - The post becomes a draft in the review queue.
  - No automated collection runs against Facebook.
  - Poster personal data follows the counsel rules.
  - A poster's name and number are kept only on the draft listing, masked like a lead's phone, and deleted when the draft is rejected.
  - It is a share target in the SellOS web app on a phone, plus pasting a post's link and text on a computer. There is no browser extension.
  - Optional, secondary, and it never blocks the rest of this task: Meta Lead Ads. Leads from a company's own Facebook lead forms arrive through the official Meta Lead Ads API and enter the CRM through `sellos.crm.intake` (create or merge, consent evidence kept). Its credentials (app ID, app secret, page access token, page ID) come from the company's Integrations screen (SOS-INT-1) and nothing in the main flow needs them. Meta's lead notification is a provider webhook under the CLAUDE.md webhook rules (signature first with the app secret, replay and order, body cap, rate limit, tenant from the site), registered in `sellos.access.webhooks` and listed in `docs/permissions.md`. If no Meta app exists when the main work is done, this part is left for later and the task still completes.
- **Test Criteria:** Parse 20 saved sample posts (fixtures with made up names and numbers from `sellos.tests.phones`) and check the parsing, a test that a shared or pasted post becomes a draft listing in the review queue, and a test that nothing is collected without an agent action. The capture of real posts is SOS-P6-10L, owned by Jayman. Optional part: Lead Ads tests through a fake Meta (a valid signed notification creates one lead; an invalid signature, a replay, an out of order and an oversized body write nothing; a company with no keys set gets nothing; the keys never appear in a log).
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): the post parser sits behind one capture interface, and the tests feed it saved post fixtures; no test or code path sends a request to Facebook. The capture of real posts by a signed in agent is SOS-P6-10L. "As counsel advises" has no source (SOS-N13 is Not Needed), and whether the assist is a browser extension or a share target is not decided; both are questions in `docs/BACKLOG_AUDIT.md`. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 7): the poster rule above replaces "as counsel advises". Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 15): a share target and paste, not a browser extension. MUST for 1 January 2027 (Jayman, 27 November 2026). Decided by Jayman, 27 November 2026: Facebook capture means capturing property posts from Facebook groups to build starting inventory. That is the main job; the Lead Ads part is secondary and optional, needs no Meta app to finish the main work, and uses the credentials from SOS-INT-1 only when it is built. Nothing scrapes Facebook.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P6-08
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-10L: Live test the Facebook capture assist
- **Epic:** Listing sources and WhatsApp
- **Description:** As Jayman, I want the capture assist checked on real Facebook posts, so that the parser built on saved fixtures works on today's pages. The live half of SOS-P6-10: Jayman, signed in to Facebook as himself, saves real group posts with the assist.
- **Acceptance Criteria:**
  - A real post is saved in two taps or clicks and becomes a draft in the review queue.
  - The parsing of 20 real posts is checked, and every miss becomes an SOS-FIX task.
  - Nothing is collected without an agent action.
- **Test Criteria:** Verified by Jayman on 20 real posts.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman's own Facebook account is used, so it is Waiting and the loop does not pick it.
- **Owner:** Jayman
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** SOS-P6-10
- **Status:** Waiting

### SOS-P6-01: Build the billing records
- **Epic:** Billing and subscriptions
- **Description:** As a Platform Admin, I want plans, coupons, subscriptions, invoices and payments recorded, so that billing has a foundation. Build Plan, Coupon, Subscription, Invoice and Payment on the control site, with limits on each plan.
- **Acceptance Criteria:**
  - All five records exist.
  - A plan defines limits such as users and listings.
  - A subscription links one company to one plan.
- **Test Criteria:** Unit tests of the records and their relationships.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): SOS-P1-01 already built a Plan stub on the control site (`plan_name`, `enabled`, `max_users`). Tenant links to it, and SOS-P1-02's worker reads it and writes `sellos_limits` into the new site's config (`sellos/provisioning/tenant_setup.py`). This task supersedes the stub: it extends the same Plan DocType, keeps those three fields and their names, and adds the other limits and the prices. Existing Plan records stay, with empty values in the new fields. The worker writes every new limit into `sellos_limits` the same way. SOS-P1-01's and SOS-P1-02's tests (`sellos/provisioning/test_p1_01_control_site.py`, `sellos/provisioning/test_p1_02_worker.py`) are updated where they read a Plan, and the number of assertions in each changed test must not fall. The Coupon record defined here holds the fields SOS-P6-05 needs (type, value, expiry, redemption limit, cycles); SOS-P6-05 adds the rules and does not redefine the fields. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 5
- **Dependencies:** SOS-P1-01
- **Status:** Not Started

### SOS-P6-02: Define the plan tiers
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want sensible plan tiers, so that pricing is clear. Claude Code reads how BuildOS structures its plans, in the read only reference copy at `~/iespl-baseline/buildos-reference`, and proposes SellOS tiers in the same shape. Jayman approves the limits and prices.
- **Acceptance Criteria:**
  - A proposal is delivered.
  - The proposed tiers are written to one data file, and a patch loads them as Plan records and can be run again safely, so the values Jayman approves in SOS-P6-02A are loaded by changing that file.
- **Test Criteria:** A test that the patch loads every tier in the file and that a second run changes nothing. Limit enforcement is tested in SOS-P6-04. Jayman's written approval is SOS-P6-02A.
- **Notes:** SOS-SETUP-21: read BuildOS code only in the read only reference copy at `~/iespl-baseline/buildos-reference`, with ls, cat, grep and find, and never write into it. Never read, list or run anything under `apps/buildos`. Split by SOS-SETUP-33 (13 November 2026): the proposal and the loader are this task, owned by Claude Code; the approval is SOS-P6-02A, owned by Jayman. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 3
- **Dependencies:** SOS-P0-01
- **Status:** Not Started

### SOS-P6-02A: Approve the plan limits and prices
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want the plan limits and prices approved, so that pricing is clear before any agency pays. The acceptance half of SOS-P6-02: read its proposal, approve or change the limits and prices, and have the data file hold the approved values.
- **Acceptance Criteria:**
  - Limits and prices are approved in writing.
  - The data file holds the approved values, and the loaded Plan records match them.
- **Test Criteria:** Verified by the written approval and the loaded plan records.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman's decision, so it is Waiting and the loop does not pick it.
- **Owner:** Jayman
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** SOS-P6-02
- **Status:** Waiting

### SOS-N14: Open Razorpay and Stripe accounts
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want Razorpay and Stripe accounts with test keys, so that billing can be built in test mode. Open both accounts, complete their business verification, and generate test keys.
- **Acceptance Criteria:**
  - The Razorpay account is active with test keys.
  - The Stripe account is active with test keys.
  - Keys are stored in the password manager, never shared in chat or email.
- **Test Criteria:** Create one test subscription in each dashboard.
- **Notes:** Decided by Jayman, 24 November 2026: Parked, not selling yet. SOS-N15 no longer depends on it. SOS-P6-03 and SOS-P6-15 still build against fakes. Bring it back by setting it to Waiting when the company is ready to sell.
- **Owner:** Jayman, Accountant
- **Priority:** P0
- **Launch:** none
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Parked

### SOS-N15: Confirm the GST invoice format
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want a written invoice format and a designed invoice template, so that SOS-P6-06 builds invoices that are compliant and look good. Deliver the format specification and the template, from the structure of Jayman's sample invoice: the issuer block, invoice number and date, terms, bill to, numbered particulars with period, rate and amount, total and amount in words, bank details, remarks, and the computer generated line. The accountant confirms the GST parts later.
- **Acceptance Criteria:**
  - `docs/INVOICE_FORMAT.md` is the written format specification: every block of the invoice above, each field with its source (a company setting, the subscription, the payment or a rule), the numbering rule with the financial year in the number derived from the invoice date (April to March, never typed), the rounding and amount in words rules, and the credit note rules.
  - The designed template (`docs/invoice-template/`, an HTML and CSS file) is prettier than the sample and follows `docs/UI_STYLE.md` (its tokens, type and colours, no colour or font of its own), prints on A4, and holds placeholders only.
  - Party details, descriptions, amounts, the bank account number and the PAN are placeholders read from company settings. None of Jayman's real data is copied into the repository, and a test fails if a real looking PAN, account number or GSTIN is found in the docs or the template.
  - Three worked examples with placeholder data: an Indian customer, an overseas customer and a credit note.
  - Every GST item is marked "To be confirmed by the accountant": GSTIN, tax code (SAC), place of supply, the tax split (CGST and SGST, or IGST), the export wording for overseas customers and any reverse charge or zero rating wording. None is invented.
- **Test Criteria:** A backend test that the spec names every block, that the template holds only placeholders and uses only UI_STYLE tokens, that the financial year in the number is derived from the date at both ends of the year (31 March and 1 April), and that no real PAN, GSTIN or account number is in the repository. The accountant's approval of samples is SOS-P6-06A.
- **Notes:** Decided by Jayman, 24 November 2026: owner changed from the Accountant to Claude Code, status Not Started, and the dependency on SOS-N14 is removed (N14 is Parked). The accountant confirms the GST fields later, in SOS-P6-06A. SOS-P6-06 builds this format, so it now depends on this task. Jayman's sample invoice is the reference for structure only and is not in the repository. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Later
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Not Started

### SOS-P6-03: Build the Razorpay adapter and recurring payments
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want Indian customers charged automatically, so that revenue is predictable. Build a gateway interface and the Razorpay adapter with subscription creation, cancellation and webhooks, in test mode first.
- **Acceptance Criteria:**
  - Against a fake Razorpay gateway behind the gateway interface, a subscription is created and renews.
  - Webhooks update the subscription.
  - Webhook handling is idempotent.
  - Failed payments are recorded.
- **Test Criteria:** Tests with the fake gateway and recorded Razorpay webhook bodies through creation, renewal, failure, cancellation and a replayed webhook. The sandbox run with real test keys is SOS-P6-03L, owned by Jayman.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): It is built and tested against a fake provider behind the adapter interface, as SOS-N21A does with `--fake`. The agent never calls the real provider and never holds a real key. SOS-N14 (the accounts) is now a dependency of the live test SOS-P6-03L, not of this task. Decided by Jayman, 24 November 2026: still built against the fake gateway; SOS-N14 is Parked, so no real keys exist and SOS-P6-03L is Parked. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 8
- **Dependencies:** SOS-P6-01
- **Status:** Not Started

### SOS-P6-03L: Live test Razorpay in test mode
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want the Razorpay adapter checked once with the real test mode keys, so that the fake gateway billing was built with behaves like Razorpay. The live half of SOS-P6-03: enter the test keys, create a subscription, let it renew, fail a payment, and check the webhooks.
- **Acceptance Criteria:**
  - A test mode subscription is created and renews.
  - Razorpay's real webhooks update the subscription, and a replayed one changes nothing.
  - A failed payment is recorded.
  - Every difference from the fake gateway becomes an SOS-FIX task.
- **Test Criteria:** Verified by Jayman against Razorpay's test dashboard.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman holds the account and keys, so it is Waiting and the loop does not pick it. Razorpay's webhooks need a public HTTPS address (question in `docs/BACKLOG_AUDIT.md`). Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 2): provider webhooks reach a public HTTPS address on staging, never a tunnel to the shared bench on port 8004, so this depends on SOS-P0-06D. Decided by Jayman, 24 November 2026: Parked with SOS-N14 (not selling yet). Its dependency on SOS-N14 stays in place for when it is brought back.
- **Owner:** Jayman
- **Priority:** P6
- **Launch:** none
- **Story Points:** 1
- **Dependencies:** SOS-N14, SOS-P6-03, SOS-P0-06D
- **Status:** Parked

### SOS-P6-15: Build the Stripe adapter
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want overseas customers charged automatically, so that international agencies can subscribe. Build the Stripe adapter behind the same gateway interface, with subscriptions, cancellation and webhooks, in test mode first. This story was split out of the original gateway task to keep each story within 8 points.
- **Acceptance Criteria:**
  - Against a fake Stripe gateway behind the gateway interface, a subscription renews.
  - Webhooks update the subscription.
  - Webhook handling is idempotent.
  - A customer is routed to Stripe or Razorpay by country.
- **Test Criteria:** Tests with the fake gateway and recorded Stripe webhook bodies through renewal, failure and a replayed webhook, and a routing test. The sandbox run with real test keys is SOS-P6-15L, owned by Jayman.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): It is built and tested against a fake provider behind the adapter interface, as SOS-N21A does with `--fake`. The agent never calls the real provider and never holds a real key. Decided by Jayman, 24 November 2026: still built against the fake gateway; SOS-N14 is Parked, so no real keys exist and SOS-P6-15L is Parked. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 5
- **Dependencies:** SOS-P6-03
- **Status:** Not Started

### SOS-P6-15L: Live test Stripe in test mode
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want the Stripe adapter checked once with the real test mode keys, so that the fake gateway behaves like Stripe. The live half of SOS-P6-15.
- **Acceptance Criteria:**
  - A test mode subscription renews.
  - Stripe's real webhooks update the subscription, and a replayed one changes nothing.
  - Every difference from the fake gateway becomes an SOS-FIX task.
- **Test Criteria:** Verified by Jayman against Stripe's test dashboard.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Jayman holds the account and keys, so it is Waiting and the loop does not pick it. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 2): provider webhooks reach a public HTTPS address on staging, never a tunnel to the shared bench on port 8004, so this depends on SOS-P0-06D. Decided by Jayman, 24 November 2026: Parked with SOS-N14 (not selling yet). Its dependency on SOS-N14 stays in place for when it is brought back.
- **Owner:** Jayman
- **Priority:** P6
- **Launch:** none
- **Story Points:** 1
- **Dependencies:** SOS-N14, SOS-P6-15, SOS-P0-06D
- **Status:** Parked

### SOS-P6-04: Build the billing lifecycle
- **Epic:** Billing and subscriptions
- **Description:** As a Platform Admin, I want subscriptions to move through clear states, so that access follows payment. Build trial, active, past due with a grace period, suspended and cancelled, with emails at each change. A suspended company's site is disabled but kept, and plan limits are enforced.
- **Acceptance Criteria:**
  - States change on gateway events.
  - Past due has a configurable grace period.
  - Suspension disables the site without deleting data.
  - Reactivation restores access.
  - Plan limits are enforced.
- **Test Criteria:** Simulate failure, grace, suspension and recovery in test mode.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): "test mode" means the fake gateway of SOS-P6-03; no test reaches Razorpay or Stripe. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 8
- **Dependencies:** SOS-P6-03, SOS-P6-02
- **Status:** Not Started

### SOS-P6-05: Build coupons
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want discount coupons, so that we can offer deals. Build percentage and fixed coupons with an expiry, a redemption limit and a number of billing cycles, applied to invoices.
- **Acceptance Criteria:**
  - Coupons discount an invoice correctly.
  - Expired or used up coupons are refused.
  - Cycle limits are honoured.
- **Test Criteria:** Unit tests for each coupon rule.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): the Coupon fields are SOS-P6-01's; this task adds the rules only. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 3
- **Dependencies:** SOS-P6-01
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-06: Build GST compliant invoices
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want compliant invoices, so that customers and the tax authority are satisfied. Generate an invoice for every payment from an editable invoice template, with GST for Indian customers and the correct treatment for overseas customers, numbered in sequence.
- **Acceptance Criteria:**
  - Each payment has a numbered invoice.
  - GST is shown for Indian customers.
  - Overseas invoices follow the treatment held in the invoice template, which SOS-P6-06A fills in from SOS-N15.
  - Credit notes are supported.
  - No invoice is issued to a real customer until SOS-N15 is Complete. A platform setting, "Invoice format approved", is Off until then; while it is Off an invoice can be previewed and saved as a draft but not issued to a customer.
  - The invoice is an editable template that a Platform Admin changes without a code change.
- **Test Criteria:** Tests of numbering, the GST lines (CGST and SGST within the state, IGST across states, the overseas treatment from the setting) and credit notes, with sample invoices saved for the accountant. The accountant's approval is SOS-P6-06A.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026): SOS-N15's own test is that the accountant approves a sample invoice made by this task, so this task cannot wait for SOS-N15. It builds the invoice from a format held in a setting (the seller's GSTIN, the service code, the numbering series, the overseas treatment) and the accountant's approval is SOS-P6-06A, which depends on SOS-N15. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 17): invoices are built as an editable template now, and none is issued to a real customer until SOS-N15 is Complete. SOS-N15's dependency on SOS-N14 is unchanged: the answer did not cover it. Decided by Jayman, 24 November 2026: builds the format specified and designed in SOS-N15 (`docs/INVOICE_FORMAT.md` and `docs/invoice-template/`). Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 5
- **Dependencies:** SOS-P6-01, SOS-N15
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-06A: The accountant approves sample invoices
- **Epic:** Billing and subscriptions
- **Description:** As the Accountant, I want to check SellOS's invoices against the confirmed GST format, so that invoices are compliant. The acceptance half of SOS-P6-06: enter the format confirmed in SOS-N15 in the invoice format setting and approve sample invoices for an Indian and an overseas customer and a credit note.
- **Acceptance Criteria:**
  - The invoice format setting holds the confirmed format.
  - Sample invoices for an Indian customer and an overseas customer, and a credit note, are approved in writing.
  - Every change asked for becomes an SOS-FIX task.
- **Test Criteria:** The accountant approves sample invoices.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). The Accountant's work, so it is Waiting and the loop does not pick it. Decided by Jayman, 24 November 2026: uses the format built in SOS-N15. It stays the accountant's approval of the samples (an Indian customer, an overseas customer and a credit note), and the accountant confirms the GST fields listed in SOS-N15. Low urgency while nothing is sold.
- **Owner:** Accountant
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 1
- **Dependencies:** SOS-N15, SOS-P6-06
- **Status:** Waiting

### SOS-P6-07: Build self service sign up
- **Epic:** Billing and subscriptions
- **Description:** As a new agency, I want to sign up and start using SellOS without waiting, so that onboarding is quick. Build a sign up flow that collects company details, plan and payment, then triggers provisioning and the setup wizard.
- **Acceptance Criteria:**
  - A new company can sign up and pay.
  - Provisioning starts automatically.
  - The company receives login details.
  - Failed payments do not create a site.
- **Test Criteria:** An end to end test in test mode from sign up to first login.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026): "test mode" means the fake gateway of SOS-P6-03; no test reaches a real gateway. Recording acceptance of the legal terms at sign up is SOS-P6-13C. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 8
- **Dependencies:** SOS-P6-04, SOS-P1-03
- **Status:** Not Started
- **Browser spec:** required

### SOS-P1-14: Back up every site and prove the restore
- **Epic:** Platform foundations and DevOps
- **Description:** As Jayman, I want per site backups and a proven restore, so that no company's data is lost. Back up every site nightly to Spaces with 30 days of retention, and provide a script that restores one site to staging.
- **Acceptance Criteria:**
  - A backup command writes one backup (database and files) per tenant site, named with the site and the date, to a store behind one interface: a local folder store, and a Spaces (S3 compatible) store whose keys come only from environment variables.
  - Pruning removes backups older than 30 days and keeps the rest.
  - A restore command recreates a site from a backup as a new tenant site, through `sellos.provisioning.tenant_sites`, and its record counts match the original's.
  - No Spaces key is ever printed, logged or written.
- **Test Criteria:** On the local bench with the local folder store: back up a tenant site that holds records, restore it to a second tenant site, compare record counts, and drop both. A pruning test with dated backups, and a fake key that never appears in output or logs.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). This task is the code, owned by Claude Code. The agent never reaches Spaces. Add no package (the bench is shared): if the bench has no S3 client, write the Spaces store with the standard library or reply NEEDS_INPUT. The nightly schedule on production, 30 days in Spaces and the restore of a Pandya test site to staging are SOS-P1-14D, owned by AMP Labs. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P1-02
- **Status:** Not Started

### SOS-P1-14D: Turn on nightly backups to Spaces and prove a restore on staging
- **Epic:** Platform foundations and DevOps
- **Description:** As Jayman, I want every site backed up nightly to Spaces and a restore proven, so that no company's data is lost. The deploy half of SOS-P1-14: AMP Labs schedules SOS-P1-14's backup command on production with the Spaces store and proves its restore on staging.
- **Acceptance Criteria:**
  - A backup per site appears in Spaces each night.
  - Retention is 30 days.
  - The restore script recreates a site on staging.
- **Test Criteria:** Restore a Pandya test site on staging and compare record counts.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). AMP Labs work, so it is Waiting and the loop does not pick it. Owned outside the SellOS build (Jayman, 24 November 2026).
- **Owner:** AMP Labs
- **Priority:** P1
- **Launch:** Jan 1
- **Story Points:** 2
- **Dependencies:** SOS-P0-04, SOS-P0-06D, SOS-P1-14
- **Status:** Waiting

### SOS-P0-12: Set up monitoring and alerts
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want uptime, error and disk alerts, so that problems are noticed before users report them. Monitor each site hostname, error rates, disk use and backup success, and send alerts to named people.
- **Acceptance Criteria:**
  - An uptime check exists for every site.
  - Alerts fire on errors, disk above 80 percent and failed backups.
  - Alerts reach named people.
- **Test Criteria:** Stop a service on staging and receive an alert within 5 minutes.
- **Notes:** AMP Labs work, so it is Waiting and the loop does not pick it (Jayman, 10 November 2026). Dependency added by SOS-SETUP-33 (13 November 2026): the failed backup alert needs the nightly backups of SOS-P1-14D. Owned outside the SellOS build (Jayman, 24 November 2026).
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P0-04, SOS-P1-14D
- **Status:** Waiting

### SOS-P6-12: Run the restore, upgrade and load tests
- **Epic:** Platform foundations and DevOps
- **Description:** As Jayman, I want the platform proven under restore, upgrade and load, so that we can onboard other agencies safely. Run a full restore test, a rolling upgrade across 20 test sites, and a load test at an agreed number of concurrent users.
- **Acceptance Criteria:**
  - A restore timing run, a rolling upgrade run across a given number of tenant sites with a record count check before and after, and a load test written with the standard library each write their numbers to one report file.
  - The targets (restore time, number of sites, concurrent users, response times) are read from one settings file, so SOS-P6-12D sets the agreed numbers without a code change.
  - At small scale on the local bench (three tenant sites made from the tenant template, ten concurrent users against `sellos_test.localhost` on port 8004) each run completes and the report holds its numbers.
- **Test Criteria:** Backend tests that run each at the small scale above and check the report, and drop every tenant site they made.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). This task is the code, owned by Claude Code. The full run on staging with 20 sites and the agreed numbers is SOS-P6-12D. Add no package for the load test. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 9): the settings file starts with the agreed numbers: one site restored within 1 hour, 20 sites in the rolling upgrade, 50 concurrent users, 95 percent of list screens within 1 second. MUST for 1 January 2027 (Jayman, 27 November 2026).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P0-08, SOS-P1-14
- **Status:** Not Started


### SOS-FIX-LISTS: Small fixes to the Site visits, Call queue, Deals, Sellers and list screens
- **Epic:** Lists and screens
- **Description:** As an Agent, I want a few wrong or confusing things on the lists corrected, so that the screens read right. Small fixes only, no new design work.
- **Acceptance Criteria:**
  - Site visits show the project name, not the internal code (for example PRJ-00510).
  - The Call queue leaves out leads whose stage is Closed won or Closed lost, and the seeded stage and consent agree with each other.
  - Deals: the Status column shows the approval date only, with who approved in the tooltip; the partner names column has a little more width; the Commission cell has spacing between its labels and amounts; the demo row "Marine Crest 1201" is named like the others ("Flat 1201, Marine Crest, Thane"); and the "No" split pill has no dotted icon.
  - Sellers: the "Never" last activity values in the seed are spread out, not all the same.
  - Lists: the CI 1280 wide check names any list that still scrolls sideways; only what it names is fixed.
- **Test Criteria:** Backend tests that read back the Call queue filter, the seeded stage and consent, and the seed's names and last activity values; a Cypress spec of the Site visits project name and the Deals Status cell.
- **Notes:** Added by Jayman, 27 November 2026. Runs after the MUST list. Browser flows are added to `docs/regression/flows.md`, one line each.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P6-12
- **Status:** Not Started
- **Browser spec:** required
### SOS-P6-12D: Run the restore, upgrade and load tests on staging
- **Epic:** Platform foundations and DevOps
- **Description:** As Jayman, I want the platform proven under restore, upgrade and load, so that we can onboard other agencies safely. The deploy half of SOS-P6-12: run SOS-P6-12's scripts on staging, a full restore, a rolling upgrade across 20 test sites and a load test at 50 concurrent users.
- **Acceptance Criteria:**
  - One site is restored within 1 hour.
  - The upgrade across 20 sites loses no data.
  - With 50 concurrent users, 95 percent of list screens answer within 1 second.
- **Test Criteria:** A results report is stored, and every failure becomes an SOS-FIX task.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026), as SOS-P0-06L split building from deploying (`docs/DEV_STRATEGY.md` row 26). The agreed numbers are a question in `docs/BACKLOG_AUDIT.md`. Waiting, and the loop does not pick it. Decided by Jayman (SOS-SETUP-34, 13 November 2026, question 9): restore within 1 hour, 50 concurrent users, 95 percent of list screens within 1 second. Owned outside the SellOS build (Jayman, 24 November 2026).
- **Owner:** AMP Labs, Jayman
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P0-08D, SOS-P1-14D, SOS-P6-12
- **Status:** Waiting

### SOS-P6-13C: Record acceptance of the terms at sign up
- **Epic:** Launch readiness
- **Description:** As Jayman, I want every new company to accept the current terms of service, privacy policy and data processing terms at sign up, so that acceptance is on record. The code half of SOS-P6-13. The texts are held by version, and until counsel's texts arrive (SOS-P6-13) the versions hold placeholder text marked as a draft.
- **Acceptance Criteria:**
  - The sign up flow shows the current version of each of the three texts and cannot finish until they are accepted.
  - Acceptance is recorded with the user, the company, each text's version and the time, and is never edited.
  - A new version can be added without a code change, and sign ups after it record the new version.
- **Test Criteria:** A sign up test confirms that acceptance is recorded with the versions, and a Cypress check of the sign up step.
- **Notes:** Added by SOS-SETUP-33 (13 November 2026). Decided by Jayman, 24 November 2026: reads the texts, support details and status page link from the Legal and Support section (SOS-P6-18) at sign up; it now depends on SOS-P6-18. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 2
- **Dependencies:** SOS-P6-07, SOS-P6-18
- **Status:** Not Started
- **Browser spec:** required

### SOS-P5-10: Commission a security review
- **Epic:** Web app, roles and security
- **Description:** As Jayman, I want an independent security review, so that known risks are fixed before outside agencies join. Review API methods, roles, company isolation, file uploads, webhooks and secrets handling. Findings are rated, and all high findings are fixed before SOS-P6-14 onboards the first outside agency.
- **Acceptance Criteria:**
  - A written report is delivered.
  - Findings are rated.
  - Every high finding is fixed and re tested.
- **Test Criteria:** Each high finding has a regression test.
- **Notes:** AMP Labs work, so it is Waiting and the loop does not pick it (Jayman, 10 November 2026). Changed by SOS-SETUP-33 (13 November 2026): there are no phase gates any more, so "before Gate 6" now reads "before SOS-P6-14". Owned outside the SellOS build (Jayman, 24 November 2026).
- **Owner:** AMP Labs
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P1-05
- **Status:** Waiting

### SOS-P6-13: Prepare legal terms and the support process
- **Epic:** Launch readiness
- **Description:** As Jayman, I want legal terms and a support process, so that other agencies can be onboarded responsibly. Prepare the terms of service, privacy policy, data processing terms and a support process with a status page.
- **Acceptance Criteria:**
  - Counsel approves the terms, privacy policy and data processing terms.
  - They are shown and accepted at sign up (built by SOS-P6-13C).
  - A support channel and response targets exist.
  - A status page is live.
- **Test Criteria:** A sign up test confirms that acceptance is recorded.
- **Notes:** Split by SOS-SETUP-33 (13 November 2026): showing the terms and recording their acceptance at sign up is code, so it is SOS-P6-13C, owned by Claude Code. This task keeps counsel's approval, the support channel and the status page. Decided by Jayman, 24 November 2026: stays Waiting for Jayman to add the content in the Legal and Support section (SOS-P6-18).
- **Owner:** Jayman, Counsel
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P6-07
- **Status:** Waiting

### SOS-P6-18: Build the Legal and Support section for the Platform Admin
- **Epic:** Launch readiness
- **Description:** As the Platform Admin, I want one place on the control site to hold the legal texts and the support details, so that sign up shows the current terms and customers know how to get help. Build a Legal and Support section in the SellOS web app (control site, Platform Admin only).
- **Acceptance Criteria:**
  - The Platform Admin uploads versioned terms of service, privacy policy and data processing terms, each version with an effective date and its text or file; a version is never edited or deleted, and a new version is added instead.
  - The section holds the support channel (an address or link), the response targets (text per severity) and the status page link.
  - SOS-P6-13C reads the current version of each text, the support details and the status page link from here at sign up; nothing is hard coded.
  - Until Jayman adds the content, the section shows each text as a draft placeholder, as SOS-P6-13C expects.
  - Only the Platform Admin edits it; sign up reads the current versions.
- **Test Criteria:** Backend tests of versions, effective dates (the current version on a given date), that a version cannot be edited or deleted, the permission test for every role, and that SOS-P6-13C's read returns the current versions; a Cypress spec of adding a version and the support details.
- **Notes:** Decided by Jayman, 24 November 2026. SOS-P6-13 stays Waiting for Jayman (and counsel) to add the content; this task is only the place to put it. Expected flow (Jayman, 24 November 2026; the builder adds it to `docs/regression/flows.md` when building the feature, one `FLOW` line each, and does not add flows in advance): 1. As platform_admin, from `/sellos/control/legal`: Sign in. Add a new version of the terms of service with an effective date, then add the support channel, the response targets and the status page link. Expected: The new version is listed as the current one from its date, the earlier version is kept and cannot be edited, and the support details are saved. 2. As company_admin, from `/sellos/control/legal`: Sign in as the gate company admin and type the address of the section. Expected: The page says there is no access. Taken out of the loop by Jayman, 27 November 2026: Launch tier Later, so the loop does not pick it (Pandya is the only company at launch, and the product working as intended comes first).
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Later
- **Story Points:** 5
- **Dependencies:** SOS-P1-01
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-14: Onboard the first outside agency
- **Epic:** Launch readiness
- **Description:** As Jayman, I want one outside agency onboarded as a pilot, so that we prove the platform with a real customer. Onboard a friendly agency through the sign up flow, support them for two weeks, and record every issue.
- **Acceptance Criteria:**
  - The agency signs up and pays in live or agreed mode.
  - Their data is isolated from Pandya's.
  - Issues are logged and triaged.
  - No SOS-FIX task is open, and the flows of the sign up, billing and WhatsApp tasks were walked in a scheduled regression report with no open defect.
- **Test Criteria:** A cross company isolation check on live data, and a review of the issue log.
- **Notes:** Changed by SOS-SETUP-33 (13 November 2026): SOS-REG-6 is Not Needed, so its criterion now names the scheduled regressions. Dependencies added: the staging proof (SOS-P6-12D), the legal terms and their acceptance (SOS-P6-13, SOS-P6-13C), the approved prices (SOS-P6-02A), the live Razorpay check (SOS-P6-03L) and the approved invoices (SOS-P6-06A). Decided by Jayman, 24 November 2026: Parked (not selling yet, no outside agency until SOS-N14 is back). Its dependencies stay as they are. SOS-P6-02A stays Waiting for Jayman.
- **Owner:** Jayman
- **Priority:** P6
- **Launch:** none
- **Story Points:** 5
- **Dependencies:** SOS-P6-07, SOS-P6-12, SOS-P5-10, SOS-P6-12D, SOS-P6-13, SOS-P6-13C, SOS-P6-02A, SOS-P6-03L, SOS-P6-06A
- **Status:** Parked

### SOS-REG-A: Scheduled regression A (about 24 November)
- **Epic:** Regression
- **Description:** A scheduled regression pause on or about 24 November 2026, done by Claude in chat, not by the build loop. Regression is a scheduled pause, not a gate (Jayman, 10 November 2026): no task depends on this one. Run `scripts/pause-loop.sh`. The loop finishes the task it is on, then picks nothing, notifies "Paused for regression" and stops. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` of every Complete task in a real browser, and write the report to `docs/regression/reg-a.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. Then run `scripts/resume-loop.sh`, mark this task Complete with `scripts/set-task-status.sh SOS-REG-A Complete TASKS.md`, commit and push, and start the loop again.
- **Acceptance Criteria:**
  - A report exists at docs/regression/reg-a.md and walks every flow of every Complete task.
  - Every defect in it is an SOS-FIX task in TASKS.md.
  - `scripts/resume-loop.sh` has been run, so the pause file is gone.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P2
- **Launch:** Jan 1
- **Dependencies:** none
- **Status:** Waiting

### SOS-REG-B: Scheduled regression B (about 12 December)
- **Epic:** Regression
- **Description:** A scheduled regression pause on or about 12 December 2026, done by Claude in chat, not by the build loop. Regression is a scheduled pause, not a gate (Jayman, 10 November 2026): no task depends on this one. Run `scripts/pause-loop.sh`. The loop finishes the task it is on, then picks nothing, notifies "Paused for regression" and stops. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` of every Complete task in a real browser, and write the report to `docs/regression/reg-b.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. Then run `scripts/resume-loop.sh`, mark this task Complete with `scripts/set-task-status.sh SOS-REG-B Complete TASKS.md`, commit and push, and start the loop again.
- **Acceptance Criteria:**
  - A report exists at docs/regression/reg-b.md and walks every flow of every Complete task.
  - Every defect in it is an SOS-FIX task in TASKS.md.
  - `scripts/resume-loop.sh` has been run, so the pause file is gone.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P2
- **Launch:** Jan 1
- **Dependencies:** none
- **Status:** Waiting

### SOS-REG-C: Scheduled regression C (about 18 December)
- **Epic:** Regression
- **Description:** A scheduled regression pause on or about 18 December 2026, done by Claude in chat, not by the build loop. Regression is a scheduled pause, not a gate (Jayman, 10 November 2026): no task depends on this one. Run `scripts/pause-loop.sh`. The loop finishes the task it is on, then picks nothing, notifies "Paused for regression" and stops. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` of every Complete task in a real browser, and write the report to `docs/regression/reg-c.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. Then run `scripts/resume-loop.sh`, mark this task Complete with `scripts/set-task-status.sh SOS-REG-C Complete TASKS.md`, commit and push, and start the loop again.
- **Acceptance Criteria:**
  - A report exists at docs/regression/reg-c.md and walks every flow of every Complete task.
  - Every defect in it is an SOS-FIX task in TASKS.md.
  - `scripts/resume-loop.sh` has been run, so the pause file is gone.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P2
- **Launch:** Jan 1
- **Dependencies:** none
- **Status:** Waiting

### SOS-REG-L: Launch regression (about 29 December)
- **Epic:** Regression
- **Description:** The launch regression on or about 29 December 2026, done by Claude in chat, not by the build loop (Jayman, 10 November 2026). It depends on every other task that is not Not Needed or Parked, so it is the last task. Run `scripts/pause-loop.sh`, then `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` in a real browser, and write the report to `docs/regression/reg-l.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. Run `scripts/resume-loop.sh` so the loop can fix them, and run this regression again until it passes. Then mark it Complete with `scripts/set-task-status.sh SOS-REG-L Complete TASKS.md`, commit and push.
- **Acceptance Criteria:**
  - A report exists at docs/regression/reg-l.md with "Result: PASS".
  - No SOS-FIX task is open.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P6
- **Launch:** Jan 1
- **Dependencies:** SOS-N15, SOS-N21, SOS-N21A, SOS-P0-01, SOS-P0-02, SOS-P0-03, SOS-P0-04, SOS-P0-05, SOS-P0-06, SOS-P0-07, SOS-P0-06L, SOS-P0-08, SOS-P0-09, SOS-P0-12, SOS-P1-06A, SOS-P1-06B, SOS-P1-14, SOS-P6-12, SOS-P0-10, SOS-P1-04, SOS-P1-05, SOS-P1-13, SOS-P5-10, SOS-P0-11, SOS-P1-01, SOS-P1-02, SOS-P1-03, SOS-P1-11, SOS-P1-07, SOS-P1-08, SOS-P1-09, SOS-P1-10, SOS-P1-12, SOS-P2-01, SOS-P2-02, SOS-P2-03, SOS-P2-04, SOS-P2-05, SOS-P2-06, SOS-P2-07, SOS-P2-08, SOS-P2-09, SOS-P2-10, SOS-P2-11, SOS-P2-13, SOS-P2-14, SOS-P3-01, SOS-P3-02, SOS-P3-03, SOS-P3-04, SOS-P3-05, SOS-P3-06, SOS-P3-07, SOS-P3-08, SOS-P3-09, SOS-P3-10, SOS-P3-11, SOS-P3-12, SOS-P3-13, SOS-P4-01, SOS-P4-02, SOS-P4-03, SOS-P4-04, SOS-P4-05, SOS-P4-06, SOS-P4-07, SOS-P4-08, SOS-P4-09, SOS-P5-01, SOS-P5-02, SOS-P5-03, SOS-P5-04, SOS-P5-05, SOS-P5-06, SOS-P5-07, SOS-P5-08, SOS-P5-09, SOS-P6-01, SOS-P6-02, SOS-P6-03, SOS-P6-15, SOS-P6-04, SOS-P6-05, SOS-P6-06, SOS-P6-07, SOS-P6-08, SOS-P6-09, SOS-P6-10, SOS-P6-11, SOS-P6-16, SOS-P6-17, SOS-P6-13, SOS-REG-A, SOS-REG-B, SOS-REG-C, SOS-FIX-1, SOS-P0-05D, SOS-P0-06D, SOS-P0-08D, SOS-P1-14D, SOS-P6-12D, SOS-P2-02L, SOS-P3-01L, SOS-P3-04A, SOS-P3-10L, SOS-P4-10C, SOS-P5-07L, SOS-P5-09A, SOS-P6-02A, SOS-P6-06A, SOS-P6-10L, SOS-P6-11L, SOS-P6-13C, SOS-N22, SOS-N23, SOS-P0-13, SOS-P1-15, SOS-P1-16, SOS-P1-17, SOS-P1-18, SOS-P1-19, SOS-P1-20, SOS-P1-21, SOS-P1-22, SOS-P1-23, SOS-P1-24, SOS-P1-25, SOS-P1-26, SOS-P7-01, SOS-P7-02, SOS-P7-03, SOS-P7-04, SOS-P7-05, SOS-P7-06, SOS-P7-07, SOS-P7-08, SOS-P7-09, SOS-P7-10, SOS-P7-11, SOS-P7-12, SOS-P7-13, SOS-P7-14, SOS-UI-1, SOS-UI-2, SOS-UI-2B, SOS-UI-3A, SOS-UI-3B, SOS-UI-3C, SOS-UI-3D, SOS-P3-14, SOS-P3-15, SOS-P3-16, SOS-P3-17, SOS-P3-17L, SOS-P4-11, SOS-P4-12, SOS-P6-18, SOS-N21B, SOS-N21BL, SOS-N21C, SOS-N23V, SOS-P7-12L
- **Status:** Waiting

### SOS-N07: Counsel reviews the consent basis and calling script
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want counsel to review our consent basis, opt in route and calling script, so that we launch on a defensible footing. Counsel reviews the 7 day inquiry basis, the consent wording on forms, the inbound opt in route for bought leads and the Pandya script against the 2026 TRAI amendment, and confirms which calls may be placed from the 022 landline number.
- **Acceptance Criteria:**
  - A written opinion is received.
  - Required changes are listed with owners.
  - Approved consent wording is stored for the website and the app.
- **Test Criteria:** Verified by the signed opinion.
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch.
- **Owner:** Counsel
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 3
- **Dependencies:** none
- **Status:** Not Needed

### SOS-N09: Open the Plivo account for international calls
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want a Plivo account for international calls, so that calls to Australia and the UAE can be placed. Plivo requires a separate account, with a different email, for international calls.
- **Acceptance Criteria:**
  - The account is created with a small balance.
  - Australia and UAE routes work.
  - API credentials are generated and stored in the password manager.
- **Test Criteria:** One test call to an Australian mobile and one to a UAE mobile, with billing checked against Plivo's rate pages.
- **Notes:** Not Needed (Jayman, 10 November 2026). International calling is dropped.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 1
- **Dependencies:** none
- **Status:** Not Needed

### SOS-N10: Confirm Australia and UAE calling rules
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want local advice on Australian and UAE telemarketing and caller ID rules, so that the consent and cap rules for those calls are correct. These rules were not verified in earlier research. Australia has a Do Not Call Register and restricted hours, and the UAE has strict telemarketing and international route rules.
- **Acceptance Criteria:**
  - Written advice for each country.
  - Permitted hours, register checks and caller ID rules are listed.
  - The rules are added to the consent check specification.
- **Test Criteria:** Verified by the advice, then exercised by the calling hours tests in SOS-P2-10.
- **Notes:** Not Needed (Jayman, 10 November 2026). International calling is dropped.
- **Owner:** Counsel
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 3
- **Dependencies:** SOS-N09
- **Status:** Not Needed

### SOS-N11: Obtain quotes and licence terms for registration data
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want quotes and licence terms from Zapkey, Square Yards and CRE Matrix, so that we can choose a registration data source. Ask each for price, five years of Mumbai coverage, delivery by API or export, update frequency, and whether other agencies on SellOS may see the data.
- **Acceptance Criteria:**
  - Three written quotes.
  - Redistribution rights are stated for each.
  - A comparison note carries a recommendation.
- **Test Criteria:** Verified by the comparison note.
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Not Needed

### SOS-N13: Confirm the rules for storing buyer and seller names
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want counsel to confirm how buyer and seller names may be stored and used, so that the market data engine stays lawful. Index II names the parties. Counsel advises on storage, access, retention and use under the DPDP Act.
- **Acceptance Criteria:**
  - Written advice.
  - Rules for storage, access and retention.
  - The research only rule for names is confirmed or amended.
- **Test Criteria:** Verified by the advice, then applied in SOS-P3-12.
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch.
- **Owner:** Counsel
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Not Needed

### SOS-N17: Name the pull request reviewer and review rhythm
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want a named reviewer and rhythm for pull requests, so that reviews do not block the build. Name who reviews, how fast, and who reviews security sensitive changes.
- **Acceptance Criteria:**
  - Reviewer names are recorded.
  - A review turnaround is agreed.
  - A second reviewer from AMP Labs is named for security sensitive changes.
- **Test Criteria:** Checked in Sprint 1 against the turnaround on the first five pull requests.
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 1
- **Dependencies:** none
- **Status:** Not Needed

### SOS-N18: Decide the DigitalOcean region, sizes and budget
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want the hosting choices decided, so that servers can be provisioned. Choose the DigitalOcean region, droplet sizes for staging and production, and a monthly budget that includes backups.
- **Acceptance Criteria:**
  - A decision note is signed off.
  - The monthly budget is approved.
- **Test Criteria:** Compared with the first month's DigitalOcean bill.
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch. The region is DigitalOcean Bangalore (see SOS-P0-04).
- **Owner:** Jayman, AMP Labs
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Not Needed

### SOS-P0-01: Summarise the BuildOS conventions
- **Epic:** Platform foundations and DevOps
- **Description:** As Jayman, I want a written summary of BuildOS's structure, tooling, build process and frontend, so that SellOS replicates them. Claude Code reads the BuildOS source in the read only reference copy at `~/iespl-baseline/buildos-reference` and documents the repository layout, app structure, bench and deployment setup, continuous integration, frontend stack, testing approach and styling, then lists any change that Frappe 16 or SellOS needs.
- **Acceptance Criteria:**
  - The summary covers structure, tooling, build, frontend and tests.
  - Every point cites a BuildOS file or script.
  - Jayman approves it in writing.
- **Test Criteria:** Spot check five claims against the repository. Jayman's approval is the gate.
- **Notes:** SOS-SETUP-19: SOS-N16 is no longer a dependency (Jayman, 10 November 2026). Claude Code already has the access it needs to build. N16 stays Waiting for the DigitalOcean token. SOS-SETUP-21: read BuildOS code only in the read only reference copy at `~/iespl-baseline/buildos-reference`, with ls, cat, grep and find, and never write into it. Never read, list or run anything under `apps/buildos`. Cite each point by its path in the reference copy, which is the BuildOS path.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** none
- **Status:** Complete

### SOS-P0-02: Create the repositories
- **Epic:** Platform foundations and DevOps
- **Description:** As a developer, I want a repository for each app and a deployment repository, mirroring BuildOS, so that work is organised the same way. Create repositories for the platform, core, telephony, intelligence, inventory, reports, scraper and WhatsApp apps, the web app and the deployment configuration. Change to this story (Jayman): BuildOS is one Frappe app with subpackages, so no separate repositories are created. Instead the `sellos` app has empty subpackages `access`, `telephony`, `intel`, `inventory`, `reports`, `scraper`, `whatsapp` and `billing`, each with an `__init__.py` and a one line docstring. `frontend/` is unchanged. Criteria (2) staging install and (3) branch protection are not covered by this change and stay with SOS-P0-04 and SOS-P0-07.
- **Acceptance Criteria:**
  - All repositories exist with the BuildOS layout.
  - Each installs on the staging bench.
  - Branch protection requires a reviewed pull request.
- **Test Criteria:** Continuous integration is green on the empty skeletons, and a direct push to the main branch is rejected.
- **Notes:** SOS-SETUP-21: read BuildOS code only in the read only reference copy at `~/iespl-baseline/buildos-reference`, with ls, cat, grep and find, and never write into it. Never read, list or run anything under `apps/buildos`.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P0-01
- **Status:** Complete

### SOS-P0-03: Write a CLAUDE.md in every repository
- **Epic:** Platform foundations and DevOps
- **Description:** As Claude Code, I want a conventions file in every repository, so that each session starts with the rules. Write CLAUDE.md with Frappe 16 conventions, the role model, test commands, the link to the Build Plan and stop and ask rules. Change to this story (Jayman): SellOS is a single app repository, so "every repository" now means two files: the `CLAUDE.md` in the repository root and `frontend/CLAUDE.md`.
- **Acceptance Criteria:**
  - Every repository has the file.
  - It lists build, test and lint commands.
  - It states when Claude Code must stop and ask.
- **Test Criteria:** A fresh Claude Code session reads the file and completes a small change, such as adding a doctype, in line with the conventions.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 2
- **Dependencies:** SOS-P0-02
- **Status:** Complete

### SOS-P0-07: Set up continuous integration
- **Epic:** Platform foundations and DevOps
- **Description:** As a reviewer, I want automated checks on every pull request, so that broken changes cannot merge. Run lint, unit tests and the build in continuous integration, and block merging on failure.
- **Acceptance Criteria:**
  - The pipeline runs on every pull request.
  - A failing check blocks the merge.
  - Run time is reported.
- **Test Criteria:** A pull request with a failing test is blocked, and a passing one merges.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P0-02
- **Status:** Complete

### SOS-P0-06L: Multitenancy on the local bench
- **Epic:** Platform foundations and DevOps
- **Description:** The local half of SOS-P0-06, so that building does not wait for deployment. SOS-P0-06 (DNS multitenancy and nginx on staging) waits for SOS-N18 and is not changed. This task makes, tests and drops company sites on the local bench `~/iespl-bench`, one site and one database per company, with a narrow MariaDB account and never with root, and proves in the test process that two companies' data never mix. It does not change how sites are served. The SellOS server stays pinned to `sellos_test.localhost` on port 8004 (`cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`). A pinned server serves that one site for every host name, and `bench serve` without `--site` falls back to `default_site`, which on this bench is BuildOS's `test_site`, so `bench serve` is never run without `--site`. Serving several company sites from one server, chosen by host name, is production routing: it belongs to SOS-P0-08 and cannot be tested on this bench (decided by Jayman, 4 November 2026, SOS-SETUP-18).
- **Acceptance Criteria:**
  - Provisioner account, first: before anything else in this task, create `sellos_tenant_probe.localhost` (database `sellos_tenant_probe`) once and drop it once, using only the MariaDB provisioner account, and keep this as the first backend test. The account's name is in `SELLOS_DB_PROVISIONER_USER` (default `sellos_provisioner`). The password comes only from `get_provisioner_password()` in `sellos/provisioning/credentials.py` (the variable `SELLOS_DB_PROVISIONER_PASSWORD` if set, else the macOS Keychain item `sellos_provisioner`), which hands it to Frappe only through a child process's environment. Never run `security find-generic-password` with `-w`, and never print, log or write the password. If `get_provisioner_password()` raises, reply NEEDS_INPUT with its message. The account has `CREATE USER`, `RELOAD` and `SHOW DATABASES` globally, and `ALL PRIVILEGES ... WITH GRANT OPTION` on `` `sellos\_tenant\_%`.* `` only. Never use the MariaDB root account or any root password, and never ask for one. Use `scripts/tenant-site.sh probe` (or `sellos.provisioning.tenant_sites.probe()`). If Frappe's new-site or drop-site needs a privilege the account lacks, reply NEEDS_INPUT and name the exact privilege and the exact SQL statement that failed, with MariaDB's error code and message (they name the user and host, never the password).
  - Create and drop: every tenant site is created, dropped, listed and probed only through `sellos/provisioning/tenant_sites.py` or `scripts/tenant-site.sh` (create <id>, drop <id>, list, probe), added by SOS-SETUP-22. They run Frappe's own command entry (`python -m frappe.utils.bench_helper frappe new-site <site> --db-name <name> --db-root-username <user>`, then `drop-site <site> --db-root-username <user> --no-backup`) from `~/iespl-bench/sites`, never the `bench` wrapper, through a launcher that takes the password from its environment and adds it in memory, so it is never on a visible command line. A failure names only the site and the exit code. Review that code against this task, keep what passes and fix what is weak, keeping these rules.
  - Names: site names are `sellos_tenant_<id>.localhost` and database names are `sellos_tenant_<id>`, for the same `<id>`, where `<id>` matches `[a-z0-9]+` (SOS-SETUP-22), so `^sellos_tenant_[a-z0-9]+\.localhost$` and `^sellos_tenant_[a-z0-9]+$`, the database name at most 64 characters (MariaDB's limit). One function in the app (`sellos.provisioning.tenant_sites.names`) validates a tenant id and gives its site and database names, and every code path, test and script that creates, drops, migrates or otherwise touches a tenant site calls it before it runs anything, and refuses any other name. A test shows it refuses at least `test_site`, `dev_site`, `pamaa_test.localhost`, `sellos.localhost`, `sellos_test.localhost`, `sellos_tenant_A.localhost`, `sellos_tenant_a.localhost.evil`, `../sellos_tenant_a.localhost` and a name whose database name is longer than 64 characters. The gate refuses any other name too: `scripts/check_site_set.py` fails a run that touched another site or database of this bench, left a tenant site or database behind, or gave a tenant site a `db_name` that is not `sellos_tenant_<id>`.
  - Isolation, in process: make two tenant sites with the code above and give each different data. In the test process, switch to each site with `frappe.init(site=...)` and `frappe.connect()`, and show that each site sees only its own records, that a record written on one is not on the other, and that each site's `db_name` is its own `sellos_tenant_<id>`. Always switch back to `sellos_test.localhost` in a `finally` block, so the rest of the suite runs on the gate's site. Do not start a server for a tenant site and do not send HTTP requests to one. Over HTTP, test only the pinned `sellos_test.localhost` on port 8004.
  - Cleanup: every tenant site a test makes is dropped by the same validated code, its database included, even when the test fails, and dropping a name that is not allowed is refused before any command runs.
  - The password is never written: a test checks that, after a create and a drop, the password's value appears in no file under the repository, the tenant site folders, `~/iespl-bench/logs` or the gate's log folder. The gate checks the same at the end of every run (`scripts/check_no_secret_leak.py`).
  - Docs: a section in `docs/` and a line in CLAUDE.md "Working rules" say how tenant sites are made and dropped on this bench (the provisioner account, the name rules, the command), that the SellOS server stays pinned to `sellos_test.localhost` on 8004, that multitenancy is tested in process and not over HTTP, and that host name routing is SOS-P0-08's.
- **Test Criteria:** Backend tests for the probe create and drop with only the provisioner account, the name check, two tenant sites isolated from each other in process, cleanup, and the password never written. The gate's site and database check and its secret leak check pass.
- **Notes:** Do not change protected files (`scripts/lib/*`, `scripts/run-tests.sh`, `docs/DEV_STRATEGY.md` and the rest listed in `scripts/check_gate_files.py`). The deployment tasks SOS-P0-04, SOS-P0-05, SOS-P0-06, SOS-P0-08 and SOS-P0-12 wait for SOS-N18 and are not part of this task. Rewritten by SOS-SETUP-18: the narrow account replaces root, and the launcher that served several tenants from one server is dropped.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** none
- **Status:** Complete

### SOS-P0-09: Keep secrets out of repositories
- **Epic:** Platform foundations and DevOps
- **Description:** As Jayman, I want secrets kept out of repositories, so that keys are never exposed. Store keys in encrypted settings or environment variables, and add a scan that fails on committed secrets.
- **Acceptance Criteria:**
  - No key appears in any repository.
  - The scan runs in continuous integration and before commits.
- **Test Criteria:** Commit a fake key on a branch and confirm it is blocked.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 2
- **Dependencies:** SOS-P0-02
- **Status:** Complete

### SOS-P1-06A: CRM works on a fresh company site
- **Epic:** Core CRM and consent
- **Description:** Reopens SOS-P1-06, which was ticked while the CRM did not work in a browser. On 4 November 2026, on the SellOS test site, every CRM call answered 403, the Leads page showed "No leads yet", the page used placeholder colours and fonts, and the page named the site instead of the company, and the whole gate was green. This task makes the CRM work on a fresh company site, for the right roles, and makes the screens say so when it does not. The records, permissions and masking rules built in SOS-P1-06 stay as they are (see CLAUDE.md, "CRM data rules").
- **Acceptance Criteria:**
  - sellos.crm.api.list_leads and save_client work for the Company Admin and the Agent on a fresh site made by prepare_clean_site, and are refused with a clear message for the others, as the permission matrix says. Quote the code that refused every user, and fix its cause without weakening the guard.
  - sellos.tests.ui_fixtures: implement _configure_company_site (call the same code that provisioning uses), seed_agent_leads and seed_client_with_phone as their docstrings say.
  - The Leads screens show an error when a call fails and never "No leads yet". The form shows the server's message. Add the data-testid attributes that cypress/integration/smoke/app_shell.cy.js and cypress/integration/crm/leads_by_role.cy.js use.
  - Those two specs pass.
  - `cypress/integration/security/phone_masking_leaks.cy.js` is SOS-P1-06B's contract and stays skipped (`context.skip`, SOS-SETUP-16). The full Cypress suite is green with it skipped. Do not remove the skip or change that spec in this task.
  - The page uses the approved tokens (#0f4c35, #e8954a, Syne headings, DM Sans body, a filled --sos-brand-mid) and shows the company name, not the site name. Find what replaced the approved tokens and restore them. The browser tab shows a favicon: the company logo when SellOS Settings has one, otherwise a SellOS default icon. Today `frontend/index.html` and `sellos/www/sellos.html` set an empty `data:,` icon between the `tab-icons` comments.
- **Test Criteria:** Backend tests for the refusals and for both fixtures, and the two Cypress specs named above pass in the gate. A Cypress check that the tab icon is the company logo when SellOS Settings has one and the SellOS default icon when it has none, and never `data:,`.
- **Notes:** Where to start, all unconfirmed until reproduced. (1) The refusal text on the guard is "This method has no declared roles." from guard_api in sellos/access/registry.py, which runs as a before_request hook and looks a method up in _REGISTRY. The registry is filled when a module with @sellos_api is imported, and a fresh server process may not have imported sellos.crm.api when the first request arrives. Reproduce over HTTP against a running server, not only in a test process. (2) The docstring of _configure_company_site says a site type or company profile is checked by sellos.access, but no such check was found in sellos/access when this task was written. Find the real cause before using that wording. (3) The placeholder tokens are in frontend/src/theme/tokens.js (brand #1d4e5f, accent #c98a2b, Inter), written in P0.10 "until the product brand is chosen". The approved values are in this task. Record them in the tokens file and in docs, with --sos-brand-mid filled in. (4) sellos/spa.py get_company_branding returns the site name when SellOS Settings has no company name. FINDING (4 November 2026, measured over HTTP, hypothesis (1) confirmed): a freshly started server process (pinned to the site the same way as the SellOS server, `cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`; this measurement was taken on a spare port) answered the first `GET /api/method/sellos.crm.api.list_leads` as the test company admin (after logging in) with 403 `{"exc_type":"PermissionError"}`, and answered 403 again on the second, third and fourth call, after `/sellos` and `/api/resource/Lead` had been requested. Nothing in a server process imports `sellos.crm.api`: `sellos/access/matrix.py` only holds the method names as strings, and `guard_api` runs before Frappe imports the method. The same Frappe WSGI app started with `import sellos.crm.api` run first (a harness in the scratchpad, not in the repository) answered the same call with 200 `{"message":[]}`. In a Python process, `is_refused("sellos.crm.api.list_leads")` is True before the import and False after it. The code that refused every user is in `sellos/access/registry.py`: `_REGISTRY` is filled only as a side effect of importing a module that uses `@sellos_api` (`_REGISTRY[path] = allowed` inside `decorate`), `is_refused` returns `bool(method) and method.startswith(PREFIX) and method not in _REGISTRY`, and the before_request hook does `method = method_from_path(request.path) or request.values.get("cmd")`, then `if is_refused(method): raise frappe.PermissionError(frappe._("This method has no declared roles."))`. So a declared method is refused until its module has been imported, and a refused call never imports it. This is also why the tests passed: the test process imports the CRM module. The fix must make the registry complete at startup without weakening the guard: an undeclared method must still be denied. For example, import every module that holds API methods (the ones in `sellos/access/matrix.py`) when `sellos.access.registry` loads or in a hook that runs at startup, and add a test that starts from a process where `sellos.crm.api` was not imported. Hypothesis (2) stands: `_configure_company_site` has no cause in `sellos.access` to quote, because the refusal above is the only thing found that refuses every user.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-04
- **Status:** Complete
- **Browser spec:** required

### SOS-P1-06B: Phone numbers do not leak
- **Epic:** Core CRM and consent
- **Description:** Closes the personal data checks for the CRM records (docs/DEV_STRATEGY.md section 6). Agents and partners see masked phone numbers and only a Company Admin sees full numbers (CLAUDE.md, "CRM data rules"). The change history, the form loader and the generic Frappe read paths must not show a full number to a role that may not see it.
- **Acceptance Criteria:**
  - Remove the `context.skip` from cypress/integration/security/phone_masking_leaks.cy.js (and the comment above it that says SOS-P1-06B removes it), and make the spec pass as written. `scripts/check_no_stale_skips.py` fails this task's gate while the skip is there.
  - A backend test for the masking and the permission rules. Reuse the approach of buildos.security.field_history so the change history never shows a full number to a role that may not see it (read BuildOS's version first, at `~/iespl-baseline/buildos-reference/buildos/security/field_history.py`).
  - Showing a full number to a Company Admin is logged, or this task says which later task logs it.
- **Test Criteria:** The backend test and the leak spec pass in the gate, and the spec first shows that the agent can read the client on at least one path.
- **Notes:** SOS-SETUP-21: read BuildOS code only in the read only reference copy at `~/iespl-baseline/buildos-reference`, with ls, cat, grep and find, and never write into it. Never read, list or run anything under `apps/buildos`. BuildOS's `buildos/security/field_history.py` (in the reference copy) wraps frappe.desk.form.load.getdoc and get_docinfo through override_whitelisted_methods in hooks.py, and takes the changes to fields the reader may not read (permission level above their access) out of each Version row. The phone and overseas_phone fields are at permission level 1 here, so the same approach applies. Changing permissions, masking or personal data needs Jayman's approval, so reply NEEDS_INPUT if the approach has to change.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-06A
- **Status:** Complete
- **Browser spec:** required

### SOS-P0-10: Build the web app shell
- **Epic:** Web app, roles and security
- **Description:** As any user, I want to sign in to a SellOS app that shows the right screens for my role, so that I never need the Frappe desk. Build the shell of the custom web app in the BuildOS frontend stack: sign in and sign out, session expiry, role based navigation, a per company theme from settings, and a layout that works at phone width.
- **Acceptance Criteria:**
  - Sign in and sign out work for each of the five roles.
  - Navigation shows only what the role may use.
  - The company logo and colours load from settings.
  - The layout works at phone width.
  - The Frappe desk is blocked for customer roles.
- **Test Criteria:** End to end tests for sign in and navigation per role, a manual check on a phone, and a test that customer roles are redirected away from the desk.
- **Notes:** SOS-SETUP-21: read BuildOS code only in the read only reference copy at `~/iespl-baseline/buildos-reference`, with ls, cat, grep and find, and never write into it. Never read, list or run anything under `apps/buildos`.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P0-01
- **Status:** Complete
- **Browser spec:** required

### SOS-P1-04: Define the roles and permissions
- **Epic:** Web app, roles and security
- **Description:** As a Company Admin, I want each role to see and do only what it should, so that client and company data stays private. Define Platform Admin, Company Admin, Agent, Client and Channel Partner with their permissions, and list the whitelisted API methods each role may call. Methods not listed are denied. Agents see their own leads unless shared.
- **Acceptance Criteria:**
  - Five roles exist with a written permission table.
  - Every API method declares its allowed roles.
  - A method with no declaration is denied.
  - Agents cannot see other agents' leads unless shared.
- **Test Criteria:** Unit tests of the permission queries, and the full matrix in SOS-P1-05.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P0-10
- **Status:** Complete

### SOS-P1-05: Build the permission test suite
- **Epic:** Web app, roles and security
- **Description:** As Jayman, I want automated proof that roles and companies are isolated, so that a release can never leak data. Build a test matrix that calls every whitelisted method as every role and as a user from another company, and run it in continuous integration.
- **Acceptance Criteria:**
  - The matrix covers every whitelisted method and role.
  - No call returns data from another company.
  - A new method with no matrix entry fails the build.
- **Test Criteria:** Add a deliberately open method and confirm continuous integration fails.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P1-04
- **Status:** Complete

### SOS-P1-13: Build support access grants
- **Epic:** Web app, roles and security
- **Description:** As a Company Admin, I want to grant platform support time limited access, so that support can help without permanent access. Build a grant with an expiry that gives the Platform Admin read access to a company site, with every action logged. Decided at SOS-P1-06: the Platform Admin sees no company CRM data by role (`SEES_ALL` in `sellos/access/lead_permissions.py` excludes them), so this grant is the only way in. Support signs in remotely, and the grant expires automatically after 4 hours.
- **Acceptance Criteria:**
  - A Company Admin can grant access for a chosen duration, up to 4 hours.
  - Access ends automatically at expiry, at most 4 hours after it starts.
  - Every action is logged with user and time.
- **Test Criteria:** Grant access for 1 hour, confirm it works and then ends, and confirm the log entries exist.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-04
- **Status:** Complete
- **Browser spec:** required

### SOS-P0-11: Write the test site script
- **Epic:** Multitenancy and provisioning
- **Description:** As a developer, I want one command that creates a company site, so that testing and provisioning share one path. Write a script that creates a site, installs the SellOS apps, seeds a test admin and cleans up afterwards.
- **Acceptance Criteria:**
  - The script creates a working site from nothing.
  - It runs in an agreed time.
  - Cleanup removes the site fully.
- **Test Criteria:** Run it twice in a row and confirm both runs succeed.
- **Notes:** Depends on SOS-P0-06L (the local bench) instead of SOS-P0-06 (staging, after SOS-N18), changed by SOS-SETUP-17. The script makes only `sellos_tenant_<id>.localhost` sites, through SOS-P0-06L's name check. Sites are created and dropped only with `sellos.provisioning.tenant_sites` or `scripts/tenant-site.sh` and the MariaDB provisioner account (`SELLOS_DB_PROVISIONER_USER`, default `sellos_provisioner`), never with root. The password comes only from `get_provisioner_password()` in `sellos/provisioning/credentials.py` (the variable `SELLOS_DB_PROVISIONER_PASSWORD` if set, else the macOS Keychain item `sellos_provisioner`), which hands it to Frappe only through a child process's environment. Never run `security find-generic-password` with `-w`, and never print, log or write the password. If `get_provisioner_password()` raises, reply NEEDS_INPUT with its message. If the account lacks a privilege, reply NEEDS_INPUT and name the exact privilege and the exact SQL statement that failed.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P0-06L
- **Status:** Complete

### SOS-P1-01: Build the control site
- **Epic:** Multitenancy and provisioning
- **Description:** As a Platform Admin, I want a control site holding tenants and provisioning jobs, so that I can manage companies in one place. Build the control site with Tenant, a Plan stub and Provisioning Job records, with statuses requested, provisioning, active and failed.
- **Acceptance Criteria:**
  - A Platform Admin can create a tenant record.
  - Status changes follow the allowed order.
  - Company users cannot open the control site.
- **Test Criteria:** Unit tests for status transitions, and a permission test for company users.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P0-06L
- **Status:** Complete
- **Browser spec:** required

### SOS-P1-02: Build the provisioning worker
- **Epic:** Multitenancy and provisioning
- **Description:** As a Platform Admin, I want new companies provisioned automatically, so that no one runs server commands by hand. Build a worker, outside the web process, that picks up a Provisioning Job, creates the site, installs the apps, applies the plan limits and emails the admin.
- **Acceptance Criteria:**
  - A queued job creates a working site.
  - Failures retry, then mark the job failed with a log.
  - The web process has no shell access.
  - The admin receives a login email.
  - The worker creates and drops sites only with the MariaDB provisioner account, never with root, by calling `sellos.provisioning.tenant_sites.create` and `drop` (SOS-SETUP-22), which get the password from `get_provisioner_password()` and hand it to Frappe only through a child process's environment. Site names are `sellos_tenant_<id>.localhost` and database names `sellos_tenant_<id>`, checked by SOS-P0-06L's name function before any command runs. The values are never written to a file, a log, a job's error log, the repository or a test fixture.
- **Test Criteria:** Provision five tenants in sequence, kill the worker during a job and confirm it recovers, and confirm a failed job is visible.
- **Notes:** Sites are created and dropped only with `sellos.provisioning.tenant_sites` (SOS-SETUP-22) and the MariaDB provisioner account (`SELLOS_DB_PROVISIONER_USER`, default `sellos_provisioner`), never with root. The password comes only from `get_provisioner_password()` in `sellos/provisioning/credentials.py` (the variable `SELLOS_DB_PROVISIONER_PASSWORD` if set, else the macOS Keychain item `sellos_provisioner`), which hands it to Frappe only through a child process's environment. Never run `security find-generic-password` with `-w`, and never print, log or write the password. If `get_provisioner_password()` raises, reply NEEDS_INPUT with its message. If the account lacks a privilege, reply NEEDS_INPUT and name the exact privilege and the exact SQL statement that failed. On the local bench the worker makes only `sellos_tenant_<id>.localhost` sites with `sellos_tenant_<id>` databases, through SOS-P0-06L's name check. Changed by SOS-SETUP-18.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P1-01, SOS-P0-11
- **Status:** Complete

### SOS-P1-03: Build the setup wizard
- **Epic:** Multitenancy and provisioning
- **Description:** As a Company Admin, I want a guided setup, so that my company is ready to use in minutes. Build the wizard for company profile, logo and colours, pipeline stages with defaults, and first users and roles, following the BuildOS pattern.
- **Acceptance Criteria:**
  - The wizard collects all four areas.
  - It can be resumed if left.
  - The branding shows in the app after completion.
- **Test Criteria:** An end to end test completes the wizard and checks the result.
- **Notes:** SOS-SETUP-21: read BuildOS code only in the read only reference copy at `~/iespl-baseline/buildos-reference`, with ls, cat, grep and find, and never write into it. Never read, list or run anything under `apps/buildos`.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P1-02
- **Status:** Complete
- **Browser spec:** required

### SOS-P1-08: Build the Consent Record
- **Epic:** Core CRM and consent
- **Description:** As Jayman, I want every lead to carry its consent status, so that whoever contacts a lead sees its lawful basis or the lack of one. Build the Consent Record with lead, basis (consent, inquiry or application), timestamp, evidence link and expiry. An inquiry basis expires after 7 days and an application after 3 months. Each lead has a consent status: Consented (a live Consent Record), Unknown (no live record, including an expired one), Opted out (an explicit stop request) or Registered DND (when a do not call result is known for the number). Consent never blocks (Jayman, 10 November 2026). The status is recorded and shown as a warning on the lead, the caller queue and the call log, and never prevents a call or an SMS. A WhatsApp STOP stops everything sent unprompted, with one confirmation reply, an advisor task and a consent log entry, and the person can still write to us and get replies (Jayman, 24 November 2026).
- **Acceptance Criteria:**
  - Each basis requires an evidence link, and a Consent Record without one is refused.
  - Expiry dates are set by basis.
  - Renewals are logged.
  - An expired record returns the lead's consent status to Unknown automatically.
  - An explicit stop request is recorded as Opted out, with its time and source, and shows a red warning. It does not block a call or an SMS; a WhatsApp STOP stops everything sent unprompted, with one confirmation reply, an advisor task and a consent log entry, and the person can still write to us and get replies (Jayman, 24 November 2026).
  - Registered DND is set when a do not call result is known for the number, and shows an amber warning.
  - The lead screen shows the consent status: an amber warning for Unknown and Registered DND, a red warning for Opted out, and no warning for Consented.
- **Test Criteria:** Time shifted tests for each expiry, a test that a record without evidence is refused, a test that a stop request is recorded as Opted out and blocks no call or SMS (a WhatsApp STOP stops what is sent unprompted, as SOS-P6-11 tests), and a Cypress check of the warning on the lead screen for each status.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-06B
- **Status:** Complete
- **Browser spec:** required

### SOS-P2-12: Enforce the UAE call cap
- **Epic:** Calling
- **Description:** As Jayman, I want UAE calls capped, so that cost stays controlled. Add a monthly cap that defaults to 20 calls, resets each month and can be changed by a Company Admin.
- **Acceptance Criteria:**
  - The 21st call in a month is blocked with a message.
  - The counter resets monthly.
  - Admins can change the cap.
- **Test Criteria:** Simulate 21 calls and confirm the last is blocked.
- **Notes:** Not Needed (Jayman, 10 November 2026). International calling is dropped.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** none (Not Needed)
- **Story Points:** 2
- **Dependencies:** SOS-P2-03
- **Status:** Not Needed
- **Browser spec:** required

### SOS-REG-0: Regression 0, Foundations
- **Epic:** Regression
- **Description:** Clickthrough regression milestone, done by Claude in chat, not by the build loop. It covers the app shell: sign in as each of the five roles, the home page, the navigation and the no access page. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` for the tasks it depends on in a real browser, and write the report to `docs/regression/reg-0.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. The milestone is marked Complete by hand with `scripts/set-task-status.sh SOS-REG-0 Complete TASKS.md`, then committed and pushed.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026): replaced by the scheduled regression pauses SOS-REG-A, SOS-REG-B, SOS-REG-C and SOS-REG-L.
  - A report exists at docs/regression/reg-0.md with "Result: PASS".
  - No SOS-FIX task is open.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Dependencies:** SOS-P0-10
- **Status:** Not Needed

### SOS-REG-1: Regression 1, Tenancy and core CRM
- **Epic:** Regression
- **Description:** Clickthrough regression milestone, done by Claude in chat, not by the build loop. It covers the CRM screens, the control site, the setup wizard, the buyer pipeline, the Consent Record and support access. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` for the tasks it depends on in a real browser, and write the report to `docs/regression/reg-1.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. The milestone is marked Complete by hand with `scripts/set-task-status.sh SOS-REG-1 Complete TASKS.md`, then committed and pushed.
- **Acceptance Criteria:**
  - A report exists at docs/regression/reg-1.md with "Result: PASS".
  - No SOS-FIX task is open.
- **Notes:** Checked by SOS-SETUP-17 on 4 November 2026, with SOS-P0-11 and SOS-P1-01 depending on SOS-P0-06L. "Phase 1 is finished" for this milestone means the tasks above and everything they depend on are Complete. SOS-P1-09, SOS-P1-10, SOS-P1-11 and SOS-P1-14 are not required, directly or through another task. SOS-P1-02 is required: this milestone depends on SOS-P1-03, and SOS-P1-03 depends on SOS-P1-02, so the provisioning worker must be Complete first. Through them it also needs SOS-P0-11 and SOS-P0-06L, and SOS-REG-0. It does not need SOS-P0-04, SOS-P0-05, SOS-P0-06, SOS-P0-08, SOS-P0-12 or SOS-N18. Phase 2 tasks depend on this milestone, so SOS-P1-09, SOS-P1-10, SOS-P1-11 and SOS-P1-14 may still be open when Phase 2 starts. Not Needed (Jayman, 10 November 2026): replaced by the scheduled regression pauses SOS-REG-A, SOS-REG-B, SOS-REG-C and SOS-REG-L.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P1
- **Launch:** none (Not Needed)
- **Dependencies:** SOS-P1-06A, SOS-P1-06B, SOS-P1-13, SOS-P1-01, SOS-P1-03, SOS-P1-07, SOS-P1-08, SOS-P1-12
- **Status:** Not Needed

### SOS-REG-2B: Regression 2B, Click to call checkpoint
- **Epic:** Regression
- **Description:** Clickthrough regression milestone, done by Claude in chat, not by the build loop. It covers telephony settings and click to call, before the rest of Phase 2 is built on them. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` for the tasks it depends on in a real browser, and write the report to `docs/regression/reg-2b.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. The milestone is marked Complete by hand with `scripts/set-task-status.sh SOS-REG-2B Complete TASKS.md`, then committed and pushed.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026): replaced by the scheduled regression pauses SOS-REG-A, SOS-REG-B, SOS-REG-C and SOS-REG-L.
  - A report exists at docs/regression/reg-2b.md with "Result: PASS".
  - No SOS-FIX task is open.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P2
- **Launch:** none (Not Needed)
- **Dependencies:** SOS-P2-01, SOS-P2-07
- **Status:** Not Needed

### SOS-REG-2: Regression 2, Calling
- **Epic:** Regression
- **Description:** Clickthrough regression milestone, done by Claude in chat, not by the build loop. It covers the whole calling area: click to call, the inbound opt in route, the caller queue, calling hours, call reports and the UAE cap. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` for the tasks it depends on in a real browser, and write the report to `docs/regression/reg-2.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. The milestone is marked Complete by hand with `scripts/set-task-status.sh SOS-REG-2 Complete TASKS.md`, then committed and pushed.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026): replaced by the scheduled regression pauses SOS-REG-A, SOS-REG-B, SOS-REG-C and SOS-REG-L.
  - A report exists at docs/regression/reg-2.md with "Result: PASS".
  - No SOS-FIX task is open.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P2
- **Launch:** none (Not Needed)
- **Dependencies:** SOS-P2-01, SOS-P2-07, SOS-P2-08, SOS-P2-09, SOS-P2-10, SOS-P2-11, SOS-P2-12
- **Status:** Not Needed

### SOS-REG-3: Regression 3, Market intelligence
- **Epic:** Regression
- **Description:** Clickthrough regression milestone, done by Claude in chat, not by the build loop. It covers comparables, valuation, the agent assistant, watched building alerts and the party name rules. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` for the tasks it depends on in a real browser, and write the report to `docs/regression/reg-3.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. The milestone is marked Complete by hand with `scripts/set-task-status.sh SOS-REG-3 Complete TASKS.md`, then committed and pushed.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026): replaced by the scheduled regression pauses SOS-REG-A, SOS-REG-B, SOS-REG-C and SOS-REG-L.
  - A report exists at docs/regression/reg-3.md with "Result: PASS".
  - No SOS-FIX task is open.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P3
- **Launch:** none (Not Needed)
- **Dependencies:** SOS-P3-08, SOS-P3-09, SOS-P3-10, SOS-P3-11, SOS-P3-12
- **Status:** Not Needed

### SOS-REG-4: Regression 4, Inventory and mandates
- **Epic:** Regression
- **Description:** Clickthrough regression milestone, done by Claude in chat, not by the build loop. It covers developers, projects, units, listings, media, the seller pipeline, mandates and deals. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` for the tasks it depends on in a real browser, and write the report to `docs/regression/reg-4.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. The milestone is marked Complete by hand with `scripts/set-task-status.sh SOS-REG-4 Complete TASKS.md`, then committed and pushed.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026): replaced by the scheduled regression pauses SOS-REG-A, SOS-REG-B, SOS-REG-C and SOS-REG-L.
  - A report exists at docs/regression/reg-4.md with "Result: PASS".
  - No SOS-FIX task is open.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P4
- **Launch:** none (Not Needed)
- **Dependencies:** SOS-P4-01, SOS-P4-02, SOS-P4-03, SOS-P4-04, SOS-P4-05, SOS-P4-06, SOS-P4-07
- **Status:** Not Needed

### SOS-REG-5: Regression 5, Reports and portals
- **Epic:** Regression
- **Description:** Clickthrough regression milestone, done by Claude in chat, not by the build loop. It covers the report engine, the agent and Company Admin reports, saved views and export, and the client and partner views. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` for the tasks it depends on in a real browser, and write the report to `docs/regression/reg-5.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. The milestone is marked Complete by hand with `scripts/set-task-status.sh SOS-REG-5 Complete TASKS.md`, then committed and pushed.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026): replaced by the scheduled regression pauses SOS-REG-A, SOS-REG-B, SOS-REG-C and SOS-REG-L.
  - A report exists at docs/regression/reg-5.md with "Result: PASS".
  - No SOS-FIX task is open.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P5
- **Launch:** none (Not Needed)
- **Dependencies:** SOS-P5-01, SOS-P5-02, SOS-P5-03, SOS-P5-04, SOS-P5-05, SOS-P5-06
- **Status:** Not Needed

### SOS-REG-6: Regression 6, Billing and integrations
- **Epic:** Regression
- **Description:** Clickthrough regression milestone, done by Claude in chat, not by the build loop. It covers coupons, invoices, self service sign up, the listing scraper, the Facebook capture assist and the WhatsApp channel. Run `scripts/prepare-regression.sh`, walk every flow in `docs/regression/flows.md` for the tasks it depends on in a real browser, and write the report to `docs/regression/reg-6.md` in the format of `docs/regression/README.md`. Every defect becomes an SOS-FIX task. The milestone is marked Complete by hand with `scripts/set-task-status.sh SOS-REG-6 Complete TASKS.md`, then committed and pushed.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026): replaced by the scheduled regression pauses SOS-REG-A, SOS-REG-B, SOS-REG-C and SOS-REG-L.
  - A report exists at docs/regression/reg-6.md with "Result: PASS".
  - No SOS-FIX task is open.
- **Owner:** Claude in chat, clickthrough regression
- **Priority:** P6
- **Launch:** none (Not Needed)
- **Dependencies:** SOS-P6-05, SOS-P6-06, SOS-P6-07, SOS-P6-08, SOS-P6-10, SOS-P6-11
- **Status:** Not Needed

### SOS-N02: Get written confirmation on the Mira Road registration
- **Epic:** Parked (Tata DLT and 140 series route)
- **Description:** Ask Plivo support whether a Telemarketer registered in Mira Road is accepted for 140 series numbers, quoting the registered address. Done when a written answer is saved and, if the answer is no, the fallback route is recorded.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch.
  - Done when a written answer is saved and, if the answer is no, the fallback route is recorded.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 1
- **Dependencies:** none
- **Status:** Not Needed

### SOS-N03: Confirm Principal Entity registration for a non Pvt Ltd business
- **Epic:** Parked (Tata DLT and 140 series route)
- **Description:** Ask Tata DLT whether Pandya Realtors, which has no company identification number, can register as Principal Entity and which documents it needs. Done when a written answer is saved and the document list is recorded.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch.
  - Done when a written answer is saved and the document list is recorded.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 1
- **Dependencies:** none
- **Status:** Not Needed

### SOS-N04: Register on Tata DLT as Telemarketer and Principal Entity
- **Epic:** Parked (Tata DLT and 140 series route)
- **Description:** Register The AMP Labs as Telemarketer and Pandya Realtors as Principal Entity on the Tata DLT portal with GST certificates. Done when both certificates and IDs are received and stored, and each entity can log in with an approved status.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch.
  - Done when both certificates and IDs are received and stored, and each entity can log in with an approved status.
- **Owner:** Jayman, AMP Labs
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 3
- **Dependencies:** SOS-N02, SOS-N03
- **Status:** Not Needed

### SOS-N05: Obtain the 140 series number and NOC from Plivo
- **Epic:** Parked (Tata DLT and 140 series route)
- **Description:** Complete the Aggregator Telemarketer Declaration with PAN, CIN, address and the DLT Telemarketer ID, sign it with the company seal and send it to Plivo support. Done when Plivo allocates a 140 series number and issues the NOC.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch.
  - Done when Plivo allocates a 140 series number and issues the NOC.
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 2
- **Dependencies:** SOS-N04
- **Status:** Not Needed

### SOS-N06: Get the voice header and template approved
- **Epic:** Parked (Tata DLT and 140 series route)
- **Description:** The Telemarketer submits the voice header with the NOC, the Principal Entity approves it with the GST certificate, and a promotional voice template is registered. Done when both approvals arrive and a test promotional call from the 140 number completes to a consented test phone.
- **Acceptance Criteria:**
- **Notes:** Not Needed (Jayman, 10 November 2026). Not needed for launch.
  - Done when both approvals arrive and a test promotional call from the 140 number completes to a consented test phone.
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** none (Not Needed)
- **Story Points:** 3
- **Dependencies:** SOS-N05
- **Status:** Not Needed

### SOS-N08: Confirm SMS to a bought list and register the SMS header
- **Epic:** Parked (Tata DLT and 140 series route)
- **Description:** Confirm with Tata DLT or counsel whether promotional SMS to bought numbers is allowed. If it is, register an SMS header and a template carrying the missed call number and the enquiry page link. Done when a written yes or no is received and, if yes, the header and template are approved.
- **Acceptance Criteria:**
  - Done when a written yes or no is received and, if yes, the header and template are approved.
- **Owner:** Jayman, Counsel
- **Priority:** P0
- **Launch:** none (Parked)
- **Story Points:** 3
- **Dependencies:** SOS-N04
- **Status:** Parked
