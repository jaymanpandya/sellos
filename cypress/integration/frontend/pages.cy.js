// SOS-P0-10: the home and no access pages. Replaces pages.test.js.
// SOS-P1-26: an agent and a sales manager land on Today, which asks for three lists. Stub them all and
// wait for them, so no real request is still running when the test ends (a slow CI run cut it off).
const stubToday = () => {
	cy.intercept("**/api/method/sellos.crm.api.list_call_outcomes*", {
		body: { message: { outcomes: [] } },
	}).as("outcomes");
	cy.intercept("**/api/method/sellos.crm.api.site_visit_options*", {
		body: { message: { confirmations: [] } },
	}).as("visitOptions");
	cy.intercept("**/api/method/sellos.crm.api.today_screen*", {
		body: {
			message: {
				scope: "own",
				counts: { follow_ups: 0, new_leads: 0, visits_today: 0, visits_tomorrow: 0 },
				follow_ups: [],
				new_leads: [],
				visits_today: [],
				visits_tomorrow: [],
			},
		},
	}).as("today");
};
const todayLoaded = () => {
	cy.wait("@outcomes");
	cy.wait("@visitOptions");
	cy.wait("@today");
};

context("SOS-P0-10: pages", () => {
	it("greets the signed in user by name", () => {
		cy.signInFresh("agent");
		cy.bootOverride((boot) => {
			boot.full_name = "Jayman";
		});
		cy.intercept("**/api/method/sellos.crm.api.list_notifications*", {
			body: { message: { unread: 0, items: [] } },
		}).as("notifications");
		stubToday();
		cy.visit("/sellos");
		cy.getByTestId("home-welcome").should("contain", "Welcome, Jayman");
		// SOS-P1-26: an agent lands on Today. Let its lists finish loading so no request is left running.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		todayLoaded();
		cy.wait("@notifications");
	});

	it("greets with the email when the boot data has no name", () => {
		// The app falls back to the email, so the greeting is never left without a name. The old
		// unit test also checked the greeting for an empty name; no sign in reaches that state.
		cy.signInFresh("agent");
		cy.bootOverride((boot) => {
			boot.full_name = "";
		});
		cy.intercept("**/api/method/sellos.crm.api.list_notifications*", {
			body: { message: { unread: 0, items: [] } },
		}).as("notifications");
		stubToday();
		cy.visit("/sellos");
		cy.getByTestId("home-welcome")
			.should("contain", "Welcome")
			.and("contain", "sos_test_agent@example.com");
		// SOS-P1-26: let the Today lists finish loading so no request is left running.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		todayLoaded();
		cy.wait("@notifications");
	});

	it("explains the no access page", () => {
		cy.signInFresh("basic");
		cy.visit("/sellos");
		cy.getByTestId("no-access").should("contain", "You do not have access to this page");
	});
});
