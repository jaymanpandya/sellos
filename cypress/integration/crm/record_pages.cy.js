// The record pages of a seller, a mandate and a deal (docs/DESIGN_SYSTEM.md, the record shape). A Company Admin
// opens each from its list and finds the record header with its status pill, a side column that is not empty, and a
// missing value reading "Not filled in". The records the spec makes (names start with "Gate Seller " and
// "Gate Deal ") are removed afterwards.
context("Record pages: seller, mandate and deal", () => {
	const checkShape = (statusTestId) => {
		cy.getByTestId("record-header").should("be.visible");
		cy.getByTestId("record-title").should("not.be.empty");
		cy.getByTestId(statusTestId).should("be.visible");
		cy.get('[aria-label="Summary"]').should("be.visible").and("not.be.empty");
		cy.get('[aria-label="Summary"]').find("section").should("have.length.at.least", 1);
	};

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));

	it("opens a seller from the list", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_seller").then((made) => {
			cy.signInFresh("company_admin");
			cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("sellers");
			cy.intercept("POST", "**/sellos.crm.api.save_lead*").as("save");
			cy.visit("/sellos/crm/sellers");
			cy.wait("@sellers");
			cy.getByTestId("seller-new").click();
			cy.getByTestId("seller-client").select(made.client_name);
			cy.getByTestId("seller-source").select("Website");
			cy.getByTestId("seller-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);

			cy.get(`[data-testid="sellos-seller-row"][data-title^="${made.client_name}"]`)
				.find("a")
				.first()
				.click();
			cy.location("pathname").should("match", /\/sellos\/crm\/sellers\/[^/]+$/);
			cy.getByTestId("seller-page").should("be.visible");
			checkShape("seller-stage");
			cy.getByTestId("seller-stage").should("contain", "New owner enquiry");
			// No lost reason and no mandate yet: the side column says so.
			cy.get('[aria-label="Summary"]').should("contain", "Not filled in");
			cy.getByTestId("seller-move-to").should("exist");
		});
	});

	it("opens a mandate from the list", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_mandate_seller").then((made) => {
			cy.signInFresh("company_admin");
			cy.intercept("POST", "**/sellos.inventory.mandates.mandate_overview*").as("overview");
			cy.intercept("POST", "**/sellos.inventory.mandates.save_mandate*").as("save");
			cy.visit("/sellos/crm/mandates");
			cy.wait("@overview");
			cy.getByTestId("mandate-new").click();
			cy.getByTestId("mandate-lead").select(made.lead);
			cy.getByTestId("mandate-type").select("Open");
			cy.getByTestId("mandate-term").type("12");
			cy.getByTestId("mandate-fee").type("2");
			cy.getByTestId("mandate-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);

			cy.get(`[data-testid="sellos-mandate-row"][data-title="${made.title}"]`)
				.find("a")
				.first()
				.click();
			cy.location("pathname").should("match", /\/sellos\/crm\/mandates\/[^/]+$/);
			cy.getByTestId("mandate-page").should("be.visible");
			checkShape("mandate-status");
			cy.getByTestId("mandate-status").should("contain", "Draft");
			// The same signing control as the list.
			cy.getByTestId("mandate-sign-file").should("exist");
		});
	});

	it("opens a deal from the list", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_deal").then((made) => {
			cy.signInFresh("company_admin");
			cy.intercept("POST", "**/sellos.inventory.deals.deal_overview*").as("overview");
			cy.intercept("POST", "**/sellos.inventory.deals.save_deal*").as("save");
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
			cy.getByTestId("deal-company-percent").type("40");
			cy.getByTestId("deal-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);

			cy.get(`[data-testid="sellos-deal-row"][data-client="${made.client}"]`)
				.find("a")
				.first()
				.click();
			cy.location("pathname").should("match", /\/sellos\/crm\/deals\/[^/]+$/);
			cy.getByTestId("deal-page").should("be.visible");
			checkShape("deal-status");
			cy.getByTestId("deal-status").should("contain", "Pending approval");
			// Nobody has approved it yet: "Approved by" reads Not filled in.
			cy.getByTestId("deal-page").should("contain", "Not filled in");
			cy.getByTestId("deal-approve").should("be.visible");
		});
	});
});
