# SellOS Tasks

This file is the backlog for building SellOS, in the BuildOS block format that `scripts/lib/tasks.py` reads. It was converted from the earlier `Tasks.md` on 4 November 2026 (107 stories, 523 points; the six DLT stories are Parked). The build loop (`scripts/build-loop.sh`) picks the next task from it. Read `docs/DEV_STRATEGY.md` and `docs/TESTING.md`.

## How the loop reads this file

* A task is a block that starts with `### SOS-<phase>-<number>: <title>`. Nothing else in this file may start with `### `, and prose belongs above the first block, because the loop sends everything up to the next `### ` to the agent as the task.
* Status values: Not Started, In Progress, Complete, Blocked, Waiting, Parked and Not Needed. The loop picks only Not Started tasks whose dependencies are all satisfied, choosing by Launch tier first (Dec 20 before Jan 1), then dependencies, then file order. A dependency is satisfied when it is Complete or Not Needed. It never picks Waiting, Parked or Not Needed tasks, and never reports a Not Needed one. A Blocked task stops the loop until a person resets it.
* `- **Launch:**` is the launch tier: Dec 20 or Jan 1. Everything is launch scope, and there is no "After launch". A Not Needed or Parked task says `none`.
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
6. Consent never blocks. A lead's consent status (Consented, Unknown, Opted out, Registered DND when known) is recorded and shown as a warning on the lead, the caller queue and the call log, and never prevents a call, an SMS or a WhatsApp message, in code or in the screens. Enforcement lives in one function behind the company setting "Consent enforcement", Off by default. An explicit stop request is recorded as Opted out with a red warning, and does not block. Calling hours stay a configurable setting.
7. Never build captcha solving or any bypass of access controls. Never commit a secret.
8. The 022 number is for service and transactional calls. A call's purpose is recorded, and a promotional purpose is shown as a warning.
9. Customers never use the Frappe desk. Every customer feature goes into the SellOS web app.
10. The product is called SellOS everywhere, exactly as BuildOS is called BuildOS, with no company or suite brand.
11. Tenant sites and the provisioner password (SOS-SETUP-22): create, drop, list and probe tenant sites only with `scripts/tenant-site.sh` or `sellos.provisioning.tenant_sites`, and get the MariaDB provisioner password only from `sellos.provisioning.credentials.get_provisioner_password()` (the variable, else the macOS Keychain item `sellos_provisioner`), which hands it to bench only through a child process's environment. Never run `security find-generic-password -w` (or any command that prints a secret), and never print, log or write the password. If `get_provisioner_password()` raises, reply NEEDS_INPUT with its message.

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

### SOS-N12: Request bulk or API access from the Department of Registration and Stamps
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want a formal request sent to the Department of Registration and Stamps, so that we know whether bulk or API access exists. Ask about bulk data, API access and licence terms. The outcome is uncertain, so this runs beside SOS-N11.
- **Acceptance Criteria:**
  - The request is sent and acknowledged.
  - The reply, or the absence of one after 30 days, is recorded.
- **Test Criteria:** Verified by the acknowledgement.
- **Owner:** Jayman, Counsel
- **Priority:** P0
- **Launch:** Jan 1
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Waiting

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

### SOS-N14: Open Razorpay and Stripe accounts
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want Razorpay and Stripe accounts with test keys, so that billing can be built in test mode. Open both accounts, complete their business verification, and generate test keys.
- **Acceptance Criteria:**
  - The Razorpay account is active with test keys.
  - The Stripe account is active with test keys.
  - Keys are stored in the password manager, never shared in chat or email.
- **Test Criteria:** Create one test subscription in each dashboard.
- **Owner:** Jayman, Accountant
- **Priority:** P0
- **Launch:** Jan 1
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Waiting

### SOS-N15: Confirm the GST invoice format
- **Epic:** Compliance, procurement and access
- **Description:** As the Accountant, I want to confirm the GST invoice format for SaaS subscriptions, so that invoices are compliant. Confirm invoice fields, GST treatment for Indian and overseas customers, numbering, and credit note rules.
- **Acceptance Criteria:**
  - A written format specification.
  - Examples for an Indian customer and an overseas customer.
- **Test Criteria:** The accountant approves a sample invoice produced by SOS-P6-06.
- **Owner:** Accountant
- **Priority:** P0
- **Launch:** Jan 1
- **Story Points:** 2
- **Dependencies:** SOS-N14
- **Status:** Waiting

### SOS-N16: Give Claude Code the access it needs
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want Claude Code to have the access it needs, so that Phase 0 can start. Grant read access to the BuildOS repository, create a SellOS GitHub organisation with Claude Code access, and create a scoped DigitalOcean token.
- **Acceptance Criteria:**
  - Claude Code can read BuildOS.
  - Claude Code can create repositories and branches in the SellOS organisation.
  - The token covers only the staging and production projects, with no billing or account level rights.
- **Test Criteria:** (1) Claude Code lists BuildOS files and creates a test branch. (2) A call using the token to delete the account is refused.
- **Owner:** Jayman
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 2
- **Dependencies:** none
- **Status:** Waiting

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

### SOS-N21: Choose the voice AI providers, call languages and disclosure line
- **Epic:** Compliance, procurement and access
- **Description:** As Jayman, I want the building blocks of the voice agent chosen, so that SOS-P5-07 is built on settled choices. Choose the speech to text, language model and text to speech providers, the languages the agent calls in, and the AI disclosure line it says at the start of every call. Added (Jayman, 10 November 2026).
- **Acceptance Criteria:**
  - The speech to text, language model and text to speech providers are named, with who holds the account and key for each.
  - The call languages are listed.
  - The exact AI disclosure line is written down in each call language.
- **Test Criteria:** Verified by Jayman.
- **Notes:** Record the choices here, in this block, for SOS-P5-07 to read.
- **Owner:** Jayman
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 1
- **Dependencies:** none
- **Status:** Waiting

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

### SOS-P0-04: Provision DigitalOcean
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want staging and production servers, so that SellOS has somewhere to run. Provision droplets, firewall, MariaDB, Redis and a Spaces bucket, with SSH key access and nightly backups.
- **Acceptance Criteria:**
  - Staging and production exist.
  - Only required ports are open.
  - MariaDB and Redis restart automatically after a reboot.
  - A nightly backup file appears in Spaces.
- **Test Criteria:** A port scan shows only the expected ports, and a server reboot brings every service back.
- **Notes:** DigitalOcean Bangalore, target 24 November 2026. AMP Labs does this work, so it is Waiting and the loop does not pick it (Jayman, 10 November 2026).
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-N18
- **Status:** Waiting

