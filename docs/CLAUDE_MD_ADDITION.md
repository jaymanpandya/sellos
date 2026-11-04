## Testing (the gate)

* Run nothing as "done" that the gate has not passed. The git hooks run `scripts/test_all.sh`
  before every commit. Never use `--no-verify`. Never edit the hooks or the scripts to get past a
  failure. Fix the failure.
* Write backend tests the way the Frappe documentation says
  (https://docs.frappe.io/framework-git/testing/overview): `IntegrationTestCase` from
  `frappe.tests` for anything that touches the database, `UnitTestCase` for anything that does
  not, data created in the test class and rolled back by the framework. Read the documentation
  or the Frappe source before inventing a test helper.
* Tests live beside the code: `test_*.py` in the same package, `*.test.js` beside the frontend
  file. A commit that changes code needs a test change in the same commit.
* Anything a story creates on a site (users, roles, records, settings) must come from code that
  can be run again safely, and a backend test must read it back. For users, add them to
  `TEST_USERS` in `sellos/testing/users.py`. The smoke check logs in as each of them over HTTP.
* Never state that something exists or works unless a test read it back or the gate output shows
  it. When you report on a story, quote the gate summary line.
* When a story creates a role, add a test user for it in the same commit.
* The gate uses only the site `sellos_test.localhost` and port 8004. It never touches the main
  bench. `SELLOS_NO_TEST_REASON` is for renames and comments only. List every waiver you use in
  PROGRESS.md.
