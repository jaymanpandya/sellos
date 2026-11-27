// SOS-P4-06: a deal and its commission split. A Company Admin records a deal for a client and a property with an
// agent, a channel partner and the company, is refused a split that does not add up to 100, records it with a
// split that does, approves it and reopens it. An Agent has no Deals page. The records the spec makes (the client
// and property are named "Gate Deal ") are removed afterwards.
context("SOS-P4-06: deals and the commission split", () => {
	const row = (client) => cy.get(`[data-testid="sellos-deal-row"][data-client="${client}"]`);
	// Approve and Reopen are in the row menu (docs/DESIGN_SYSTEM.md, "Lists"): open it, then choose the move.
	const rowAction = (client, label) => {
		row(client).find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', label).click();
	};

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));

	it("refuses a split that is not 100, records one that is, approves and reopens it", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_deal").then((made) => {
			cy.signInFresh("company_admin");
			cy.intercept("POST", "**/sellos.inventory.deals.deal_overview*").as("overview");
			cy.intercept("POST", "**/sellos.inventory.deals.save_deal*").as("save");
			cy.intercept("POST", "**/sellos.inventory.deals.approve_splits*").as("approve");
			cy.intercept("POST", "**/sellos.inventory.deals.reopen_splits*").as("reopen");
			cy.visit("/sellos/crm/deals");
			cy.wait("@overview");

			cy.getByTestId("deal-new").click();
			cy.getByTestId("deal-client").select(made.client);
			cy.getByTestId("deal-property").select(made.property);
			cy.getByTestId("deal-price").type("8200000");
			cy.getByTestId("deal-commission").type("123000");
			cy.getByTestId("deal-agent").select(made.agent);
			cy.getByTestId("deal-agent-percent").type("40");
			cy.getByTestId("deal-firm").select(made.firm);
			cy.getByTestId("deal-firm-percent").type("20");
			cy.getByTestId("deal-company-percent").type("30");
			cy.getByTestId("deal-total").should("contain", "adds up to 90 percent");

			// 40 + 20 + 30 is 90: the server refuses it and nothing is saved.
			cy.expectApiStatus("sellos.inventory.deals.save_deal", 417);
			cy.getByTestId("deal-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 417);
			cy.getByTestId("deal-error").should("contain", "exactly 100 percent");
			row(made.client).should("not.exist");

			// 40 + 20 + 40 is 100.
			cy.getByTestId("deal-company-percent").clear().type("40");
			cy.getByTestId("deal-total").should("contain", "adds up to 100 percent");
			cy.getByTestId("deal-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);
			row(made.client).should("have.attr", "data-status", "Pending approval");
			row(made.client)
				.find('[data-testid="sellos-deal-split"]')
				.should("have.length", 3)
				.and("contain", "49,200");
			row(made.client)
				.find('[data-testid="sellos-deal-split"][data-party="Channel Partner"]')
				.should("have.length", 1);
			// The split columns: the partners line says there is a channel partner, and each party shows its share.
			row(made.client)
				.find('[data-testid="sellos-deal-has-split"]')
				.should("contain", "Yes");
			row(made.client)
				.find('[data-testid="sellos-deal-split"][data-party="Channel Partner"]')
				.should("contain", "20%");
			row(made.client)
				.find('[data-testid="sellos-deal-split"][data-party="Agent"]')
				.should("contain", "40%");
			row(made.client)
				.find('[data-testid="sellos-deal-split"][data-party="Company"]')
				.should("contain", "40%");

			// The period switch defaults to Month to date, shows its dates, and drives the cards.
			cy.getByTestId("deal-period").should("contain", "Month to date");
			cy.getByTestId("deal-period-dates").should("contain", " to ");
			cy.getByTestId("deal-stats").should("contain", "Total commission");
			cy.getByTestId("deal-stats").should("contain", "Channel Partner payout");
			cy.getByTestId("deal-stats").should("contain", "Company share");

			// A Company Admin approves the split, then reopens it.
			row(made.client)
				.find('button:not([data-testid="sellos-row-menu-button"])')
				.should("not.exist");
			rowAction(made.client, "Approve the split");
			cy.wait("@approve").its("response.statusCode").should("eq", 200);
			row(made.client).should("have.attr", "data-status", "Approved");
			row(made.client).find('[data-testid="sellos-deal-approved"]').should("be.visible");
			// One line: the date, then who approved it. The long sentence is on the deal page, not in the cell.
			row(made.client)
				.find('[data-testid="sellos-deal-approved"]')
				.invoke("text")
				.should("match", /^\d{1,2} [A-Z][a-z]{2} \d{4} \u00b7 \S/)
				.and("not.contain", "The split is kept");
			rowAction(made.client, "Reopen the split");
			cy.wait("@reopen").its("response.statusCode").should("eq", 200);
			row(made.client).should("have.attr", "data-status", "Pending approval");
		});
	});

	it("gives an agent no Deals page", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("nav").should("not.contain", "Deals");
	});
});
