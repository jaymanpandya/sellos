// SOS-P7-13: a Company Admin sets how fast a new lead must be assigned and contacted. The screen shows the
// defaults (10 and 120 minutes), saves new limits, refuses a limit that is not a whole number of minutes
// from 1 to 2880, and is not there for an agent. Real screen, real server.
context("SOS-P7-13: response time alerts settings", () => {
	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.reset_response_limits");
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.reset_response_limits");
	});

	it("shows the defaults, saves new limits and keeps them after a reload", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.crm.response_times.*").as("limits");
		cy.visit("/sellos/company/response-alerts");
		cy.wait("@limits");
		cy.getByTestId("response-unassigned").should("have.value", "10");
		cy.getByTestId("response-contact").should("have.value", "120");

		cy.getByTestId("response-unassigned").clear().type("15");
		cy.getByTestId("response-contact").clear().type("90");
		cy.getByTestId("response-save").click();
		cy.getByTestId("response-saved").should("be.visible");
		cy.getByTestId("response-error").should("not.exist");

		cy.reload();
		cy.getByTestId("response-unassigned").should("have.value", "15");
		cy.getByTestId("response-contact").should("have.value", "90");
	});

	it("refuses a limit outside 1 to 2880 minutes and keeps the old one", () => {
		cy.expectApiStatus("sellos.crm.response_times.save_response_limits", 417);
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/response-alerts");
		cy.getByTestId("response-unassigned").should("have.value", "10");
		cy.getByTestId("response-unassigned").clear().type("0");
		cy.getByTestId("response-save").click();
		cy.getByTestId("response-error").should("contain.text", "from 1 to 2880");
		cy.getByTestId("response-saved").should("not.exist");

		cy.reload();
		cy.getByTestId("response-unassigned").should("have.value", "10");
	});

	it("is not open to an agent", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/company/response-alerts");
		cy.getByTestId("response-form").should("not.exist");
		cy.location("pathname").should("not.eq", "/sellos/company/response-alerts");
	});
});
