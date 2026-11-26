// SOS-P4-05: a mandate and its Private Sale Dossier. An Agent records a mandate for their seller, cannot sign it
// without a valid signed document, cannot move the seller to Listed while it is a draft, signs it, opens the
// Dossier (which was hidden until then) twice, and then moves the seller to Listed. The records the spec makes
// (names start with "Gate Seller ") are removed afterwards.
context("SOS-P4-05: mandates and the Private Sale Dossier", () => {
	const row = (title) => cy.get(`[data-testid="sellos-mandate-row"][data-title="${title}"]`);
	// Every row action is in the row menu (docs/DESIGN_SYSTEM.md, "Lists"): the signature and the Dossier are in a
	// drawer opened from "Record signature manually", and a seller moves stage from "Move stage".
	const drawer = () => cy.get('[data-testid="sellos-mandate-drawer"]');
	const menu = (rowEl, label) => {
		rowEl.find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', label).click();
	};
	const openDrawer = (title) => menu(row(title), "Record signature manually");
	const sellerRow = (title) =>
		cy.get(`[data-testid="sellos-seller-row"][data-title="${title}"]`);
	const moveSeller = (title, stage) => {
		menu(sellerRow(title), "Move stage");
		cy.getByTestId("seller-move-to").select(stage);
		cy.getByTestId("seller-move").click();
	};
	const openMandates = () => {
		cy.intercept("POST", "**/sellos.inventory.mandates.mandate_overview*").as("overview");
		cy.visit("/sellos/crm/mandates");
		cy.wait("@overview");
	};

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads"));

	it("records a draft, refuses a bad signature, keeps the Dossier hidden, signs and logs each view", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_mandate_seller").then((made) => {
			const title = made.title;
			cy.signInFresh("agent");
			openMandates();

			// Record the mandate: a draft with its type, term and fee.
			cy.intercept("POST", "**/sellos.inventory.mandates.save_mandate*").as("save");
			cy.getByTestId("mandate-new").click();
			cy.getByTestId("mandate-lead").select(made.lead);
			cy.getByTestId("mandate-type").select("Open");
			cy.getByTestId("mandate-term").type("12");
			cy.getByTestId("mandate-fee").type("2");
			cy.getByTestId("mandate-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);
			row(title).should("have.attr", "data-status", "Draft");
			row(title)
				.find('[data-testid="sellos-mandate-terms"]')
				.should("contain", "Open")
				.and("contain", "12 months")
				.and("contain", "2%");
			// A draft that is not sent offers no signed copy, and no button sits in the row but the menu.
			row(title)
				.find("button:not([data-testid='sellos-row-menu-button'])")
				.should("not.exist");

			// The Dossier is hidden until it is signed: a note can be kept, but is not shown.
			openDrawer(title);
			drawer().find('[data-testid="sellos-mandate-dossier-locked"]').should("be.visible");
			drawer().find('[data-testid="sellos-mandate-dossier-open"]').should("not.exist");
			cy.intercept("POST", "**/sellos.inventory.mandates.add_dossier_note*").as("note");
			drawer().find('[data-testid="sellos-mandate-note-title"]').type("Reserve price");
			drawer()
				.find('textarea[data-testid="sellos-mandate-note-text"]')
				.type("Not below the reserve.");
			drawer().find('[data-testid="sellos-mandate-note-add"]').click();
			cy.wait("@note").its("response.statusCode").should("eq", 200);
			drawer().find('[data-testid="sellos-mandate-dossier-locked"]').should("be.visible");
			cy.contains("Not below the reserve.").should("not.exist");

			// A file that is not a PDF, PNG or JPG does not sign it.
			cy.intercept("POST", "**/sellos.inventory.mandates.sign_mandate*").as("sign");
			cy.expectApiStatus("sellos.inventory.mandates.sign_mandate", 417);
			drawer()
				.find('[data-testid="sellos-mandate-sign-file"]')
				.selectFile({
					contents: Cypress.Buffer.from("<html>not a pdf</html>"),
					fileName: "mandate.pdf",
					mimeType: "application/pdf",
				});
			cy.wait("@sign").its("response.statusCode").should("eq", 417);
			cy.getByTestId("mandate-error").should("contain", "PDF, PNG or JPG");
			row(title).should("have.attr", "data-status", "Draft");

			// The seller cannot be moved to Listed without a signed mandate.
			cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("sellers");
			cy.visit("/sellos/crm/sellers");
			cy.wait("@sellers");
			cy.intercept("POST", "**/sellos.crm.api.move_lead_stage*").as("move");
			cy.expectApiStatus("sellos.crm.api.move_lead_stage", 417);
			moveSeller(title, "Listed");
			cy.wait("@move").its("response.statusCode").should("eq", 417);
			cy.getByTestId("seller-error").should("contain", "signed mandate");
			sellerRow(title).should("have.attr", "data-stage", "New owner enquiry");

			// Signing needs the signed document. With it, the Dossier is released.
			openMandates();
			openDrawer(title);
			drawer()
				.find('[data-testid="sellos-mandate-sign-file"]')
				.selectFile({
					contents: Cypress.Buffer.from(made.pdf, "base64"),
					fileName: "signed-mandate.pdf",
					mimeType: "application/pdf",
				});
			cy.wait("@sign").its("response.statusCode").should("eq", 200);
			row(title).should("have.attr", "data-status", "Signed");
			drawer().find('[data-testid="sellos-mandate-signed"]').should("be.visible");
			drawer()
				.find('[data-testid="sellos-mandate-dossier-open"]')
				.should("contain", "(1)")
				.click();
			drawer()
				.find('[data-testid="sellos-mandate-dossier-item"]')
				.should("have.length", 1)
				.and("contain", "Reserve price")
				.and("contain", "Not below the reserve.");
			drawer().find('[data-testid="sellos-mandate-view"]').should("have.length", 1);

			// Each opening is logged.
			drawer().find('[data-testid="sellos-mandate-dossier-open"]').click();
			drawer().find('[data-testid="sellos-mandate-view"]').should("have.length", 2);

			// Now the seller reaches Listed.
			cy.visit("/sellos/crm/sellers");
			cy.wait("@sellers");
			moveSeller(title, "Listed");
			cy.wait("@move").its("response.statusCode").should("eq", 200);
			sellerRow(title).should("have.attr", "data-stage", "Listed");
		});
	});
});