### SOS-P0-05: Create the wildcard DNS record and certificate
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want a wildcard record and certificate for the SellOS domain, so that every company subdomain works over HTTPS without manual steps. Create the wildcard record in DigitalOcean DNS and issue a wildcard certificate through the DNS API, with automatic renewal.
- **Acceptance Criteria:**
  - The wildcard record resolves to the server.
  - The certificate is valid for all subdomains.
  - Renewal runs automatically.
- **Test Criteria:** Two test hostnames serve valid HTTPS, and a renewal dry run succeeds.
- **Owner:** AMP Labs, Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P0-04
- **Status:** Not Started

### SOS-P0-06: Install the Frappe 16 bench with multitenancy
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want a Frappe 16 bench with DNS multitenancy, so that each hostname serves its own site. Install the bench pinned to Frappe 16.x, turn on DNS multitenancy and generate the nginx configuration.
- **Acceptance Criteria:**
  - The bench runs on staging.
  - Two sites on different subdomains serve separate data.
  - The Frappe version is pinned.
- **Test Criteria:** Create different content on two sites and confirm each hostname shows only its own.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P0-04
- **Status:** Not Started

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

### SOS-P0-08: Write the deployment scripts
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want scripted deployment and rolling upgrades, so that a release reaches every company site safely. Write one command to deploy a tagged release to staging, another to promote it to production, and a rolling upgrade that runs migrations site by site and stops on the first failure.
- **Acceptance Criteria:**
  - The deploy and promote commands work.
  - The rolling upgrade stops on failure and reports which site failed.
  - Rollback steps are documented.
- **Test Criteria:** Deploy to staging with two sites, force a migration failure on one, and confirm the run stops and reports it.
- **Owner:** Claude Code
- **Priority:** P0
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P0-06
- **Status:** Not Started

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

### SOS-P0-12: Set up monitoring and alerts
- **Epic:** Platform foundations and DevOps
- **Description:** As the platform team, I want uptime, error and disk alerts, so that problems are noticed before users report them. Monitor each site hostname, error rates, disk use and backup success, and send alerts to named people.
- **Acceptance Criteria:**
  - An uptime check exists for every site.
  - Alerts fire on errors, disk above 80 percent and failed backups.
  - Alerts reach named people.
- **Test Criteria:** Stop a service on staging and receive an alert within 5 minutes.
- **Notes:** AMP Labs work, so it is Waiting and the loop does not pick it (Jayman, 10 November 2026).
- **Owner:** AMP Labs
- **Priority:** P0
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P0-04
- **Status:** Waiting

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

### SOS-P1-14: Back up every site and prove the restore
- **Epic:** Platform foundations and DevOps
- **Description:** As Jayman, I want per site backups and a proven restore, so that no company's data is lost. Back up every site nightly to Spaces with 30 days of retention, and provide a script that restores one site to staging.
- **Acceptance Criteria:**
  - A backup per site exists each night.
  - Retention is 30 days.
  - The restore script recreates a site.
- **Test Criteria:** Restore a Pandya test site and compare record counts.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P1-02
- **Status:** Not Started

### SOS-P6-12: Run the restore, upgrade and load tests
- **Epic:** Platform foundations and DevOps
- **Description:** As Jayman, I want the platform proven under restore, upgrade and load, so that we can onboard other agencies safely. Run a full restore test, a rolling upgrade across 20 test sites, and a load test at an agreed number of concurrent users.
- **Acceptance Criteria:**
  - The restore completes within the agreed time.
  - The upgrade across 20 sites loses no data.
  - The load test meets the agreed response times.
- **Test Criteria:** A results report is stored, and every failure becomes a tracked bug before SOS-REG-6.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P0-08, SOS-P1-14
- **Status:** Not Started

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

### SOS-P5-10: Commission a security review
- **Epic:** Web app, roles and security
- **Description:** As Jayman, I want an independent security review, so that known risks are fixed before outside agencies join. Review API methods, roles, company isolation, file uploads, webhooks and secrets handling. Findings are rated, and all high findings are fixed before Gate 6.
- **Acceptance Criteria:**
  - A written report is delivered.
  - Findings are rated.
  - Every high finding is fixed and re tested.
- **Test Criteria:** Each high finding has a regression test.
- **Notes:** AMP Labs work, so it is Waiting and the loop does not pick it (Jayman, 10 November 2026).
- **Owner:** AMP Labs
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P1-05
- **Status:** Waiting

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

### SOS-P1-11: Create the Pandya Realtors site
- **Epic:** Multitenancy and provisioning
- **Description:** As Jayman, I want the Pandya Realtors company site live, so that the first tenant can start working. Create the Pandya site at its subdomain, apply the branding and load the users.
- **Acceptance Criteria:**
  - The site is live over HTTPS.
  - Admin and agent users exist.
  - Branding is applied.
- **Test Criteria:** Jayman signs in as each role and sees the correct screens.
- **Owner:** AMP Labs, Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-03
- **Status:** Waiting

### SOS-P1-07: Build the buyer pipeline
- **Epic:** Core CRM and consent
- **Description:** As an Agent, I want a buyer pipeline with clear stages, so that I know where every buyer stands. Build the stages New, Consent pending, Contacted, Qualified, Site visit booked, Site visit done, Negotiation, Booking, Closed won, Closed lost and Nurture. A lead may move to any stage whatever its consent status. Consent never blocks (Jayman, 10 November 2026). Moving a lead that is not Consented to Contacted is allowed, and its consent warning is recorded on the stage change.
- **Acceptance Criteria:**
  - All stages exist and a Company Admin can configure them within limits.
  - A lead in any consent status (Consented, Unknown, Opted out, Registered DND) can be moved to Contacted and to every other stage. Nothing in the code or the screens refuses it.
  - A move made while the lead is not Consented records the consent warning on the stage change, and the lead shows it.
  - Stage changes are logged.
- **Test Criteria:** Move a lead in each consent status to Contacted, confirm every move succeeds, and confirm the warning is recorded and shown for each status except Consented.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-06B, SOS-P1-08
- **Status:** Not Started
- **Browser spec:** required

### SOS-P1-08: Build the Consent Record
- **Epic:** Core CRM and consent
- **Description:** As Jayman, I want every lead to carry its consent status, so that whoever contacts a lead sees its lawful basis or the lack of one. Build the Consent Record with lead, basis (consent, inquiry or application), timestamp, evidence link and expiry. An inquiry basis expires after 7 days and an application after 3 months. Each lead has a consent status: Consented (a live Consent Record), Unknown (no live record, including an expired one), Opted out (an explicit stop request) or Registered DND (when a do not call result is known for the number). Consent never blocks (Jayman, 10 November 2026). The status is recorded and shown as a warning on the lead, the caller queue and the call log, and never prevents a call, an SMS or a WhatsApp message.
- **Acceptance Criteria:**
  - Each basis requires an evidence link, and a Consent Record without one is refused.
  - Expiry dates are set by basis.
  - Renewals are logged.
  - An expired record returns the lead's consent status to Unknown automatically.
  - An explicit stop request is recorded as Opted out, with its time and source, and shows a red warning. It does not block a call, an SMS or a WhatsApp message.
  - Registered DND is set when a do not call result is known for the number, and shows an amber warning.
  - The lead screen shows the consent status: an amber warning for Unknown and Registered DND, a red warning for Opted out, and no warning for Consented.
