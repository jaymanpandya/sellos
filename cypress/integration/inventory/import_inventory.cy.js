// SOS-P4-10C: the Company Admin imports developers, projects, units, listings and mandates from a spreadsheet in the
// web app. The files come from seed_inventory_import_sample (generated names and numbers), and what the import made
// is read back from the database.
context("SOS-P4-10C: import the inventory, listings and mandates", () => {
	let sample;

	// Each test makes its own data, so none depends on another test having run (SOS-SETUP-24).
	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		cy.bench("sellos.tests.ui_fixtures.seed_inventory_import_sample").then((made) => {
			sample = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	const state = () =>
		cy.bench("sellos.tests.ui_fixtures.inventory_import_state", { tag: sample.tag });

	const openImport = () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/inventory/import");
		cy.getByTestId("inventory-import-page").should("be.visible");
	};

	// Choose the record type and the file, and wait for the dry run the page makes by itself.
	const chooseFile = (type) => {
		cy.intercept("POST", "**/sellos.inventory.import_data.preview_inventory_import*").as(
			"dryRun"
		);
		cy.getByTestId(`inventory-import-type-${type}`).click();
		cy.getByTestId("inventory-import-file").selectFile({
			contents: Cypress.Buffer.from(sample.files[type]),
			fileName: `gate-${type.toLowerCase()}.csv`,
			mimeType: "text/csv",
		});
		cy.wait("@dryRun");
	};

	const runImport = () => {
		cy.intercept("POST", "**/sellos.inventory.import_data.run_inventory_import*").as("run");
		cy.getByTestId("inventory-import-run").click();
		cy.wait("@run").its("response.statusCode").should("eq", 200);
		cy.getByTestId("inventory-import-result").should("be.visible");
	};

	it("downloads a template, shows a dry run that writes nothing, imports, and a second import changes nothing", () => {
		openImport();
		cy.intercept("POST", "**/sellos.inventory.import_data.import_template*").as("template");
		cy.getByTestId("inventory-import-type-Project").click();
		cy.getByTestId("inventory-import-help").should("contain", "RERA number");
		cy.getByTestId("inventory-import-template").click();
		cy.wait("@template").its("response.statusCode").should("eq", 200);

		chooseFile("Developer");
		cy.getByTestId("inventory-import-dry-counts").should(
			"contain",
			"1 rows: 1 would be created, 0 would be updated"
		);
		state().then((now) => expect(now.developers).to.eq(0));
		runImport();
		cy.getByTestId("inventory-import-result-counts").should("contain", "1 created");
		cy.getByTestId("inventory-import-report")
			.should("have.attr", "href")
			.and("contain", "/private/files/import-report-developers-");
		state().then((now) => expect(now.developers).to.eq(1));

		// The same file again: nothing is created or updated, and there is still one developer.
		chooseFile("Developer");
		cy.getByTestId("inventory-import-dry-counts").should("contain", "1 unchanged");
		runImport();
		cy.getByTestId("inventory-import-result-counts")
			.should("contain", "0 created, 0 updated, 1 unchanged")
			.and("contain", "0 failed");
		state().then((now) => expect(now.developers).to.eq(1));
	});

	it("names the rows that fail, merges duplicates in a file, and imports a mandate unsigned", () => {
		openImport();
		chooseFile("Developer");
		runImport();

		chooseFile("Project");
		cy.getByTestId("inventory-import-dry-counts").should("contain", "1 failed");
		cy.getByTestId("inventory-import-dry-failed").should("contain", "No Such Developer");
		runImport();
		cy.getByTestId("inventory-import-failed").should("contain", "Row 3");

		chooseFile("Unit");
		cy.getByTestId("inventory-import-dry-counts").should(
			"contain",
			"3 rows: 2 would be created, 0 would be updated, 0 unchanged, 1 merged into another row of the file"
		);
		state().then((now) => expect(now.units).to.have.length(0));
		runImport();
		state().then((now) => {
			expect(now.projects).to.eq(1);
			expect(now.units.map((u) => u.unit_number)).to.deep.eq(["101", "102"]);
			// The later row of unit 102 wins, and the status is never imported.
			expect(now.units[1].carpet_area).to.eq(660);
			expect(now.units.every((u) => u.status === "Available")).to.eq(true);
		});

		chooseFile("Listing");
		runImport();
		chooseFile("Mandate");
		runImport();
		state().then((now) => {
			expect(now.listings).to.deep.eq([{ published: 0, listing_type: "Primary" }]);
			expect(now.mandates).to.have.length(1);
			expect(now.mandates[0].status).to.eq("Draft");
			expect(now.mandates[0].signed_document).to.eq(null);
		});
	});

	it("is not offered to an agent, and the import refuses one", () => {
		cy.signInFresh("agent");
		cy.apiAs("sellos.inventory.import_data.run_inventory_import", {
			record_type: "Developer",
			csv_text: sample.files.Developer,
		})
			.its("status")
			.should("eq", 403);
		cy.visit("/sellos/inventory");
		cy.getByTestId("inventory-page").should("be.visible");
		cy.getByTestId("nav-inventory-import").should("not.exist");
		state().then((now) => expect(now.developers).to.eq(0));
	});
});
