// SOS-P1-16: the duplicate warning when a lead is entered, adding the enquiry to the existing client,
// and the merge a Company Admin does. It goes through the real screens and the real server.
// seed_duplicate_clients commits its clients, so remove_seeded_leads clears them after the spec.
context("SOS-P1-16: duplicates", () => {
	let seeded;

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_duplicate_clients").then((made) => {
			seeded = made;
		});
	});

	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	it("warns an agent, hides what they cannot see, and adds the enquiry to the existing client", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/leads");
		cy.fillNewLead({ name: "Someone New", email: seeded.own_email.toUpperCase() });
		cy.getByTestId("lead-form-save").click();

		cy.getByTestId("duplicate-warning").should("be.visible");
		cy.getByTestId("duplicate-match")
			.should("have.length", 1)
			.and("have.attr", "data-visible", "yes");
		cy.getByTestId("duplicate-name").should("contain", seeded.own_name);
		cy.getByTestId("duplicate-lead").should("have.length", 1);
		cy.getByTestId("duplicate-phone").should("contain", seeded.own_masked);
		seeded.own_phone_forms.forEach((form) => {
			cy.getByTestId("duplicate-warning").should("not.contain", form);
		});

		cy.getByTestId("duplicate-add").click();
		cy.getByTestId("lead-name").should("contain", seeded.own_name);
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("lead-row")
			.filter(`:contains("${seeded.own_name}")`)
			.should("have.length", 2);
	});

	it("tells an agent a client exists without showing it when another agent owns it", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/leads");
		cy.fillNewLead({ name: "Someone Else", email: seeded.hidden_email });
		cy.getByTestId("lead-form-save").click();

		cy.getByTestId("duplicate-match").should("have.attr", "data-visible", "no");
		cy.getByTestId("duplicate-name").should("not.contain", seeded.hidden_name);
		cy.getByTestId("duplicate-warning")
			.should("not.contain", seeded.hidden_name)
			.and("not.contain", seeded.hidden_email);
		cy.getByTestId("duplicate-add").should("not.exist");
		seeded.hidden_phone_forms.forEach((form) => {
			cy.getByTestId("duplicate-warning").should("not.contain", form);
		});
		cy.getByTestId("duplicate-new").should("be.visible");
	});

	it("saves with no warning when nothing matches", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/leads");
		cy.fillNewLead({ name: "Gate Own Nobody", email: `nobody${Date.now()}@example.com` });
		cy.getByTestId("lead-form-save").click();
		cy.getByTestId("duplicate-warning").should("not.exist");
		cy.getByTestId("lead-page").should("be.visible");
	});

	it("lets a Company Admin merge two clients and gives an agent no merge", () => {
		cy.signInFresh("company_admin");
		cy.intercept("**/api/method/sellos.crm.api.merge_clients*").as("merge");
		cy.intercept("**/api/method/sellos.crm.api.list_clients*").as("clients");
		cy.visit(`/sellos/crm/leads/${seeded.twin_a_lead}`);
		cy.getByTestId("merge").should("be.visible");
		cy.getByTestId("merge-select").select(seeded.twin_b_client);
		cy.getByTestId("merge-save").click();
		cy.wait("@merge").its("response.statusCode").should("eq", 200);
		cy.getByTestId("merge-done").should("contain", "1 lead");
		// The screen asks for the client list when it opens and again after a merge; let both finish.
		cy.wait("@clients");
		cy.wait("@clients");
		cy.optionTexts("merge-select").then((texts) => {
			expect(texts.join("|")).not.to.contain(seeded.twin_b_name);
		});
		cy.visit(`/sellos/crm/leads/${seeded.twin_b_lead}`);
		cy.getByTestId("lead-name").should("contain", seeded.twin_a_name);

		cy.signInFresh("agent");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("lead-row").first().click();
		cy.getByTestId("lead-page").should("be.visible");
		cy.getByTestId("merge").should("not.exist");
	});
});