- **Test Criteria:** Time shifted tests for each expiry, a test that a record without evidence is refused, a test that a stop request is recorded as Opted out and blocks nothing, and a Cypress check of the warning on the lead screen for each status.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-06B
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
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P1-08
- **Status:** Not Started

### SOS-P1-10: Connect the Pandya website forms
- **Epic:** Core CRM and consent
- **Description:** As Jayman, I want the Pandya website forms connected to SellOS, so that enquiries arrive automatically. Point the form handlers at the endpoint, show the consent wording approved by counsel next to each form, and keep the website's own copy of each lead.
- **Acceptance Criteria:**
  - Each form posts to the endpoint.
  - The approved wording is shown.
  - Failures are retried and alerted.
  - The website still holds a copy.
- **Test Criteria:** Submit a form and see the lead in SellOS within a minute.
- **Owner:** AMP Labs
- **Priority:** P1
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P1-09
- **Status:** Waiting

### SOS-P1-12: Import the bought lead lists
- **Epic:** Core CRM and consent
- **Description:** As Jayman, I want the bought lead lists imported safely, so that they enter SellOS with an honest consent status. Build a CSV import that maps columns to leads, merges duplicates and gives every imported lead the consent status Unknown with the source bought list, or Registered DND when the file carries a known do not call result. Consent never blocks (Jayman, 10 November 2026). An imported lead can be called and messaged, and the warning is recorded each time.
- **Acceptance Criteria:**
  - Imported leads are Unknown, or Registered DND when the file says so, and show the warning.
  - Duplicates are merged.
  - An imported lead can be called, sent an SMS and sent a WhatsApp message, and the consent warning is recorded on each.
- **Test Criteria:** Import a sample with duplicates, verify the statuses and warnings, and confirm click to call proceeds and records the warning.
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-07
- **Status:** Not Started
- **Browser spec:** required

### SOS-P2-01: Build Telephony Settings
- **Epic:** Calling
- **Description:** As a Company Admin, I want to enter our Plivo details once, so that calling works for my company. Build a settings screen for both Plivo accounts with encrypted keys that are never shown after saving, and a test connection button.
- **Acceptance Criteria:**
  - Both accounts can be configured.
  - Keys are encrypted and no API returns them.
  - The test connection button reports success or the error.
  - Only Company Admins can open the screen.
- **Test Criteria:** A permission test blocks agents, and a test confirms keys never appear in API responses.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P1-04, SOS-N09
- **Status:** Not Started
- **Browser spec:** required

### SOS-P2-02: Build the provider adapter
- **Epic:** Calling
- **Description:** As a developer, I want one adapter interface for telephony providers, so that Plivo can be replaced later. Define the interface with place call, read webhook and fetch recording, and implement it for Plivo, mapping provider errors to clear messages.
- **Acceptance Criteria:**
  - The interface is documented.
  - The Plivo adapter places a call and reads its events.
  - Provider errors map to clear messages.
- **Test Criteria:** Unit tests with recorded provider responses, and one live test call.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P2-01
- **Status:** Not Started

### SOS-P2-03: Build the call router
- **Epic:** Calling
- **Description:** As the system, I want each call sent through the right account and number, so that calls follow the rules. Route +91 numbers through the India account and the 022 landline number, which is for service and transactional calls. International calling is dropped (Jayman, 10 November 2026), so +61, +971 and every other country code are refused with a clear message. A 140 series route is parked.
- **Acceptance Criteria:**
  - A +91 number is routed through the India account and the 022 number.
  - Each call records its purpose. A promotional purpose on the 022 number is recorded and shown as a warning on the call log. It is not refused.
  - Every other country code is refused with a clear message.
- **Test Criteria:** A table driven test of numbers and purposes against the expected account and series.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-02
- **Status:** Not Started

### SOS-P2-04: Build the consent status check and warnings
- **Epic:** Calling
- **Description:** As Jayman, I want every call, SMS and WhatsApp message to record the lead's consent status, so that the team sees the risk and no contact is lost to a block. Consent never blocks (Jayman, 10 November 2026). Build one function, the only place consent is evaluated, which every dial, SMS send and WhatsApp send calls first. It returns the lead's consent status (Consented, Unknown, Opted out, Registered DND when known) and its warning, and the warning is written to the call log or message log. Enforcement lives only in this function, behind the company setting "Consent enforcement", which is Off by default. With it Off the function never refuses anything. Calling hours are a separate setting (SOS-P2-10).
- **Acceptance Criteria:**
  - Every call, SMS and WhatsApp send goes through the one function, and no other code or screen checks consent or refuses on it.
  - With Consent enforcement Off, the default on a new company site, a call, an SMS and a WhatsApp message each proceed in every consent status, and the status and warning are recorded on the log entry.
  - Consent enforcement is a company setting, Off by default, that only a Company Admin can change, and every change is logged.
  - With Consent enforcement On, the same function refuses a contact to a lead that is not Consented, logs the refusal with its reason, and the screen explains it.
  - A promotional purpose on the 022 number is recorded as a warning, not refused.
- **Test Criteria:** A matrix of the four consent statuses against call, SMS and WhatsApp with Consent enforcement Off: every contact proceeds and the warning is recorded. The same matrix with it On: only Consented proceeds. A test that no module but the one function refuses on consent.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P1-08
- **Status:** Not Started

### SOS-P2-05: Extend the Call Log
- **Epic:** Calling
- **Description:** As an Agent and a Company Admin, I want every call recorded with its cost, so that we can review and report on calling. Extend the Call Log with provider, call ID, manual or AI mode, duration, billed duration, cost in rupees, hangup cause, recording link, outcome and consent reference, linked to the lead.
- **Acceptance Criteria:**
  - One log exists per call.
  - It links to the lead and the consent record.
  - Cost is stored in rupees.
- **Test Criteria:** Unit tests of cost conversion, and a test that a placed call creates a log.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-02
- **Status:** Not Started

### SOS-P2-06: Build the webhook endpoint
- **Epic:** Calling
- **Description:** As the system, I want Plivo's call events received safely, so that the Call Log is accurate. Build a whitelisted endpoint that verifies Plivo's signature, ignores replayed events, updates the Call Log with answer, hangup, duration and recording link, and fetches the recording after the call.
- **Acceptance Criteria:**
  - Valid events update the log.
  - Invalid signatures are rejected.
  - Replayed events change nothing.
  - The recording link is stored after the call ends.
