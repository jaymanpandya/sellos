# SellOS Tasks

This file is the working backlog for building SellOS. It was generated from the Product backlog in the SellOS Build Plan on 4 November 2026.

There are 107 stories worth 523 points. Six stories (13 points) are parked, which leaves 101 active stories and 510 active points.

## Done so far

* The Plivo account is created and its KYC is approved.
* The Indian number +91 22 6998 6373 is bought. It is a 022 landline series number, so it is for service and transactional calls only.
* Decisions already made: Frappe 16.x without ERPNext, DigitalOcean for DNS and servers, a custom web app for every role, one Frappe site per company at a subdomain of sellos.interactivesoftwares.com, Razorpay for India and Stripe for international billing, and the Bandra to Andheri corridor for the first five years of market data.
* Claude Code builds. Jayman reviews the commits on 1.0.

## Rules for Claude Code

1. Work one story at a time, in dependency order. A story is ready only when every story in its Depends on list is ticked.
2. Read the CLAUDE.md in the repository first. After P0.01 is approved, also read the BuildOS conventions summary and follow it.
3. Write the tests named in Test criteria with the code. A story is not done until they pass in continuous integration.
4. Make one commit per story on 1.0, with the story ID at the start of the message. Push after `pre-commit run --all-files` passes. Do not open pull requests, and never force push.
5. Tick the story's checkbox and change its Status in the same commit that completes it, after the acceptance criteria have been shown on staging.
6. Stop and ask Jayman when a story needs a secret or account you do not have, when an acceptance criterion is ambiguous, when a change touches permissions or the consent check, or when a dependency is blocked.
7. Never add an override to the consent check. Never build captcha solving or any bypass of access controls. Never commit a secret.
8. Calls placed from the 022 number are service or transactional only. The system must refuse a promotional call purpose.
9. Stories owned by Jayman, AMP Labs, Counsel or the Accountant are not yours to do. Prepare drafts and checklists for them and flag what is waiting.
10. Customers never use the Frappe desk. Every customer feature goes into the SellOS web app.

## Status values

not started, in progress, blocked, done, parked.

## Definition of ready

A story is ready when it has a description, acceptance criteria, test criteria, points, an owner and no unmet dependency.

## Definition of done

1. The code is merged through a reviewed pull request.
2. Automated tests pass in continuous integration, including the permission tests for any new API method.
3. The change is deployed to staging and each acceptance criterion is demonstrated.
4. No secret is in the repository.
5. The CLAUDE.md file and the deployment notes are updated.
6. For compliance stories, written evidence is stored and the owner has signed off.

## Estimation

Points use the scale 1, 2, 3, 5, 8 and 13. A point measures complexity, risk and review effort, not hours. Any story that reaches 13 must be split before it enters a sprint. Velocity is measured over Sprints 1 and 2, and the sprint plan is then re baselined.

## Epics

* E1 Compliance, procurement and access: 11 active stories, 22 active points. Starts in week 1.
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
* Parked: 6 stories, 13 points, listed at the end of this file.

## Start here

These can start now, in this order:

1. N16 Give Claude Code the access it needs (Jayman). Nothing else in Phase 0 can start without it.
2. N17 Name the pull request reviewer and review rhythm (Jayman).
3. N18 Decide the DigitalOcean region, sizes and budget (Jayman, AMP Labs). P0.04 waits on it.
4. P0.01 Summarise the BuildOS conventions (Claude Code), as soon as N16 is ticked.
5. In parallel, owners can begin N07, N11, N12, N13 and N14.


# E1 Compliance, procurement and access

Goal: clear every registration, licence and account that gates engineering. These enabler stories start in week 1 and mostly belong to Jayman, counsel and the accountant. Active stories total 22 points.

## N07 Counsel reviews the consent basis and calling script

* [ ] **N07** · Points 3 · Owner Counsel · Depends on none · Status not started

**Story.** As Jayman, I want counsel to review our consent basis, opt in route and calling script, so that we launch on a defensible footing.

**Description.** Counsel reviews the 7 day inquiry basis, the consent wording on forms, the inbound opt in route for bought leads and the Pandya script against the 2026 TRAI amendment, and confirms which calls may be placed from the 022 landline number.

**Acceptance criteria.** (1) A written opinion is received. (2) Required changes are listed with owners. (3) Approved consent wording is stored for the website and the app.

**Test criteria.** Verified by the signed opinion.

## N09 Open the Plivo account for international calls

* [ ] **N09** · Points 1 · Owner Jayman · Depends on none · Status not started

**Story.** As Jayman, I want a Plivo account for international calls, so that calls to Australia and the UAE can be placed.

**Description.** Plivo requires a separate account, with a different email, for international calls.

**Acceptance criteria.** (1) The account is created with a small balance. (2) Australia and UAE routes work. (3) API credentials are generated and stored in the password manager.

**Test criteria.** One test call to an Australian mobile and one to a UAE mobile, with billing checked against Plivo's rate pages.

## N10 Confirm Australia and UAE calling rules

* [ ] **N10** · Points 3 · Owner Counsel · Depends on N09 · Status not started

**Story.** As Jayman, I want local advice on Australian and UAE telemarketing and caller ID rules, so that the consent and cap rules for those calls are correct.

**Description.** These rules were not verified in earlier research. Australia has a Do Not Call Register and restricted hours, and the UAE has strict telemarketing and international route rules.

**Acceptance criteria.** (1) Written advice for each country. (2) Permitted hours, register checks and caller ID rules are listed. (3) The rules are added to the consent check specification.

**Test criteria.** Verified by the advice, then exercised by the calling hours tests in P2.10.

## N11 Obtain quotes and licence terms for registration data

* [ ] **N11** · Points 2 · Owner Jayman · Depends on none · Status not started

**Story.** As Jayman, I want quotes and licence terms from Zapkey, Square Yards and CRE Matrix, so that we can choose a registration data source.

**Description.** Ask each for price, five years of Mumbai coverage, delivery by API or export, update frequency, and whether other agencies on SellOS may see the data.

**Acceptance criteria.** (1) Three written quotes. (2) Redistribution rights are stated for each. (3) A comparison note carries a recommendation.

**Test criteria.** Verified by the comparison note.

## N12 Request bulk or API access from the Department of Registration and Stamps

* [ ] **N12** · Points 2 · Owner Jayman, Counsel · Depends on none · Status not started

**Story.** As Jayman, I want a formal request sent to the Department of Registration and Stamps, so that we know whether bulk or API access exists.

**Description.** Ask about bulk data, API access and licence terms. The outcome is uncertain, so this runs beside N11.

**Acceptance criteria.** (1) The request is sent and acknowledged. (2) The reply, or the absence of one after 30 days, is recorded.

**Test criteria.** Verified by the acknowledgement.

## N13 Confirm the rules for storing buyer and seller names

* [ ] **N13** · Points 2 · Owner Counsel · Depends on none · Status not started

**Story.** As Jayman, I want counsel to confirm how buyer and seller names may be stored and used, so that the market data engine stays lawful.

**Description.** Index II names the parties. Counsel advises on storage, access, retention and use under the DPDP Act.

**Acceptance criteria.** (1) Written advice. (2) Rules for storage, access and retention. (3) The research only rule for names is confirmed or amended.

**Test criteria.** Verified by the advice, then applied in P3.12.

## N14 Open Razorpay and Stripe accounts

* [ ] **N14** · Points 2 · Owner Jayman, Accountant · Depends on none · Status not started

**Story.** As Jayman, I want Razorpay and Stripe accounts with test keys, so that billing can be built in test mode.

**Description.** Open both accounts, complete their business verification, and generate test keys.

**Acceptance criteria.** (1) The Razorpay account is active with test keys. (2) The Stripe account is active with test keys. (3) Keys are stored in the password manager, never shared in chat or email.

**Test criteria.** Create one test subscription in each dashboard.

## N15 Confirm the GST invoice format

* [ ] **N15** · Points 2 · Owner Accountant · Depends on N14 · Status not started

**Story.** As the Accountant, I want to confirm the GST invoice format for SaaS subscriptions, so that invoices are compliant.

**Description.** Confirm invoice fields, GST treatment for Indian and overseas customers, numbering, and credit note rules.

**Acceptance criteria.** (1) A written format specification. (2) Examples for an Indian customer and an overseas customer.

**Test criteria.** The accountant approves a sample invoice produced by P6.06.

## N16 Give Claude Code the access it needs

* [ ] **N16** · Points 2 · Owner Jayman · Depends on none · Status not started

**Story.** As Jayman, I want Claude Code to have the access it needs, so that Phase 0 can start.

**Description.** Grant read access to the BuildOS repository, create a SellOS GitHub organisation with Claude Code access, and create a scoped DigitalOcean token.

**Acceptance criteria.** (1) Claude Code can read BuildOS. (2) Claude Code can create repositories and branches in the SellOS organisation. (3) The token covers only the staging and production projects, with no billing or account level rights.

**Test criteria.** (1) Claude Code lists BuildOS files and creates a test branch. (2) A call using the token to delete the account is refused.

## N17 Name the pull request reviewer and review rhythm

* [ ] **N17** · Points 1 · Owner Jayman · Depends on none · Status not started

