# SellOS UI tests (Cypress)

Run from the bench, with the SellOS server running on port 8004, pinned to the site:
`cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004`.
Never use `bench start` or the servers on 8000 (BuildOS) and 8002 (Pamaa) for SellOS.

```bash
cd ~/iespl-bench
bench --site sellos_test.localhost run-ui-tests sellos --headless                 # all specs
bench --site sellos_test.localhost run-ui-tests sellos --headless \
  --spec cypress/integration/crm/leads_by_role.cy.js                              # one spec
bench --site sellos_test.localhost run-ui-tests sellos                            # interactive
```

`scripts/run-tests.sh` runs every spec headless as part of the gate and fails if any spec fails.

Where specs go, how to select elements, how to sign in, how to make data and what fails a spec
without an assertion are all in `docs/TESTING.md`. The short version:

* One folder per area, one `<screen_or_flow>.cy.js` per screen or flow, the task ID in `context()`.
* `cy.getByTestId("<area>-<thing>")` selects `data-testid="sellos-<area>-<thing>"`. Never select by
  style, position or visible text.
* `cy.signInFresh(role)` signs in as `platform_admin`, `company_admin`, `agent`, `channel_partner`,
  `client` or `basic`.
* `cy.bench("sellos.tests.ui_fixtures.<name>", {kwargs})` runs a server side helper. Phone numbers
  come from there, never from a literal.
* An API answer of 400 or more, a console error or an uncaught error fails the test, unless the spec
  declared it with `cy.expectApiStatus` or `cy.expectConsoleError`.
