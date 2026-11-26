// SOS-LOOP: the Company Profile (colours checked for contrast), the DocuSeal settings (the key is never shown back),
// the signing panel of a mandate ("Connect DocuSeal" when it is not set up), and the Dossier PDF (make, download,
// regenerate). The real DocuSeal is not reached here: sending and the webhook are tested on the server against a fake
// DocuSeal. The sellers the spec makes are named "Gate Seller Mandate " and are removed afterwards.
context("SOS-LOOP: company profile, DocuSeal settings, signing panel and Dossier PDF", () => {
	const reset = () => cy.bench("sellos.tests.ui_fixtures.reset_company_profile_and_docuseal");
	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		reset();
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		reset();
	});

	it("checks the colours for contrast and saves a readable profile", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.inventory.branding.get_company_profile*").as("load");
		cy.intercept("POST", "**/sellos.inventory.branding.save_company_profile*").as("save");
		cy.visit("/sellos/company/profile");
		cy.wait("@load");

		cy.getByTestId("profile-name").clear().type("Gate Profile Realty");
		cy.getByTestId("profile-primary").clear().type("#9EC9B0");
		cy.getByTestId("colour-contrast").first().should("contain", "Too pale");
		cy.expectApiStatus("sellos.inventory.branding.save_company_profile", 417);
		cy.getByTestId("profile-save").click();
		cy.wait("@save").its("response.statusCode").should("eq", 417);
		cy.getByTestId("profile-error").should("contain", "contrast");

		cy.getByTestId("profile-primary").clear().type("#0B5D3B");
		cy.getByTestId("colour-contrast").first().should("contain", "Readable");
		cy.getByTestId("profile-accent").clear().type("#B45309");
		cy.getByTestId("profile-footer").clear().type("Gate Profile Realty, confidential");
		cy.getByTestId("profile-save").click();
		cy.wait("@save").its("response.statusCode").should("eq", 200);
		cy.getByTestId("profile-notice").should("contain", "saved");

		cy.reload();
		cy.wait("@load");
		cy.getByTestId("profile-primary").should("have.value", "#0B5D3B");
		cy.getByTestId("profile-footer").should("have.value", "Gate Profile Realty, confidential");
	});

	it("saves the DocuSeal settings and never shows the key back", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.inventory.docuseal.get_docuseal_settings*").as("load");
		cy.intercept("POST", "**/sellos.inventory.docuseal.save_docuseal_settings*").as("save");
		cy.visit("/sellos/company/settings");
		cy.wait("@load");
		cy.getByTestId("docuseal-state").should("contain", "Not connected");
		cy.getByTestId("docuseal-url").type("https://sign.gate-example.com");
		cy.getByTestId("docuseal-key").type("gate-fake-key-only");
		cy.getByTestId("docuseal-secret").type("gate-fake-secret-only");
		cy.getByTestId("docuseal-signer-name").type("Gate Signer");
		cy.getByTestId("docuseal-signer-email").type("gate.signer@example.com");
		cy.getByTestId("docuseal-save").click();
		cy.wait("@save").its("response.statusCode").should("eq", 200);
		cy.getByTestId("docuseal-notice").should("contain", "saved");
		cy.getByTestId("docuseal-state").should("contain", "Connected");
		cy.getByTestId("docuseal-key").should("have.value", "");
		cy.getByTestId("docuseal-settings")
			.should("not.contain", "gate-fake-key-only")
			.and("contain", "saved, leave empty to keep it");
		cy.get("@save")
			.its("response.body")
			.then((body) => expect(JSON.stringify(body)).to.not.contain("gate-fake-key-only"));
	});

	it("asks to connect DocuSeal, and makes the Dossier PDF of a signed mandate in versions", () => {
		reset();
		cy.bench("sellos.tests.ui_fixtures.make_gate_mandates").then((made) => {
			cy.signInFresh("company_admin");
			cy.intercept("POST", "**/sellos.inventory.mandates.mandate_overview*").as("overview");
			cy.intercept("POST", "**/sellos.inventory.docuseal.docuseal_status*").as("status");
			cy.visit(`/sellos/crm/mandates/${made.draft}`);
			cy.wait("@overview");
			cy.wait("@status");
			cy.getByTestId("signing-status").should("have.attr", "data-status", "Not sent");
			cy.getByTestId("signing-connect")
				.should("contain", "Connect DocuSeal")
				.find("a")
				.should("have.attr", "href", "/sellos/company/settings");
			cy.getByTestId("signing-send").should("not.exist");

			// An agent is told to ask a Company Admin.
			cy.signInFresh("agent");
			cy.visit(`/sellos/crm/mandates/${made.draft}`);
			cy.getByTestId("signing-connect").should("contain", "Ask a Company Admin");

			// The Dossier PDF of a signed mandate: make it, download it, regenerate it.
			cy.intercept("POST", "**/sellos.inventory.mandates.generate_dossier_pdf*").as("pdf");
			cy.visit(`/sellos/crm/mandates/${made.signed}?tab=dossier`);
			cy.getByTestId("tab-dossier").click();
			cy.getByTestId("dossier-pdf-none").should("be.visible");
			cy.getByTestId("dossier-pdf-generate").click();
			cy.wait("@pdf").its("response.statusCode").should("eq", 200);
			cy.getByTestId("dossier-pdf-version").should("contain", "Version 1");
			cy.getByTestId("dossier-pdf-download").should("be.visible");
			cy.getByTestId("dossier-pdf-generate").should("contain", "Regenerate").click();
			cy.wait("@pdf").its("response.statusCode").should("eq", 200);
			cy.getByTestId("dossier-pdf-version").should("contain", "Version 2");

			// The draft has no Dossier PDF to make.
			cy.visit(`/sellos/crm/mandates/${made.draft}`);
			cy.getByTestId("tab-dossier").click();
			cy.getByTestId("dossier-pdf").should("not.exist");
		});
	});
});