**Story.** As Jayman, I want a named reviewer and rhythm for pull requests, so that reviews do not block the build.

**Description.** Name who reviews, how fast, and who reviews security sensitive changes.

**Acceptance criteria.** (1) Reviewer names are recorded. (2) A review turnaround is agreed. (3) A second reviewer from AMP Labs is named for security sensitive changes.

**Test criteria.** Checked in Sprint 1 against the turnaround on the first five pull requests.

## N18 Decide the DigitalOcean region, sizes and budget

* [ ] **N18** · Points 2 · Owner Jayman, AMP Labs · Depends on none · Status not started

**Story.** As Jayman, I want the hosting choices decided, so that servers can be provisioned.

**Description.** Choose the DigitalOcean region, droplet sizes for staging and production, and a monthly budget that includes backups.

**Acceptance criteria.** (1) A decision note is signed off. (2) The monthly budget is approved.

**Test criteria.** Compared with the first month's DigitalOcean bill.

# E2 Platform foundations and DevOps

Goal: a reproducible Frappe 16 platform on DigitalOcean with continuous integration, scripted deployment, backups and monitoring. It totals 49 points across Phases 0, 1 and 6.

## P0.01 Summarise the BuildOS conventions

* [x] **P0.01** · Points 5 · Owner Claude Code · Depends on N16 · Status done

**Story.** As Jayman, I want a written summary of BuildOS's structure, tooling, build process and frontend, so that SellOS replicates them.

**Description.** Claude Code reads the BuildOS repository and documents the repository layout, app structure, bench and deployment setup, continuous integration, frontend stack, testing approach and styling, then lists any change that Frappe 16 or SellOS needs.

**Acceptance criteria.** (1) The summary covers structure, tooling, build, frontend and tests. (2) Every point cites a BuildOS file or script. (3) Jayman approves it in writing.

**Test criteria.** Spot check five claims against the repository. Jayman's approval is the gate.

## P0.02 Create the repositories

* [x] **P0.02** · Points 3 · Owner Claude Code · Depends on P0.01 · Status done

**Story.** As a developer, I want a repository for each app and a deployment repository, mirroring BuildOS, so that work is organised the same way.

**Description.** Create repositories for the platform, core, telephony, intelligence, inventory, reports, scraper and WhatsApp apps, the web app and the deployment configuration.

**Acceptance criteria.** (1) All repositories exist with the BuildOS layout. (2) Each installs on the staging bench. (3) Branch protection requires a reviewed pull request.

**Test criteria.** Continuous integration is green on the empty skeletons, and a direct push to the main branch is rejected.

**Change to this story (Jayman).** BuildOS is one Frappe app with subpackages, so no separate repositories are created. Instead the `sellos` app has empty subpackages `access`, `telephony`, `intel`, `inventory`, `reports`, `scraper`, `whatsapp` and `billing`, each with an `__init__.py` and a one line docstring. `frontend/` is unchanged. Criteria (2) staging install and (3) branch protection are not covered by this change and stay with P0.04 and P0.07.

## P0.03 Write a CLAUDE.md in every repository

* [x] **P0.03** · Points 2 · Owner Claude Code · Depends on P0.02 · Status done

**Story.** As Claude Code, I want a conventions file in every repository, so that each session starts with the rules.

**Description.** Write CLAUDE.md with Frappe 16 conventions, the role model, test commands, the link to the Build Plan and stop and ask rules.

**Acceptance criteria.** (1) Every repository has the file. (2) It lists build, test and lint commands. (3) It states when Claude Code must stop and ask.

**Test criteria.** A fresh Claude Code session reads the file and completes a small change, such as adding a doctype, in line with the conventions.

**Change to this story (Jayman).** SellOS is a single app repository, so "every repository" now means two files: the `CLAUDE.md` in the repository root and `frontend/CLAUDE.md`.

## P0.04 Provision DigitalOcean

* [ ] **P0.04** · Points 5 · Owner AMP Labs, Claude Code · Depends on N18 · Status not started

**Story.** As the platform team, I want staging and production servers, so that SellOS has somewhere to run.

**Description.** Provision droplets, firewall, MariaDB, Redis and a Spaces bucket, with SSH key access and nightly backups.

**Acceptance criteria.** (1) Staging and production exist. (2) Only required ports are open. (3) MariaDB and Redis restart automatically after a reboot. (4) A nightly backup file appears in Spaces.

**Test criteria.** A port scan shows only the expected ports, and a server reboot brings every service back.

## P0.05 Create the wildcard DNS record and certificate

* [ ] **P0.05** · Points 3 · Owner AMP Labs, Claude Code · Depends on P0.04 · Status not started

**Story.** As the platform team, I want a wildcard record and certificate for the SellOS domain, so that every company subdomain works over HTTPS without manual steps.

**Description.** Create the wildcard record in DigitalOcean DNS and issue a wildcard certificate through the DNS API, with automatic renewal.

**Acceptance criteria.** (1) The wildcard record resolves to the server. (2) The certificate is valid for all subdomains. (3) Renewal runs automatically.

**Test criteria.** Two test hostnames serve valid HTTPS, and a renewal dry run succeeds.

## P0.06 Install the Frappe 16 bench with multitenancy

* [ ] **P0.06** · Points 5 · Owner Claude Code · Depends on P0.04 · Status not started

**Story.** As the platform team, I want a Frappe 16 bench with DNS multitenancy, so that each hostname serves its own site.

**Description.** Install the bench pinned to Frappe 16.x, turn on DNS multitenancy and generate the nginx configuration.

**Acceptance criteria.** (1) The bench runs on staging. (2) Two sites on different subdomains serve separate data. (3) The Frappe version is pinned.

**Test criteria.** Create different content on two sites and confirm each hostname shows only its own.

## P0.07 Set up continuous integration

* [x] **P0.07** · Points 3 · Owner Claude Code · Depends on P0.02 · Status done

**Story.** As a reviewer, I want automated checks on every pull request, so that broken changes cannot merge.

**Description.** Run lint, unit tests and the build in continuous integration, and block merging on failure.

**Acceptance criteria.** (1) The pipeline runs on every pull request. (2) A failing check blocks the merge. (3) Run time is reported.

**Test criteria.** A pull request with a failing test is blocked, and a passing one merges.

## P0.08 Write the deployment scripts

* [ ] **P0.08** · Points 5 · Owner Claude Code · Depends on P0.06 · Status not started

**Story.** As the platform team, I want scripted deployment and rolling upgrades, so that a release reaches every company site safely.

**Description.** Write one command to deploy a tagged release to staging, another to promote it to production, and a rolling upgrade that runs migrations site by site and stops on the first failure.

**Acceptance criteria.** (1) The deploy and promote commands work. (2) The rolling upgrade stops on failure and reports which site failed. (3) Rollback steps are documented.

**Test criteria.** Deploy to staging with two sites, force a migration failure on one, and confirm the run stops and reports it.

## P0.09 Keep secrets out of repositories

* [x] **P0.09** · Points 2 · Owner Claude Code · Depends on P0.02 · Status done

**Story.** As Jayman, I want secrets kept out of repositories, so that keys are never exposed.

**Description.** Store keys in encrypted settings or environment variables, and add a scan that fails on committed secrets.

**Acceptance criteria.** (1) No key appears in any repository. (2) The scan runs in continuous integration and before commits.

**Test criteria.** Commit a fake key on a branch and confirm it is blocked.

## P0.12 Set up monitoring and alerts

* [ ] **P0.12** · Points 3 · Owner AMP Labs · Depends on P0.04 · Status not started

**Story.** As the platform team, I want uptime, error and disk alerts, so that problems are noticed before users report them.

**Description.** Monitor each site hostname, error rates, disk use and backup success, and send alerts to named people.

**Acceptance criteria.** (1) An uptime check exists for every site. (2) Alerts fire on errors, disk above 80 percent and failed backups. (3) Alerts reach named people.

**Test criteria.** Stop a service on staging and receive an alert within 5 minutes.

## P1.14 Back up every site and prove the restore

* [ ] **P1.14** · Points 5 · Owner Claude Code · Depends on P1.02 · Status not started

**Story.** As Jayman, I want per site backups and a proven restore, so that no company's data is lost.

**Description.** Back up every site nightly to Spaces with 30 days of retention, and provide a script that restores one site to staging.

**Acceptance criteria.** (1) A backup per site exists each night. (2) Retention is 30 days. (3) The restore script recreates a site.

**Test criteria.** Restore a Pandya test site and compare record counts.

## P6.12 Run the restore, upgrade and load tests

* [ ] **P6.12** · Points 8 · Owner Claude Code · Depends on P0.08, P1.14 · Status not started

**Story.** As Jayman, I want the platform proven under restore, upgrade and load, so that we can onboard other agencies safely.

**Description.** Run a full restore test, a rolling upgrade across 20 test sites, and a load test at an agreed number of concurrent users.

**Acceptance criteria.** (1) The restore completes within the agreed time. (2) The upgrade across 20 sites loses no data. (3) The load test meets the agreed response times.

**Test criteria.** A results report is stored, and every failure becomes a tracked bug before Gate 6.

# E3 Web app, roles and security

Goal: the custom SellOS app and a permission model that tests prove. It totals 32 points across Phases 0, 1 and 5.

