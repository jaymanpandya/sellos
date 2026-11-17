# Stops

Every stop of the SellOS build loop, appended by `scripts/build-loop.sh` (SOS-SETUP-33). The loop
prints the hours since the last stop. The exit test in `docs/DEV_STRATEGY.md` section 11 is ten
consecutive tasks without an unplanned stop. Categories: `blocked` (the gate failed after its
repairs), `task broke older specs` (the gate failed on a spec the task did not change, SOS-SETUP-37),
`needs-input`, `crash`, `unrecognized`, `environment`, `ci-red`, `push-failed`, `blocked-exists`
(before SOS-SETUP-37), `no-work`, `start` (a check before any task), `unexpected`, `gate hole` (a hole
in the gate found by a stop, recorded by hand), `test pins a moving value` (a test asserted something
the loop changes, such as a real task's status, SOS-SETUP-38), and the planned ones, `paused` and `stopped`. "Attempt
lost" is the time from the task's start to the stop. "Idle until restart" is filled in when the loop
starts again; it is 0.0 for a Blocked task the loop went on from at once (SOS-SETUP-37).

| Time (UTC) | Task | Category | Cause | Attempt lost (min) | Idle until restart (h) |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 02:05 | SOS-N21A | blocked | the gate still failed after 3 gate runs: the phone number guard and the no-commands guard (docs/DEV_STRATEGY.md row 38); recorded by hand by SOS-SETUP-33 | 34 | 7.1 |
| 2026-11-13 22:05 | SOS-P1-15 | gate hole | stopped by hand (exit 143, SOS-SETUP-36): the baseline restore reset only the tables in the 4 November dump, so a Support Grant and Consent Records the agent seeded by hand, and older Provisioning Job and Tenant rows, survived into the backend suite (13 failures); nothing reset the site between the changed specs and the backend suite. Work saved on wip/SOS-P1-15-20261113 | 774 | 6.3 |
| 2026-11-14 04:52 | SOS-P1-15 | stopped | stopped by a signal (sellos stop --now, Ctrl-C or a shutdown) | 29 | 0.0 |
| 2026-11-14 07:25 | SOS-P1-20 | task broke older specs | the gate still failed after 3 gate run(s): UI TESTS FAILED. The task made the lead form's Source a required select and updated only leads_screen.cy.js; leads_by_role.cy.js and duplicate_warning.cy.js made a lead without a source and failed only in the whole suite. Blocked at 12:55 IST and the loop stood idle (recategorised by hand by SOS-SETUP-37; finished by hand in 08b6a92) | 42 | 56.5 |
| 2026-11-16 17:46 | SOS-P1-07 | stopped | stopped by a signal (sellos stop --now, Ctrl-C or a shutdown) | 109 | 3.1 |
| 2026-11-16 21:00 | SOS-P1-07 | test pins a moving value | CI run 43954312044 on 757df9c, red on two jobs. Server: test_tasks_selection.py asserted that the real SOS-P1-07 was Not Started, and the loop had marked it In Progress (SOS-N21 was pinned to Waiting the same way). UI: frontend/route_access.cy.js reached 3 in the flaky log (CI runs 43897848128, 43902088789, 43954312044), each time "list_lead_sources failed Failed to fetch" in the after each hook of the test after the one that left a real, unstubbed list_lead_sources call running. Recategorised by hand from ci-red by SOS-SETUP-38; P1-07's work stayed In Progress in the tree | 0 | 3.9 |
| 2026-11-17 07:52 | SOS-P1-21 | stopped | stopped by a signal (sellos stop --now, Ctrl-C or a shutdown) | 320 | 0.0 |
| 2026-11-17 07:53 | SOS-P1-21 | crash | Claude's process exited 1; the loop went on to the next task | 0 | 0.0 |
| 2026-11-17 09:20 | SOS-P1-17 | blocked | two tasks Blocked in a row (SOS-P1-21, then SOS-P1-17): the gate still failed after 3 gate run(s): BACKEND TESTS FAILED | 87 | 0.5 |
| 2026-11-17 11:14 | SOS-P2-04 | blocked | the gate still failed after 3 gate run(s): see the gate log; the loop went on to the next task | 84 | 0.0 |
| 2026-11-17 19:17 | SOS-P2-01 | environment | The gate stopped before testing anything (exit 2). | 483 | 0.1 |
| 2026-11-17 20:30 | SOS-P2-02 | stopped | stopped by a signal (sellos stop --now, Ctrl-C or a shutdown) | 26 | 0.1 |
| 2026-11-17 20:33 | - | push-failed | unpushed commits that do not start with SOS- | 0 | 0.1 |
