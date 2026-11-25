// SOS-P7-05: a Company Admin adds a tower to a project, adds its floors and generates the units of a floor
// from a pattern; generating again changes nothing; a unit that is not Available stops the removal of its
// floor; the possession date and amenities are saved; a Sales Manager only reads. The records the spec makes
// (names start with "Gate Inventory ") are removed afterwards.
context("SOS-P7-05: towers, wings and floors for projects", () => {
	const tag = Date.now();
	const developer = `Gate Inventory Developer ${tag}`;
	const projectName = `Gate Inventory Tower ${tag}`;
	const amenity = `Gate Inventory Pool ${tag}`;
	const rera = `P5180${String(tag).slice(-7)}`;
	const towerRow = (name) => cy.get(`[data-testid="sellos-tower-row"][data-tower="${name}"]`);
	const floorRow = (n) => cy.get(`[data-testid="sellos-floor-row"][data-floor="${n}"]`);

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory"));

	it("adds a tower, generates a floor twice and keeps Held units from being removed", () => {
		cy.signInFresh("company_admin");
		// The server refuses the removal of a floor with a Held unit: the answer the spec expects.
		cy.expectApiStatus("sellos.inventory.structure.remove_floor", 417);
		cy.intercept("POST", "**/sellos.inventory.api.inventory_overview*").as("overview");
		cy.visit("/sellos/inventory");
		cy.wait("@overview");
		cy.intercept("POST", "**/sellos.inventory.api.save_developer*").as("saveDeveloper");
		cy.getByTestId("inventory-add-developer").click();
		cy.getByTestId("inventory-developer-name").type(developer);
		cy.getByTestId("inventory-developer-save").click();
		cy.wait("@saveDeveloper").its("response.statusCode").should("eq", 200);
		cy.intercept("POST", "**/sellos.inventory.api.save_project*").as("saveProject");
		cy.getByTestId("inventory-add-project").click();
		cy.getByTestId("inventory-project-name").type(projectName);
		cy.getByTestId("inventory-project-developer").select(developer);
		cy.getByTestId("inventory-project-city").type("Mumbai");
		cy.getByTestId("inventory-project-rera").type(rera);
		cy.getByTestId("inventory-project-save").click();
		cy.wait("@saveProject").its("response.statusCode").should("eq", 200);
		cy.contains('[data-testid="sellos-inventory-project-row"]', projectName)
			.find('[data-testid="sellos-inventory-project-link"]')
			.click();
		cy.getByTestId("project-page").should("be.visible");
		cy.getByTestId("tab-structure").click();

		cy.intercept("POST", "**/sellos.inventory.structure.add_tower*").as("addTower");
		cy.getByTestId("tower-open").click();
		cy.getByTestId("tower-name-input").type("Tower A");
		cy.getByTestId("tower-floors-input").type("11 to 12");
		cy.getByTestId("tower-save").click();
		cy.wait("@addTower").its("response.statusCode").should("eq", 200);
		towerRow("Tower A").should("contain", "2 floors");
		floorRow(12).should("be.visible");

		cy.intercept("POST", "**/sellos.inventory.structure.generate_floor_units*").as("generate");
		cy.getByTestId("generate-open").click();
		cy.getByTestId("generate-tower").select("Tower A");
		cy.getByTestId("generate-floor").select("12");
		cy.getByTestId("generate-pattern").type("1201 to 1208");
		cy.getByTestId("generate-configuration").select("2 BHK");
		cy.getByTestId("generate-area").type("640");
		cy.getByTestId("generate-save").click();
		cy.wait("@generate").its("response.statusCode").should("eq", 200);
		cy.getByTestId("structure-notice").should("contain", "8 units made, 0 already there");
		floorRow(12).find('[data-testid="sellos-floor-unit"]').should("have.length", 8);

		// Generating again changes nothing.
		cy.getByTestId("generate-open").click();
		cy.getByTestId("generate-save").click();
		cy.wait("@generate").its("response.statusCode").should("eq", 200);
		cy.getByTestId("structure-notice").should("contain", "0 units made, 8 already there");
		floorRow(12).find('[data-testid="sellos-floor-unit"]').should("have.length", 8);

		// A Held unit stops the floor from being removed, and the message counts it.
		cy.getByTestId("tab-units").click();
		cy.get('[data-testid="sellos-unit-row"][data-number="1203"]')
			.find('[data-testid="sellos-unit-set-held"]')
			.click();
		cy.get('[data-testid="sellos-unit-row"][data-number="1203"]').should(
			"have.attr",
			"data-status",
			"Held"
		);
		cy.getByTestId("tab-structure").click();
		cy.intercept("POST", "**/sellos.inventory.structure.remove_floor*").as("removeFloor");
		floorRow(12).find('[data-testid="sellos-floor-remove"]').click();
		cy.wait("@removeFloor");
		cy.getByTestId("structure-error").should("contain", "1 of its units are not Available");
		floorRow(12).should("be.visible");

		// An empty floor goes.
		floorRow(11).find('[data-testid="sellos-floor-remove"]').click();
		cy.wait("@removeFloor").its("response.statusCode").should("eq", 200);
		floorRow(11).should("not.exist");

		cy.bench("sellos.tests.ui_fixtures.gate_tower_state", { project_name: projectName }).then(
			(state) => {
				expect(state.towers["Tower A"].floors).to.deep.eq([12]);
				expect(state.towers["Tower A"].units).to.have.length(8);
			}
		);
	});

	it("saves the possession date and the amenities a Company Admin keeps", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.inventory.api.get_project*").as("project");
		cy.visit("/sellos/inventory");
		cy.contains('[data-testid="sellos-inventory-project-row"]', projectName)
			.find('[data-testid="sellos-inventory-project-link"]')
			.click();
		cy.wait("@project");
		cy.getByTestId("tab-structure").click();
		cy.intercept("POST", "**/sellos.inventory.structure.save_amenity*").as("saveAmenity");
		cy.getByTestId("amenity-input").type(amenity);
		cy.getByTestId("amenity-add").click();
		cy.wait("@saveAmenity").its("response.statusCode").should("eq", 200);
		cy.get(`[data-testid="sellos-amenity-choice"][data-amenity="${amenity}"]`).should("exist");
		cy.get(`[data-testid="sellos-amenity-choice"][data-amenity="${amenity}"]`).check({
			force: true,
		});
		cy.getByTestId("possession-date").type("2028-03-31");
		cy.intercept("POST", "**/sellos.inventory.structure.save_project_details*").as("details");
		cy.getByTestId("details-save").click();
		cy.wait("@details").its("response.statusCode").should("eq", 200);
		cy.getByTestId("project-possession").should("contain", "31 Mar 2028");
		cy.bench("sellos.tests.ui_fixtures.gate_tower_state", { project_name: projectName }).then(
			(state) => {
				expect(state.possession_date).to.eq("2028-03-31");
				expect(state.amenities).to.deep.eq([amenity]);
			}
		);
	});

	it("lets a Sales Manager read the structure but not change it", () => {
		cy.signInFresh("sales_manager");
		cy.visit("/sellos/inventory");
		cy.contains('[data-testid="sellos-inventory-project-row"]', projectName)
			.find('[data-testid="sellos-inventory-project-link"]')
			.click();
		cy.getByTestId("tab-structure").click();
		towerRow("Tower A").should("be.visible");
		cy.getByTestId("tower-form").should("not.exist");
		cy.getByTestId("generate-form").should("not.exist");
		cy.getByTestId("floor-remove").should("not.exist");
		cy.getByTestId("details-save").should("not.exist");
	});
});