## P0.10 Build the web app shell

* [x] **P0.10** · Points 8 · Owner Claude Code · Depends on P0.01 · Status done

**Story.** As any user, I want to sign in to a SellOS app that shows the right screens for my role, so that I never need the Frappe desk.

**Description.** Build the shell of the custom web app in the BuildOS frontend stack: sign in and sign out, session expiry, role based navigation, a per company theme from settings, and a layout that works at phone width.

**Acceptance criteria.** (1) Sign in and sign out work for each of the five roles. (2) Navigation shows only what the role may use. (3) The company logo and colours load from settings. (4) The layout works at phone width. (5) The Frappe desk is blocked for customer roles.

**Test criteria.** End to end tests for sign in and navigation per role, a manual check on a phone, and a test that customer roles are redirected away from the desk.

## P1.04 Define the roles and permissions

* [x] **P1.04** · Points 8 · Owner Claude Code · Depends on P0.10 · Status done

**Story.** As a Company Admin, I want each role to see and do only what it should, so that client and company data stays private.

**Description.** Define Platform Admin, Company Admin, Agent, Client and Channel Partner with their permissions, and list the whitelisted API methods each role may call. Methods not listed are denied. Agents see their own leads unless shared.

**Acceptance criteria.** (1) Five roles exist with a written permission table. (2) Every API method declares its allowed roles. (3) A method with no declaration is denied. (4) Agents cannot see other agents' leads unless shared.

**Test criteria.** Unit tests of the permission queries, and the full matrix in P1.05.

## P1.05 Build the permission test suite

* [ ] **P1.05** · Points 8 · Owner Claude Code · Depends on P1.04 · Status not started

**Story.** As Jayman, I want automated proof that roles and companies are isolated, so that a release can never leak data.

**Description.** Build a test matrix that calls every whitelisted method as every role and as a user from another company, and run it in continuous integration.

**Acceptance criteria.** (1) The matrix covers every whitelisted method and role. (2) No call returns data from another company. (3) A new method with no matrix entry fails the build.

**Test criteria.** Add a deliberately open method and confirm continuous integration fails.

## P1.13 Build support access grants

* [ ] **P1.13** · Points 3 · Owner Claude Code · Depends on P1.04 · Status not started

**Story.** As a Company Admin, I want to grant platform support time limited access, so that support can help without permanent access.

**Description.** Build a grant with an expiry that gives the Platform Admin read access to a company site, with every action logged.

**Acceptance criteria.** (1) A Company Admin can grant access for a chosen duration. (2) Access ends automatically at expiry. (3) Every action is logged with user and time.

**Test criteria.** Grant access for 1 hour, confirm it works and then ends, and confirm the log entries exist.

## P5.10 Commission a security review

* [ ] **P5.10** · Points 5 · Owner AMP Labs · Depends on P1.05 · Status not started

**Story.** As Jayman, I want an independent security review, so that known risks are fixed before outside agencies join.

**Description.** Review API methods, roles, company isolation, file uploads, webhooks and secrets handling. Findings are rated, and all high findings are fixed before Gate 6.

**Acceptance criteria.** (1) A written report is delivered. (2) Findings are rated. (3) Every high finding is fixed and re tested.

**Test criteria.** Each high finding has a regression test.

# E4 Multitenancy and provisioning

Goal: one site per company, created automatically with no manual server work. It totals 27 points across Phases 0 and 1.

## P0.11 Write the test site script

* [ ] **P0.11** · Points 3 · Owner Claude Code · Depends on P0.06 · Status not started

**Story.** As a developer, I want one command that creates a company site, so that testing and provisioning share one path.

**Description.** Write a script that creates a site, installs the SellOS apps, seeds a test admin and cleans up afterwards.

**Acceptance criteria.** (1) The script creates a working site from nothing. (2) It runs in an agreed time. (3) Cleanup removes the site fully.

**Test criteria.** Run it twice in a row and confirm both runs succeed.

## P1.01 Build the control site

* [ ] **P1.01** · Points 5 · Owner Claude Code · Depends on P0.06 · Status not started

**Story.** As a Platform Admin, I want a control site holding tenants and provisioning jobs, so that I can manage companies in one place.

**Description.** Build the control site with Tenant, a Plan stub and Provisioning Job records, with statuses requested, provisioning, active and failed.

**Acceptance criteria.** (1) A Platform Admin can create a tenant record. (2) Status changes follow the allowed order. (3) Company users cannot open the control site.

**Test criteria.** Unit tests for status transitions, and a permission test for company users.

## P1.02 Build the provisioning worker

* [ ] **P1.02** · Points 8 · Owner Claude Code · Depends on P1.01, P0.11 · Status not started

**Story.** As a Platform Admin, I want new companies provisioned automatically, so that no one runs server commands by hand.

**Description.** Build a worker, outside the web process, that picks up a Provisioning Job, creates the site, installs the apps, applies the plan limits and emails the admin.

**Acceptance criteria.** (1) A queued job creates a working site. (2) Failures retry, then mark the job failed with a log. (3) The web process has no shell access. (4) The admin receives a login email.

**Test criteria.** Provision five tenants in sequence, kill the worker during a job and confirm it recovers, and confirm a failed job is visible.

## P1.03 Build the setup wizard

* [ ] **P1.03** · Points 8 · Owner Claude Code · Depends on P1.02 · Status not started

**Story.** As a Company Admin, I want a guided setup, so that my company is ready to use in minutes.

**Description.** Build the wizard for company profile, logo and colours, pipeline stages with defaults, and first users and roles, following the BuildOS pattern.

**Acceptance criteria.** (1) The wizard collects all four areas. (2) It can be resumed if left. (3) The branding shows in the app after completion.

**Test criteria.** An end to end test completes the wizard and checks the result.

## P1.11 Create the Pandya Realtors site

* [ ] **P1.11** · Points 3 · Owner AMP Labs, Claude Code · Depends on P1.03 · Status not started

**Story.** As Jayman, I want the Pandya Realtors company site live, so that the first tenant can start working.

**Description.** Create the Pandya site at its subdomain, apply the branding and load the users.

**Acceptance criteria.** (1) The site is live over HTTPS. (2) Admin and agent users exist. (3) Branding is applied.

**Test criteria.** Jayman signs in as each role and sees the correct screens.

# E5 Core CRM and consent

Goal: leads, clients and consent records that gate every contact. It totals 29 points in Phase 1.

## P1.06 Build Client, Lead, Activity, Task and Site Visit

* [ ] **P1.06** · Points 8 · Owner Claude Code · Depends on P1.04 · Status not started

**Story.** As an Agent, I want to record clients, leads, activities, tasks and site visits, so that I can work every enquiry in one place.

**Description.** Build the records and their screens in the app. A Client can be a buyer, seller, investor or NRI. A Lead links to a Client, and activities, tasks and site visits attach to a lead on a timeline.

**Acceptance criteria.** (1) Records can be created, viewed and edited from the app. (2) A lead shows a timeline of activities, tasks and visits. (3) Tasks have due dates and show as overdue. (4) An agent sees only their own leads.

**Test criteria.** Unit and permission tests, and an end to end test that creates a lead and logs an activity.

## P1.07 Build the buyer pipeline

* [ ] **P1.07** · Points 5 · Owner Claude Code · Depends on P1.06, P1.08 · Status not started

**Story.** As an Agent, I want a buyer pipeline with clear stages, so that I know where every buyer stands.

**Description.** Build the stages New, Consent pending, Contacted, Qualified, Site visit booked, Site visit done, Negotiation, Booking, Closed won, Closed lost and Nurture. A lead cannot move to Contacted without a live consent record.

**Acceptance criteria.** (1) All stages exist and a Company Admin can configure them within limits. (2) Moving to Contacted without a live consent is refused with a reason. (3) Stage changes are logged.

**Test criteria.** Try to move a lead without consent and confirm refusal, then move it with consent and confirm success.

## P1.08 Build the Consent Record

* [ ] **P1.08** · Points 5 · Owner Claude Code · Depends on P1.06 · Status not started

**Story.** As Jayman, I want every lead to carry its consent state, so that no contact happens without a lawful basis.

**Description.** Build the Consent Record with lead, basis (consent, inquiry or application), timestamp, evidence link and expiry. An inquiry basis expires after 7 days and an application after 3 months. An expired record returns the lead to Consent pending.

**Acceptance criteria.** (1) Each basis requires evidence. (2) Expiry dates are set by basis. (3) Renewals are logged. (4) An expired record changes the lead state automatically.

**Test criteria.** Time shifted tests for each expiry, and a test that a record without evidence is refused.

## P1.09 Build the website lead endpoint

* [ ] **P1.09** · Points 5 · Owner Claude Code · Depends on P1.08 · Status not started

**Story.** As the website, I want a secure endpoint to send enquiries, so that leads reach SellOS with their consent wording.

**Description.** Build an HTTPS endpoint secured by a per company key. It creates a Lead and a Consent Record from each submission and rejects submissions with no consent wording.

**Acceptance criteria.** (1) A valid submission creates a lead and a consent record. (2) A bad key is rejected. (3) A submission without consent wording is rejected. (4) The endpoint is rate limited.

**Test criteria.** Tests for valid, bad key, missing consent and flood submissions.

