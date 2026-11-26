// SOS-P4-04: the seller pipeline. A Company Admin adds a seller (a lead on the Seller pipeline, linked to a
// client), moves it along the stages, is asked for a reason on Closed lost, and reads the stage history. The
// buyer Leads list does not show it. The records the spec makes (names start with "Gate Seller ") are removed
// afterwards.
context("SOS-P4-04: seller pipeline", () => {
	const row = (title) => cy.get(`[data-testid="sellos-seller-row"][data-title^="${title}"]`);
	const menu = (name, label) => {
		row(name).find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', label).click();
	};
	const openSellers = () => {
		cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("sellers");
		cy.visit("/sellos/crm/sellers");
		cy.wait("@sellers");
	};

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));

	it("adds a seller, moves it along its stages, asks for a lost reason and logs every move", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_seller").then((made) => {
			const name = made.client_name;
			cy.signInFresh("company_admin");
			openSellers();
			// The stage block is gone: the Filters button carries the stage filter, one option per stage.
			cy.getByTestId("seller-stage-count").should("not.exist");

			cy.intercept("POST", "**/sellos.crm.api.save_lead*").as("save");
			cy.getByTestId("seller-new").click();
			cy.getByTestId("seller-client").select(name);
			cy.getByTestId("seller-source").select("Website");
			cy.getByTestId("seller-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);
			row(name).should("have.attr", "data-stage", "New owner enquiry");

			cy.intercept("POST", "**/sellos.crm.api.move_lead_stage*").as("move");
			// A row holds no button but its menu; moving a stage is in the menu and opens a small drawer.
			row(name)
				.find("button:not([data-testid='sellos-row-menu-button'])")
				.should("not.exist");
			menu(name, "Move stage");
			cy.getByTestId("seller-move-to").select("Qualified");
			cy.get('textarea[data-testid="sellos-seller-move-note"]').type("Spoke to the owner");
			cy.getByTestId("seller-move").click();
			cy.wait("@move").its("response.statusCode").should("eq", 200);
			row(name).should("have.attr", "data-stage", "Qualified");
			cy.getByTestId("seller-notice").should("contain", "moved to Qualified");

			// Closed lost needs a reason.
			menu(name, "Move stage");
			cy.getByTestId("seller-move-to").select("Closed lost");
			cy.expectApiStatus("sellos.crm.api.move_lead_stage", 417);
			cy.getByTestId("seller-move").click();
			cy.wait("@move").its("response.statusCode").should("eq", 417);
			cy.getByTestId("seller-error").should("contain", "lost reason");
			cy.contains("button", "Cancel").click();
			row(name).should("have.attr", "data-stage", "Qualified");

			// The history names both moves' stages.
			menu(name, "Stage history");
			cy.getByTestId("seller-log")
				.find('[data-testid="sellos-seller-log-row"]')
				.should("have.length", 1)
				.and("contain", "New owner enquiry")
				.and("contain", "Qualified");

			// A seller is not on the buyer list.
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("leads-page").should("be.visible");
			cy.contains(name).should("not.exist");
		});
	});
});
