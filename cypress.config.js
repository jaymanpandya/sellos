// Cypress config for SellOS UI tests, the same shape as BuildOS.
// Run with: bench --site sellos_test.localhost run-ui-tests sellos --headless
// Cypress and its plugins are installed in apps/frappe/node_modules by
// run-ui-tests, so this file deliberately avoids require("cypress").
// See cypress/README.md for where specs go and how to select elements.
module.exports = {
	defaultCommandTimeout: 20000,
	pageLoadTimeout: 15000,
	video: false,
	screenshotOnRunFailure: true,
	viewportHeight: 960,
	viewportWidth: 1400,
	fixturesFolder: "cypress/fixtures",
	retries: {
		runMode: 0,
		openMode: 0,
	},
	e2e: {
		// baseUrl is overridden by run-ui-tests via CYPRESS_baseUrl, built from the site's
		// webserver_port. Locally that is 8004, on the SellOS server pinned to the site:
		//   cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004
		// CI is not affected: it runs on its own machine on port 8000 and sets its own host_name.
		baseUrl: "http://sellos_test.localhost:8004",
		specPattern: "cypress/integration/**/*.cy.js",
		supportFile: "cypress/support/e2e.js",
		testIsolation: false,
	},
};