## P1.10 Connect the Pandya website forms

* [ ] **P1.10** · Points 3 · Owner AMP Labs · Depends on P1.09 · Status not started

**Story.** As Jayman, I want the Pandya website forms connected to SellOS, so that enquiries arrive automatically.

**Description.** Point the form handlers at the endpoint, show the consent wording approved by counsel next to each form, and keep the website's own copy of each lead.

**Acceptance criteria.** (1) Each form posts to the endpoint. (2) The approved wording is shown. (3) Failures are retried and alerted. (4) The website still holds a copy.

**Test criteria.** Submit a form and see the lead in SellOS within a minute.

## P1.12 Import the bought lead lists

* [ ] **P1.12** · Points 3 · Owner Claude Code · Depends on P1.07 · Status not started

**Story.** As Jayman, I want the bought lead lists imported safely, so that they can enter the opt in route without being called.

**Description.** Build a CSV import that maps columns to leads, merges duplicates and sets every imported lead to Consent pending with the source bought list.

**Acceptance criteria.** (1) Imported leads are all Consent pending. (2) Duplicates are merged. (3) No imported lead can be called.

**Test criteria.** Import a sample with duplicates, verify the states, and confirm click to call is blocked.

# E6 Calling

Goal: manual calling through Plivo, with consent enforced before every dial. It totals 68 points in Phase 2. Calls use the 022 landline number, so only service and transactional purposes are allowed until the number series question is settled.

## P2.01 Build Telephony Settings

* [ ] **P2.01** · Points 3 · Owner Claude Code · Depends on P1.04, N09 · Status not started

**Story.** As a Company Admin, I want to enter our Plivo details once, so that calling works for my company.

**Description.** Build a settings screen for both Plivo accounts with encrypted keys that are never shown after saving, and a test connection button.

**Acceptance criteria.** (1) Both accounts can be configured. (2) Keys are encrypted and no API returns them. (3) The test connection button reports success or the error. (4) Only Company Admins can open the screen.

**Test criteria.** A permission test blocks agents, and a test confirms keys never appear in API responses.

## P2.02 Build the provider adapter

* [ ] **P2.02** · Points 8 · Owner Claude Code · Depends on P2.01 · Status not started

**Story.** As a developer, I want one adapter interface for telephony providers, so that Plivo can be replaced later.

**Description.** Define the interface with place call, read webhook and fetch recording, and implement it for Plivo, mapping provider errors to clear messages.

**Acceptance criteria.** (1) The interface is documented. (2) The Plivo adapter places a call and reads its events. (3) Provider errors map to clear messages.

**Test criteria.** Unit tests with recorded provider responses, and one live test call.

## P2.03 Build the call router

* [ ] **P2.03** · Points 5 · Owner Claude Code · Depends on P2.02 · Status not started

**Story.** As the system, I want each call sent through the right account and number series, so that calls follow the compliance rules.

**Description.** Route +91 numbers through the India account and +61 and +971 numbers through the global account. Calls from India use the 022 landline number, which is for service and transactional calls only. A 140 series route is parked.

**Acceptance criteria.** (1) Country code selects the account. (2) Only service and transactional purposes may use the 022 number, and a promotional purpose is refused. (3) Unknown countries are refused.

**Test criteria.** A table driven test of numbers and purposes against the expected account and series.

## P2.04 Build the consent check

* [ ] **P2.04** · Points 5 · Owner Claude Code · Depends on P1.08 · Status not started

**Story.** As Jayman, I want every dial checked for a lawful basis, so that no call can break the rules.

**Description.** Run a check before every dial that requires a live Consent Record and refuses Consent pending leads. No role has an override, and each refusal is logged with its reason.

**Acceptance criteria.** (1) A call with a live basis passes. (2) A call without one is refused. (3) No override exists for any role. (4) Refusals are logged with a reason. (5) A call with a promotional purpose is refused while only the 022 landline number is available.

**Test criteria.** A matrix of lead states against outcomes, and an attempt to bypass the check through the API that fails.

## P2.05 Extend the Call Log

* [ ] **P2.05** · Points 5 · Owner Claude Code · Depends on P2.02 · Status not started

**Story.** As an Agent and a Company Admin, I want every call recorded with its cost, so that we can review and report on calling.

**Description.** Extend the Call Log with provider, call ID, manual or AI mode, duration, billed duration, cost in rupees, hangup cause, recording link, outcome and consent reference, linked to the lead.

**Acceptance criteria.** (1) One log exists per call. (2) It links to the lead and the consent record. (3) Cost is stored in rupees.

**Test criteria.** Unit tests of cost conversion, and a test that a placed call creates a log.

## P2.06 Build the webhook endpoint

* [ ] **P2.06** · Points 5 · Owner Claude Code · Depends on P2.05 · Status not started

**Story.** As the system, I want Plivo's call events received safely, so that the Call Log is accurate.

**Description.** Build a whitelisted endpoint that verifies Plivo's signature, ignores replayed events, updates the Call Log with answer, hangup, duration and recording link, and fetches the recording after the call.

**Acceptance criteria.** (1) Valid events update the log. (2) Invalid signatures are rejected. (3) Replayed events change nothing. (4) The recording link is stored after the call ends.

**Test criteria.** Tests for valid, invalid signature, replayed and out of order events.

## P2.07 Build click to call

* [ ] **P2.07** · Points 8 · Owner Claude Code · Depends on P2.03, P2.04, P2.06 · Status not started

**Story.** As an Agent, I want to click a lead and be connected, so that I can call without dialling.

**Description.** Add a click to call button that rings the agent's Indian mobile first and then the lead, shows the consent state, and asks for the outcome after the call. Both call legs must stay in India.

**Acceptance criteria.** (1) The agent's phone rings first. (2) The lead is connected after the agent answers. (3) A lead without consent shows a blocked state. (4) An agent number outside India shows a clear error. (5) An outcome form is required after the call.

**Test criteria.** An end to end test with two test phones, and a test of the media anchoring error path.

## P2.08 Build the inbound opt in route

* [ ] **P2.08** · Points 8 · Owner Claude Code · Depends on P2.04 · Status not started

**Story.** As Jayman, I want bought leads given a way to respond, so that they can become callable leads.

**Description.** Give bought leads ways to come to us: a missed call to the 022 number, a link to the enquiry page shared through WhatsApp or ads, and the website forms. A missed call or form submission creates an inquiry Consent Record with a 7 day clock. Opt outs are respected. The SMS route is parked with the Tata DLT stories.

**Acceptance criteria.** (1) A missed call to the 022 number is detected without the call being answered. (2) A missed call creates a Consent Record and moves the lead. (3) The enquiry page records the consent wording. (4) Opt outs are respected.

**Test criteria.** Give a missed call from a test number, submit the enquiry page, and confirm the record and the lead state. Check the Plivo statement to see whether the rejected call is billed.

## P2.09 Build the caller queue

* [ ] **P2.09** · Points 3 · Owner Claude Code · Depends on P2.04 · Status not started

**Story.** As the caller, I want a queue of callable leads ordered by urgency, so that no consent window is wasted.

**Description.** Show leads with a live basis sorted by soonest expiry, with the time left, and drop expired leads.

**Acceptance criteria.** (1) Only leads with a live basis appear. (2) The order is soonest expiry first. (3) Time left is shown.

**Test criteria.** Seed leads with different expiries and check the order.

## P2.10 Enforce calling hours and do not call checks

* [ ] **P2.10** · Points 5 · Owner Claude Code · Depends on P2.04, N10 · Status not started

**Story.** As Jayman, I want calling hours and do not call lists enforced, so that calls stay within the rules.

**Description.** Block calls outside permitted hours per country, and add import and checking of do not call lists, with rules configurable per country.

**Acceptance criteria.** (1) Calls outside hours are blocked. (2) Do not call numbers are blocked. (3) An admin sets the rules per country.

**Test criteria.** Boundary time tests per country, and a test with a listed number.

## P2.11 Build call reports

* [ ] **P2.11** · Points 5 · Owner Claude Code · Depends on P2.05 · Status not started

**Story.** As a Company Admin, I want calling reports, so that I can see cost and performance.

**Description.** Build reports for cost by country and by agent, connect rate, talk time and consent coverage, with date filters.

**Acceptance criteria.** (1) Each report filters by date. (2) Totals match the Call Log. (3) Each figure drills down to calls.

**Test criteria.** Reconcile the totals with Plivo's statement for a test month.

## P2.12 Enforce the UAE call cap

* [ ] **P2.12** · Points 2 · Owner Claude Code · Depends on P2.03 · Status not started

**Story.** As Jayman, I want UAE calls capped, so that cost stays controlled.

**Description.** Add a monthly cap that defaults to 20 calls, resets each month and can be changed by a Company Admin.

**Acceptance criteria.** (1) The 21st call in a month is blocked with a message. (2) The counter resets monthly. (3) Admins can change the cap.

**Test criteria.** Simulate 21 calls and confirm the last is blocked.

## P2.13 Make and check test calls

* [ ] **P2.13** · Points 3 · Owner Jayman · Depends on P2.07 · Status not started

**Story.** As Jayman, I want test calls proven end to end, so that we trust the setup before real use.

