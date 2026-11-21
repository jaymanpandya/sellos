// SOS-P4-01: a Company Admin creates a project with units in the web app, an Agent changes a unit's status
// and reads the log, a Sales Manager reads only, and a Client or Channel Partner sees no inventory. The
// records the spec makes (names start with "Gate Inventory ") are removed afterwards.
context("SOS-P4-01: developers, projects, units and properties", () => {
	const tag = Date.now();
	const developer = `Gate Inventory Developer ${tag}`;
	const projectName = `Gate Inventory Tower ${tag}`;
	const rera = `P5180${String(tag).slice(-7)}`;
	const unitRow = (number) => cy.get(`[data-testid="sellos-unit-row"][data-number="${number}"]`);

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory"));

	it("creates a developer, a project with its RERA number and two units, and saves them", () => {
		cy.signInFresh("company_admin");
		// The server refuses a bad RERA number and a repeated unit number: two answers the spec expects.
		cy.expectApiStatus("sellos.inventory.api.save_project", 417);
		cy.expectApiStatus("sellos.inventory.api.save_unit", 417);
		cy.intercept("POST", "**/sellos.inventory.api.inventory_overview*").as("overview");
		cy.visit("/sellos/inventory");
		cy.wait("@overview");
		cy.getByTestId("inventory-page").should("be.visible");

		cy.intercept("POST", "**/sellos.inventory.api.save_developer*").as("saveDeveloper");
		cy.getByTestId("inventory-developer-name").type(developer);
		cy.getByTestId("inventory-developer-save").click();
		cy.wait("@saveDeveloper").its("response.statusCode").should("eq", 200);
		cy.getByTestId("inventory-notice").should("contain", "was added");

		// A RERA number that can not be one is refused by the server and nothing is made.
		cy.intercept("POST", "**/sellos.inventory.api.save_project*").as("saveProject");
		cy.getByTestId("inventory-project-name").type(projectName);
		cy.getByTestId("inventory-project-developer").select(developer);
		cy.getByTestId("inventory-project-city").type("Mumbai");
		cy.getByTestId("inventory-project-rera").type("no");
		cy.getByTestId("inventory-project-save").click();
		cy.wait("@saveProject");
		cy.getByTestId("inventory-error").should("be.visible");
		cy.contains('[data-testid="sellos-inventory-project-row"]', projectName).should(
			"not.exist"
		);

		cy.getByTestId("inventory-project-rera").clear().type(rera.toLowerCase());
		cy.getByTestId("inventory-project-save").click();
		cy.wait("@saveProject").its("response.statusCode").should("eq", 200);
		cy.contains('[data-testid="sellos-inventory-project-row"]', projectName)
			.should("contain", rera)
			.find('[data-testid="sellos-inventory-project-link"]')
			.click();

		cy.getByTestId("project-page").should("be.visible");
		cy.getByTestId("project-rera").should("have.text", rera);
		cy.intercept("POST", "**/sellos.inventory.api.save_unit*").as("saveUnit");
		cy.getByTestId("unit-number-input").type("1201");
		cy.getByTestId("unit-configuration").select("2 BHK");
		cy.getByTestId("unit-area").type("640");
		cy.getByTestId("unit-floor").type("12");
		cy.getByTestId("unit-parking").type("2");
		cy.getByTestId("unit-save").click();
		cy.wait("@saveUnit").its("response.statusCode").should("eq", 200);
		cy.getByTestId("unit-number-input").type("1202");
		cy.getByTestId("unit-area").type("655");
		cy.getByTestId("unit-save").click();
		cy.wait("@saveUnit").its("response.statusCode").should("eq", 200);
		// The same unit number twice in one project is refused.
		cy.getByTestId("unit-number-input").type("1202");
		cy.getByTestId("unit-area").type("655");
		cy.getByTestId("unit-save").click();
		cy.wait("@saveUnit");
		cy.getByTestId("project-error").should("contain", "already in this project");
		unitRow("1201").should("have.attr", "data-status", "Available");
		unitRow("1202").should("have.attr", "data-status", "Available");
		cy.getByTestId("project-counts").should("contain", "2 units");

		// It is saved: the server holds the RERA number and both units.
		cy.bench("sellos.tests.ui_fixtures.gate_project_state", {
			project_name: projectName,
		}).then((state) => {
			expect(state.rera_number).to.eq(rera);
			expect(Object.keys(state.units).sort()).to.deep.eq(["1201", "1202"]);
			expect(state.units["1201"].carpet_area).to.eq(640);
			expect(state.units["1201"].log).to.deep.eq(["Available"]);
		});
	});

	it("lets an agent hold and sell a unit, and logs each change with its reason", () => {
		cy.signInFresh("agent");
		cy.intercept("POST", "**/sellos.inventory.api.get_project*").as("project");
		cy.intercept("POST", "**/sellos.inventory.api.set_inventory_status*").as("status");
		cy.visit("/sellos/inventory");
		cy.contains('[data-testid="sellos-inventory-project-row"]', projectName)
			.find('[data-testid="sellos-inventory-project-link"]')
			.click();
		cy.wait("@project");
		unitRow("1201").find('[data-testid="sellos-unit-reason"]').type("Buyer needs two days");
		unitRow("1201").find('[data-testid="sellos-unit-set-held"]').click();
		cy.wait("@status").its("response.statusCode").should("eq", 200);
		unitRow("1201").should("have.attr", "data-status", "Held");
		unitRow("1201").find('[data-testid="sellos-unit-set-sold"]').click();
		cy.wait("@status").its("response.statusCode").should("eq", 200);
		unitRow("1201").should("have.attr", "data-status", "Sold");
		unitRow("1201").find("summary").click();
		unitRow("1201").find('[data-testid="sellos-unit-log-row"]').should("have.length", 3);
		unitRow("1201")
			.find('[data-testid="sellos-unit-log"]')
			.should("contain", "Buyer needs two days");
		cy.getByTestId("project-counts").should("contain", "1 sold");
		cy.bench("sellos.tests.ui_fixtures.gate_project_state", {
			project_name: projectName,
		}).then((state) => {
			expect(state.units["1201"].status).to.eq("Sold");
			expect(state.units["1201"].log).to.deep.eq(["Available", "Held", "Sold"]);
		});
	});

	it("lets a Sales Manager read inventory but not change it", () => {
		cy.signInFresh("sales_manager");
		cy.visit("/sellos/inventory");
		cy.getByTestId("inventory-page").should("be.visible");
		cy.contains('[data-testid="sellos-inventory-project-row"]', projectName)
			.find('[data-testid="sellos-inventory-project-link"]')
			.click();
		unitRow("1201").should("be.visible");
		cy.getByTestId("unit-form").should("not.exist");
		cy.getByTestId("unit-set-held").should("not.exist");
	});

	it("keeps inventory from a client and a channel partner", () => {
		["client", "channel_partner"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/inventory");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("inventory-page").should("not.exist");
		});
	});
});