- **Test Criteria:** Tests for valid, invalid signature, replayed and out of order events.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-05
- **Status:** Not Started

### SOS-P2-07: Build click to call
- **Epic:** Calling
- **Description:** As an Agent, I want to click a lead and be connected, so that I can call without dialling. Add a click to call button that rings the agent's Indian mobile first and then the lead, shows the lead's consent status as a warning, and asks for the outcome after the call. Both call legs must stay in India.
- **Acceptance Criteria:**
  - The agent's phone rings first.
  - The lead is connected after the agent answers.
  - The lead's consent status and warning show before and during the call, and a lead in any consent status can be called. Consent never blocks (Jayman, 10 November 2026).
  - An agent number outside India shows a clear error.
  - An outcome form is required after the call.
- **Test Criteria:** An end to end test with two test phones, and a test of the media anchoring error path.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P2-03, SOS-P2-04, SOS-P2-06
- **Status:** Not Started
- **Browser spec:** required

### SOS-P2-08: Build the inbound opt in route
- **Epic:** Calling
- **Description:** As Jayman, I want bought leads given a way to respond, so that they can become callable leads. Give bought leads ways to come to us: a missed call to the 022 number, a link to the enquiry page shared through WhatsApp or ads, and the website forms. A missed call or form submission creates an inquiry Consent Record with a 7 day clock. An explicit stop request is recorded as Opted out with a red warning, and does not block. Consent never blocks (Jayman, 10 November 2026). The SMS route is parked with the Tata DLT stories.
- **Acceptance Criteria:**
  - A missed call to the 022 number is detected without the call being answered.
  - A missed call creates a Consent Record and moves the lead.
  - The enquiry page records the consent wording.
  - A stop request, by call, form or message, is recorded as Opted out and shows a red warning on the lead, the caller queue and the call log. It does not block a later call, SMS or WhatsApp message.
- **Test Criteria:** Give a missed call from a test number, submit the enquiry page, and confirm the record and the lead state. Check the Plivo statement to see whether the rejected call is billed.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P2-04
- **Status:** Not Started
- **Browser spec:** required

### SOS-P2-09: Build the caller queue
- **Epic:** Calling
- **Description:** As the caller, I want a queue of leads ordered by urgency with each lead's consent status shown, so that no consent window is wasted and every risk is visible. Show every lead the caller may call: Consented leads first, soonest expiry first, with the time left, then the rest. Each lead shows its consent warning. Consent never blocks (Jayman, 10 November 2026). No lead is dropped from the queue for its consent status.
- **Acceptance Criteria:**
  - Every lead the caller may see appears, whatever its consent status.
  - Consented leads come first, soonest expiry first, with the time left shown.
  - Each lead shows its consent status: an amber warning for Unknown and Registered DND, a red warning for Opted out.
- **Test Criteria:** Seed leads in every consent status and with different expiries, and check the order and the warnings.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P2-04
- **Status:** Not Started
- **Browser spec:** required

### SOS-P2-10: Make calling hours a setting and flag do not call numbers
- **Epic:** Calling
- **Description:** As Jayman, I want calling hours set by the company and do not call numbers flagged, so that callers see the rules. Calling hours stay a configurable company setting (start, end and days, India time). A do not call list can be imported and checked, and a number on it gives the lead the consent status Registered DND with a warning. Consent never blocks (Jayman, 10 November 2026). A do not call number is never refused by this task: only the one consent function of SOS-P2-04 may refuse, and only when Consent enforcement is On. International calling is dropped, so the rules are for India.
- **Acceptance Criteria:**
  - Calling hours are a company setting that a Company Admin can change, and a call outside them is refused with the hours in the message.
  - A do not call list can be imported. A listed number gives the lead Registered DND with an amber warning on the lead, the caller queue and the call log, and the call proceeds.
- **Test Criteria:** Boundary time tests for the calling hours, and a call to a listed number that proceeds with the warning recorded.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-04, SOS-N10
- **Status:** Not Started
- **Browser spec:** required

### SOS-P2-11: Build call reports
- **Epic:** Calling
- **Description:** As a Company Admin, I want calling reports, so that I can see cost and performance. Build reports for cost by country and by agent, connect rate, talk time and consent coverage, with date filters.
- **Acceptance Criteria:**
  - Each report filters by date.
  - Totals match the Call Log.
  - Each figure drills down to calls.
- **Test Criteria:** Reconcile the totals with Plivo's statement for a test month.
- **Owner:** Claude Code
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P2-05
- **Status:** Not Started
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

### SOS-P2-13: Make and check test calls
- **Epic:** Calling
- **Description:** As Jayman, I want test calls proven end to end, so that we trust the setup before real use. The Indian number, +91 22 6998 6373, is already bought. Place test calls to India, Australia and UAE numbers and check cost and recordings.
- **Acceptance Criteria:**
  - Calls to all three countries complete.
  - Logged cost is within an agreed tolerance of Plivo's statement.
  - Recordings play.
- **Test Criteria:** Reconcile the Call Log with the Plivo statement.
- **Owner:** Jayman
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P2-07
- **Status:** Waiting

### SOS-P2-14: Onboard the first caller and start the baseline
- **Epic:** Calling
- **Description:** As Jayman, I want the first caller trained and a baseline measured, so that the AI pilot has something to beat. Train the caller on the app and script, have them work from the caller queue, which shows each lead's consent warning, and track the four week baseline metrics.
- **Acceptance Criteria:**
  - The caller completes training.
  - The caller works from the caller queue and reads each lead's consent warning before calling.
  - Baseline metrics are tracked weekly.
- **Test Criteria:** A weekly baseline report is produced for four weeks.
- **Owner:** Jayman
- **Priority:** P2
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P2-13
- **Status:** Waiting

### SOS-P3-01: Build the source adapter
- **Epic:** Market intelligence
- **Description:** As a developer, I want one adapter interface for registration data sources, so that SellOS works with whichever source we secure. Define the interface with fetch batch and map fields, and build the adapter for the source chosen through SOS-N11 or SOS-N12, running on a schedule with failure alerts.
- **Acceptance Criteria:**
  - The interface is documented.
  - The adapter for the chosen source ingests a batch.
  - Runs are scheduled and failures raise alerts.
  - The adapter never solves captchas or bypasses access controls.
- **Test Criteria:** Contract tests with sample payloads, and a test that a failed run raises an alert.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-N11, SOS-N12
- **Status:** Not Started

### SOS-P3-02: Create the raw transaction table
- **Epic:** Market intelligence
- **Description:** As a data engineer, I want every record stored untouched, so that cleaning can always be repeated from the original. Store each record exactly as received, with its source, fetch time and a hash.
- **Acceptance Criteria:**
  - Original fields are unchanged.
  - Source, fetch time and hash are stored.
  - Re runs do not create duplicates.