**Description.** The Indian number, +91 22 6998 6373, is already bought. Place test calls to India, Australia and UAE numbers and check cost and recordings.

**Acceptance criteria.** (1) Calls to all three countries complete. (2) Logged cost is within an agreed tolerance of Plivo's statement. (3) Recordings play.

**Test criteria.** Reconcile the Call Log with the Plivo statement.

## P2.14 Onboard the first caller and start the baseline

* [ ] **P2.14** · Points 3 · Owner Jayman · Depends on P2.13 · Status not started

**Story.** As Jayman, I want the first caller trained and a baseline measured, so that the AI pilot has something to beat.

**Description.** Train the caller on the app and script, restrict them to the consented queue, and track the four week baseline metrics.

**Acceptance criteria.** (1) The caller completes training. (2) The caller works only from the consented queue. (3) Baseline metrics are tracked weekly.

**Test criteria.** A weekly baseline report is produced for four weeks.

# E7 Market intelligence

Goal: turn five years of registered Mumbai transactions into comparables, valuation ranges and guidance for agents, starting with the Bandra to Andheri corridor. It totals 74 points in Phase 3 and cannot start until a data source is secured through N11 or N12.

## P3.01 Build the source adapter

* [ ] **P3.01** · Points 5 · Owner Claude Code · Depends on N11, N12 · Status not started

**Story.** As a developer, I want one adapter interface for registration data sources, so that SellOS works with whichever source we secure.

**Description.** Define the interface with fetch batch and map fields, and build the adapter for the source chosen through N11 or N12, running on a schedule with failure alerts.

**Acceptance criteria.** (1) The interface is documented. (2) The adapter for the chosen source ingests a batch. (3) Runs are scheduled and failures raise alerts. (4) The adapter never solves captchas or bypasses access controls.

**Test criteria.** Contract tests with sample payloads, and a test that a failed run raises an alert.

## P3.02 Create the raw transaction table

* [ ] **P3.02** · Points 3 · Owner Claude Code · Depends on P3.01 · Status not started

**Story.** As a data engineer, I want every record stored untouched, so that cleaning can always be repeated from the original.

**Description.** Store each record exactly as received, with its source, fetch time and a hash.

**Acceptance criteria.** (1) Original fields are unchanged. (2) Source, fetch time and hash are stored. (3) Re runs do not create duplicates.

**Test criteria.** Ingest the same batch twice and confirm there are no duplicates.

## P3.03 Build the normaliser

* [ ] **P3.03** · Points 8 · Owner Claude Code · Depends on P3.02 · Status not started

**Story.** As an Agent, I want clean, comparable figures, so that rates mean the same thing across records.

**Description.** Translate or transliterate Marathi names and property text into English, standardise dates, parse consideration and market value, and convert areas to carpet area in square feet, recording the rule used.

**Acceptance criteria.** (1) English fields are filled and the original is kept. (2) Dates are standard. (3) Areas are in carpet square feet with the conversion rule recorded. (4) Unparseable records go to a review list.

**Test criteria.** A golden file of 100 verified records, with an accuracy threshold agreed with Jayman.

## P3.04 Build the building and micro market master

* [ ] **P3.04** · Points 5 · Owner Claude Code, Jayman · Depends on P3.02 · Status not started

**Story.** As an Agent, I want buildings and micro markets defined, so that transactions roll up the way agents think.

**Description.** Define micro markets for the Bandra to Andheri corridor with boundaries, and buildings and projects with CTS numbers and RERA numbers where known, editable by admins.

**Acceptance criteria.** (1) Micro markets and boundaries exist. (2) Buildings carry CTS and RERA numbers where known. (3) Admins can edit them.

**Test criteria.** Twenty buildings are verified by agents.

## P3.05 Build the matcher

* [ ] **P3.05** · Points 8 · Owner Claude Code · Depends on P3.03, P3.04 · Status not started

**Story.** As an Agent, I want each transaction tied to the right building, so that comparables are trustworthy.

**Description.** Match using CTS or survey number, address and RERA number, give each match a confidence score, and send low confidence records to a review queue.

**Acceptance criteria.** (1) Each record gets a match or a review status. (2) Confidence is stored. (3) Reviewer decisions are saved and reused.

**Test criteria.** Precision and recall are measured on 200 hand matched records.

## P3.06 Flag outliers

* [ ] **P3.06** · Points 5 · Owner Claude Code · Depends on P3.05 · Status not started

**Story.** As an Agent, I want unusual deals flagged, so that they do not distort comparables.

**Description.** Flag related party sales, token prices, bundled units and parking sold separately. Exclude flagged records from comparables by default and show the reason.

**Acceptance criteria.** (1) Each flag type is detected. (2) Flagged records are excluded by default. (3) The reason is visible.

**Test criteria.** Seeded examples of each flag type.

## P3.07 Build the nightly jobs

* [ ] **P3.07** · Points 5 · Owner Claude Code · Depends on P3.05 · Status not started

**Story.** As an Agent, I want up to date rates and trends, so that guidance reflects the market.

**Description.** Compute rate per square foot, rolling 3, 6 and 12 month trends and building statistics every night.

**Acceptance criteria.** (1) Jobs run nightly and are repeatable. (2) They finish within the agreed window. (3) Failures raise alerts.

**Test criteria.** Recompute a known sample by hand and compare.

## P3.08 Build the comparables API and profiles

* [ ] **P3.08** · Points 8 · Owner Claude Code · Depends on P3.07 · Status not started

**Story.** As an Agent, I want comparables and building profiles, so that I can price and advise with evidence.

**Description.** Build an API that returns comparables for a building, project or micro market with filters, and screens for building and project profiles showing five year trend, volume, resale against primary, and price against the ready reckoner.

**Acceptance criteria.** (1) The API filters by area, floor, date and type. (2) Profiles show trend, volume and price against the ready reckoner. (3) Every figure links to its records. (4) Role permissions apply.

**Test criteria.** API tests, and an end to end view of a known building.

## P3.09 Build the valuation range

* [ ] **P3.09** · Points 8 · Owner Claude Code · Depends on P3.08 · Status not started

**Story.** As an Agent, I want a valuation range for a property, so that I can advise sellers confidently.

**Description.** Produce a low, middle and high range with the number of comparables, the method and the comparables used, and refuse to answer when too few comparables exist.

**Acceptance criteria.** (1) A range is returned with its comparables. (2) The method is shown. (3) Too few comparables returns a clear refusal.

**Test criteria.** Back test against 50 known sales and report the error.

## P3.10 Build the agent assistant

* [ ] **P3.10** · Points 8 · Owner Claude Code · Depends on P3.08 · Status not started

**Story.** As an Agent, I want to ask market questions in plain language, so that I get answers grounded in records.

**Description.** Build an assistant that answers only through query tools, lists the records behind every answer, refuses to guess, logs questions and respects role limits on party names.

**Acceptance criteria.** (1) Answers cite records. (2) Unknown buildings get a clear refusal. (3) Party names are hidden where the role forbids them. (4) Questions are logged.

**Test criteria.** A scripted question set with expected tool calls, and a test with an unknown building to confirm it does not invent figures.

## P3.11 Build alerts for watched buildings

* [ ] **P3.11** · Points 3 · Owner Claude Code · Depends on P3.07 · Status not started

**Story.** As an Agent, I want alerts on watched buildings, so that I hear about new sales first.

**Description.** Let agents watch buildings, and send an in app and email alert when a new registration appears, with a frequency cap.

**Acceptance criteria.** (1) Agents can watch and unwatch buildings. (2) New registrations create alerts. (3) The cap limits repeats.

**Test criteria.** Ingest a test record in a watched building.

## P3.12 Apply the party name rules

* [ ] **P3.12** · Points 3 · Owner Claude Code · Depends on N13, P3.02 · Status not started

**Story.** As Jayman, I want party names handled as counsel advises, so that we stay lawful.

**Description.** Apply the storage, access and retention rules from N13, hide names from roles that do not need them, disable search by name unless allowed, and log every access.

**Acceptance criteria.** (1) Names are visible only to allowed roles. (2) Name search is off unless allowed. (3) Access is logged. (4) Retention follows the advice.

**Test criteria.** Permission tests for each role.

## P3.13 Load and verify five years of data

* [ ] **P3.13** · Points 5 · Owner Jayman · Depends on P3.05 · Status not started

**Story.** As Jayman, I want five years of corridor data loaded and checked, so that agents can trust it.

**Description.** Load five years of Bandra to Andheri data and check 50 records against Index II.

**Acceptance criteria.** (1) Five years are loaded. (2) 50 records are checked against Index II. (3) The accuracy is reported and discrepancies are logged.

**Test criteria.** An audit report with the sample and the results.

# E8 Inventory, mandates and deals

Goal: listings, mandates and deals with comparables attached, feeding the Pandya website. It totals 53 points in Phase 4.

## P4.01 Build Developer, Project, Unit and Property

* [ ] **P4.01** · Points 8 · Owner Claude Code · Depends on P1.04 · Status not started

**Story.** As an Agent, I want developers, projects, units and properties recorded with RERA numbers, so that inventory is accurate.

**Description.** Build the records with RERA numbers, unit configuration, carpet area, floor and parking, and a unit status of available, held or sold, for both primary projects and secondary properties.

