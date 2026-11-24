// SOS-P7-08: an Agent opens a lead's matching homes and sees each scored with its parts and reasons; a unit
// shows the leads it suits, only the agent's own, with a masked phone number. A held unit is never offered.
// The project, listing and buyers (names start with "Gate Inventory " and "Gate Match ") are removed afterwards.
context("SOS-P7-08: match buyers to inventory", () => {
	let made;
	const match = (unit) =>
		cy.get(`[data-testid="sellos-lead-match"][data-title$="unit ${unit}"]`);

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.make_gate_matches").then((data) => {
			made = data;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	it("shows an agent the matching homes of their lead, scored, with the reason of each part", () => {
		cy.signInFresh("agent");
		cy.intercept("POST", "**/sellos.inventory.matching.matches_for_lead*").as("matches");
		cy.visit(`/sellos/crm/leads/${encodeURIComponent(made.agent_lead)}?tab=requirements`);
		cy.getByTestId("lead-matches-load").click();
		cy.wait("@matches").its("response.statusCode").should("eq", 200);
		match("M101")
			.should("have.attr", "data-score", "95")
			.within(() => {
				cy.getByTestId("match-part").should("have.length", 4);
				cy.contains("5 percent over budget").should("be.visible");
				cy.contains("2 BHK matches").should("be.visible");
			});
		match("M102")
			.should("have.attr", "data-score")
			.and("match", /^[0-9]+$/);
		match("M103").should("not.exist"); // Held: never suggested
		cy.get('[data-testid="sellos-lead-match"][data-kind="Listing"]')
			.should("have.length", 1)
			.and("have.attr", "data-score", "100");
	});

	it("shows an agent only their own leads a unit suits, with masked phone numbers", () => {
		cy.signInFresh("agent");
		cy.intercept("POST", "**/sellos.inventory.matching.leads_for_unit*").as("suited");
		cy.visit(`/sellos/inventory/projects/${encodeURIComponent(made.project)}`);
		cy.get('[data-testid="sellos-grid-unit"][data-number="M101"]').click();
		cy.getByTestId("suited-load").click();
		cy.wait("@suited").its("response.statusCode").should("eq", 200);
		cy.getByTestId("suited-lead").should("have.length", 1).and("contain", made.agent_buyer);
		cy.getByTestId("suited-leads").should("not.contain", made.admin_buyer);
		made.phone_forms.forEach((form) => {
			cy.getByTestId("suited-leads").should("not.contain", form);
		});
		cy.getByTestId("suited-phone").should("not.be.empty");
	});

	it("shows a Company Admin every lead a unit suits and lets them set the weights", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.inventory.matching.leads_for_unit*").as("suited");
		cy.visit(`/sellos/inventory/projects/${encodeURIComponent(made.project)}`);
		cy.get('[data-testid="sellos-grid-unit"][data-number="M101"]').click();
		cy.getByTestId("suited-load").click();
		cy.wait("@suited");
		cy.getByTestId("suited-lead").should("have.length", 2);

		cy.intercept("POST", "**/sellos.inventory.matching.save_match_settings*").as("save");
		cy.visit("/sellos/inventory");
		cy.getByTestId("match-weights").should("be.visible");
		cy.getByTestId("match-weight-budget").clear().type("40");
		cy.getByTestId("match-weights-save").click();
		cy.wait("@save").its("response.statusCode").should("eq", 200);
		cy.getByTestId("match-weights-notice").should("contain", "The weights are saved.");
		cy.getByTestId("match-weight-budget").clear().type("25");
		cy.getByTestId("match-weights-save").click();
		cy.wait("@save").its("response.statusCode").should("eq", 200);
	});
});