- **Test Criteria:** Ingest the same batch twice and confirm there are no duplicates.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P3-01
- **Status:** Not Started

### SOS-P3-03: Build the normaliser
- **Epic:** Market intelligence
- **Description:** As an Agent, I want clean, comparable figures, so that rates mean the same thing across records. Translate or transliterate Marathi names and property text into English, standardise dates, parse consideration and market value, and convert areas to carpet area in square feet, recording the rule used.
- **Acceptance Criteria:**
  - English fields are filled and the original is kept.
  - Dates are standard.
  - Areas are in carpet square feet with the conversion rule recorded.
  - Unparseable records go to a review list.
- **Test Criteria:** A golden file of 100 verified records, with an accuracy threshold agreed with Jayman.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-02
- **Status:** Not Started

### SOS-P3-04: Build the building and micro market master
- **Epic:** Market intelligence
- **Description:** As an Agent, I want buildings and micro markets defined, so that transactions roll up the way agents think. Define micro markets for the Bandra to Andheri corridor with boundaries, and buildings and projects with CTS numbers and RERA numbers where known, editable by admins.
- **Acceptance Criteria:**
  - Micro markets and boundaries exist.
  - Buildings carry CTS and RERA numbers where known.
  - Admins can edit them.
- **Test Criteria:** Twenty buildings are verified by agents.
- **Owner:** Claude Code, Jayman
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-02
- **Status:** Not Started

### SOS-P3-05: Build the matcher
- **Epic:** Market intelligence
- **Description:** As an Agent, I want each transaction tied to the right building, so that comparables are trustworthy. Match using CTS or survey number, address and RERA number, give each match a confidence score, and send low confidence records to a review queue.
- **Acceptance Criteria:**
  - Each record gets a match or a review status.
  - Confidence is stored.
  - Reviewer decisions are saved and reused.
- **Test Criteria:** Precision and recall are measured on 200 hand matched records.
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
  - They finish within the agreed window.
  - Failures raise alerts.
- **Test Criteria:** Recompute a known sample by hand and compare.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-05
- **Status:** Not Started

### SOS-P3-08: Build the comparables API and profiles
- **Epic:** Market intelligence
- **Description:** As an Agent, I want comparables and building profiles, so that I can price and advise with evidence. Build an API that returns comparables for a building, project or micro market with filters, and screens for building and project profiles showing five year trend, volume, resale against primary, and price against the ready reckoner.
- **Acceptance Criteria:**
  - The API filters by area, floor, date and type.
  - Profiles show trend, volume and price against the ready reckoner.
  - Every figure links to its records.
  - Role permissions apply.
- **Test Criteria:** API tests, and an end to end view of a known building.
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
- **Test Criteria:** Back test against 50 known sales and report the error.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-08
- **Status:** Not Started
- **Browser spec:** required

### SOS-P3-10: Build the agent assistant
- **Epic:** Market intelligence
- **Description:** As an Agent, I want to ask market questions in plain language, so that I get answers grounded in records. Build an assistant that answers only through query tools, lists the records behind every answer, refuses to guess, logs questions and respects role limits on party names.
- **Acceptance Criteria:**
  - Answers cite records.
  - Unknown buildings get a clear refusal.
  - Party names are hidden where the role forbids them.
  - Questions are logged.
- **Test Criteria:** A scripted question set with expected tool calls, and a test with an unknown building to confirm it does not invent figures.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P3-08
- **Status:** Not Started
- **Browser spec:** required

### SOS-P3-11: Build alerts for watched buildings
- **Epic:** Market intelligence
- **Description:** As an Agent, I want alerts on watched buildings, so that I hear about new sales first. Let agents watch buildings, and send an in app and email alert when a new registration appears, with a frequency cap.
- **Acceptance Criteria:**
  - Agents can watch and unwatch buildings.
  - New registrations create alerts.
  - The cap limits repeats.
- **Test Criteria:** Ingest a test record in a watched building.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P3-07
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
- **Test Criteria:** Permission tests for each role.
- **Owner:** Claude Code
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-N13, SOS-P3-02
- **Status:** Not Started
- **Browser spec:** required

### SOS-P3-13: Load and verify five years of data
- **Epic:** Market intelligence
- **Description:** As Jayman, I want five years of corridor data loaded and checked, so that agents can trust it. Load five years of Bandra to Andheri data and check 50 records against Index II.
- **Acceptance Criteria:**
  - Five years are loaded.
  - 50 records are checked against Index II.
  - The accuracy is reported and discrepancies are logged.
- **Test Criteria:** An audit report with the sample and the results.
- **Owner:** Jayman
- **Priority:** P3
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-05
- **Status:** Waiting

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
- **Status:** Not Started
- **Browser spec:** required

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
- **Status:** Not Started
- **Browser spec:** required

### SOS-P4-03: Build Media Asset
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want photos and videos linked to listings, so that listings look complete. Link media from the asset library to listings, with size and type checks and an order.
- **Acceptance Criteria:**
  - Media attaches to a listing.
  - Invalid files are rejected.
  - The order can be changed.
- **Test Criteria:** Upload valid and invalid files.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P4-02
- **Status:** Not Started
- **Browser spec:** required

### SOS-P4-04: Build the seller pipeline
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want a seller pipeline, so that owners are tracked to a signed mandate and a sale. Build the stages New owner enquiry, Qualified, Valuation shared, Mandate proposed, Mandate signed, Listed, Offers received, Sold, Closed lost and Nurture.
- **Acceptance Criteria:**
  - All stages exist.
  - Stage rules are enforced, such as no Listed stage without a signed mandate.
  - Changes are logged.
- **Test Criteria:** Stage rule tests.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P4-02
- **Status:** Not Started
- **Browser spec:** required

### SOS-P4-05: Build Mandate
- **Epic:** Inventory, mandates and deals
- **Description:** As an owner and an Agent, I want a mandate recorded, so that the Private Sale Dossier is shared only against a signed agreement. Build Mandate as exclusive or open with term, fee and a signed document upload. The Dossier is released only when the mandate is signed, and each view is audited.
- **Acceptance Criteria:**
  - Mandates carry type, term and fee.
  - The signed document is required.
  - The Dossier is hidden until signed.
  - Each Dossier view is logged.
- **Test Criteria:** Try to open the Dossier without a signed mandate and confirm it fails.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P4-04
- **Status:** Not Started
- **Browser spec:** required

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
- **Status:** Not Started
- **Browser spec:** required

### SOS-P4-07: Attach comparables to listings and mandates
- **Epic:** Inventory, mandates and deals
- **Description:** As an Agent, I want comparables and a valuation range on listing and mandate screens, so that I can advise with evidence. Show comparables and the valuation range with links to the underlying records, hidden when the data licence does not allow it.
- **Acceptance Criteria:**
  - Comparables appear on both screens.
  - Each links to its records.
  - They are hidden if the licence forbids showing them.