**Acceptance criteria.** (1) Records can be created and edited in the app. (2) The RERA number is stored for projects. (3) Unit status changes are logged. (4) Only permitted roles can edit.

**Test criteria.** Unit and permission tests, and an end to end test of creating a project with units.

## P4.02 Build Listing

* [ ] **P4.02** · Points 5 · Owner Claude Code · Depends on P4.01 · Status not started

**Story.** As an Agent, I want listings typed as primary, Direct or Partner, so that the website shows the right sections.

**Description.** Build Listing linked to a unit or property, with a type, a publish flag and a change history.

**Acceptance criteria.** (1) Each listing has a type. (2) Publishing needs the required fields. (3) Changes are audited.

**Test criteria.** An end to end create and publish, and a test that an incomplete listing cannot publish.

## P4.03 Build Media Asset

* [ ] **P4.03** · Points 3 · Owner Claude Code · Depends on P4.02 · Status not started

**Story.** As an Agent, I want photos and videos linked to listings, so that listings look complete.

**Description.** Link media from the asset library to listings, with size and type checks and an order.

**Acceptance criteria.** (1) Media attaches to a listing. (2) Invalid files are rejected. (3) The order can be changed.

**Test criteria.** Upload valid and invalid files.

## P4.04 Build the seller pipeline

* [ ] **P4.04** · Points 5 · Owner Claude Code · Depends on P4.02 · Status not started

**Story.** As an Agent, I want a seller pipeline, so that owners are tracked to a signed mandate and a sale.

**Description.** Build the stages New owner enquiry, Qualified, Valuation shared, Mandate proposed, Mandate signed, Listed, Offers received, Sold, Closed lost and Nurture.

**Acceptance criteria.** (1) All stages exist. (2) Stage rules are enforced, such as no Listed stage without a signed mandate. (3) Changes are logged.

**Test criteria.** Stage rule tests.

## P4.05 Build Mandate

* [ ] **P4.05** · Points 8 · Owner Claude Code · Depends on P4.04 · Status not started

**Story.** As an owner and an Agent, I want a mandate recorded, so that the Private Sale Dossier is shared only against a signed agreement.

**Description.** Build Mandate as exclusive or open with term, fee and a signed document upload. The Dossier is released only when the mandate is signed, and each view is audited.

**Acceptance criteria.** (1) Mandates carry type, term and fee. (2) The signed document is required. (3) The Dossier is hidden until signed. (4) Each Dossier view is logged.

**Test criteria.** Try to open the Dossier without a signed mandate and confirm it fails.

## P4.06 Build Deal and Commission Split

* [ ] **P4.06** · Points 8 · Owner Claude Code · Depends on P4.05 · Status not started

**Story.** As a Company Admin, I want deals and commission splits recorded, so that we know who earns what.

**Description.** Build Deal linking client, unit or property and price, and Commission Split among agent, channel partner and company with percentages that sum to 100, approved by a Company Admin.

**Acceptance criteria.** (1) Deals link client and property. (2) Splits must sum to 100 percent. (3) A Company Admin approves splits. (4) Channel Partner shares are supported.

**Test criteria.** Validation tests and worked split examples.

## P4.07 Attach comparables to listings and mandates

* [ ] **P4.07** · Points 5 · Owner Claude Code · Depends on P3.09, P4.05 · Status not started

**Story.** As an Agent, I want comparables and a valuation range on listing and mandate screens, so that I can advise with evidence.

**Description.** Show comparables and the valuation range with links to the underlying records, hidden when the data licence does not allow it.

**Acceptance criteria.** (1) Comparables appear on both screens. (2) Each links to its records. (3) They are hidden if the licence forbids showing them.

**Test criteria.** An end to end check on a known building, and a test of the licence switch.

## P4.08 Build the listings endpoint

* [ ] **P4.08** · Points 5 · Owner Claude Code · Depends on P4.02 · Status not started

**Story.** As the website, I want a read only listings endpoint, so that listings appear without manual entry.

**Description.** Build an endpoint, keyed per company, that returns published listings, plus a webhook that announces changes, with caching.

**Acceptance criteria.** (1) Only published listings are returned. (2) Changes trigger the webhook. (3) A bad key is rejected.

**Test criteria.** Contract tests and a change push test.

## P4.09 Switch the website to read listings from SellOS

* [ ] **P4.09** · Points 3 · Owner AMP Labs · Depends on P4.08 · Status not started

**Story.** As Jayman, I want the Pandya website to show listings from SellOS, so that nothing is entered twice.

**Description.** Render the listing pages from the endpoint, remove unpublished listings within the agreed time, and fall back safely if the endpoint is down.

**Acceptance criteria.** (1) Pages render from the endpoint. (2) Unpublishing removes a listing within the agreed time. (3) An outage shows the last good copy.

**Test criteria.** Toggle a listing and check the site, and simulate an outage.

## P4.10 Import current listings and mandates

* [ ] **P4.10** · Points 3 · Owner AMP Labs, Jayman · Depends on P4.05 · Status not started

**Story.** As Jayman, I want current listings and mandates imported, so that SellOS holds the real business.

**Description.** Import Pandya's current listings and mandates and reconcile the counts with the source sheet.

**Acceptance criteria.** (1) Imports complete. (2) Counts reconcile. (3) Duplicates are resolved.

**Test criteria.** A reconciliation report signed off by Jayman.

# E9 Reporting

Goal: role scoped reports with drill down, export and scheduling. It totals 26 points in Phase 5.

## P5.01 Build the report engine

* [ ] **P5.01** · Points 8 · Owner Claude Code · Depends on P1.06 · Status not started

**Story.** As a Company Admin, I want a report engine, so that every report shares filters, scoping and drill down.

**Description.** Build Report Definition with filters, grouping and role scope, backed by nightly summary tables, with drill down to the underlying records.

**Acceptance criteria.** (1) Reports are defined by configuration. (2) Role scope limits the rows. (3) Each figure drills down to records. (4) Summary tables refresh nightly.

**Test criteria.** Compare results with a hand calculation.

## P5.02 Build the agent and Company Admin reports

* [ ] **P5.02** · Points 8 · Owner Claude Code · Depends on P5.01, P4.06, P2.11 · Status not started

**Story.** As an Agent and a Company Admin, I want the standard reports, so that I can run the business from data.

**Description.** For agents: my pipeline, calls and outcomes, follow ups due and site visits. For Company Admins: lead funnel and conversion by stage, source performance, agent productivity, call reports, listing and mandate ageing, and deal pipeline and commission.

**Acceptance criteria.** (1) Every listed report exists. (2) Each filters by date. (3) Each reconciles with its raw data.

**Test criteria.** Reconcile every report against raw data.

## P5.03 Build the Channel Partner and Platform reports

* [ ] **P5.03** · Points 5 · Owner Claude Code · Depends on P5.01 · Status not started

**Story.** As a Channel Partner and a Platform Admin, I want my reports, so that I can track results.

**Description.** Build Channel Partner reports for own leads, deals and commission statements, and Platform Admin reports for companies, usage and calling spend. The revenue, churn and failed payment panels switch on once billing data exists.

**Acceptance criteria.** (1) Partners see only their own data. (2) Platform reports cover companies, usage and calling spend. (3) Revenue panels activate after billing is live.

**Test criteria.** Permission tests, and a check of the totals.

## P5.04 Build saved views, export and scheduling

* [ ] **P5.04** · Points 5 · Owner Claude Code · Depends on P5.01 · Status not started

**Story.** As a Company Admin, I want to save, export and schedule reports, so that results reach the right people.

**Description.** Add saved filters, CSV and PDF export, and scheduled email delivery with recipients, all scoped by role.

**Acceptance criteria.** (1) Views can be saved and shared. (2) Exports match the screen. (3) Scheduled emails arrive on time. (4) Recipients only get data they may see.

**Test criteria.** Compare an export with the screen, and run a scheduled email.

# E10 Client and partner views

Goal: Client and Channel Partner access inside the same app. It totals 16 points in Phase 5.

## P5.05 Build the client views

* [ ] **P5.05** · Points 8 · Owner Claude Code · Depends on P4.05 · Status not started

**Story.** As a Client, I want to see my shortlist, visits and deal status, so that I stay informed.

**Description.** Buyers see their shortlist, site visits and deal status. Sellers see mandate status and enquiries on their property. The Dossier appears only after a signed mandate.

**Acceptance criteria.** (1) Buyers see shortlist, visits and status. (2) Sellers see mandate status and enquiries. (3) The Dossier is hidden until a mandate is signed. (4) Clients see only their own data.

**Test criteria.** Permission tests, and an end to end walk through for a buyer and a seller.

## P5.06 Build the Channel Partner views

* [ ] **P5.06** · Points 8 · Owner Claude Code · Depends on P4.06 · Status not started

**Story.** As a Channel Partner, I want to register leads and track my deals, so that I can work with Pandya.

**Description.** Build partner views to register leads with consent, see shared inventory, and track their own deals and commission status.

**Acceptance criteria.** (1) Leads can be registered with consent wording. (2) Shared inventory is visible. (3) Deals and commission status show only the partner's own. (4) Partners cannot see other partners' leads.

**Test criteria.** Permission tests, and an end to end test of registering a lead.

# E11 Voice AI pilot

