# Clickthrough regression

The build loop proves a task with tests. A person still has to use the product, so on a schedule the
loop is paused and Claude in chat runs a clickthrough, in a real browser, the way a person would.
Regression is a scheduled pause, not a gate (Jayman, 10 November 2026, SOS-SETUP-19): SOS-REG-A (about
24 November), SOS-REG-B (about 12 December), SOS-REG-C (about 18 December) and SOS-REG-L (about 29
December, the launch regression, which depends on every other active task). Each is a task in TASKS.md
with the status Waiting and the owner "Claude in chat, clickthrough regression". No task depends on A, B
or C. The old milestones SOS-REG-0 to SOS-REG-6 and SOS-REG-2B are Not Needed.

## How a milestone is run

1. Run `scripts/pause-loop.sh`. It creates `/tmp/sellos-loop.pause`. Before picking each task the loop
   checks for that file, so it finishes the task it is on, then picks nothing, notifies "Paused for
   regression" and stops. Wait for it to stop. The milestone itself is Waiting.
2. Run `scripts/prepare-regression.sh`. It refuses while the build loop, a gate run or a BuildOS gate is
   running. It restores the clean baseline over `sellos_test.localhost`, builds the front end, migrates,
   runs `prepare_clean_site` and `seed_regression_data`, checks `/sellos` answers, and prints the URL
   and the six test users. It never starts or stops a server, so the SellOS server must already be running on port 8004:
   `cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`. It refuses any other port, and stops if that server is not SellOS.
3. Read `docs/regression/flows.md`. Walk every flow of every Complete task (for SOS-REG-L, of every task). A flow is
   one line: `FLOW <task id>-<n> | role | start path | steps | expected result`. Sign in as the role
   named in the flow. Take a screenshot of anything that fails.
4. Watch the network and the console for the whole walk. An `/api/` answer of 400 or more, or a console
   error, is a defect unless the flow says it is expected (for example a refused call the screen must
   explain).
5. Write the report to `docs/regression/<milestone>.md`, for example `docs/regression/reg-a.md` for
   SOS-REG-A and `docs/regression/reg-l.md` for SOS-REG-L, in the format below.
6. Make every defect into an SOS-FIX task (below). Run `scripts/resume-loop.sh`, which removes the pause
   file, and start the loop again; it picks the fixes first. For SOS-REG-A, B and C, mark the milestone
   Complete by hand once the report is written and its defects are tasks:
   `scripts/set-task-status.sh <SOS-REG-x> Complete TASKS.md`, commit the report and TASKS.md, and push.
   SOS-REG-L is marked Complete only when its result is PASS and no SOS-FIX task is open; until then it
   is run again from step 1 after the fixes.

Keep a flow honest: if a screen has no flow, add the flow (a flow may be added, never removed) and walk
it. Seed more data in `sellos.tests.ui_fixtures.seed_regression_data` when a flow needs it, through the
production API, and update the docstring of that function.

## The report

```
# <milestone id>: <title>

Commit: <full hash the walk ran against>
Date: <YYYY-MM-DD>
Site: sellos_test.localhost (prepare-regression.sh, regression data seeded)
Result: PASS | FAIL

## Flows

| Flow | Role | Result | Notes |
| --- | --- | --- | --- |
| SOS-P0-10-1 | agent | PASS | |
| SOS-P0-10-2 | company_admin | FAIL | Leads page showed "No leads yet" (D1) |

## Failed API calls

| Flow | Method and URL | Status | Message |
| --- | --- | --- | --- |
| none | | | |

## Console errors

| Flow | Error |
| --- | --- |
| none | |

## Defects

| ID | Severity | Flow | What happened | Expected | Task |
| --- | --- | --- | --- | --- | --- |
| D1 | High | SOS-P1-06A-2 | ... | ... | SOS-FIX-n |
```

Rules for the report:

* "Result: PASS" appears only when every flow is PASS, no API call failed unexpectedly, no console error
  is unexplained, and no defect of any severity is open. Anything else is "Result: FAIL".
* Every flow of every task the milestone depends on has a row. A flow that could not be walked is FAIL.
* Severity: **Critical** (data leak, wrong permission, data loss, a role reaches the desk), **High** (a
  flow cannot be completed, or a call fails), **Medium** (a flow completes but shows a wrong or
  misleading result), **Low** (wording, layout, polish).

## How defects become SOS-FIX tasks

Each defect becomes one task block in TASKS.md, placed just above the first Not Started task so the
loop picks it next, in the format `scripts/lib/tasks.py` reads:

```
### SOS-FIX-<n>: <what is wrong, in a few words>
- **Epic:** Regression fixes
- **Description:** <the defect: flow id, what happened, what was expected, the report that found it>
- **Acceptance Criteria:**
  - <the flow now behaves as expected>
  - A test fails without the fix and passes with it.
- **Priority:** <the phase of the work it fixes, for example P1>
- **Launch:** Dec 20
- **Dependencies:** none
- **Status:** Not Started
- **Browser spec:** required
```

* The loop picks by Launch tier, then dependencies, then file order, so a fix in the Dec 20 tier placed
  above the first Not Started task is picked next. Use Jan 1 only for a defect in Jan 1 work found after
  20 December.
* A Critical defect also stops the loop for a person: say so in the report and in the task.
* The fix task adds a flow to `docs/regression/flows.md` when the defect was in a flow that did not
  exist, and a test (backend or Cypress) that names its SOS-FIX id.
* A defect is closed when its SOS-FIX task is Complete and the milestone run that follows walks the
  flow and passes it. The new report names the earlier defects it closes.
