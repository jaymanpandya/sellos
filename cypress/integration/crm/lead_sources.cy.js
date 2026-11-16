// SOS-P1-20: the lead source picker. The list comes from the real server. The spec makes its own
// source and client (names start with Gate Source) and removes them afterwards (SOS-SETUP-24).
const STANDARD = [
	"Website",
	"Portal",
	"Referral",
	"Walk in",
	"Channel partner",
	"Facebook",
	"Missed call",
	"Bought list",
];

context("SOS-P1-20: the lead source picker", () => {
	const tag = Date.now();
	const source = `Gate Source ${tag}`;

	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_lead_sources");
	});

	it("a company admin adds a source, chooses it and saves a lead with it", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/api/method/sellos.crm.api.save_lead_source").as("addSource");
		cy.intercept("POST", "**/api/method/sellos.crm.api.save_lead").as("saveLead");
		cy.intercept("POST", "**/api/method/sellos.crm.api.list_clients*").as("mergeChoices");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("leads-new").click();
		STANDARD.forEach((name) => {
			cy.getByTestId("lead-form-source").find("option").contains(name).should("exist");
		});
		cy.getByTestId("lead-source-new").type(source);
		cy.getByTestId("lead-source-add-button").click();
		cy.wait("@addSource").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-form-source").find("option:selected").should("have.text", source);

		cy.getByTestId("lead-form-name").type(`Gate Source Client ${tag}`);
		cy.getByTestId("lead-form-campaign").type("Gate Campaign");
		cy.getByTestId("lead-form").submit();
		cy.wait("@saveLead").its("response.statusCode").should("eq", 200);
		cy.location("pathname").should("match", /\/sellos\/crm\/leads\/LD-/);
		// Let the lead page finish its own requests before leaving it, so none is cut off.
		cy.wait("@mergeChoices").its("response.statusCode").should("eq", 200);

		cy.visit("/sellos/crm/leads");
		cy.getByTestId("lead-row")
			.contains(`Gate Source Client ${tag}`)
			.closest("[data-testid=sellos-lead-row]")
			.find("[data-testid=sellos-lead-source]")
			.should("contain", source)
			.and("contain", "Gate Campaign");
	});

	it("an agent picks from the list and cannot extend it", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("leads-new").click();
		cy.getByTestId("lead-form-source").find("option").contains(source).should("exist");
		cy.getByTestId("lead-form-source").find("option").contains("Referral").should("exist");
		cy.getByTestId("lead-source-new").should("not.exist");
		cy.getByTestId("lead-form-source").select("Referral");
		cy.getByTestId("lead-form-source").find("option:selected").should("have.text", "Referral");
	});
});
