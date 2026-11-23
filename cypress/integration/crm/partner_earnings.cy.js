// SOS-P5-06: the Channel Partner views. A partner reads their own deal, what they have earned so far, what they
// may still earn and their own QR code. An Agent has no such page. Registering a buyer is SOS-P7-02's screen
// (cypress/integration/security/partner_registrations.cy.js) and is not built twice. The records the spec makes
// (project "Gate Inventory ", client "Gate Deal ", firm "Gate Firm ") are removed afterwards.
context("SOS-P5-06: channel partner deals and earnings", () => {
	beforeEach(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_commission"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_commission"));

	const open = () => {
		cy.signInFresh("channel_partner");
		cy.intercept("POST", "**/sellos.crm.partner_views.partner_overview*").as("overview");
		cy.visit("/sellos/partner/earnings");
		cy.wait("@overview").its("response.statusCode").should("eq", 200);
	};

	it("shows the partner earnings so far, potential earnings, their deal and their QR code", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_commission", { stage: "paid" }).then(
			(made) => {
				open();
				cy.getByTestId("partner-earnings-earned").should("contain", "32,000.00");
				cy.getByTestId("partner-earnings-potential").should("contain", "0.00");
				cy.getByTestId("partner-earnings-deal")
					.should("have.length", 1)
					.and("have.attr", "data-deal", made.deal)
					.and("have.attr", "data-status", "Paid")
					.and("contain", "20%");
				cy.getByTestId("partner-earnings-qr")
					.should("be.visible")
					.and("have.attr", "src")
					.and("match", /^data:image\/svg\+xml;base64,/);
				cy.getByTestId("partner-earnings-link").should("contain", "partner=");
			}
		);
	});

	it("counts a payout that is not yet paid as potential earnings", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_commission", { stage: "due" });
		open();
		cy.getByTestId("partner-earnings-earned").should("contain", "0.00");
		cy.getByTestId("partner-earnings-potential").should("contain", "32,000.00");
		cy.getByTestId("partner-earnings-deal").should("have.attr", "data-status", "Due");
	});

	it("is in the partner's menu and not in an agent's", () => {
		cy.signInFresh("channel_partner");
		cy.visit("/sellos");
		cy.getByTestId("nav").should("contain", "Deals and earnings");
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("nav").should("not.contain", "Deals and earnings");
	});
});
