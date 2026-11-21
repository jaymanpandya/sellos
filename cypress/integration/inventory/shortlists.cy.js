// SOS-P7-09: an Agent builds a shortlist for a buyer from the matching homes, orders it, adds a note and shares it;
// the client signs in, reads only their own shortlist and opens a home; the agent sees which home was opened and
// when; a home that is no longer available is marked. The project, listing and buyers (names start with
// "Gate Inventory " and "Gate Match ") are removed afterwards.
context("SOS-P7-09: shortlists and sharing with buyers", () => {
	let made;
	const item = (title) =>
		cy.get(`[data-testid="sellos-shortlist-item"][data-title$="${title}"]`);

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_shortlists");
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.make_gate_shortlists").then((data) => {
			made = data;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_shortlists");
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	it("lets an agent add matches to a shortlist, order it, note it and share it, then the client reads it and the agent sees what was opened", () => {
		cy.signInFresh("agent");
		cy.intercept("POST", "**/sellos.inventory.matching.matches_for_lead*").as("matches");
		cy.intercept("POST", "**/sellos.inventory.shortlists.add_to_shortlist*").as("add");
		cy.intercept("POST", "**/sellos.inventory.shortlists.share_shortlist*").as("share");
		cy.intercept("POST", "**/sellos.inventory.shortlists.reorder_shortlist*").as("reorder");
		cy.intercept("POST", "**/sellos.inventory.shortlists.save_item_note*").as("note");
		cy.visit(`/sellos/crm/leads/${encodeURIComponent(made.agent_lead)}`);
		cy.getByTestId("lead-matches-load").click();
		cy.wait("@matches").its("response.statusCode").should("eq", 200);
		cy.get('[data-testid="sellos-lead-match"][data-title$="unit M101"]')
			.find('[data-testid="sellos-lead-match-add"]')
			.click();
		cy.wait("@add").its("response.statusCode").should("eq", 200);
		cy.get('[data-testid="sellos-lead-match"][data-kind="Listing"]')
			.find('[data-testid="sellos-lead-match-add"]')
			.click();
		cy.wait("@add");
		cy.get('[data-testid="sellos-lead-match"][data-title$="unit M101"]')
			.find('[data-testid="sellos-lead-match-add"]')
			.click();
		cy.wait("@add");
		cy.get('[data-testid="sellos-lead-match"][data-title$="unit M101"]')
			.find('[data-testid="sellos-lead-match-added"]')
			.should("contain", "Already on the shortlist");

		cy.getByTestId("shortlist-row")
			.should("have.length", 1)
			.find('[data-testid="sellos-shortlist-open"]')
			.click();
		cy.getByTestId("shortlist-item").should("have.length", 2);
		cy.getByTestId("shortlist-item")
			.first()
			.should("have.attr", "data-title")
			.and("contain", "unit M101");
		cy.getByTestId("shortlist-item")
			.first()
			.find('[data-testid="sellos-shortlist-down"]')
			.click();
		cy.wait("@reorder").its("response.statusCode").should("eq", 200);
		cy.getByTestId("shortlist-item")
			.last()
			.should("have.attr", "data-title")
			.and("contain", "unit M101");
		cy.getByTestId("shortlist-item")
			.last()
			.find('[data-testid="sellos-shortlist-item-note"]')
			.type("Corner flat, park facing");
		cy.getByTestId("shortlist-item")
			.last()
			.find('[data-testid="sellos-shortlist-item-save"]')
			.click();
		cy.wait("@note").its("response.statusCode").should("eq", 200);
		cy.getByTestId("shortlist-notice").should("contain", "The note is saved.");
		cy.getByTestId("shortlist-opened").each(($el) => {
			expect($el.text()).to.contain("Not opened yet");
		});
		cy.getByTestId("shortlist-share-link").click();
		cy.wait("@share").its("response.statusCode").should("eq", 200);
		cy.getByTestId("shortlist-notice").should("contain", "Shared as a link");
		cy.getByTestId("shortlist-link").should("contain", "/sellos/client/shortlists/SL-");

		cy.signInFresh("client");
		cy.intercept("POST", "**/sellos.inventory.shortlists.open_shortlist_item*").as("open");
		cy.visit("/sellos/client/shortlists");
		cy.getByTestId("client-shortlist-row").should("have.length", 1);
		cy.getByTestId("client-shortlist-link").click();
		cy.getByTestId("client-shortlist-agent").should("contain", made.agent_phone);
		cy.getByTestId("client-shortlist-item").should("have.length", 2);
		cy.getByTestId("client-shortlist-page").should("contain", "Corner flat, park facing");
		cy.getByTestId("client-shortlist-page").should("not.contain", made.admin_buyer);
		made.phone_forms.forEach((form) => {
			cy.getByTestId("client-shortlist-page").should("not.contain", form);
		});
		cy.get('[data-testid="sellos-client-shortlist-item"][data-title$="unit M101"]')
			.find('[data-testid="sellos-client-shortlist-open"]')
			.click();
		cy.wait("@open").its("response.statusCode").should("eq", 200);
		cy.getByTestId("client-shortlist-detail").should("be.visible");

		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${encodeURIComponent(made.agent_lead)}`);
		cy.getByTestId("shortlist-open").click();
		item("unit M101")
			.find('[data-testid="sellos-shortlist-opened"]')
			.should("have.attr", "data-count", "1")
			.and("contain", "Opened 1 time(s)");
		cy.get('[data-testid="sellos-shortlist-item"][data-title*="Powai Flat Listing"]')
			.find('[data-testid="sellos-shortlist-opened"]')
			.should("contain", "Not opened yet");
	});

	it("marks a home that is no longer available for the agent and the client, and shows a client nothing of another buyer", () => {
		cy.bench("sellos.tests.ui_fixtures.set_gate_unit_status", {
			unit: made.units.M101,
			status: "Held",
		});
		cy.bench("sellos.tests.ui_fixtures.set_gate_listing_published", {
			listing: made.listing,
			published: 0,
		});
		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${encodeURIComponent(made.agent_lead)}`);
		cy.getByTestId("shortlist-open").click();
		item("unit M101").should("have.attr", "data-unavailable", "true");
		item("unit M101")
			.find('[data-testid="sellos-shortlist-unavailable"]')
			.should("contain", "No longer available (Held)");
		cy.getByTestId("shortlist-item").should("have.length", 2);
		cy.getByTestId("shortlist-unavailable").should("have.length", 2);

		cy.signInFresh("client");
		cy.visit("/sellos/client/shortlists");
		cy.getByTestId("client-shortlist-link").click();
		cy.getByTestId("client-shortlist-unavailable").should("have.length", 2);
		cy.getByTestId("client-shortlist-item").should("have.length", 2);
	});

	it("keeps a client out of the agent's screens", () => {
		cy.signInFresh("client");
		cy.visit(`/sellos/crm/leads/${encodeURIComponent(made.agent_lead)}`);
		cy.getByTestId("no-access").should("exist");
	});
});