Goal: a governed AI calling pilot, compared fairly against human callers. It totals 16 points in Phase 5, and the pilot cannot start until the four week human baseline from P2.14 exists. While only the 022 number exists, AI calls are limited to service and transactional purposes, so the pilot design may change or wait.

## P5.07 Build the voice agent service

* [ ] **P5.07** · Points 8 · Owner Claude Code · Depends on P2.03, P2.04 · Status not started

**Story.** As Jayman, I want an AI voice agent that can hold a short qualifying call, so that we can test AI calling safely.

**Description.** Build a service that receives call audio from Plivo by audio streaming, uses speech to text, a language model and text to speech in one language, reads lead context from SellOS and writes the outcome back. It says it is an AI at the start and hands over to a human on request or confusion.

**Acceptance criteria.** (1) A live call connects to the agent over audio streaming. (2) The agent states it is an AI at the start. (3) It hands over to a human on request or confusion. (4) It writes the outcome and transcript to the Call Log. (5) It calls only leads that pass the consent check, and while only the 022 number exists it makes only service or transactional calls.

**Test criteria.** Scripted test calls covering normal, interruption, silence and handover cases, and a latency measurement against the agreed target.

## P5.08 Run the AI pilot

* [ ] **P5.08** · Points 5 · Owner Jayman · Depends on P5.07, P2.14 · Status not started

**Story.** As Jayman, I want a controlled AI pilot, so that we learn before scaling.

**Description.** Run 400 AI calls over about four weeks in one language, reviewing transcripts weekly. While only the 022 number exists, the calls are limited to service and transactional purposes, such as site visit confirmations and follow ups for existing clients, so the pilot design may change or wait until the number series question is settled. Any complaint stops the pilot for review.

**Acceptance criteria.** (1) 400 calls are completed, or the pilot is stopped with a recorded reason. (2) Transcripts are reviewed weekly. (3) Complaints are logged, and zero are required to continue.

**Test criteria.** A weekly review log is kept.

## P5.09 Compare AI with the human baseline

* [ ] **P5.09** · Points 3 · Owner Jayman, Claude Code · Depends on P5.08 · Status not started

**Story.** As Jayman, I want AI and human calling compared fairly, so that we decide whether to scale.

**Description.** Compare connect rate, qualified lead rate, site visits booked, cost per qualified lead, handover rate and complaints, using the four week human baseline.

**Acceptance criteria.** (1) A comparison report covers all six measures. (2) The data reconciles with the Call Log. (3) A go or no go decision is recorded.

**Test criteria.** Reconcile the report with the raw data.

# E12 Billing and subscriptions

Goal: fixed plans, coupons and recurring payments so that other agencies can subscribe. It totals 45 points in Phase 6.

## P6.01 Build the billing records

* [ ] **P6.01** · Points 5 · Owner Claude Code · Depends on P1.01 · Status not started

**Story.** As a Platform Admin, I want plans, coupons, subscriptions, invoices and payments recorded, so that billing has a foundation.

**Description.** Build Plan, Coupon, Subscription, Invoice and Payment on the control site, with limits on each plan.

**Acceptance criteria.** (1) All five records exist. (2) A plan defines limits such as users and listings. (3) A subscription links one company to one plan.

**Test criteria.** Unit tests of the records and their relationships.

## P6.02 Define the plan tiers

* [ ] **P6.02** · Points 3 · Owner Claude Code, Jayman · Depends on P0.01 · Status not started

**Story.** As Jayman, I want sensible plan tiers, so that pricing is clear.

**Description.** Claude Code reads how BuildOS structures its plans and proposes SellOS tiers in the same shape. Jayman approves the limits and prices.

**Acceptance criteria.** (1) A proposal is delivered. (2) Limits and prices are approved in writing. (3) The approved tiers are loaded as plans.

**Test criteria.** Verified by the written approval and the loaded plan records. Limit enforcement is tested in P6.04.

## P6.03 Build the Razorpay adapter and recurring payments

* [ ] **P6.03** · Points 8 · Owner Claude Code · Depends on N14, P6.01 · Status not started

**Story.** As Jayman, I want Indian customers charged automatically, so that revenue is predictable.

**Description.** Build a gateway interface and the Razorpay adapter with subscription creation, cancellation and webhooks, in test mode first.

**Acceptance criteria.** (1) A test subscription is created and renews. (2) Webhooks update the subscription. (3) Webhook handling is idempotent. (4) Failed payments are recorded.

**Test criteria.** Sandbox subscriptions through renewal and failure.

## P6.15 Build the Stripe adapter

* [ ] **P6.15** · Points 5 · Owner Claude Code · Depends on P6.03 · Status not started

**Story.** As Jayman, I want overseas customers charged automatically, so that international agencies can subscribe.

**Description.** Build the Stripe adapter behind the same gateway interface, with subscriptions, cancellation and webhooks, in test mode first. This story was split out of the original gateway task to keep each story within 8 points.

**Acceptance criteria.** (1) A test subscription renews. (2) Webhooks update the subscription. (3) Webhook handling is idempotent. (4) A customer is routed to Stripe or Razorpay by country.

**Test criteria.** Sandbox subscriptions through renewal and failure, and a routing test.

## P6.04 Build the billing lifecycle

* [ ] **P6.04** · Points 8 · Owner Claude Code · Depends on P6.03, P6.02 · Status not started

**Story.** As a Platform Admin, I want subscriptions to move through clear states, so that access follows payment.

**Description.** Build trial, active, past due with a grace period, suspended and cancelled, with emails at each change. A suspended company's site is disabled but kept, and plan limits are enforced.

**Acceptance criteria.** (1) States change on gateway events. (2) Past due has a configurable grace period. (3) Suspension disables the site without deleting data. (4) Reactivation restores access. (5) Plan limits are enforced.

**Test criteria.** Simulate failure, grace, suspension and recovery in test mode.

## P6.05 Build coupons

* [ ] **P6.05** · Points 3 · Owner Claude Code · Depends on P6.01 · Status not started

**Story.** As Jayman, I want discount coupons, so that we can offer deals.

**Description.** Build percentage and fixed coupons with an expiry, a redemption limit and a number of billing cycles, applied to invoices.

**Acceptance criteria.** (1) Coupons discount an invoice correctly. (2) Expired or used up coupons are refused. (3) Cycle limits are honoured.

**Test criteria.** Unit tests for each coupon rule.

## P6.06 Build GST compliant invoices

* [ ] **P6.06** · Points 5 · Owner Claude Code · Depends on N15, P6.01 · Status not started

**Story.** As Jayman, I want compliant invoices, so that customers and the tax authority are satisfied.

**Description.** Generate an invoice for every payment in the format the accountant confirms, with GST for Indian customers and the correct treatment for overseas customers, numbered in sequence.

**Acceptance criteria.** (1) Each payment has a numbered invoice. (2) GST is shown for Indian customers. (3) Overseas invoices follow the confirmed treatment. (4) Credit notes are supported.

**Test criteria.** The accountant approves sample invoices.

## P6.07 Build self service sign up

* [ ] **P6.07** · Points 8 · Owner Claude Code · Depends on P6.04, P1.03 · Status not started

**Story.** As a new agency, I want to sign up and start using SellOS without waiting, so that onboarding is quick.

**Description.** Build a sign up flow that collects company details, plan and payment, then triggers provisioning and the setup wizard.

**Acceptance criteria.** (1) A new company can sign up and pay. (2) Provisioning starts automatically. (3) The company receives login details. (4) Failed payments do not create a site.

**Test criteria.** An end to end test in test mode from sign up to first login.

# E13 Listing sources and WhatsApp

Goal: bring listings in from registries, developer sites and agent captured posts, and move the WhatsApp flows into SellOS. It totals 43 points in Phase 6.

## P6.08 Build the listing scraper for registries and developer sites

* [ ] **P6.08** · Points 8 · Owner Claude Code · Depends on P4.02 · Status not started

**Story.** As an Agent, I want listings from public registries and developer sites collected automatically, so that inventory data is not entered by hand.

**Description.** Build Source and Raw Listing records and scheduled collection for RERA registries and developer websites, with polite rate limits, respect for each site's access rules, RERA number matching, a review queue and an on and off switch per source.

**Acceptance criteria.** (1) Each source has a switch and a last run log. (2) Collection respects rate limits and each site's access rules. (3) Records are matched on RERA number. (4) Nothing publishes without review approval.

**Test criteria.** A dry run against saved pages for each source, and a test that a changed page layout raises an alert instead of loading bad data.

## P6.09 Review each portal's terms

* [ ] **P6.09** · Points 3 · Owner Jayman, Counsel · Depends on P6.08 · Status not started

**Story.** As Jayman, I want each listing portal's terms reviewed, so that we only use sources we are allowed to use.

**Description.** Review each portal's terms and any official feed or partner access, and switch on only the sources that pass.

**Acceptance criteria.** (1) A decision is recorded for each portal. (2) Only approved sources are enabled. (3) Rejected sources stay off.

**Test criteria.** Verified by the decision log and the source switches.

## P6.10 Build the Facebook capture assist

* [ ] **P6.10** · Points 8 · Owner Claude Code · Depends on P6.08 · Status not started

