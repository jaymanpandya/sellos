# SellOS backlog audit (SOS-SETUP-33, 13 November 2026)

Every task in `TASKS.md` whose status was not Complete, Not Needed or Parked on 13 November 2026 (85
tasks) was read and checked against the code under `sellos/` and `frontend/`, `CLAUDE.md`, and the
decisions in `docs/DEV_STRATEGY.md` section 9 (consent never blocks, calls in Hinglish, the product is
called SellOS with no company or suite brand, customers never use the desk). The fixes follow the model
of SOS-SETUP-31 (a supersede note when two tasks define the same data) and of SOS-P0-06L and SOS-P0-04
(row 26: building and deploying are separate tasks). No Status of an existing task was changed, and no
block was deleted. SOS-N21A stays Blocked, as committed. Jayman answered the questions on 13
November 2026, and SOS-SETUP-34 applied the answers: see "Jayman's answers" at the end.

Key to the problem column: **X** mixes code with deployment, a live account or human acceptance;
**O** overlaps another task's data; **C** contradicts a decision or a rule; **M** missing dependency;
**A** ambiguous acceptance criterion; **P** needs a provider (Plivo, WhatsApp, payments, Facebook, a
language model) and now has a fake provider plus a live test.

## Summary

| Task | Outside needs | Problems found | Fix |
| --- | --- | --- | --- |
| SOS-N12 DoRS bulk access | Department of Registration and Stamps, counsel | Now the only data source (SOS-N11 Not Needed) | Feeds SOS-P3-01L only; question 8 |
| SOS-N14 Razorpay and Stripe accounts | Both gateways, Accountant | none | Now feeds SOS-P6-03L and SOS-P6-15L, not the code |
| SOS-N15 GST invoice format | Accountant | C: its test needs SOS-P6-06's output, while SOS-P6-06 waited on it; depends on SOS-N14 for no stated reason | SOS-P6-06 split; question 17 |
| SOS-N16 Claude Code access | GitHub, DigitalOcean token | Mostly done; the token is only for deploy work AMP Labs now owns | None; mark it Complete or Not Needed by hand |
| SOS-N21 Choose voice providers | Sarvam, Deepgram, ElevenLabs keys, a language model, Jayman's recordings | Live bake-off run was implicit | Note: the live run is part of this task |
| SOS-N21A Bake-off harness (Blocked) | none (fakes only) | C: recording 08's spoken number trips the raw phone guard in tests | Note: spoken numbers in tests come from `sellos.tests.phones`; question 1 |
| SOS-P0-04 Provision DigitalOcean | AMP Labs, DigitalOcean | none | none |
| SOS-P0-05 Wildcard DNS and certificate | DigitalOcean DNS token, AMP Labs | X | Split: code here, SOS-P0-05D Waiting |
| SOS-P0-06 Frappe bench with multitenancy | Servers, AMP Labs | X | Split: install script here, SOS-P0-06D Waiting |
| SOS-P0-08 Deployment scripts | Staging | X, M (local bench) | Split: tested on local tenant sites, SOS-P0-08D Waiting |
| SOS-P0-12 Monitoring and alerts | AMP Labs, alert tool | M (backups) | Depends on SOS-P1-14D |
| SOS-P1-14 Backups and restore | Spaces keys, AMP Labs | X | Split: code with a local store, SOS-P1-14D Waiting |
| SOS-P6-12 Restore, upgrade, load tests | Staging, agreed numbers | X, A, C (names SOS-REG-6) | Split: scripts here, SOS-P6-12D Waiting; question 9 |
| SOS-P5-10 Security review | AMP Labs, a reviewer | C (names "Gate 6") | Now "before SOS-P6-14" |
| SOS-P1-11 Pandya site | Production server, AMP Labs | M | Depends on SOS-P0-05D, SOS-P0-06D |
| SOS-P1-07 Buyer pipeline | none | Fixed by SOS-SETUP-31 | SOS-P4-04 now declares its overlap |
| SOS-P1-09 Website lead endpoint | none | O (intake with SOS-P2-08, key with SOS-P4-08), A (evidence link) | Note; depends on SOS-P2-08 |
| SOS-P1-10 Pandya website forms | AMP Labs, the website | C: "wording approved by counsel", but SOS-N07 is Not Needed | Note; question 5 |
| SOS-P1-12 Bought lead import | The bought lists | C/M: tests calls, SMS and WhatsApp that do not exist yet (SMS parked); O (DND) | Criterion moved to SOS-P2-04 and SOS-P2-07; note |
| SOS-P2-01 Telephony Settings | Plivo (via fake) | C: "both accounts" (SOS-N09 Not Needed); O (interface); P | One account; fake provider; note |
| SOS-P2-02 Provider adapter | Plivo | X (live call), P | Live call moved to SOS-P2-02L |
| SOS-P2-03 Call router | none | P | Note: fake provider |
| SOS-P2-04 Consent check | none | O (consent fields on the Call Log and messages), A (no log exists, SMS parked) | Owns a Consent Check record; note |
| SOS-P2-05 Call Log | none | C: "extend" a Call Log that does not exist (no ERPNext); O; M | Creates it, links Consent Check; depends on SOS-P2-04 |
| SOS-P2-06 Webhook endpoint | Public HTTPS address for live events | P | Note: fake signing key; live in SOS-P2-02L |
| SOS-P2-07 Click to call | Two real phones | X, P | Test through the fake; real call in SOS-P2-13 |
| SOS-P2-08 Inbound opt in route | Plivo statement | X, M, O (intake), A ("moves the lead", wording) | Depends on SOS-P2-06; owns the intake function; questions 5, 6 |
| SOS-P2-09 Caller queue | none | none | none |
| SOS-P2-10 Calling hours and DND | none | M, O (DND with SOS-P1-12) | Depends on SOS-P2-03, P2-05, P2-09; note |
| SOS-P2-11 Call reports | Plivo statement | C ("cost by country"), X | By agent and purpose; reconciliation in SOS-P2-13 |
| SOS-P2-13 Test calls | Plivo, phones | C (Australia, UAE), A (tolerance), M | India only; holds the live checks; question 9 |
| SOS-P2-14 First caller and baseline | A caller | A (timing against Dec 20) | Question 4 |
| SOS-P3-01 Source adapter | A data source | M: hung on SOS-N11 (Not Needed) and SOS-N12 | Split: file adapter and fake now, SOS-P3-01L Waiting |
| SOS-P3-02 Raw transaction table | none | Which site holds it is undecided | Question 8 |
| SOS-P3-03 Normaliser | 100 verified records | A (threshold "agreed with Jayman") | Question 9 |
| SOS-P3-04 Building master | Boundaries, agents | X | Split: SOS-P3-04A Waiting |
| SOS-P3-05 Matcher | 200 hand matched records | A | Question 9 |
| SOS-P3-06 Outliers | none | none | none |
| SOS-P3-07 Nightly jobs | Mail for alerts | A ("agreed window") | Questions 9, 16 |
| SOS-P3-08 Comparables and profiles | Ready reckoner rates | A: no task supplies the ready reckoner | Question 8 |
| SOS-P3-09 Valuation range | 50 known sales | A | Question 9 |
| SOS-P3-10 Agent assistant | A language model and key | P, M (party names) | Fake model; depends on SOS-P3-12; SOS-P3-10L Waiting |
| SOS-P3-11 Watched building alerts | Mail | Outgoing mail has no task | Question 16 |
| SOS-P3-12 Party name rules | Counsel | C: "rules from SOS-N13", which is Not Needed | Note; question 7 |
| SOS-P3-13 Load five years | Index II, the source | M | Depends on SOS-P3-01L, SOS-P3-04A |
| SOS-P4-01 Developer, Project, Unit | none | none | none |
| SOS-P4-02 Listing | none | Draft listings also come from SOS-P6-08 and SOS-P6-10 (declared there) | none |
| SOS-P4-03 Media Asset | none | A ("asset library" undefined) | Question 11 |
| SOS-P4-04 Seller pipeline | none | O (Pipeline Stage), M (Listed rule needs Mandate), A (seller record) | Supersede note; rule moved to SOS-P4-05; question 11 |
| SOS-P4-05 Mandate | none | A (Dossier undefined) | Takes the Listed rule; question 11 |
| SOS-P4-06 Deal and Commission Split | none | none | none |
| SOS-P4-07 Comparables on listings | Data licence | A (licence switch has no source) | Question 8 |
| SOS-P4-08 Listings endpoint | none | O (per company key), M | Depends on SOS-P1-09; note |
| SOS-P4-09 Website reads listings | AMP Labs, website | A ("agreed time") | Question 9 |
| SOS-P4-10 Import listings and mandates | Pandya's sheets | C: no importer, and Data Import is a desk tool | SOS-P4-10C builds the import |
| SOS-P5-01 Report engine | none | none | none |
| SOS-P5-02 Agent and Admin reports | none | O (call reports of SOS-P2-11) | Note: register, do not rebuild |
| SOS-P5-03 Partner and Platform reports | none | C risk (Platform Admin and CRM data), M | Totals only; depends on SOS-P2-05 |
| SOS-P5-04 Saved views, export, scheduling | Mail | C (only the Platform Admin may bulk export) | Note; questions 12, 16 |
| SOS-P5-05 Client views | none | A ("shortlist" undefined) | Question 11 |
| SOS-P5-06 Channel Partner views | none | C (names Pandya; partner is read only), M | "the company"; depends on SOS-P2-08; question 13 |
| SOS-P5-07 Voice agent service | Plivo streaming, chosen providers | X, P, M (Call Log, locked by a test) | Fakes; SOS-P5-07L Waiting; question 3 |
| SOS-P5-08 AI pilot | Plivo, providers, callers | C ("one language"), M (locked by a test), A (purposes, timing) | Hinglish; note; questions 3, 4 |
| SOS-P5-09 AI against human baseline | none | X (owners mixed) | Split: SOS-P5-09A Waiting; question 3 |
| SOS-P6-01 Billing records | none | O (Plan stub of SOS-P1-01; Coupon with SOS-P6-05) | Supersede note |
| SOS-P6-02 Plan tiers | Jayman's approval | X | Split: SOS-P6-02A Waiting |
| SOS-P6-03 Razorpay adapter | Razorpay | P, X | Fake gateway; SOS-N14 moved to SOS-P6-03L |
| SOS-P6-15 Stripe adapter | Stripe | P, X | Fake gateway; SOS-P6-15L Waiting |
| SOS-P6-04 Billing lifecycle | Mail | "test mode" unclear | Note: fake gateway |
| SOS-P6-05 Coupons | none | O (Coupon fields) | Note |
| SOS-P6-06 GST invoices | Accountant | X, circular with SOS-N15 | Split: SOS-P6-06A Waiting; question 17 |
| SOS-P6-07 Self service sign up | none | "test mode" unclear | Note: fake gateway |
| SOS-P6-08 Listing scraper | none | A (a source's initial switch) | Every source starts Off |
| SOS-P6-09 Portal terms | Counsel | none | none |
| SOS-P6-10 Facebook capture assist | Facebook, counsel | P, C (counsel rules have no source), A (extension or share target) | Fixtures; SOS-P6-10L Waiting; questions 7, 15 |
| SOS-P6-11 WhatsApp foundation | WhatsApp provider, Meta verification | P, X, M (consent function) | Fake provider; depends on SOS-P2-04; SOS-P6-11L Waiting; question 14 |
| SOS-P6-16 WhatsApp flows 1 | Flow designs | P, A (where the designs are) | Fake provider; question 14 |
| SOS-P6-17 WhatsApp flows 2 | Flow designs | P, A ("ten flows", "calendar") | Fake provider; question 14 |
| SOS-P6-13 Legal terms and support | Counsel, status page | X (acceptance at sign up is code) | Split: SOS-P6-13C code |
| SOS-P6-14 First outside agency | An agency, live payments | C (names SOS-REG-6), M | Criterion rewritten; six dependencies added |
| SOS-REG-A, B, C | Claude in chat | none | none |
| SOS-REG-L | Claude in chat | Must depend on every active task | 19 new tasks added |
| SOS-FIX-1 Unknown path | none | none (router still has no catch-all) | none |

### New tasks

| New task | Split from | Owner | Status | Depends on |
| --- | --- | --- | --- | --- |
| SOS-P0-05D Run the wildcard DNS and certificate setup | SOS-P0-05 | AMP Labs | Waiting | SOS-P0-04, SOS-P0-05 |
| SOS-P0-06D Install the bench on staging and production | SOS-P0-06 | AMP Labs | Waiting | SOS-P0-04, SOS-P0-06 |
| SOS-P0-08D Prove the deployment scripts on staging | SOS-P0-08 | AMP Labs | Waiting | SOS-P0-06D, SOS-P0-08 |
| SOS-P1-14D Nightly backups to Spaces, restore on staging | SOS-P1-14 | AMP Labs | Waiting | SOS-P0-04, SOS-P0-06D, SOS-P1-14 |
| SOS-P6-12D Restore, upgrade and load tests on staging | SOS-P6-12 | AMP Labs, Jayman | Waiting | SOS-P0-08D, SOS-P1-14D, SOS-P6-12 |
| SOS-P2-02L Live test the Plivo adapter and webhook | SOS-P2-01, P2-02, P2-06 | Jayman | Waiting | SOS-P2-01, SOS-P2-02, SOS-P2-06 |
| SOS-P3-01L Ingest the first real batch | SOS-P3-01 | Jayman | Waiting | SOS-N12, SOS-P3-01 |
| SOS-P3-04A Supply and verify the corridor buildings | SOS-P3-04 | Jayman | Waiting | SOS-P3-04 |
| SOS-P3-10L Live test the agent assistant | SOS-P3-10 | Jayman | Waiting | SOS-P3-10 |
| SOS-P4-10C Build the listings and mandates import | SOS-P4-10 | Claude Code | Not Started | SOS-P4-05, SOS-P1-12 |
| SOS-P5-07L Live test the voice agent | SOS-P5-07 | Jayman | Waiting | SOS-P5-07, SOS-N21, SOS-P2-02L |
| SOS-P5-09A Record the AI go or no go decision | SOS-P5-09 | Jayman | Waiting | SOS-P5-09 |
| SOS-P6-02A Approve the plan limits and prices | SOS-P6-02 | Jayman | Waiting | SOS-P6-02 |
| SOS-P6-03L Live test Razorpay in test mode | SOS-P6-03 | Jayman | Waiting | SOS-N14, SOS-P6-03 |
| SOS-P6-15L Live test Stripe in test mode | SOS-P6-15 | Jayman | Waiting | SOS-N14, SOS-P6-15 |
| SOS-P6-06A The accountant approves sample invoices | SOS-P6-06 | Accountant | Waiting | SOS-N15, SOS-P6-06 |
| SOS-P6-10L Live test the Facebook capture assist | SOS-P6-10 | Jayman | Waiting | SOS-P6-10 |
| SOS-P6-11L Live test WhatsApp on a real number | SOS-P6-11 | Jayman | Waiting | SOS-P6-11 |
| SOS-P6-13C Record acceptance of the terms at sign up | SOS-P6-13 | Claude Code | Not Started | SOS-P6-07 |

Suffixes: D is the deploy half, L the live provider or source test, A a person's acceptance, C a code
half split from a Waiting task. (SOS-P0-06L already means "local", so the P0-06 deploy half is D.)
Every new ID matches the ID pattern of `scripts/lib/tasks.py` and of `scripts/check_no_stale_skips.py`.

## Counts

* Tasks audited: 85 (61 Not Started, 23 Waiting, 1 Blocked). Tasks with at least one problem or a
  needed update: 71. Clean: 14 (SOS-N14, P0-04, P1-07, P2-09, P3-06, P4-01, P4-02, P4-06, P5-01,
  P6-09, REG-A, REG-B, REG-C, FIX-1).
* Tasks that mixed code with deployment, a live account or a person's acceptance: 19 tasks split into
  19 new tasks (17 Waiting halves, 2 code halves). Three more live checks (SOS-P2-07, SOS-P2-08,
  SOS-P2-11) were moved into the existing Waiting SOS-P2-13.
* Tasks that need Plivo, WhatsApp, a payment gateway, Facebook or a language model, now written as
  "fake provider behind an adapter, live test owned by Jayman": 17 (SOS-P2-01, P2-02, P2-03, P2-06,
  P2-07, P2-08, P2-11, P3-10, P5-07, P6-03, P6-15, P6-04, P6-07, P6-10, P6-11, P6-16, P6-17).
* Overlaps (two tasks defining the same data), each now with a note saying which wins: 10 (stage list
  SOS-P1-07/P4-04; Plan SOS-P1-01/P6-01; Coupon SOS-P6-01/P6-05; consent fields SOS-P2-04/P2-05/P6-11;
  lead intake SOS-P2-08/P1-09/P5-06; per company key SOS-P1-09/P4-08; do not call SOS-P1-12/P2-10;
  telephony interface SOS-P2-01/P2-02; call reports SOS-P2-11/P5-02; keyterms SOS-N21A/P5-07).
* Contradictions with a decision or a rule: 19. Fixed in the text: 14 (SOS-N21A, N15 with P6-06, P1-12,
  P2-01, P2-05, P2-11, P2-13, P4-10, P5-03, P5-06's company name, P5-08, P5-10, P6-12, P6-14). Noted
  and left as questions: 5 (SOS-P1-10, P3-12 and P6-10 cite counsel tasks that are Not Needed; SOS-P5-04
  export; SOS-P5-06 partner create).
* Dependency edges added to existing tasks: 27 (plus the 19 new tasks on SOS-REG-L). Edges removed
  from a code half: 6 (SOS-P0-04 off SOS-P0-05 and P0-06, SOS-N11 and N12 off SOS-P3-01, SOS-N14 off
  SOS-P6-03, SOS-N15 off SOS-P6-06); SOS-P0-04, SOS-N12, SOS-N14 and SOS-N15 now sit on the new Waiting
  halves, and SOS-N11 (Not Needed) was dropped. Dangling dependencies: 0. Cycles: 0.
* Ambiguous acceptance criteria left for a decision: 21, in questions 4 to 15.
* Effect on the loop: SOS-P0-05, SOS-P0-06, SOS-P0-08 and the code of SOS-P1-14 and SOS-P6-12 no
  longer wait for servers, and SOS-P3-01 no longer waits for SOS-N12. Nothing is picked while SOS-N21A
  is Blocked (question 1).

Checks run on the edited file: `scripts/select-next-task.sh TASKS.md` prints `BLOCKED_EXISTS:SOS-N21A`
(as committed). `python3 scripts/lib/tasks.py order` on a temporary copy with SOS-N21A reset lists 62
tasks, starting SOS-N21A, SOS-P0-05, SOS-P0-06, SOS-P0-08, SOS-P1-07. A separate check found no
dangling dependency and no cycle, no unknown status, every active task in a tier, SOS-REG-L depending
on exactly every other active task, no other task depending on a SOS-REG task, the voice chain
dependencies unchanged (locked by `test_the_voice_pilot_chain`), and the SOS-P1-07 strings that
`test_tasks_selection.py` asserts still present.

Not changed, for a person to decide: the epic counts at the top of `TASKS.md` are now out of date,
and SOS-P2-10 still lists SOS-N10 (Not Needed, so harmless).

## Per task

### Compliance, procurement and access

* **SOS-N12** (Waiting, Jayman, Counsel). Outside: DoRS and counsel. With SOS-N11 Not Needed it is the
  only planned source, and its outcome is uncertain. Fix: SOS-P3-01's code no longer waits for it;
  only SOS-P3-01L does. Question 8.
* **SOS-N14** (Waiting). Outside: Razorpay, Stripe, the Accountant. Now holds up only the live tests
  SOS-P6-03L and SOS-P6-15L.
* **SOS-N15** (Waiting, Accountant). Its test is "the accountant approves a sample invoice produced
  by SOS-P6-06", while SOS-P6-06 depended on it. Fix: SOS-P6-06 builds with a format setting;
  SOS-P6-06A holds the approval. Its dependency on SOS-N14 has no stated reason (question 17).
* **SOS-N16** (Waiting). Claude Code reads BuildOS through the reference copy and the repository
  exists; only the DigitalOcean token remains, and the deploy halves are AMP Labs' work. No fix;
  SOS-REG-L depends on it, so a person should close it.
* **SOS-N21** (Waiting). Outside: three provider keys, a language model, Jayman's recordings. Note
  added: the live bake-off run (record, store keys, `--live`, rating sheet) is part of this task.
* **SOS-N21A** (Blocked, status left as committed). The 5c6a5c6 Block: a test that writes recording
  08's spoken phone number trips `test_no_raw_phone_numbers.py`, and the agent disguised the number
  (row 36). Note added: spoken numbers in tests are made from `sellos.tests.phones` by a helper. The
  recovery is on `wip/SOS-N21A-recovery-20261113`. Question 1.

### Platform foundations and DevOps

* **SOS-P0-04** (Waiting, AMP Labs). Clean. Depends on SOS-N18 (Not Needed, satisfied).
* **SOS-P0-05** (Not Started). X: owned by "AMP Labs, Claude Code" and waiting on servers. Split: the
  code (DigitalOcean DNS API script, certificate config, dry run, fake API tests, token from
  `SELLOS_DO_TOKEN`) stays, owner Claude Code, no dependency; SOS-P0-05D (AMP Labs, Waiting) holds the
  original criteria.
* **SOS-P0-06** (Not Started). X. Split: `deploy/install-bench.sh` with a dry run, the pinned version
  checked against `ci.yml`, and a refusal for an existing bench (`~/iespl-bench` included, SOS-SETUP-20);
  SOS-P0-06D runs it on staging and production.
* **SOS-P0-08** (Not Started). X. Split: the rolling upgrade is tested on two local tenant sites with
  a forced migration failure; deploy and promote in dry run. M: SOS-P0-06L added. SOS-P0-08D proves it
  on staging.
* **SOS-P0-12** (Waiting). M: the failed backup alert needs backups; depends on SOS-P1-14D.
* **SOS-P1-14** (Not Started). X: "nightly to Spaces" and "restore to staging". Split: backup, prune
  and restore with a store interface (local folder for tests, Spaces with keys from the environment),
  tested on local tenant sites; no new package. SOS-P1-14D schedules it on production.
* **SOS-P6-12** (Not Started). X, A ("agreed time", "agreed response times"), C ("before SOS-REG-6",
  which is Not Needed). Split: scripts with targets in one settings file, tested at small scale
  locally; SOS-P6-12D runs on staging and turns failures into SOS-FIX tasks. Question 9.

### Web app, roles and security

* **SOS-P5-10** (Waiting, AMP Labs). C: "before Gate 6"; there are no gates. Now "before SOS-P6-14".

### Multitenancy and provisioning

* **SOS-P1-11** (Waiting). M: a live HTTPS site needs the production bench and the certificate;
  depends on SOS-P0-05D and SOS-P0-06D.

### Core CRM and consent

* **SOS-P1-07** (Not Started). Clean after SOS-SETUP-31. The seller pipeline overlap is declared in
  SOS-P4-04, not here, so the strings `test_tasks_selection.py` checks are untouched.
* **SOS-P1-09** (Not Started). O: SOS-P2-08's enquiry page also turns a form into a Lead and a
  Consent Record, and SOS-P4-08 also needs a per company key. A: SOS-P1-08 accepts only a web address
  or `/files/` path as evidence. Fix: SOS-P2-08 owns `sellos.crm.intake`; this endpoint calls it; the
  key record has a scope; evidence is the raw submission as a private file. Depends on SOS-P2-08.
* **SOS-P1-10** (Waiting, AMP Labs). C: "consent wording approved by counsel", but SOS-N07 is Not
  Needed. Note; question 5.
* **SOS-P1-12** (Not Started, next after SOS-P1-07). C/M: its third criterion needs click to call
  (SOS-P2-07), SMS (parked) and WhatsApp (SOS-P6-11), none of which exist when it runs, so the gate
  could not pass honestly. Fix: the criterion now says the import sets nothing that stops contact,
  and SOS-P2-04's matrix proves an imported lead proceeds. O: do not call results go only through
  `record_dnd_result` (`sellos/crm/consent.py`), shared with SOS-P2-10.

### Calling

* **SOS-P2-01** (Not Started). C: "both Plivo accounts", but SOS-N09 is Not Needed. P. O: the test
  connection button needs an adapter before SOS-P2-02. Fix: one India account; the interface starts
  here with `test_connection` and a fake; SOS-P2-02 extends it; real keys in SOS-P2-02L.
* **SOS-P2-02** (Not Started). X: "one live test call". Fix: recorded responses and the fake; the live
  call, the real webhook and the real keys are SOS-P2-02L (Jayman, Waiting).
* **SOS-P2-03** (Not Started). Note: tests route through the fake.
* **SOS-P2-04** (Not Started). O and A: it writes the warning "to the call log or message log", but no
  Call Log exists (no ERPNext, `sellos/sellos/doctype/` has none), SOS-P2-05 also puts a consent
  reference on the Call Log, SOS-P6-11 adds messages, and SMS is parked. Fix: this task owns a Consent
  Check record (one per check, dynamic link to its log entry); the Call Log and messages link to it and
  define no consent fields; the SMS channel is tested through the function only.
* **SOS-P2-05** (Not Started). C: "Extend the Call Log" when none exists. Fix: it creates the DocType,
  with purpose and the Consent Check link. M: depends on SOS-P2-04.
* **SOS-P2-06** (Not Started). P. Outside: Plivo can reach a webhook only at a public HTTPS address.
  Fix: fake signing key and recorded events; real events in SOS-P2-02L. Question 2.
* **SOS-P2-07** (Not Started). X: "two test phones". Fix: both legs through the fake; real phones in
  SOS-P2-13.
* **SOS-P2-08** (Not Started). X: "check the Plivo statement". M: missed calls arrive through the
  webhook (SOS-P2-06). O: intake. A: "moves the lead" names no stage; the wording has no source. Fix:
  the statement check moved to SOS-P2-13; depends on SOS-P2-06; owns `sellos.crm.intake`; wording is a
  company setting; evidence is a private file. Questions 5 and 6.
* **SOS-P2-09** (Not Started). Clean.
* **SOS-P2-10** (Not Started). M: the warning shows on the caller queue and the call log, and the hours
  check sits in the dial path. Fix: depends on SOS-P2-03, SOS-P2-05, SOS-P2-09. O: do not call shares
  `record_dnd_result`. Refusing outside calling hours stays allowed (decision: calling hours stay a
  setting) and stays out of the consent function.
* **SOS-P2-11** (Not Started). C: "cost by country" with international calling dropped. X:
  reconciliation with Plivo's statement. Fix: by agent and purpose; seeded Call Logs; the statement in
  SOS-P2-13.
* **SOS-P2-13** (Waiting, Jayman). C: calls to Australia and the UAE. A: "agreed tolerance". Fix:
  India only; it now holds the live checks of SOS-P2-07, P2-08 and P2-11; depends on SOS-P2-02L,
  P2-08, P2-11. Question 9.
* **SOS-P2-14** (Waiting, Jayman). Outside: a caller. A: a four week baseline that starts after the
  calling build cannot end by 20 December. Question 4.

### Market intelligence

* **SOS-P3-01** (Not Started). M: waited on SOS-N11 (Not Needed) and SOS-N12 (uncertain). Fix: the
  interface, a file adapter, a fake source, the schedule and alerts are built now; SOS-P3-01L ingests
  the first real batch. Question 8.
* **SOS-P3-02** (Not Started). Which site holds market data is not decided: one database per company
  (CLAUDE.md decision 1) against data shared by every agency. Question 8.
* **SOS-P3-03** (Not Started). A: "accuracy threshold agreed with Jayman", and who verifies the 100
  golden records. Question 9.
* **SOS-P3-04** (Not Started). X: "Twenty buildings are verified by agents", owner "Claude Code,
  Jayman". Split: code with a sample corridor file; SOS-P3-04A (Jayman) supplies and verifies.
* **SOS-P3-05** (Not Started). A: precision and recall on 200 hand matched records, no target, no
  source. Question 9.
* **SOS-P3-06** (Not Started). Clean.
* **SOS-P3-07** (Not Started). A: "the agreed window". Alerts need outgoing mail. Questions 9 and 16.
* **SOS-P3-08** (Not Started). A: "price against the ready reckoner" needs ready reckoner rates that
  no task supplies. Question 8.
* **SOS-P3-09** (Not Started). A: a back test on 50 known sales needs real data and an error target.
  Question 9.
* **SOS-P3-10** (Not Started). P: a language model and its key. M: the party name limits are
  SOS-P3-12's. Fix: model behind an adapter with a fake that scripts tool calls; depends on SOS-P3-12;
  SOS-P3-10L (Jayman). Question 10.
* **SOS-P3-11** (Not Started). Outgoing mail has no task. Question 16.
* **SOS-P3-12** (Not Started). C: applies "the rules from SOS-N13", which is Not Needed, and the task
  touches personal data. Note; question 7.
* **SOS-P3-13** (Waiting, Jayman). M: needs the real source and the verified buildings; depends on
  SOS-P3-01L and SOS-P3-04A.

### Inventory, mandates and deals

* **SOS-P4-01** (Not Started). Clean.
* **SOS-P4-02** (Not Started). Clean. Draft listings from SOS-P6-08 and SOS-P6-10 reach Listing only
  after review (declared in SOS-P6-08).
* **SOS-P4-03** (Not Started). A: "the asset library" is not defined anywhere. Question 11.
* **SOS-P4-04** (Not Started). O: Pipeline Stage (`stage_name`, `position`, `stage_type`) has no
  pipeline field, so seller stages would mix with the buyer stages of SOS-P1-03 and SOS-P1-07. M: the
  rule "no Listed stage without a signed mandate" needs Mandate, which SOS-P4-05 builds after this
  task. A: is a seller a Lead or a record of its own? Fix: supersede note (a `pipeline` field, a patch
  setting existing stages to Buyer, limits per pipeline, assertions must not fall); the Listed rule
  moved to SOS-P4-05. Question 11.
* **SOS-P4-05** (Not Started). A: "Private Sale Dossier" is not defined. Takes the Listed rule.
  Question 11.
* **SOS-P4-06** (Not Started). Clean.
* **SOS-P4-07** (Not Started). A: "hidden when the data licence does not allow it": the licence came
  from SOS-N11, which is Not Needed. Question 8.
* **SOS-P4-08** (Not Started). O and M: a second per company key. Fix: adds a Listings read scope to
  SOS-P1-09's key record; depends on SOS-P1-09.
* **SOS-P4-09** (Waiting, AMP Labs). A: "within the agreed time". Question 9.
* **SOS-P4-10** (Waiting). C: no task built an importer, and Frappe's Data Import is a desk tool
  (CLAUDE.md decision 4). Fix: SOS-P4-10C (Claude Code) builds it in the web app, reusing SOS-P1-12's
  import code; SOS-P4-10 depends on it.

### Reporting, client and partner views

* **SOS-P5-01** (Not Started). Clean.
* **SOS-P5-02** (Not Started). O: "call reports" are SOS-P2-11's. Note: register them on the engine,
  keep their tests.
* **SOS-P5-03** (Not Started). C risk: the Platform Admin sees no company CRM data by role. M: calling
  spend needs the Call Log. Fix: totals per company only; depends on SOS-P2-05.
* **SOS-P5-04** (Not Started). C: CLAUDE.md lets only the Platform Admin bulk export. Outgoing mail.
  Note; questions 12 and 16.
* **SOS-P5-05** (Not Started). A: no task defines a shortlist. Question 11.
* **SOS-P5-06** (Not Started). C: "work with Pandya" names a company in the product; CLAUDE.md makes
  partners read only, but they register leads here. M: registration uses the intake function. Fix:
  "work with the company"; depends on SOS-P2-08. Question 13.

### Voice AI pilot

* **SOS-P5-07** (Not Started). X and P: "A live call connects". M: the latency and transcript fields
  belong on SOS-P2-05's Call Log, but `test_the_voice_pilot_chain` locks this task's dependencies.
  Fix: fakes for the stream and all three providers; SOS-P5-07L (Jayman) holds the real calls; note
  that SOS-P2-05 comes first in the same tier. Question 3.
* **SOS-P5-08** (Waiting). C: "in one language"; now Hinglish. M: must not start before SOS-P5-07L, but
  the test locks its dependencies, so it is a note. A: pilot purposes on the 022 number and timing.
  Questions 3 and 4.
* **SOS-P5-09** (Not Started). X: owners "Jayman, Claude Code". Split: the report is Claude Code's;
  SOS-P5-09A (Jayman) records the decision. Question 3.

### Billing and subscriptions

* **SOS-P6-01** (Not Started). O: SOS-P1-01 already made a Plan (`plan_name`, `enabled`,
  `max_users`) that Tenant links to and the worker writes into `sellos_limits`
  (`sellos/provisioning/tenant_setup.py`). O: Coupon fields with SOS-P6-05. Fix: supersede note (extend
  the same Plan, keep the fields, records carry over, update SOS-P1-01 and P1-02 tests without losing
  assertions).
* **SOS-P6-02** (Not Started). X: proposal, approval and loading in one task. Split: proposal and a
  loader from one data file; SOS-P6-02A (Jayman) approves.
* **SOS-P6-03** (Not Started). P and X: "test mode first", depends on SOS-N14. Fix: fake gateway and
  recorded webhooks; SOS-P6-03L holds SOS-N14 and the sandbox run.
* **SOS-P6-15** (Not Started). P and X. Same fix; SOS-P6-15L.
* **SOS-P6-04** (Not Started). Note: "test mode" means the fake gateway. Outgoing mail (question 16).
* **SOS-P6-05** (Not Started). O: Coupon fields are SOS-P6-01's. Note.
* **SOS-P6-06** (Not Started). X and circular with SOS-N15. Split: builds from a format setting;
  SOS-P6-06A (Accountant) approves, after SOS-N15. Question 17.
* **SOS-P6-07** (Not Started). Note: fake gateway; terms acceptance is SOS-P6-13C.

### Listing sources and WhatsApp

* **SOS-P6-08** (Not Started). A: nothing said a source starts Off. Fix: every source is Off until
  SOS-P6-09's decision (CLAUDE.md decision 10 holds).
* **SOS-P6-09** (Waiting, Jayman, Counsel). Clean.
* **SOS-P6-10** (Not Started). P: Facebook. C: "as counsel advises" with no counsel task. A: browser
  extension or share target. Fix: parser behind a capture interface, saved post fixtures, no request
  to Facebook; SOS-P6-10L (Jayman). Questions 7 and 15.
* **SOS-P6-11** (Not Started). P: no provider named; each company connects its own number (Meta
  business verification). M: every send goes through SOS-P2-04's function. Fix: fake provider; depends
  on SOS-P2-04; messages link to a Consent Check; SOS-P6-11L (Jayman). Question 14.
* **SOS-P6-16** (Not Started). P; A: "the existing WhatsApp CRM designs" are not in the repository.
  Fix: fake provider. Question 14.
* **SOS-P6-17** (Not Started). P; A: "all ten flows" are not listed; "the agent's calendar" is taken
  to be Site Visit. Fix: fake provider. Question 14.

### Launch readiness

* **SOS-P6-13** (Waiting, Jayman, Counsel). X: "shown and accepted at sign up" is code. Split:
  SOS-P6-13C (Claude Code) records versioned acceptance.
* **SOS-P6-14** (Waiting, Jayman). C: "SOS-REG-6 is Complete" (Not Needed). M: legal terms, live
  payments, approved prices and invoices, the staging proof. Fix: criterion names the scheduled
  regressions; depends on SOS-P6-12D, P6-13, P6-13C, P6-02A, P6-03L, P6-06A.

### Regression

* **SOS-REG-A, SOS-REG-B, SOS-REG-C** (Waiting). Clean.
* **SOS-REG-L** (Waiting). Now depends on the 19 new tasks too.
* **SOS-FIX-1** (Not Started). Clean; `frontend/src/router.js` still has no catch-all route.

### Checked and found clean on the decisions

No active task blocks on consent, uses English only voice, or names a suite brand, and no code under
`frontend/src`, `sellos/www`, `sellos/templates` or `sellos/spa.py` names AMP Labs or Interactive
Softwares. "Pandya" remains only where it names the first company's own site, website or data
(SOS-P1-10, P1-11, P1-14D, P4-09, P4-10, P6-14), which is not product branding.

## Questions for Jayman

1. **SOS-N21A is Blocked and stops the whole loop. Reset it to Not Started?** Recommended: yes, now.
   SOS-SETUP-32 fixed the repair context and SOS-SETUP-33's note says how to test spoken phone numbers
   without tripping the guard. Let the agent rebuild from the task text, with
   `wip/SOS-N21A-recovery-20261113` kept for reference only. Unblocks: the loop, SOS-N21, SOS-P5-07.
2. **Where do live provider tests get a public HTTPS address for webhooks?** Recommended: staging
   (SOS-P0-04 targets 24 November), not a tunnel to the shared bench on port 8004. If you agree, add
   SOS-P0-06D as a dependency of each live test. Unblocks: SOS-P2-02L, SOS-P2-13, SOS-P5-07L,
   SOS-P6-03L, SOS-P6-15L, SOS-P6-11L.
3. **May a SOS-SETUP task change `test_the_voice_pilot_chain`, so the voice chain's dependencies can be
   corrected, and may SOS-P5-07 start before SOS-N21?** Recommended: yes. SOS-P5-07 also depends on
   SOS-P2-05; SOS-P5-08 depends on SOS-P5-07L; SOS-P5-09 depends on SOS-P5-07 and SOS-P2-11 instead of
   SOS-P5-08 (it only needs the Call Log). SOS-P5-07 builds adapters for all four bake-off candidates
   behind the provider setting, and SOS-N21 only sets that setting. Unblocks: SOS-P5-07 in the Dec 20
   tier, and the SOS-P5-09 report before the pilot ends.
4. **The baseline (four weeks, SOS-P2-14) and the pilot (about four weeks, SOS-P5-08) cannot finish by
   20 December, and the 022 number allows only service and transactional calls. What is the plan?**
   Recommended: move SOS-P2-14, SOS-P5-08, SOS-P5-09 and SOS-P5-09A to the Jan 1 tier, and limit the
   pilot to site visit confirmations and follow ups for existing clients. Unblocks: SOS-P5-08's design
   and an honest Dec 20 tier.
5. **SOS-N07 (counsel's review) is Not Needed. Who writes and approves the consent wording shown on
   forms?** Recommended: you write a default text; it is the company setting "Consent wording", which
   each Company Admin can edit; counsel reviews it after launch. Unblocks: SOS-P2-08, SOS-P1-09,
   SOS-P1-10, SOS-P5-06.
6. **What does "a missed call moves the lead" (SOS-P2-08) mean?** Recommended: no stage change. The
   missed call creates an Inquiry Consent Record (7 days) and an activity, the lead becomes Consented
   and rises to the top of the caller queue, and a missed call from an unknown number creates a new
   lead on New. Unblocks: SOS-P2-08.
7. **Without counsel (SOS-N13 Not Needed), what are the rules for third party names: Index II buyer
   and seller names, and Facebook posters' names and numbers?** Recommended: party names are visible
   only to Company Admins, never searchable, every view logged, kept five years; a poster's details are
   kept only on the draft listing, masked like a lead's phone, and deleted when the draft is rejected.
   This touches personal data, so it needs your decision. Unblocks: SOS-P3-12, SOS-P3-10, SOS-P6-10.
8. **Where does market data live and come from?** Company databases are never shared, yet the data
   serves every agency; SOS-N11 is Not Needed and SOS-N12 is uncertain; no task supplies ready reckoner
   rates or a data licence. Recommended: keep it on the control site, served to company sites through a
   role checked API; load it from export files you supply (Index II or DoRS) through SOS-P3-01's file
   adapter; load ready reckoner rates from a file you supply; the licence switch is a platform setting,
   On by default for data you own. Unblocks: SOS-P3-01L, SOS-P3-02, SOS-P3-08, SOS-P3-13, SOS-P4-07.
9. **What are the "agreed" numbers?** Recommended: normaliser at least 95 percent of fields correct
   (SOS-P3-03); matcher precision at least 95 percent and recall at least 85 percent (SOS-P3-05);
   nightly jobs within 2 hours (SOS-P3-07); valuation median error at most 10 percent (SOS-P3-09); call
   cost within 2 percent of Plivo's statement (SOS-P2-13); an unpublished listing gone from the website
   within 15 minutes (SOS-P4-09); one site restored within 1 hour, 50 concurrent users, 95 percent of
   list screens within 1 second (SOS-P6-12D). The gate uses synthetic golden files that Claude Code
   writes; the real checks are SOS-P3-13. Unblocks: those tasks' acceptance.
10. **Which language model, on whose account, for the agent assistant and the voice agent?**
    Recommended: one provider for both, the account and key held by you, keys in the Keychain locally
    and in encrypted settings in production. Unblocks: SOS-P3-10L, SOS-N21, SOS-P5-07L.
11. **What are the Private Sale Dossier, the asset library, a shortlist, and a seller record?**
    Recommended: the Dossier is the files and notes attached to a Mandate, released only when it is
    signed; the asset library is the company's uploaded files; a shortlist is a list of listings per
    client, made by the agent and seen by the client; a seller is a Lead on the Seller pipeline linked
    to a Client. Unblocks: SOS-P4-03, SOS-P4-04, SOS-P4-05, SOS-P5-05.
12. **May a Company Admin export reports (SOS-P5-04), given that only the Platform Admin may bulk
    export?** Recommended: yes for report results only (the rows and figures they can already see,
    phone numbers masked, every export logged); raw DocType export stays Platform Admin only. Unblocks:
    SOS-P5-04.
13. **May a Channel Partner create a lead (SOS-P5-06), given that partners are read only?**
    Recommended: yes, through one whitelisted method that creates the lead with them as partner; after
    that it is read only to them and they log nothing. This is a permission change. Unblocks: SOS-P5-06.
14. **WhatsApp: which provider, who does Meta's business verification, where are the existing flow
    designs, and which are the ten flows?** Recommended: Meta's Cloud API directly behind the adapter,
    with you holding the Meta business account; you put the designs and the list of ten flows in
    `docs/whatsapp/`; "the agent's calendar" means Site Visit records. Unblocks: SOS-P6-11, SOS-P6-11L,
    SOS-P6-16, SOS-P6-17.
15. **Is the Facebook capture assist a browser extension or a share target?** Recommended: a share
    target in the SellOS web app on a phone, plus pasting a post's link and text on a computer; no
    browser extension, which would be a second product to ship and review. Unblocks: SOS-P6-10.
16. **No task sets up outgoing email in production. Add one?** Recommended: yes, a Waiting AMP Labs
    task (a transactional mail provider, SPF and DKIM on the domain), and make SOS-P1-11 depend on it.
    Unblocks: real emails from SOS-P1-02, SOS-P3-07, SOS-P3-11, SOS-P5-04, SOS-P6-04, SOS-P6-07.
17. **May SOS-P6-06 build invoices before SOS-N15 (format in a setting, approval in SOS-P6-06A), and
    may SOS-N15 drop its dependency on SOS-N14?** Recommended: yes to both. The accountant then
    approves real samples, and SOS-N15 can start now. Unblocks: SOS-P6-06, SOS-N15.

## Jayman's answers (SOS-SETUP-34, 13 November 2026)

Questions 1 to 3, 5 to 9, 11, 12 and 14 to 16 were answered "as recommended". Questions 4, 10, 13 and
17 had their own answers, given below. Each answer is now in the blocks it names, as a note that
starts "Decided by Jayman (SOS-SETUP-34" and, where the answer changes what is built, as an acceptance
criterion.

| # | Answer | What changed in `TASKS.md` |
| --- | --- | --- |
| 1 | Reset SOS-N21A | Status Not Started (`scripts/set-task-status.sh`); the recovery branch is reference only |
| 2 | Staging gives live tests their public HTTPS address | SOS-P0-06D added to SOS-P2-02L, P2-13, P5-07L, P6-03L, P6-15L, P6-11L |
| 3 | The voice chain may change; SOS-P5-07 may start before SOS-N21 | SOS-P5-07 depends on SOS-P2-03, P2-04, P2-05 and builds adapters for every candidate; SOS-P5-08 on SOS-P5-07L and P2-14; SOS-P5-09 on SOS-P5-07 and P2-11; `test_the_voice_pilot_chain` changed to match |
| 4 | As recommended, and the Dec 20 test is at least 50 supervised end to end AI calls (the disclosure, the handover, reviewed transcripts) | SOS-P5-07L holds the 50 calls; SOS-P2-14, P5-08, P5-09 and P5-09A moved to Jan 1; the pilot is limited to site visit confirmations and follow ups for existing clients; SOS-P5-09A now also depends on SOS-P5-08 |
| 5 | Jayman writes the default consent wording; a company setting; counsel reviews after launch | Notes on SOS-P2-08, P1-09, P1-10, P5-06; new SOS-N22 (Jayman, Waiting), a dependency of SOS-P1-10 and P2-13 |
| 6 | A missed call changes no stage | SOS-P2-08's criterion rewritten; it depends on SOS-P2-09 (the caller queue) |
| 7 | Party names: Company Admins only, never searchable, views logged, kept five years; poster details only on the draft, masked, deleted on rejection | Criteria on SOS-P3-12 and P6-10, note on P3-10 |
| 8 | Market data on the control site behind a role checked API, from files Jayman supplies; ready reckoner from a file; licence switch a platform setting, On by default | Criteria on SOS-P3-02, P3-08, P4-07, P3-01L; notes on P3-01, P3-13 |
| 9 | The recommended numbers | SOS-P3-03 95 percent; P3-05 precision 95, recall 85; P3-07 2 hours; P3-09 median error 10 percent; P2-13 2 percent; P4-09 15 minutes; P6-12 and P6-12D 1 hour, 20 sites, 50 users, 95 percent within 1 second |
| 10 | One provider account held by Jayman, Anthropic; two model settings (voice agent: fast; assistant: stronger); the agent does not choose the model | SOS-N21A gains a language model comparison: the 20 Roman Hinglish replies through two or three candidate models named in `~/iespl-baseline/bakeoff/llm-models.txt`, a rating sheet `docs/bakeoff/llm-rating-sheet.md`, the Keychain item `sellos_anthropic_key` (5 to 6 points); SOS-N21 chooses each model from it; settings "Voice agent model" on SOS-P5-07 and "Assistant model" on SOS-P3-10 |
| 11 | The recommended definitions | Notes on SOS-P4-03, P4-04, P4-05 (and a criterion for the Dossier), P5-05 |
| 12 | Company Admins export report results only | Criterion on SOS-P5-04 |
| 13 | Partners create leads through one whitelisted method, rate limited, and see only their own leads | Criterion on SOS-P5-06: the setting "Partner lead limit", default 20 leads per partner per hour |
| 14 | Meta's Cloud API; Jayman holds the account and verifies it; designs in `docs/whatsapp/` | Notes on SOS-P6-11, P6-11L, P6-16, P6-17; new SOS-N23 (Jayman, Waiting), a dependency of SOS-P6-16 and P6-17 |
| 15 | A share target and paste, no browser extension | Criterion on SOS-P6-10 |
| 16 | Add an outgoing email task | New SOS-P0-13 (AMP Labs, Waiting, Dec 20), a dependency of SOS-P1-11 |
| 17 | Invoices as an editable template; no invoice to a real customer until SOS-N15 is Complete | SOS-P6-06's description and criteria; the platform setting "Invoice format approved" is Off until then. SOS-N15 keeps its dependency on SOS-N14, which the answer did not cover |

SOS-REG-L depends on the three new tasks. After the changes there is no dangling dependency, no cycle,
and no Dec 20 task depends on an unfinished Jan 1 task. `scripts/select-next-task.sh TASKS.md` picks SOS-N21A.

### Remaining scope for Claude Code (13 November 2026, after SOS-SETUP-34)

Tasks owned by Claude Code that are Not Started (none is In Progress or Blocked): 64 tasks, 357 points.
Before this commit: 64 tasks, 356 points; SOS-N21A gained a point, and SOS-P5-09 (3 points) moved from
Dec 20 to Jan 1. SOS-P1-11 is owned by "AMP Labs, Claude Code" and is Waiting, so it is not counted.

| Tier | Tasks | Points | Pace by 12 December (29 days) | Pace by 22 December (39 days) |
| --- | --- | --- | --- | --- |
| Dec 20 | 19 | 91 | 0.66 tasks, 3.1 points a day | 0.49 tasks, 2.3 points a day |
| Jan 1 | 45 | 266 | | |
| All | 64 | 357 | 2.2 tasks, 12.3 points a day | 1.6 tasks, 9.2 points a day |

The days count from 14 November to the date, inclusive. For comparison, the loop finished 8 tasks (36
points) on 10 November and 9 (48 points) on 11 November. Those were mostly rebuilds of code that
already existed. It has finished none since SOS-N21A was Blocked on 13 November.
