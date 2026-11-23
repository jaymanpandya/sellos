# Stops

Every stop of the SellOS build loop, appended by `scripts/build-loop.sh` (SOS-SETUP-33). The loop
prints the hours since the last stop. The exit test in `docs/DEV_STRATEGY.md` section 11 is ten
consecutive tasks without an unplanned stop. Categories: `blocked` (the gate failed after its
repairs), `task broke older specs` (the gate failed on a spec the task did not change, SOS-SETUP-37),
`needs-input`, `crash`, `unrecognized`, `environment`, `ci-red`, `push-failed`, `blocked-exists`
(before SOS-SETUP-37), `no-work`, `start` (a check before any task), `unexpected`, `gate hole` (a hole
in the gate found by a stop, recorded by hand), `test pins a moving value` (a test asserted something
the loop changes, such as a real task's status, SOS-SETUP-38), `gate timeout` (a limit or the stall watchdog killed the gate twice in a row, SOS-SETUP-39), `machine slept or gate hung` (the 17 November 2026 hang, recorded by hand), and the planned ones, `paused` and `stopped`. "Attempt
lost" is the time from the task's start to the stop. "Idle until restart" is filled in when the loop
starts again; it is 0.0 for a Blocked task the loop went on from at once (SOS-SETUP-37).

Gate limits (SOS-SETUP-39), chosen from the times the gate measured in /tmp/sellos-test-logs on 16 and 17
November 2026. A spec took 67 to 85 s (two slow runs took 684 s and 1827 s), the whole Cypress suite 6 to 7 min,
the backend suite 12 to 14 min (26 once) and a whole gate run 31 to 51 min, plus up to 90 min waiting for the
bench lock. So: a spec 15 min, the Cypress suite and the backend suite 45 min each, the whole gate 150 min,
and 15 min without a new line in the loop log. Each is an environment variable (SELLOS_SPEC_TIMEOUT,
SELLOS_UI_SUITE_TIMEOUT, SELLOS_BACKEND_TIMEOUT, SELLOS_GATE_TIMEOUT and SELLOS_STALL_TIMEOUT, in seconds). Past one,
SellOS's own process tree is killed, the bench lock is released, Telegram is told, and the gate runs once more; a
second timeout stops the loop with the category `gate timeout`. A timeout is never handed to the repair agent.

| Time (UTC) | Task | Category | Cause | Attempt lost (min) | Idle until restart (h) |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 02:05 | SOS-N21A | blocked | the gate still failed after 3 gate runs: the phone number guard and the no-commands guard (docs/DEV_STRATEGY.md row 38); recorded by hand by SOS-SETUP-33 | 34 | 7.1 |
| 2026-11-13 22:05 | SOS-P1-15 | gate hole | stopped by hand (exit 143, SOS-SETUP-36): the baseline restore reset only the tables in the 4 November dump, so a Support Grant and Consent Records the agent seeded by hand, and older Provisioning Job and Tenant rows, survived into the backend suite (13 failures); nothing reset the site between the changed specs and the backend suite. Work saved on wip/SOS-P1-15-20261113 | 774 | 6.3 |
| 2026-11-14 04:52 | SOS-P1-15 | stopped | stopped by a signal (sellos stop --now, Ctrl-C or a shutdown) | 29 | 0.0 |
| 2026-11-14 07:25 | SOS-P1-20 | task broke older specs | the gate still failed after 3 gate run(s): UI TESTS FAILED. The task made the lead form's Source a required select and updated only leads_screen.cy.js; leads_by_role.cy.js and duplicate_warning.cy.js made a lead without a source and failed only in the whole suite. Blocked at 12:55 IST and the loop stood idle (recategorised by hand by SOS-SETUP-37; finished by hand in 08b6a92) | 42 | 56.5 |
| 2026-11-16 17:46 | SOS-P1-07 | stopped | stopped by a signal (sellos stop --now, Ctrl-C or a shutdown) | 109 | 3.1 |
| 2026-11-16 21:00 | SOS-P1-07 | test pins a moving value | CI run 43954312044 on 757df9c, red on two jobs. Server: test_tasks_selection.py asserted that the real SOS-P1-07 was Not Started, and the loop had marked it In Progress (SOS-N21 was pinned to Waiting the same way). UI: frontend/route_access.cy.js reached 3 in the flaky log (CI runs 43897848128, 43902088789, 43954312044), each time "list_lead_sources failed Failed to fetch" in the after each hook of the test after the one that left a real, unstubbed list_lead_sources call running. Recategorised by hand from ci-red by SOS-SETUP-38; P1-07's work stayed In Progress in the tree | 0 | 3.9 |
| 2026-11-17 07:52 | SOS-P1-21 | machine slept or gate hung | the gate (run-tests.sh, started 08:17 IST) held the bench lock for 5 hours after the Mac slept on battery power, inside the changed spec crm/buyer_pipeline.cy.js (run 1), with no output, no Telegram message and no latest.log (it was linked only when a gate ended). Stopped by hand with sellos stop --now. Recategorised by hand from stopped by SOS-SETUP-39, which adds the limits, the stall watchdog, caffeinate and the leftover cleanup | 320 | 0.0 |
| 2026-11-17 07:53 | SOS-P1-21 | crash | Claude's process exited 1; the loop went on to the next task | 0 | 0.0 |
| 2026-11-17 09:20 | SOS-P1-17 | blocked | two tasks Blocked in a row (SOS-P1-21, then SOS-P1-17): the gate still failed after 3 gate run(s): BACKEND TESTS FAILED | 87 | 0.5 |
| 2026-11-17 11:14 | SOS-P2-04 | blocked | the gate still failed after 3 gate run(s): see the gate log; the loop went on to the next task | 84 | 0.0 |
| 2026-11-17 19:17 | SOS-P2-01 | environment | The gate stopped before testing anything (exit 2). | 483 | 0.1 |
| 2026-11-17 20:30 | SOS-P2-02 | stopped | stopped by a signal (sellos stop --now, Ctrl-C or a shutdown) | 26 | 0.1 |
| 2026-11-17 20:33 | - | push-failed | unpushed commits that do not start with SOS- | 0 | 0.1 |
| 2026-11-17 20:36 | - | push-failed | unpushed commits that do not start with SOS- | 0 | 0.3 |
| 2026-11-18 04:13 | SOS-FIX-1 | blocked | the gate still failed after 2 gate run(s): BACKEND TESTS FAILED; the loop went on to the next task | 168 | 0.0 |
| 2026-11-18 06:28 | SOS-P4-01 | blocked | two tasks Blocked in a row (SOS-FIX-1, then SOS-P4-01): the gate still failed after 3 gate run(s): CHANGED SPEC FAILED: inventory/projects_units.cy.js | 135 | 4.6 |
| 2026-11-18 16:54 | SOS-P1-23 | blocked | the gate still failed after 3 gate run(s): CHANGED SPEC FAILED: crm/leads_by_role.cy.js; the loop went on to the next task | 54 | 0.0 |
| 2026-11-18 18:01 | SOS-P2-04 | blocked | two tasks Blocked in a row (SOS-P1-23, then SOS-P2-04): the gate still failed after 3 gate run(s): see the gate log | 67 | 1.0 |
| 2026-11-18 20:36 | SOS-P1-22 | ci-red | CI still red on 0858628 (the commit for SOS-P1-22) after 2 repair attempt(s): (no failing test could be read from the log; its last lines:) run 44391986098 is still in progress; logs will be availabl… | 40 | 4.4 |
| 2026-11-19 06:35 | SOS-P2-04 | ci-red | CI still red on e565aa1 (the commit for SOS-P2-04) after 2 repair attempt(s): 1) "after each" hook for "shows a partner the timeline but no way to log or archive" 1) SOS-P1-06A: lead detail | 68 | 9.0 |
| 2026-11-19 16:38 | SOS-P2-05 | ci-red | CI still red on 15dddeb (the commit for SOS-P2-05) after 2 repair attempt(s): 1) SellOS Agent sees only navigation inside its own areas 2) "after each" hook for "SellOS Agent sees only navigation ins… | 64 | 4.7 |
| 2026-11-19 21:22 | SOS-P2-06 | needs-input | SOS-P2-06's webhook has to be callable by Plivo, which has no SellOS login, and I can't build that without changing how API methods are declared. That touches permissions, so I need your decision fir… | 0 | 0.2 |
| 2026-11-19 23:43 | SOS-P2-06 | needs-input | SOS-P2-06's webhook has to be callable by Plivo, which has no SellOS login. I can't build that without changing how API methods are declared, and `docs/STOPS.md` shows an earlier run stopped on the s… | 0 | 3.9 |
| 2026-11-20 04:17 | - | paused | the regression pause file exists | 0 | 7.3 |
| 2026-11-20 12:05 | SOS-P2-06 | stopped | stopped by a signal (sellos stop --now, Ctrl-C or a shutdown) | 32 | 4.4 |
| 2026-11-20 17:15 | SOS-P2-08 | needs-input | The enquiry page is a form a prospect submits with no SellOS login, so its submit method has to allow guests. CLAUDE.md says a provider webhook is the only method that may allow guests, and that `all… | 0 | 2.4 |
| 2026-11-21 01:17 | SOS-FIX-1 | blocked | the gate still failed after 3 gate run(s): CHANGED SPEC FAILED: smoke/not_found.cy.js; the loop went on to the next task | 25 | 0.0 |
| 2026-11-21 03:38 | - | paused | the regression pause file exists | 0 | 0.5 |
| 2026-11-21 09:59 | - | paused | the regression pause file exists | 0 | 9.1 |
| 2026-11-21 22:15 | - | paused | the regression pause file exists | 0 | 0.2 |
| 2026-11-21 23:33 | SOS-P4-08 | needs-input | SOS-P4-08 needs a method that a site's website can call with no SellOS login, using only a Listings read key. CLAUDE.md allows only two kinds of guest method: provider webhooks, and public intake for… | 0 | 6.6 |
| 2026-11-22 08:44 | SOS-P4-04 | blocked | the gate still failed after 3 gate run(s): CHANGED SPEC FAILED: crm/seller_pipeline.cy.js; the loop went on to the next task | 112 | 0.0 |
| 2026-11-22 15:20 | - | paused | the regression pause file exists | 0 | 6.0 |
| 2026-11-23 07:20 | SOS-P7-10 | environment | CI red on f3e7d24 (the commit for SOS-P7-10) for a reason outside the code, still red after one rerun: the log of CI run 45123546228 was still not readable after 1800s | 115 | 1.4 |
| 2026-11-23 11:33 | SOS-P5-05 | needs-input | SOS-P5-05 says sellers see "enquiries on their property". I can't build that from what exists, and it exposes buyers' personal data to sellers, so I need your decision first. I changed nothing and le… | 0 | 2.3 |
| 2026-11-23 20:16 | SOS-P3-04 | blocked | the gate still failed after 2 gate run(s): CHANGED SPEC FAILED: intel/market_master.cy.js; the loop went on to the next task | 31 | 0.0 |
