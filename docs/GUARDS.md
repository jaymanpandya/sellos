# Guards

A guard checks the code itself rather than a feature. Every guard runs in one script, in under 30
seconds, with no database and no bench:

```
scripts/check-guards.sh          # the files you changed since the task started: run it before you finish
scripts/check-guards.sh --all    # every file, with CI's exact lint and Semgrep commands (the gate and CI)
```

The gate runs `--all` first and stops at the first failing run, before any test. CI's Linters job
runs the same script. When a guard fails it prints:

```
GUARD FAILED: <name>
Fix: <what is wrong, and the fix>
<the files and lines>
END GUARD
```

**Read the Fix line and apply that fix. Do not work around a guard.** Working around it means
disguising what it looks for (joins, ranges, concatenation, escapes, encodings, computed strings),
moving code to a folder it skips, adding to an allowed list, adding `noqa`, `nosemgrep` or
`eslint-disable`, or editing the guard. Each of those is caught in review and the task is redone. On 13
November 2026 SOS-N21A was Blocked because the agent hid a phone number in
`"".join(map(str, range(9, -1, -1)))`. Semgrep caught the `map`, and a repair turned it back into a
literal. The phone guard's message had named the fix from the start.

| # | Guard | Runs | Exit when it fails |
| --- | --- | --- | --- |
| 1 | phones | `sellos/testing/guards.py` | 1 |
| 2 | commands | `sellos/testing/guards.py` | 1 |
| 3 | secrets | `scripts/check_no_secret_leak.py` over the repository | 1 |
| 4 | gate-files | `scripts/check_gate_files.py` (only when the loop sets a task) | 1 |
| 5 | assertion-ratchet | `scripts/check_assertion_ratchet.py` | 1 |
| 6 | task-evidence | `scripts/check_task_evidence.py` (only when the loop sets a task) | 1 |
| 7 | stale-skips | `scripts/check_no_stale_skips.py` | 1 |
| 8 | lint | `pre-commit` (gitleaks, ruff, ruff format, prettier, eslint, file checks) | 1 |
| 9 | semgrep | Semgrep with the Frappe rules and `r/python.lang.correctness` | 1 |
| 10 | serve | `sellos/testing/guards.py` over every file git knows | 1 |

A missing tool (pre-commit, Semgrep or its rules) exits 3. That is a problem with the environment, not the code.

## 1. phones: no phone number written by hand

**Why.** A number written by hand can be invalid, can collide with another test's number, or can be a
real person's number committed to the repository. SellOS's allowed list is empty and stays empty.

**How to comply.** Generate every number with `sellos.tests.phones` (`in_mobile(seed)`, `au_mobile`,
`ae_mobile`, `near_in_mobile`) and derive every other form from it. A Cypress spec gets its number
from the backend fixture that seeds its data.

```python
# wrong                                   # right
TEN_DIGITS = "9876543210"                 from sellos.tests.phones import in_mobile
                                          NUMBER = in_mobile(7)          # +91 and ten digits
                                          TEN_DIGITS = NUMBER[-10:]      # its national digits
```

## 2. commands: only `sellos/provisioning` runs commands

**Why.** The web process has no shell (SOS-P1-02). A module that imports `subprocess`, `pty` or
`pexpect`, or calls `os.system` or `os.popen`, is allowed only in `sellos/provisioning`, `sellos/tests`,
`sellos/testing` and test files.

**How to comply.** Put the command in a helper in `sellos/provisioning` (`credentials.py` reads the
Keychain, `tenant_sites.py` handles sites) and import the helper. Do not move your module to a folder
the guard skips.

```python
# wrong: sellos/voice/bakeoff/keys.py      # right: sellos/voice/bakeoff/keys.py
import subprocess                          from sellos.provisioning import credentials
subprocess.run(["security", ...])          value, failure = credentials.<helper>(service)
```

## 3. secrets: no loop secret in the repository

**Why.** The provisioner password, the Telegram token and chat ID, and BuildOS's credentials must never
be in a file (SOS-SETUP-18, SOS-SETUP-29). The check searches for their values, so it prints the file and
the variable name, never the value. gitleaks (in lint) catches keys that look like keys.

**How to comply.** Read a secret through `get_provisioner_password()` or the Keychain, at the moment it
is used. Never print, log, write or pass it on a command line.

## 4. gate-files: a task never changes what judges it

**Why.** If a task could edit the gate, the Cypress support file or CI, it could make a failing test
pass by changing the judge. The list is in `scripts/check_gate_files.py` and `docs/TESTING.md`.
`docs/regression/flows.md` is append only, and the `[tool.ruff]` tables in `pyproject.toml` are protected.

**How to comply.** Put the file back (`git diff $SELLOS_BASE_SHA -- <file>` shows your change) and fix
the code instead. Only a human can allow a change, by writing `- **Gate files:** allowed` in the task.

## 5. assertion-ratchet: tests only get stronger

**Why.** "Never weaken an assertion" was once only a sentence in a prompt. No test file may be
deleted, and no changed test file may have fewer assertions than it had at the base commit.

**How to comply.** Fix the code so the test passes. When a later task replaces data an earlier task
locked in (for example the buyer stages, SOS-SETUP-31), change the assertion's expected values and keep the count.

## 6. task-evidence: a test names the task

**Why.** A task with no test that names it has acceptance criteria that nobody tests.

**How to comply.** Put the task ID in a new or changed test's class docstring (or a Cypress `context()`
title), with assertions. A task marked `Browser spec: required` also needs a changed `*.cy.js` that
names it and a `FLOW <task id>-<n> | role | start path | steps | expected result` line in
`docs/regression/flows.md`.

```python
class TestBuyerPipeline(IntegrationTestCase):
	"""SOS-P1-07: the eleven buyer stages."""
```

## 7. stale-skips: a skipped spec waits for a named, unfinished task

**Why.** A contract spec for a later task is skipped until that task. A skip that names no task, or a
task that is Complete or is the one now being finished, would hide a failure for good.

**How to comply.** Put the waiting task's ID in a comment directly above `context.skip(`. When your task
is the one named, remove the skip and make the spec pass.

## 8. lint: CI's pre-commit hooks

**Why.** CI runs these on every push, and a lint failure after the push stops the loop.

**How to comply.** ruff format and prettier rewrite what they can on the first pass. Fix the rest in
the code. Never add `noqa` or `eslint-disable`, and never change the `[tool.ruff]` tables.

## 9. semgrep: the Frappe rules

**Why.** CI runs Semgrep with the Frappe rules and `r/python.lang.correctness`, and it has failed pushes
three times.

**How to comply.** Rewrite the code the way the rule's message says. Two common cases:

```python
# frappe-no-functional-code                 # right
"".join(map(str, digits))                  "".join(str(d) for d in digits)

# frappe-security-file-traversal            # right
with open(path) as f: ...                  Path(path).read_text(encoding="utf-8")
                                           # with the path built from a fixed folder, never from input
```

Never add `nosemgrep` to pass. The few existing ones mark a fixed path that the loop itself passes in.

## 10. serve: every serve command is the pinned SellOS one

**Why.** A serve with no `--site` falls back to default_site and serves BuildOS's site on every host
name (SOS-SETUP-13). CI run 92 failed on 9cbace7 because a hand commit wrote the command with `$SITE`
and `$PORT`, and only the full backend suite checked it. Since SOS-SETUP-34 this guard runs the same
check in a second.

**How to comply.** Write the command out literally, in every script, document and test:
`bench --site sellos_test.localhost serve --port 8004`. A line that warns against the unpinned form names it after
the word "without" and `--site`.