- **Test Criteria:** An end to end check on a known building, and a test of the licence switch.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P3-09, SOS-P4-05
- **Status:** Not Started
- **Browser spec:** required

### SOS-P4-08: Build the listings endpoint
- **Epic:** Inventory, mandates and deals
- **Description:** As the website, I want a read only listings endpoint, so that listings appear without manual entry. Build an endpoint, keyed per company, that returns published listings, plus a webhook that announces changes, with caching.
- **Acceptance Criteria:**
  - Only published listings are returned.
  - Changes trigger the webhook.
  - A bad key is rejected.
- **Test Criteria:** Contract tests and a change push test.
- **Owner:** Claude Code
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P4-02
- **Status:** Not Started

### SOS-P4-09: Switch the website to read listings from SellOS
- **Epic:** Inventory, mandates and deals
- **Description:** As Jayman, I want the Pandya website to show listings from SellOS, so that nothing is entered twice. Render the listing pages from the endpoint, remove unpublished listings within the agreed time, and fall back safely if the endpoint is down.
- **Acceptance Criteria:**
  - Pages render from the endpoint.
  - Unpublishing removes a listing within the agreed time.
  - An outage shows the last good copy.
- **Test Criteria:** Toggle a listing and check the site, and simulate an outage.
- **Owner:** AMP Labs
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P4-08
- **Status:** Waiting

### SOS-P4-10: Import current listings and mandates
- **Epic:** Inventory, mandates and deals
- **Description:** As Jayman, I want current listings and mandates imported, so that SellOS holds the real business. Import Pandya's current listings and mandates and reconcile the counts with the source sheet.
- **Acceptance Criteria:**
  - Imports complete.
  - Counts reconcile.
  - Duplicates are resolved.
- **Test Criteria:** A reconciliation report signed off by Jayman.
- **Owner:** AMP Labs, Jayman
- **Priority:** P4
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P4-05
- **Status:** Waiting

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
- **Status:** Not Started
- **Browser spec:** required

### SOS-P5-02: Build the agent and Company Admin reports
- **Epic:** Reporting
- **Description:** As an Agent and a Company Admin, I want the standard reports, so that I can run the business from data. For agents: my pipeline, calls and outcomes, follow ups due and site visits. For Company Admins: lead funnel and conversion by stage, source performance, agent productivity, call reports, listing and mandate ageing, and deal pipeline and commission.
- **Acceptance Criteria:**
  - Every listed report exists.
  - Each filters by date.
  - Each reconciles with its raw data.
- **Test Criteria:** Reconcile every report against raw data.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P5-01, SOS-P4-06, SOS-P2-11
- **Status:** Not Started
- **Browser spec:** required

### SOS-P5-03: Build the Channel Partner and Platform reports
- **Epic:** Reporting
- **Description:** As a Channel Partner and a Platform Admin, I want my reports, so that I can track results. Build Channel Partner reports for own leads, deals and commission statements, and Platform Admin reports for companies, usage and calling spend. The revenue, churn and failed payment panels switch on once billing data exists.
- **Acceptance Criteria:**
  - Partners see only their own data.
  - Platform reports cover companies, usage and calling spend.
  - Revenue panels activate after billing is live.
- **Test Criteria:** Permission tests, and a check of the totals.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P5-01
- **Status:** Not Started
- **Browser spec:** required

### SOS-P5-04: Build saved views, export and scheduling
- **Epic:** Reporting
- **Description:** As a Company Admin, I want to save, export and schedule reports, so that results reach the right people. Add saved filters, CSV and PDF export, and scheduled email delivery with recipients, all scoped by role.
- **Acceptance Criteria:**
  - Views can be saved and shared.
  - Exports match the screen.
  - Scheduled emails arrive on time.
  - Recipients only get data they may see.
- **Test Criteria:** Compare an export with the screen, and run a scheduled email.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P5-01
- **Status:** Not Started
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
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P4-05
- **Status:** Not Started
- **Browser spec:** required

### SOS-P5-06: Build the Channel Partner views
- **Epic:** Client and partner views
- **Description:** As a Channel Partner, I want to register leads and track my deals, so that I can work with Pandya. Build partner views to register leads with consent, see shared inventory, and track their own deals and commission status. Added at SOS-P1-06 (Jayman): the partner also sees earnings so far, potential future earnings, and a QR code specific to them for sharing sales materials. SOS-P1-06 already gives partners their own leads and the timeline of those leads, read only.
- **Acceptance Criteria:**
  - Leads can be registered with consent wording. A lead registered without it is saved with consent status Unknown and a warning. Consent never blocks (Jayman, 10 November 2026).
  - Shared inventory is visible.
  - Deals and commission status show only the partner's own, with earnings so far, potential earnings and the partner's QR code.
  - Partners cannot see other partners' leads.
- **Test Criteria:** Permission tests, and an end to end test of registering a lead.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P4-06
- **Status:** Not Started
- **Browser spec:** required

### SOS-P5-07: Build the voice agent service
- **Epic:** Voice AI pilot
- **Description:** As Jayman, I want an AI voice agent that can hold a short qualifying call, so that we can test AI calling safely. Build a service that receives call audio from Plivo by audio streaming, uses the speech to text, language model and text to speech providers and the call languages chosen in SOS-N21, reads lead context from SellOS and writes the outcome back. It opens every call with the AI disclosure line chosen in SOS-N21 and hands over to a human on request or confusion.
- **Acceptance Criteria:**
  - A live call connects to the agent over audio streaming.
  - The agent opens every call with the AI disclosure line from SOS-N21.
  - It hands over to a human on request or confusion.
  - It writes the outcome and transcript to the Call Log.
  - It runs the consent function of SOS-P2-04 before each call and records the consent status and warning on the Call Log. It never refuses a call on consent while Consent enforcement is Off. Consent never blocks (Jayman, 10 November 2026).
  - It records each call's purpose, and a promotional purpose on the 022 number is recorded as a warning.
- **Test Criteria:** Scripted test calls covering normal, interruption, silence and handover cases, and a latency measurement against the agreed target.
- **Owner:** Claude Code
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 8
- **Dependencies:** SOS-P2-03, SOS-P2-04, SOS-N21
- **Status:** Not Started

### SOS-P5-08: Run the AI pilot
- **Epic:** Voice AI pilot
- **Description:** As Jayman, I want a controlled AI pilot, so that we learn before scaling. Run 400 AI calls over about four weeks in one language, reviewing transcripts weekly. While only the 022 number exists, the calls are limited to service and transactional purposes, such as site visit confirmations and follow ups for existing clients, so the pilot design may change or wait until the number series question is settled. Any complaint stops the pilot for review.
- **Acceptance Criteria:**
  - 400 calls are completed, or the pilot is stopped with a recorded reason.
  - Transcripts are reviewed weekly.
  - Complaints are logged, and zero are required to continue.
