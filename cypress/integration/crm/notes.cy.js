// SOS-LOOP: notes on a seller. A Company Admin adds a note of a managed type with an image, sees it as a pill with a
// thumbnail, filters by type, edits it, removes it, and is asked for a label when the type is Other. The seller the
// spec makes is named "Gate Seller Mandate " and is removed afterwards.
context("Notes on a seller", () => {
	// A 1 x 1 PNG.
	const PNG =
		"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));

	it("adds, filters, edits and removes a note with an image", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_mandate_seller").then((made) => {
			cy.signInFresh("company_admin");
			cy.intercept("POST", "**/sellos.crm.notes.list_notes*").as("list");
			cy.intercept("POST", "**/sellos.crm.notes.add_note*").as("add");
			cy.intercept("POST", "**/sellos.crm.notes.update_note*").as("update");
			cy.intercept("POST", "**/sellos.crm.notes.delete_note*").as("remove");
			cy.visit(`/sellos/crm/sellers/${made.lead}`);
			cy.wait("@list");
			cy.getByTestId("note-empty").should("be.visible");

			// A note with a photo.
			cy.getByTestId("note-new").click();
			cy.getByTestId("note-type-select").select("Photos");
			cy.getByTestId("note-text").type("Front of the building");
			cy.getByTestId("note-files").selectFile({
				contents: Cypress.Buffer.from(PNG, "base64"),
				fileName: "front.png",
				mimeType: "image/png",
			});
			cy.getByTestId("note-picked").should("contain", "front.png");
			cy.getByTestId("note-save").click();
			cy.wait("@add").its("response.statusCode").should("eq", 200);
			cy.get('[data-testid="sellos-note"][data-type="Photos"]')
				.should("have.length", 1)
				.within(() => {
					cy.getByTestId("note-type").should("contain", "Photos");
					cy.getByTestId("note-body").should("contain", "Front of the building");
					cy.getByTestId("note-image").find("img").should("have.attr", "src");
				});

			// Other asks for a short label.
			cy.getByTestId("note-new").click();
			cy.getByTestId("note-type-select").select("Other");
			cy.getByTestId("note-text").type("Parking is shared");
			cy.expectApiStatus("sellos.crm.notes.add_note", 417);
			cy.getByTestId("note-save").click();
			cy.wait("@add").its("response.statusCode").should("eq", 417);
			cy.getByTestId("note-error").should("contain", "short label");
			cy.getByTestId("note-label").type("Parking");
			cy.getByTestId("note-save").click();
			cy.wait("@add").its("response.statusCode").should("eq", 200);
			cy.get('[data-testid="sellos-note"][data-type="Parking"]').should("have.length", 1);

			// Filter by type.
			cy.getByTestId("note-filter").select("Photos");
			cy.get('[data-testid="sellos-note"]').should("have.length", 1);
			cy.getByTestId("note-filter").select("All types");
			cy.get('[data-testid="sellos-note"]').should("have.length", 2);

			// Edit, then remove.
			cy.get('[data-testid="sellos-note"][data-type="Photos"]')
				.find('[data-testid="sellos-note-edit"]')
				.click();
			cy.getByTestId("note-text").clear().type("Front, seen from the road");
			cy.getByTestId("note-save").click();
			cy.wait("@update").its("response.statusCode").should("eq", 200);
			cy.get('[data-testid="sellos-note"][data-type="Photos"]')
				.should("contain", "Front, seen from the road")
				.and("contain", "edited");
			cy.get('[data-testid="sellos-note"][data-type="Photos"]')
				.find('[data-testid="sellos-note-remove"]')
				.click();
			cy.get('[data-testid="sellos-note"][data-type="Photos"]')
				.find('[data-testid="sellos-note-remove-confirm"]')
				.click();
			cy.wait("@remove").its("response.statusCode").should("eq", 200);
			cy.get('[data-testid="sellos-note"]').should("have.length", 1);
		});
	});
});
