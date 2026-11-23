// SOS-P5-05: the client views. The gate client user is a buyer (a lead, a site visit and a deal) and a seller (a
// property with a Draft mandate and two enquiries, the second outside its response SLA). The client reads their own
// data, sees the Dossier only after the mandate is signed, sees each enquiry as four plain fields and nothing of
// the buyers, and another property's enquiry never shows. The clients and properties are named "Gate Buyer
// Views ...", "Gate Seller Views ..." and "Gate Deal Views ..." and are removed afterwards.
context("SOS-P5-05: the client views", () => {
	let made;

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		cy.bench("sellos.tests.ui_fixtures.make_gate_client_views").then((data) => {
			made = data;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	it("shows a buyer their visit and deal, and a seller their mandate and enquiries as plain rows, with the Dossier after the signature", () => {
		cy.signInFresh("client");
		cy.intercept("POST", "**/sellos.crm.client_views.my_overview*").as("overview");
		cy.visit("/sellos/client/overview");
		cy.wait("@overview").its("response.statusCode").should("eq", 200);

		cy.getByTestId("client-visit").should("contain", made.visit_project);
		cy.getByTestId("client-deal")
			.should("contain", made.deal_property)
			.and("contain", "Booked");

		cy.getByTestId("client-seller").should("contain", made.property);
		cy.getByTestId("client-mandate-status").should("contain", "Draft");
		cy.getByTestId("client-dossier").should("contain", "available once the mandate is signed");
		cy.getByTestId("client-seller").should("not.contain", "Gate owner reserve");

		cy.getByTestId("client-enquiry").should("have.length", 2);
		cy.getByTestId("client-enquiry-label").first().should("have.text", "Enquiry 1");
		cy.getByTestId("client-enquiry-sla").first().should("contain", "In SLA");
		cy.getByTestId("client-enquiry-sla").last().should("contain", "Outside SLA");
		cy.getByTestId("client-seller")
			.should("not.contain", made.one_name)
			.and("not.contain", made.two_name)
			.and("not.contain", made.stray_name);
		cy.getByTestId("client-overview-page").should("not.contain", "Gate views secret note");

		cy.bench("sellos.tests.ui_fixtures.sign_gate_client_mandate", {
			mandate: made.mandate,
			pdf: made.pdf,
		});
		cy.reload();
		cy.wait("@overview");
		cy.getByTestId("client-mandate-status").should("contain", "Signed");
		cy.getByTestId("client-dossier").should("contain", "Gate owner reserve");
		cy.getByTestId("client-overview-page").should("not.contain", "Gate views secret note");
	});

	it("keeps the client out of the agent's screens and the page out of reach of an agent", () => {
		cy.signInFresh("client");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("no-access").should("exist");
		cy.signInFresh("agent");
		cy.visit("/sellos/client/overview");
		cy.getByTestId("no-access").should("exist");
	});
});
