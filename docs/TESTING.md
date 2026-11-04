# Testing SellOS

Nothing is committed unless the gate passes. The gate is `scripts/test_all.sh`. The git hooks run
it for you before every commit, and the pre push hook refuses to push a commit that never passed.

## What the gate runs

1. Tests accompany code changes. Staged code in `sellos/` or `frontend/src/` needs a staged test
   (`test_*.py` or `*.test.js`) in the same commit.
2. Lint. All the pre-commit hooks (ruff, prettier, eslint and the rest).
3. Frontend install with a frozen lockfile, then the frontend unit tests (Vitest).
4. Frontend build.
5. Site migrate on the dedicated test site, then the test users are created and read back.
6. Backend tests (`bench run-tests --app sellos`), including the site state tests.
7. HTTP smoke check. A real server starts on port 8004. For every user in `TEST_USERS` it checks
   that a wrong password is refused, that login works, that `/sellos` opens, that the page holds
   the app root and the user's boot data, and that every built asset loads. A guest must be sent
   to the login page.

A commit that changes only Markdown runs the lint step alone.

## One time setup

```
scripts/install_hooks.sh
scripts/setup_test_site.sh
```

The second command creates `sellos_test.localhost`. It asks for the MariaDB root password. The
gate refuses to use `sellos.localhost`, any BuildOS, Pamaa or AWH site, and ports 8000, 8003, 9000,
11000 and 13000. It never starts or stops the main bench.

## How backend tests are written

Follow the Frappe testing documentation: https://docs.frappe.io/framework-git/testing/overview

* Tests that touch the database extend `IntegrationTestCase` from `frappe.tests`. It rolls back
  after the class, so tests leave nothing behind. If you override `setUpClass`, call `super()`.
* Tests that never touch the database extend `UnitTestCase`.
* Create data inside the test class with `frappe.get_doc(...).insert()`, guarded by
  `frappe.db.exists`, the way Frappe's own tests do. Do not commit inside a test.
* The one exception is `ensure_test_users` in `sellos/testing/users.py`. The HTTP smoke check
  runs against a separate server process, so its users must be committed. The gate runs that
  fixture with `bench execute`.

## Rules that stop silent failures

* A story that creates users, roles, records or settings must create them in code that can be run
  again safely (a function in `sellos/testing/` or a patch), and a test must read them back.
* Every user in `sellos/testing/users.py` is logged in through the real login endpoint by the
  smoke check. A user that does not exist, or whose login fails, fails the gate.
* When a story creates a role, add a test user for it to `TEST_USERS` in the same commit.
  `test_every_sellos_role_has_a_test_user` fails otherwise.
* Never commit with `--no-verify`. If the gate cannot run, fix that first.

## Waivers

* `SELLOS_NO_TEST_REASON="reason"` lets a commit without tests through (renames, moves, comments).
  The reason is written to `.git/sellos_gate_waivers`.
* `SELLOS_SKIP_GATE="reason"` lets a push through that has ungated commits. Use it for emergencies
  only. It is logged in the same file.

## Running parts by hand

```
scripts/test_all.sh fast        lint, test presence check and frontend unit tests
scripts/test_all.sh             everything
cd frontend && yarn test        frontend unit tests only
```

Step logs are in `/tmp/sellos_gate/`.
