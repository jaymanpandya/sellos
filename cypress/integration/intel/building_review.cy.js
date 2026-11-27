// SOS-P3-04: editing a building, and correcting then confirming one on the building review screen, against
// the real server. The market and two buildings come from sellos.tests.ui_fixtures.seed_building_review (made
// through the buildings API) and are removed afterwards (SOS-SETUP-24).
context("SOS-P3-04: the building review", () => {
	let made;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_building_review").then((data) => {
			made = data;
		});
	});

	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_buildings");
	});

	const openBuilding = (name) => {
		cy.getByTestId("building-row").contains(name).click();
		cy.getByTestId("building-form").should("be.visible");
	};

	it("an agent corrects a building and the correction keeps the old value", () => {
		cy.signInFresh("agent");
		cy.intercept("POST", "**/api/method/sellos.intel.buildings_api.correct_building*").as(
			"correct"
		);
		cy.visit("/sellos/inventory/buildings");
		cy.getByTestId("building-row").should("have.length.at.least", 2);
		openBuilding(made.first);
		cy.getByTestId("building-village").type("Gate Village");
		cy.getByTestId("building-save").click();
		cy.wait("@correct").its("response.statusCode").should("eq", 200);
		cy.getByTestId("buildings-notice").should("contain", "Corrections saved");
		openBuilding(made.first);
		cy.getByTestId("building-correction")
			.should("have.length", 1)
			.and("contain", "Village")
			.and("contain", "empty")
			.and("contain", "Gate Village");
	});

	it("an agent confirms a building and it moves to the Confirmed tab", () => {
		cy.signInFresh("agent");
		cy.intercept("POST", "**/api/method/sellos.intel.buildings_api.confirm_building*").as(
			"confirm"
		);
		cy.visit("/sellos/inventory/buildings");
		openBuilding(made.second);
		cy.getByTestId("building-confirm").click();
		cy.wait("@confirm").its("response.statusCode").should("eq", 200);
		cy.getByTestId("buildings-notice").should("contain", "Building confirmed");
		cy.getByTestId("building-row").should("not.contain", made.second);
		cy.getByTestId("tab-Confirmed").click();
		cy.getByTestId("building-row")
			.contains(made.second)
			.closest("[data-testid=sellos-building-row]")
			.should("have.attr", "data-status", "Confirmed");
	});

	it("a company admin adds a building and edits its RERA number", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/api/method/sellos.intel.buildings_api.save_building*").as("save");
		cy.intercept("POST", "**/api/method/sellos.intel.buildings_api.correct_building*").as(
			"correct"
		);
		const name = `${made.first} Added`;
		cy.visit("/sellos/inventory/buildings");
		cy.getByTestId("buildings-new").click();
		cy.getByTestId("building-name").type(name);
		cy.getByTestId("building-save").click();
		cy.wait("@save").its("response.statusCode").should("eq", 200);
		cy.getByTestId("building-row").contains(name).should("be.visible");
		openBuilding(name);
		cy.getByTestId("building-rera-number").type("p51800 000777");
		cy.getByTestId("building-save").click();
		cy.wait("@correct").its("response.statusCode").should("eq", 200);
		cy.getByTestId("building-row").contains("P51800000777").should("be.visible");
	});
});