- **Test Criteria:** A weekly review log is kept.
- **Owner:** Jayman
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 5
- **Dependencies:** SOS-P5-07, SOS-P2-14
- **Status:** Waiting

### SOS-P5-09: Compare AI with the human baseline
- **Epic:** Voice AI pilot
- **Description:** As Jayman, I want AI and human calling compared fairly, so that we decide whether to scale. Compare connect rate, qualified lead rate, site visits booked, cost per qualified lead, handover rate and complaints, using the four week human baseline.
- **Acceptance Criteria:**
  - A comparison report covers all six measures.
  - The data reconciles with the Call Log.
  - A go or no go decision is recorded.
- **Test Criteria:** Reconcile the report with the raw data.
- **Owner:** Jayman, Claude Code
- **Priority:** P5
- **Launch:** Dec 20
- **Story Points:** 3
- **Dependencies:** SOS-P5-08
- **Status:** Not Started

### SOS-P6-01: Build the billing records
- **Epic:** Billing and subscriptions
- **Description:** As a Platform Admin, I want plans, coupons, subscriptions, invoices and payments recorded, so that billing has a foundation. Build Plan, Coupon, Subscription, Invoice and Payment on the control site, with limits on each plan.
- **Acceptance Criteria:**
  - All five records exist.
  - A plan defines limits such as users and listings.
  - A subscription links one company to one plan.
- **Test Criteria:** Unit tests of the records and their relationships.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P1-01
- **Status:** Not Started

### SOS-P6-02: Define the plan tiers
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want sensible plan tiers, so that pricing is clear. Claude Code reads how BuildOS structures its plans, in the read only reference copy at `~/iespl-baseline/buildos-reference`, and proposes SellOS tiers in the same shape. Jayman approves the limits and prices.
- **Acceptance Criteria:**
  - A proposal is delivered.
  - Limits and prices are approved in writing.
  - The approved tiers are loaded as plans.
- **Test Criteria:** Verified by the written approval and the loaded plan records. Limit enforcement is tested in SOS-P6-04.
- **Notes:** SOS-SETUP-21: read BuildOS code only in the read only reference copy at `~/iespl-baseline/buildos-reference`, with ls, cat, grep and find, and never write into it. Never read, list or run anything under `apps/buildos`.
- **Owner:** Claude Code, Jayman
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P0-01
- **Status:** Not Started

### SOS-P6-03: Build the Razorpay adapter and recurring payments
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want Indian customers charged automatically, so that revenue is predictable. Build a gateway interface and the Razorpay adapter with subscription creation, cancellation and webhooks, in test mode first.
- **Acceptance Criteria:**
  - A test subscription is created and renews.
  - Webhooks update the subscription.
  - Webhook handling is idempotent.
  - Failed payments are recorded.
- **Test Criteria:** Sandbox subscriptions through renewal and failure.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-N14, SOS-P6-01
- **Status:** Not Started

### SOS-P6-15: Build the Stripe adapter
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want overseas customers charged automatically, so that international agencies can subscribe. Build the Stripe adapter behind the same gateway interface, with subscriptions, cancellation and webhooks, in test mode first. This story was split out of the original gateway task to keep each story within 8 points.
- **Acceptance Criteria:**
  - A test subscription renews.
  - Webhooks update the subscription.
  - Webhook handling is idempotent.
  - A customer is routed to Stripe or Razorpay by country.
- **Test Criteria:** Sandbox subscriptions through renewal and failure, and a routing test.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P6-03
- **Status:** Not Started

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
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
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
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P6-01
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-06: Build GST compliant invoices
- **Epic:** Billing and subscriptions
- **Description:** As Jayman, I want compliant invoices, so that customers and the tax authority are satisfied. Generate an invoice for every payment in the format the accountant confirms, with GST for Indian customers and the correct treatment for overseas customers, numbered in sequence.
- **Acceptance Criteria:**
  - Each payment has a numbered invoice.
  - GST is shown for Indian customers.
  - Overseas invoices follow the confirmed treatment.
  - Credit notes are supported.
- **Test Criteria:** The accountant approves sample invoices.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-N15, SOS-P6-01
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-07: Build self service sign up
- **Epic:** Billing and subscriptions
- **Description:** As a new agency, I want to sign up and start using SellOS without waiting, so that onboarding is quick. Build a sign up flow that collects company details, plan and payment, then triggers provisioning and the setup wizard.
- **Acceptance Criteria:**
  - A new company can sign up and pay.
  - Provisioning starts automatically.
  - The company receives login details.
  - Failed payments do not create a site.
- **Test Criteria:** An end to end test in test mode from sign up to first login.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P6-04, SOS-P1-03
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-08: Build the listing scraper for registries and developer sites
- **Epic:** Listing sources and WhatsApp
- **Description:** As an Agent, I want listings from public registries and developer sites collected automatically, so that inventory data is not entered by hand. Build Source and Raw Listing records and scheduled collection for RERA registries and developer websites, with polite rate limits, respect for each site's access rules, RERA number matching, a review queue and an on and off switch per source.
- **Acceptance Criteria:**
  - Each source has a switch and a last run log.
  - Collection respects rate limits and each site's access rules.
  - Records are matched on RERA number.
  - Nothing publishes without review approval.
- **Test Criteria:** A dry run against saved pages for each source, and a test that a changed page layout raises an alert instead of loading bad data.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P4-02
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-09: Review each portal's terms
- **Epic:** Listing sources and WhatsApp
- **Description:** As Jayman, I want each listing portal's terms reviewed, so that we only use sources we are allowed to use. Review each portal's terms and any official feed or partner access, and switch on only the sources that pass.
- **Acceptance Criteria:**
  - A decision is recorded for each portal.
  - Only approved sources are enabled.
  - Rejected sources stay off.
- **Test Criteria:** Verified by the decision log and the source switches.
- **Owner:** Jayman, Counsel
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 3
- **Dependencies:** SOS-P6-08
- **Status:** Waiting

### SOS-P6-10: Build the Facebook capture assist
- **Epic:** Listing sources and WhatsApp
- **Description:** As an Agent, I want to save a Facebook post to SellOS myself, so that group listings reach our review queue without automated collection. Build a browser extension or share target so that an agent signed in as themselves saves or shares a post, which is parsed into a draft listing in the review queue. Personal data of posters is handled as counsel advises.
- **Acceptance Criteria:**
  - An agent can save a post in two taps or clicks.
  - The post becomes a draft in the review queue.
  - No automated collection runs against Facebook.
  - Poster personal data follows the counsel rules.
