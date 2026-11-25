// SOS-P7-04: commission rates and payouts. A Company Admin adds a rate for a project, which makes the payout of
// a deal that was waiting for one, approves it and records its payment; a partner reads their own statement. An
// Agent has no Commission page. The records the spec makes (the project is named "Gate Inventory ", the client
// "Gate Deal ", the firm "Gate Firm ") are removed afterwards.
context("SOS-P7-04: commission rates and payouts", () => {
	// A payout's moves are in its row menu (SOS-LOOP): open the menu, then choose the move.
	const payoutAction = (label) => {
		cy.getByTestId("commission-payout").find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', label).click();
	};
	// Each test makes its own deal, project and firm, so each starts from a clean slate.
	beforeEach(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_commission"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_commission"));

	it("makes the payout when a rate is added, approves it and records the payment", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_commission", { stage: "waiting" }).then(
			(made) => {
				cy.signInFresh("company_admin");
				cy.intercept("POST", "**/sellos.inventory.commissions.commission_overview*").as(
					"overview"
				);
				cy.intercept("POST", "**/sellos.inventory.commissions.save_commission_rate*").as(
					"rate"
				);
				cy.intercept("POST", "**/sellos.inventory.commissions.move_payout*").as("move");
				cy.visit("/sellos/crm/commission");
				cy.wait("@overview");

				// The approved deal waits: there is no rate, so no payout.
				cy.getByTestId("commission-waiting").should("contain", made.deal);
				cy.getByTestId("commission-payout").should("not.exist");

				cy.getByTestId("commission-rate-new").click();
				cy.getByTestId("commission-project").select(made.project);
				cy.getByTestId("commission-value").type("2");
				cy.getByTestId("commission-start").type("2026-01-01");
				cy.getByTestId("commission-save-rate").click();
				cy.wait("@rate").its("response.statusCode").should("eq", 200);

				// 2% of Rs 80,00,000 is Rs 1,60,000. The firm's 20% of it is Rs 32,000.
				cy.getByTestId("commission-waiting").should("not.exist");
				cy.getByTestId("commission-rate").should("have.length", 1).and("contain", "2%");
				cy.getByTestId("commission-payout")
					.should("have.length", 1)
					.and("have.attr", "data-status", "Due")
					.and("contain", made.firm);
				cy.getByTestId("commission-payout-due").should("contain", "Rs 32,000");
				cy.getByTestId("commission-total-due").should("contain", "Rs 32,000");

				payoutAction("Approve");
				cy.wait("@move").its("response.statusCode").should("eq", 200);
				cy.getByTestId("commission-payout").should("have.attr", "data-status", "Approved");

				// A payment needs its reference and date.
				cy.expectApiStatus("sellos.inventory.commissions.move_payout", 417);
				payoutAction("Record payment");
				cy.getByTestId("commission-pay-save").click();
				cy.wait("@move").its("response.statusCode").should("eq", 417);
				cy.getByTestId("commission-error").should("contain", "payment reference");
				cy.getByTestId("commission-payout").should("have.attr", "data-status", "Approved");

				cy.getByTestId("commission-reference").type("UTR-SPEC-1");
				cy.getByTestId("commission-paid-on").type("2026-04-02");
				cy.getByTestId("commission-pay-save").click();
				cy.wait("@move").its("response.statusCode").should("eq", 200);
				cy.getByTestId("commission-payout").should("have.attr", "data-status", "Paid");
				cy.getByTestId("commission-payout-paid")
					.should("contain", "UTR-SPEC-1")
					.and("contain", "2 Apr 2026");
				cy.getByTestId("commission-total-paid").should("contain", "Rs 32,000");
				cy.getByTestId("commission-total-due").should("contain", "Rs 0");
			}
		);
	});

	it("puts a payout on hold with a reason and releases it", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_commission", { stage: "due" });
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.inventory.commissions.move_payout*").as("move");
		cy.visit("/sellos/crm/commission");
		cy.getByTestId("commission-payout").should("have.attr", "data-status", "Due");
		payoutAction("Put on hold");
		cy.getByTestId("commission-hold-reason").type("Waiting for the agreement copy");
		cy.getByTestId("commission-hold-save").click();
		cy.wait("@move").its("response.statusCode").should("eq", 200);
		cy.getByTestId("commission-payout").should("have.attr", "data-status", "On hold");
		cy.getByTestId("commission-payout-hold").should(
			"contain",
			"Waiting for the agreement copy"
		);
		payoutAction("Release the hold");
		cy.wait("@move").its("response.statusCode").should("eq", 200);
		cy.getByTestId("commission-payout").should("have.attr", "data-status", "Due");
	});

	it("shows a partner their own statement for a date range", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_commission", { stage: "paid" }).then(
			(made) => {
				cy.signInFresh("channel_partner");
				cy.intercept("POST", "**/sellos.inventory.commissions.partner_commission*").as(
					"statement"
				);
				cy.visit("/sellos/partner/commission");
				cy.wait("@statement");

				cy.getByTestId("partner-commission-payout")
					.should("have.length", 1)
					.and("have.attr", "data-status", "Paid")
					.and("have.attr", "data-deal", made.deal)
					.and("contain", "Rs 32,000")
					.and("contain", "UTR-GATE-704");
				cy.getByTestId("partner-commission-total-paid").should("contain", "Rs 32,000");
				cy.getByTestId("partner-commission-total").should("contain", "Rs 32,000");

				// A range that holds no booking has no payout.
				cy.getByTestId("partner-commission-from").clear().type("2025-01-01");
				cy.getByTestId("partner-commission-to").clear().type("2025-12-31");
				cy.getByTestId("partner-commission-to")
					.closest("form")
					.find("button[type=submit]")
					.click();
				cy.wait("@statement");
				cy.getByTestId("partner-commission-payout").should("not.exist");
				cy.contains("Nothing in these dates").should("be.visible");
			}
		);
	});

	it("gives an agent no Commission page", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("nav").should("not.contain", "Commission");
	});
});