**Story.** As an Agent, I want to save a Facebook post to SellOS myself, so that group listings reach our review queue without automated collection.

**Description.** Build a browser extension or share target so that an agent signed in as themselves saves or shares a post, which is parsed into a draft listing in the review queue. Personal data of posters is handled as counsel advises.

**Acceptance criteria.** (1) An agent can save a post in two taps or clicks. (2) The post becomes a draft in the review queue. (3) No automated collection runs against Facebook. (4) Poster personal data follows the counsel rules.

**Test criteria.** Capture 20 sample posts and check the parsing, and a test that nothing is collected without an agent action.

## P6.11 Build the WhatsApp channel foundation

* [ ] **P6.11** · Points 8 · Owner Claude Code · Depends on P1.08 · Status not started

**Story.** As Jayman, I want WhatsApp working per company, so that each agency has its own number and templates.

**Description.** Build the WhatsApp channel foundation in SellOS: a per company number and templates, inbound and outbound messages, Leads and Consent Records created from conversations, and handoff to a human agent.

**Acceptance criteria.** (1) A company can connect its own number. (2) Messages create or update leads. (3) An opt in creates a consent record. (4) A conversation can be handed to a human.

**Test criteria.** An end to end test on a sandbox number with inbound, outbound and handoff.

## P6.16 Rebuild WhatsApp flows, group one

* [ ] **P6.16** · Points 8 · Owner Claude Code · Depends on P6.11 · Status not started

**Story.** As an Agent, I want the lead qualification, NRI buyer and investor flows, so that WhatsApp enquiries are qualified automatically.

**Description.** Rebuild these flows from the existing WhatsApp CRM designs inside SellOS. Each flow asks its questions, scores the lead and hands over to an agent when needed. This story and P6.17 were split out of the original rebuild task to keep each within 8 points.

**Acceptance criteria.** (1) Each flow runs end to end. (2) Answers are stored on the lead. (3) Handoff works from each flow. (4) Flows follow the consent rules.

**Test criteria.** Scripted conversations through each flow on a sandbox number.

## P6.17 Rebuild WhatsApp flows, group two

* [ ] **P6.17** · Points 8 · Owner Claude Code · Depends on P6.11 · Status not started

**Story.** As an Agent, I want the site visit booking, cold lead nurture, human handoff and remaining flows, so that WhatsApp supports the whole journey.

**Description.** Rebuild the remaining flows from the existing designs, including booking site visits into the agent's calendar and nurture messages for cold leads within the consent rules.

**Acceptance criteria.** (1) Site visits are booked from WhatsApp. (2) Nurture messages respect consent and opt outs. (3) Handoff passes the full conversation. (4) All ten flows are live.

**Test criteria.** Scripted conversations through each flow, including an opt out.

# E14 Launch readiness

Goal: legal terms, support and the first outside agency. It totals 10 points in Phase 6.

## P6.13 Prepare legal terms and the support process

* [ ] **P6.13** · Points 5 · Owner Jayman, Counsel · Depends on P6.07 · Status not started

**Story.** As Jayman, I want legal terms and a support process, so that other agencies can be onboarded responsibly.

**Description.** Prepare the terms of service, privacy policy, data processing terms and a support process with a status page.

**Acceptance criteria.** (1) Counsel approves the terms, privacy policy and data processing terms. (2) They are shown and accepted at sign up. (3) A support channel and response targets exist. (4) A status page is live.

**Test criteria.** A sign up test confirms that acceptance is recorded.

## P6.14 Onboard the first outside agency

* [ ] **P6.14** · Points 5 · Owner Jayman · Depends on P6.07, P6.12, P5.10 · Status not started

**Story.** As Jayman, I want one outside agency onboarded as a pilot, so that we prove the platform with a real customer.

**Description.** Onboard a friendly agency through the sign up flow, support them for two weeks, and record every issue.

**Acceptance criteria.** (1) The agency signs up and pays in live or agreed mode. (2) Their data is isolated from Pandya's. (3) Issues are logged and triaged. (4) Gate 6 is signed off.

**Test criteria.** A cross company isolation check on live data, and a review of the issue log.

# Parked stories

These six stories belong to the Tata DLT and 140 series route. They are parked until the number series question is settled, and they take 13 points out of the active scope. Reactivate them together. Do not work on them while parked.

## N02 Get written confirmation on the Mira Road registration (parked)

* [ ] **N02** · Points 1 · Owner Jayman · Depends on none · Status parked

Ask Plivo support whether a Telemarketer registered in Mira Road is accepted for 140 series numbers, quoting the registered address. Done when a written answer is saved and, if the answer is no, the fallback route is recorded.

## N03 Confirm Principal Entity registration for a non Pvt Ltd business (parked)

* [ ] **N03** · Points 1 · Owner Jayman · Depends on none · Status parked

Ask Tata DLT whether Pandya Realtors, which has no company identification number, can register as Principal Entity and which documents it needs. Done when a written answer is saved and the document list is recorded.

## N04 Register on Tata DLT as Telemarketer and Principal Entity (parked)

* [ ] **N04** · Points 3 · Owner Jayman, AMP Labs · Depends on N02, N03 · Status parked

Register The AMP Labs as Telemarketer and Pandya Realtors as Principal Entity on the Tata DLT portal with GST certificates. Done when both certificates and IDs are received and stored, and each entity can log in with an approved status.

## N05 Obtain the 140 series number and NOC from Plivo (parked)

* [ ] **N05** · Points 2 · Owner AMP Labs · Depends on N04 · Status parked

Complete the Aggregator Telemarketer Declaration with PAN, CIN, address and the DLT Telemarketer ID, sign it with the company seal and send it to Plivo support. Done when Plivo allocates a 140 series number and issues the NOC.

## N06 Get the voice header and template approved (parked)

* [ ] **N06** · Points 3 · Owner AMP Labs · Depends on N05 · Status parked

The Telemarketer submits the voice header with the NOC, the Principal Entity approves it with the GST certificate, and a promotional voice template is registered. Done when both approvals arrive and a test promotional call from the 140 number completes to a consented test phone.

## N08 Confirm SMS to a bought list and register the SMS header (parked)

* [ ] **N08** · Points 3 · Owner Jayman, Counsel · Depends on N04 · Status parked

Confirm with Tata DLT or counsel whether promotional SMS to bought numbers is allowed. If it is, register an SMS header and a template carrying the missed call number and the enquiry page link. Done when a written yes or no is received and, if yes, the header and template are approved.

# Phase gates

Each gate is a release checkpoint. Jayman signs off after the listed evidence is shown on staging.

* Gate 0, Foundations: BuildOS conventions approved, the web app signs in, and a test company site is created by script. Evidence: P0.01 approval, P0.10 and P0.11 demos.
* Gate 1, Tenancy and core CRM: a Pandya admin logs in and a website lead arrives with its consent record. Evidence: P1.09 and P1.10 demo, P1.05 passing.
* Gate 2, Calling: calls are logged with cost, and leads without consent cannot be called. Evidence: P2.04 matrix, P2.13 reconciliation.
* Gate 3, Market intelligence: five years of corridor data are loaded and comparables are checked by Pandya agents. Evidence: P3.13 audit, P3.09 back test.
* Gate 4, Inventory and mandates: Pandya runs real listings and mandates in SellOS and the website reads listings from it. Evidence: P4.09 and P4.10.
* Gate 5, Reports and portals: reports and portals are in use, the AI pilot is reviewed, and there are zero complaints. Evidence: P5.09 and P5.10.
* Gate 6, Billing and integrations: another agency can sign up, pay and use SellOS, and the restore, upgrade and load tests pass. Evidence: P6.12 and P6.14.

# Indicative sprint plan

Sprints are two weeks long. The plan is indicative and is re baselined after Sprint 2, once the first velocity is measured.

* S1, weeks 1 to 2: E1 starts. Phase 0 foundations: repositories, servers, bench.
* S2, weeks 3 to 4: Phase 0 app shell and test site script. Phase 1 starts. Velocity measured.
* S3, weeks 5 to 6: Phase 1 control site, provisioning, roles and permission tests.
* S4, weeks 7 to 8: Phase 1 CRM, consent, website endpoint, Pandya site. Gate 1.
* S5, weeks 9 to 10: Phase 2 settings, adapter, router, consent check, Call Log.
* S6, weeks 11 to 12: Phase 2 click to call, inbound opt in route, reports. Gate 2.
* S7, weeks 13 to 14: Phase 3 ingestion, normaliser, building master.
* S8, weeks 15 to 16: Phase 3 matcher, nightly jobs, comparables.
* S9, weeks 17 to 18: Phase 3 valuation and assistant. Gate 3. Phase 4 starts.
* S10, weeks 19 to 20: Phase 4 inventory, listings, mandates.
* S11, weeks 21 to 22: Phase 4 deals and website feed. Gate 4.
* S12, weeks 23 to 24: Phase 5 reporting module.
* S13, weeks 25 to 26: Phase 5 portals and voice agent service.
* S14, weeks 27 to 28: Phase 5 AI pilot review and security review. Gate 5. Phase 6 starts.
* S15, weeks 29 to 30: Phase 6 billing, listing sources, WhatsApp.
* S16, week 31: Phase 6 platform tests and the first outside agency. Gate 6.
