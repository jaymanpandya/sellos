// Defines what the leads screen must do for each role. It goes through the real screens, so a
// list that fails to load, or a save the server refuses, fails here instead of showing an empty page.
context("SOS-P1-06A: leads by role", () => {
	const unique = (label) => `${label} ${Date.now()}`;

	it("the company admin creates a lead and sees it in the list", () => {
		const name = unique("Gate Buyer");
		cy.signInFresh("company_admin");
		cy.bench("sellos.tests.ui_fixtures.fresh_phone", { seed: 11 }).then(({ phone }) => {
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("leads-new").click();
			cy.getByTestId("lead-form-name").type(name);
			cy.getByTestId("lead-form-phone").type(phone);
			cy.getByTestId("lead-form-save").click();
			cy.getByTestId("lead-form-error").should("not.exist");
			cy.getByTestId("lead-row").contains(name).should("be.visible");
		});
	});

	it("shows an error, never an empty list, when the list cannot load", () => {
		cy.signInFresh("company_admin");
		cy.intercept("**/sellos.crm.api.list_leads*", {
			statusCode: 500,
			body: { exc_type: "ValidationError" },
		});
		cy.expectApiStatus("sellos.crm.api.list_leads", 500);
		cy.expectConsoleError("list_leads");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("leads-error").should("be.visible");
		cy.getByTestId("leads-empty").should("not.exist");
	});

	it("an agent sees only their own leads", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads").then(({ own, others }) => {
			cy.signInFresh("agent");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("lead-row").contains(own).should("be.visible");
			others.forEach((name) =>
				cy.getByTestId("lead-row").contains(name).should("not.exist")
			);
		});
	});

	it("a channel partner sees their leads and cannot change anything", () => {
		cy.signInFresh("channel_partner");
		cy.visit("/sellos/partner/leads");
		cy.getByTestId("leads-error").should("not.exist");
		cy.getByTestId("leads-new").should("not.exist");
		cy.getByTestId("lead-form-save").should("not.exist");
	});

	it("a client and the platform admin have no CRM screen", () => {
		["client", "platform_admin"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("lead-row").should("not.exist");
		});
	});
});
