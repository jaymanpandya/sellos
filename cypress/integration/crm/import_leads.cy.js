// SOS-P1-12: the Company Admin imports a bought lead list in the web app. The file is built by
// seed_import_sample (its numbers are generated), and what the import made is read back from the server.
context("SOS-P1-12: import the bought lead lists", () => {
	let sample;

	// Each test makes its own data, so none depends on another test having run (SOS-SETUP-24).
	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		cy.bench("sellos.tests.ui_fixtures.seed_import_sample").then((made) => {
			sample = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	const chooseFile = () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.crm.api.preview_lead_import*").as("preview");
		cy.visit("/sellos/crm/import");
		cy.getByTestId("import-page").should("be.visible");
		cy.getByTestId("import-file").selectFile({
			contents: Cypress.Buffer.from(sample.csv),
			fileName: "gate-bought-list.csv",
			mimeType: "text/csv",
		});
		cy.wait("@preview");
	};

	it("previews the file, then imports it with the honest statuses and merged duplicates", () => {
		chooseFile();
		cy.getByTestId("import-map-name").should("have.value", "Name");
		cy.getByTestId("import-map-do_not_call").should("have.value", "DND Status");
		// Alpha twice and Beta are new, Known is merged into the client already there, one row has no name.
		cy.getByTestId("import-counts")
			.should("contain", "5 rows")
			.and("contain", "2 new leads")
			.and("contain", "1 merged with people already in SellOS")
			.and("contain", "1 merged within the file")
			.and("contain", "1 on the do not call list")
			.and("contain", "1 skipped");
		cy.getByTestId("import-skipped").should("contain", "Row 6: No name.");
		cy.getByTestId("import-sample").should(
			"not.contain",
			sample.csv.split("\n")[1].split(",")[1]
		);
		cy.intercept("POST", "**/sellos.crm.api.import_bought_list*").as("import");
		cy.getByTestId("import-run").click();
		cy.wait("@import").its("response.statusCode").should("eq", 200);
		cy.getByTestId("import-result")
			.should("contain", "2 leads imported")
			.and("contain", "1 merged into leads already there")
			.and("contain", "1 skipped")
			.and("contain", "1 are registered on the do not call list");
		cy.bench("sellos.tests.ui_fixtures.import_state", { names: sample.names }).then(
			(state) => {
				const alpha = state["Gate Import Alpha"];
				const beta = state["Gate Import Beta"];
				const known = state["Gate Import Known"];
				expect(alpha.clients).to.eq(1);
				expect(alpha.leads).to.deep.eq([
					{ source: "Bought list", consent_status: "Unknown", blocked: false },
				]);
				expect(beta.leads).to.deep.eq([
					{ source: "Bought list", consent_status: "Registered DND", blocked: false },
				]);
				// The known client keeps its one Website lead, and nothing marks it as not to be contacted.
				expect(known.clients).to.eq(1);
				expect(known.leads).to.have.length(1);
				expect(known.leads[0].source).to.eq("Website");
				expect(known.leads[0].blocked).to.eq(false);
			}
		);
	});

	it("shows the imported leads with their warning, and an agent has no import", () => {
		chooseFile();
		cy.getByTestId("import-run").click();
		cy.getByTestId("import-result").should("contain", "2 leads imported");
		cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("listLeads");
		cy.getByTestId("import-view-leads").click();
		cy.wait("@listLeads");
		cy.getByTestId("lead-row").contains("Gate Import Beta").click();
		cy.getByTestId("lead-consent-status").should("contain", "Registered DND");
		cy.getByTestId("lead-consent-warning")
			.should("have.attr", "data-level", "amber")
			.and("contain", "You can still call and message this lead");
		// The lead replaces the list (SOS-UI-2B), so go back to it.
		cy.getByTestId("lead-back").click();
		cy.getByTestId("lead-row")
			.contains("Gate Import Alpha")
			.closest("a")
			.invoke("attr", "href")
			.then((href) => cy.visit(href));
		cy.getByTestId("lead-consent-status").should("contain", "Unknown");
		cy.getByTestId("lead-consent-warning").should("have.attr", "data-level", "amber");
		cy.signInFresh("agent");
		cy.apiAs("sellos.crm.api.import_bought_list", { csv_text: sample.csv })
			.its("status")
			.should("eq", 403);
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("leads-page").should("be.visible");
		cy.getByTestId("nav-import").should("not.exist");
	});
});