- **Test Criteria:** Capture 20 sample posts and check the parsing, and a test that nothing is collected without an agent action.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P6-08
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-11: Build the WhatsApp channel foundation
- **Epic:** Listing sources and WhatsApp
- **Description:** As Jayman, I want WhatsApp working per company, so that each agency has its own number and templates. Build the WhatsApp channel foundation in SellOS: a per company number and templates, inbound and outbound messages, Leads and Consent Records created from conversations, and handoff to a human agent.
- **Acceptance Criteria:**
  - A company can connect its own number.
  - Messages create or update leads.
  - An opt in creates a consent record.
  - A stop request in a conversation is recorded as Opted out with a red warning, and does not block later messages.
  - Every send goes through the consent function of SOS-P2-04 and records the consent status and warning. None is refused while Consent enforcement is Off. Consent never blocks (Jayman, 10 November 2026).
  - A conversation can be handed to a human.
- **Test Criteria:** An end to end test on a sandbox number with inbound, outbound and handoff.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P1-08
- **Status:** Not Started
- **Browser spec:** required

### SOS-P6-16: Rebuild WhatsApp flows, group one
- **Epic:** Listing sources and WhatsApp
- **Description:** As an Agent, I want the lead qualification, NRI buyer and investor flows, so that WhatsApp enquiries are qualified automatically. Rebuild these flows from the existing WhatsApp CRM designs inside SellOS. Each flow asks its questions, scores the lead and hands over to an agent when needed. This story and SOS-P6-17 were split out of the original rebuild task to keep each within 8 points.
- **Acceptance Criteria:**
  - Each flow runs end to end.
  - Answers are stored on the lead.
  - Handoff works from each flow.
  - Each flow records the lead's consent status and shows its warning to the agent, and never stops a message on consent while Consent enforcement is Off. Consent never blocks (Jayman, 10 November 2026).
- **Test Criteria:** Scripted conversations through each flow on a sandbox number.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P6-11
- **Status:** Not Started

### SOS-P6-17: Rebuild WhatsApp flows, group two
- **Epic:** Listing sources and WhatsApp
- **Description:** As an Agent, I want the site visit booking, cold lead nurture, human handoff and remaining flows, so that WhatsApp supports the whole journey. Rebuild the remaining flows from the existing designs, including booking site visits into the agent's calendar and nurture messages for cold leads recording each lead's consent status.
- **Acceptance Criteria:**
  - Site visits are booked from WhatsApp.
  - Nurture messages go through the consent function of SOS-P2-04 and record each lead's consent status and warning. A stop request is recorded as Opted out with a red warning and does not block. Consent never blocks (Jayman, 10 November 2026).
  - Handoff passes the full conversation.
  - All ten flows are live.
- **Test Criteria:** Scripted conversations through each flow, including an opt out.
- **Owner:** Claude Code
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 8
- **Dependencies:** SOS-P6-11
- **Status:** Not Started

### SOS-P6-13: Prepare legal terms and the support process
- **Epic:** Launch readiness
- **Description:** As Jayman, I want legal terms and a support process, so that other agencies can be onboarded responsibly. Prepare the terms of service, privacy policy, data processing terms and a support process with a status page.
- **Acceptance Criteria:**
  - Counsel approves the terms, privacy policy and data processing terms.
  - They are shown and accepted at sign up.
  - A support channel and response targets exist.
  - A status page is live.
- **Test Criteria:** A sign up test confirms that acceptance is recorded.
- **Owner:** Jayman, Counsel
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P6-07
- **Status:** Waiting

### SOS-P6-14: Onboard the first outside agency
- **Epic:** Launch readiness
- **Description:** As Jayman, I want one outside agency onboarded as a pilot, so that we prove the platform with a real customer. Onboard a friendly agency through the sign up flow, support them for two weeks, and record every issue.
- **Acceptance Criteria:**
  - The agency signs up and pays in live or agreed mode.
  - Their data is isolated from Pandya's.
  - Issues are logged and triaged.
  - SOS-REG-6 is Complete.
- **Test Criteria:** A cross company isolation check on live data, and a review of the issue log.
- **Owner:** Jayman
- **Priority:** P6
- **Launch:** Jan 1
- **Story Points:** 5
- **Dependencies:** SOS-P6-07, SOS-P6-12, SOS-P5-10
- **Status:** Waiting

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
- **Dependencies:** SOS-N12, SOS-N14, SOS-N15, SOS-N16, SOS-N21, SOS-P0-01, SOS-P0-02, SOS-P0-03, SOS-P0-04, SOS-P0-05, SOS-P0-06, SOS-P0-07, SOS-P0-06L, SOS-P0-08, SOS-P0-09, SOS-P0-12, SOS-P1-06A, SOS-P1-06B, SOS-P1-14, SOS-P6-12, SOS-P0-10, SOS-P1-04, SOS-P1-05, SOS-P1-13, SOS-P5-10, SOS-P0-11, SOS-P1-01, SOS-P1-02, SOS-P1-03, SOS-P1-11, SOS-P1-07, SOS-P1-08, SOS-P1-09, SOS-P1-10, SOS-P1-12, SOS-P2-01, SOS-P2-02, SOS-P2-03, SOS-P2-04, SOS-P2-05, SOS-P2-06, SOS-P2-07, SOS-P2-08, SOS-P2-09, SOS-P2-10, SOS-P2-11, SOS-P2-13, SOS-P2-14, SOS-P3-01, SOS-P3-02, SOS-P3-03, SOS-P3-04, SOS-P3-05, SOS-P3-06, SOS-P3-07, SOS-P3-08, SOS-P3-09, SOS-P3-10, SOS-P3-11, SOS-P3-12, SOS-P3-13, SOS-P4-01, SOS-P4-02, SOS-P4-03, SOS-P4-04, SOS-P4-05, SOS-P4-06, SOS-P4-07, SOS-P4-08, SOS-P4-09, SOS-P4-10, SOS-P5-01, SOS-P5-02, SOS-P5-03, SOS-P5-04, SOS-P5-05, SOS-P5-06, SOS-P5-07, SOS-P5-08, SOS-P5-09, SOS-P6-01, SOS-P6-02, SOS-P6-03, SOS-P6-15, SOS-P6-04, SOS-P6-05, SOS-P6-06, SOS-P6-07, SOS-P6-08, SOS-P6-09, SOS-P6-10, SOS-P6-11, SOS-P6-16, SOS-P6-17, SOS-P6-13, SOS-P6-14, SOS-REG-A, SOS-REG-B, SOS-REG-C, SOS-FIX-1
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
- **Owner:** Claude Code
- **Priority:** P1
- **Launch:** Dec 20
- **Story Points:** 1
- **Dependencies:** SOS-P0-10
- **Status:** Not Started
- **Browser spec:** required

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
