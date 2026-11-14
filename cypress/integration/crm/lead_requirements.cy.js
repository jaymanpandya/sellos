// SOS-P1-15: an agent fills the Requirements card on a lead they own and filters the leads list by it.
// It goes through the real screens and the real server. seed_agent_leads commits its leads, so they
// are removed after the spec (SOS-SETUP-24).
context("SOS-P1-15: what each buyer wants", () => {
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	it("an agent fills the card, is refused a budget the wrong way round, and filters the list", () => {
		const locality = `Gatevale${Date.now()}`;
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads").then(({ own }) => {
			cy.signInFresh("agent");
			cy.intercept("**/api/method/sellos.crm.api.save_lead*").as("save");
			cy.intercept("**/api/method/sellos.crm.api.list_leads*").as("list");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("lead-row").contains(own).click();

			cy.getByTestId("lead-requirements").should("be.visible");
			cy.getByTestId("lead-req-budget-from").type("9000000");
			cy.getByTestId("lead-req-budget-to").type("5000000");
			cy.expectApiStatus("sellos.crm.api.save_lead", 417);
			cy.getByTestId("lead-req-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 417);
			cy.getByTestId("lead-req-error").should(
				"contain",
				"Budget from cannot be above budget to"
			);

			cy.getByTestId("lead-req-budget-from").clear().type("5000000");
			cy.getByTestId("lead-req-budget-to").clear().type("9000000");
			cy.getByTestId("lead-req-configuration").check("2 BHK");
			cy.getByTestId("lead-req-configuration").check("3 BHK");
			cy.getByTestId("lead-req-property-type").select("Apartment");
			cy.getByTestId("lead-req-purpose").select("End use");
			cy.getByTestId("lead-req-timeline").select("Within 3 months");
			cy.getByTestId("lead-req-possession").select("Under construction");
			cy.getByTestId("lead-req-localities").type(`${locality}, Powai`);
			cy.getByTestId("lead-req-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);
			cy.getByTestId("lead-req-error").should("not.exist");
			cy.getByTestId("lead-req-summary")
				.should("contain", "2 BHK, 3 BHK")
				.and("contain", "Apartment")
				.and("contain", locality)
				.and("contain", "Within 3 months")
				.and("contain", "Under construction");

			// What was saved is there after a fresh load.
			cy.reload();
			cy.getByTestId("lead-req-summary").should("contain", locality);

			cy.visit("/sellos/crm/leads");
			cy.getByTestId("leads-filter-locality").type(locality);
			cy.getByTestId("leads-filter-apply").click();
			cy.getByTestId("lead-row").should("have.length", 1).and("contain", own);

			cy.getByTestId("leads-filter-locality").clear().type("NoSuchPlace");
			cy.getByTestId("leads-filter-apply").click();
			cy.getByTestId("lead-row").should("not.exist");

			cy.getByTestId("leads-filter-clear").click();
			cy.getByTestId("leads-filter-configuration").select("3 BHK");
			cy.getByTestId("leads-filter-timeline").select("Within 3 months");
			cy.getByTestId("leads-filter-budget-min").type("6000000");
			cy.getByTestId("leads-filter-budget-max").type("8000000");
			cy.getByTestId("leads-filter-apply").click();
			cy.getByTestId("lead-row").should("have.length", 1).and("contain", own);

			cy.getByTestId("leads-filter-timeline").select("Immediate");
			cy.getByTestId("leads-filter-apply").click();
			cy.getByTestId("lead-row").should("not.exist");
		});
	});

	it("shows a channel partner the card with no way to change it", () => {
		cy.signInFresh("channel_partner");
		cy.visit("/sellos/partner/leads");
		cy.getByTestId("leads-filters").should("be.visible");
		cy.getByTestId("lead-req-save").should("not.exist");
	});
});
