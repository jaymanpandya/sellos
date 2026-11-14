# Stops

Every stop of the SellOS build loop, appended by `scripts/build-loop.sh` (SOS-SETUP-33). The loop
prints the hours since the last stop. The exit test in `docs/DEV_STRATEGY.md` section 11 is ten
consecutive tasks without an unplanned stop. Categories: `blocked` (the gate failed after its
repairs), `needs-input`, `crash`, `unrecognized`, `environment`, `ci-red`, `push-failed`,
`blocked-exists`, `no-work`, `start` (a check before any task), `unexpected`, `gate hole` (a hole in the
gate found by a stop, recorded by hand), and the planned ones,
`paused` and `stopped`. "Attempt lost" is the time from the task's start to the stop. "Idle until
restart" is filled in when the loop starts again.

| Time (UTC) | Task | Category | Cause | Attempt lost (min) | Idle until restart (h) |
| --- | --- | --- | --- | --- | --- |
| 2026-11-13 02:05 | SOS-N21A | blocked | the gate still failed after 3 gate runs: the phone number guard and the no-commands guard (docs/DEV_STRATEGY.md row 38); recorded by hand by SOS-SETUP-33 | 34 | 7.1 |
| 2026-11-13 22:05 | SOS-P1-15 | gate hole | stopped by hand (exit 143, SOS-SETUP-36): the baseline restore reset only the tables in the 4 November dump, so a Support Grant and Consent Records the agent seeded by hand, and older Provisioning Job and Tenant rows, survived into the backend suite (13 failures); nothing reset the site between the changed specs and the backend suite. Work saved on wip/SOS-P1-15-20261113 | 774 | 6.3 |
