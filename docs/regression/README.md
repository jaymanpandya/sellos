# Clickthrough regression

The build loop proves a task with tests. A person still has to use the product, so at the end of each
phase the loop runs out of eligible tasks and a regression milestone (SOS-REG-0 to SOS-REG-6, and
SOS-REG-2B inside Phase 2) waits for a clickthrough. Claude in chat runs it, in a real browser, the way
a person would. A milestone is a task in TASKS.md with the status Waiting and the owner "Claude in chat,
clickthrough regression".

## How a milestone is run

1. Check that every task the milestone depends on is Complete and the loop is stopped. The milestone
   itself is Waiting.
2. Run `scripts/prepare-regression.sh`. It refuses while the build loop, a gate run or a BuildOS gate is
   running. It restores the clean baseline over `sellos_test.localhost`, builds the front end, migrates,
   runs `prepare_clean_site` and `seed_regression_data`, checks `/sellos` answers, and prints the URL
   and the six test users. It never starts or stops a server, so the SellOS server must already be running on port 8004:
   `cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`. It refuses any other port, and stops if that server is not SellOS.
3. Read `docs/regression/flows.md`. Walk every flow of every task the milestone depends on. A flow is
   one line: `FLOW <task id>-<n> | role | start path | steps | expected result`. Sign in as the role
   named in the flow. Take a screenshot of anything that fails.
4. Watch the network and the console for the whole walk. An `/api/` answer of 400 or more, or a console
   error, is a defect unless the flow says it is expected (for example a refused call the screen must
   explain).
5. Write the report to `docs/regression/<milestone>.md`, for example `docs/regression/reg-0.md` for
   SOS-REG-0 and `docs/regression/reg-2b.md` for SOS-REG-2B, in the format below.
6. If the result is PASS and no SOS-FIX task is open, mark the milestone Complete by hand:
   `scripts/set-task-status.sh <SOS-REG-n> Complete TASKS.md`, commit the report and TASKS.md, push, and
   start the loop again. If the result is FAIL, leave the milestone Waiting and make the defects into
   SOS-FIX tasks (below). The loop fixes them, and the milestone is run again from step 2.

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

Each defect becomes one task block at the end of the active tasks in TASKS.md, in the format
`scripts/lib/tasks.py` reads:

```
### SOS-FIX-<n>: <what is wrong, in a few words>
- **Epic:** Regression fixes
- **Description:** <the defect: flow id, what happened, what was expected, the report that found it>
- **Acceptance Criteria:**
  - <the flow now behaves as expected>
  - A test fails without the fix and passes with it.
- **Priority:** <the phase of the milestone, for example P1>
- **Dependencies:** none
- **Status:** Not Started
- **Browser spec:** required
```

* The priority is the phase of the milestone, so the loop picks the fix before the next phase starts.
* A Critical defect also stops the loop for a person: say so in the report and in the task.
* The fix task adds a flow to `docs/regression/flows.md` when the defect was in a flow that did not
  exist, and a test (backend or Cypress) that names its SOS-FIX id.
* A defect is closed when its SOS-FIX task is Complete and the milestone run that follows walks the
  flow and passes it. The new report names the earlier defects it closes.
