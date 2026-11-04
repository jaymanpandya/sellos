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
		// baseUrl is overridden by run-ui-tests via CYPRESS_baseUrl.
		baseUrl: "http://sellos_test.localhost:8000",
		specPattern: "cypress/integration/**/*.cy.js",
		supportFile: "cypress/support/e2e.js",
		testIsolation: false,
	},
};
