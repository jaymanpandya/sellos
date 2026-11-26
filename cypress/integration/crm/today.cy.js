// SOS-P1-26: the Today screen, against the real server. The data comes from ui_fixtures.seed_today through
// the lead, task and site visit APIs: the test agent owns Gate Today Mine New (stage New), Gate Today Mine
// Busy (two follow ups due today and overdue, a visit today and one tomorrow) and Gate Today Mine Later
// (a follow up next week). Gate Today Agent is in the same team as the Sales Manager and owns Gate Today
// Theirs. remove_today removes it all afterwards.
context("SOS-P1-26: the Today screen", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_today").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_today");
	});

	const rowFor = (section, name) =>
		cy
			.get(`[data-testid="sellos-today-section-${section}"]`)
			.contains("[data-testid=sellos-today-row]", name);

	// Every row action is in the row menu (kebab) of the row.
	const menu = (rowEl, label) => {
		rowEl.find("[data-testid=sellos-row-menu-button]").click();
		cy.contains("[role=menuitem]", label).click();
	};

	it("lands an agent on Today with their own lists, and counts that match", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("today").should("be.visible");
		cy.getByTestId("today-count-follow_ups").should("have.text", "2");
		cy.getByTestId("today-count-new_leads").should("have.text", "1");
		cy.getByTestId("today-count-visits_today").should("have.text", "1");
		cy.getByTestId("today-count-visits_tomorrow").should("have.text", "1");
		cy.getByTestId("today-section-follow_ups")
			.find("[data-testid=sellos-today-row]")
			.should("have.length", 2);
		// The one two hours ago is overdue. The one with only a day is due today, so it is not.
		rowFor("follow_ups", "Gate Today overdue ring").should("contain", "Overdue");
		rowFor("follow_ups", "Gate Today day only").should("not.contain", "Overdue");
		cy.getByTestId("today-section-new_leads").should("contain", seed.mine_new);
		cy.getByTestId("today-section-visits_today").should("contain", "Gate Today Noon Tower");
		cy.getByTestId("today-section-visits_tomorrow").should(
			"contain",
			"Gate Today Tomorrow Tower"
		);
		// Nothing of the next week, the team mate or the Company Admin.
		cy.getByTestId("today").should("not.contain", "Gate Today next week");
		cy.getByTestId("today").should("not.contain", seed.theirs);
		cy.getByTestId("today").should("not.contain", seed.theirs_new);
		cy.getByTestId("today").should("not.contain", seed.admin);
		cy.getByTestId("today-agent").should("not.exist");
	});

	it("shows an agent the masked number and never the full one", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		menu(rowFor("new_leads", seed.mine_new), "Call");
		cy.get("[data-testid=sellos-today-number]")
			.should("be.visible")
			.invoke("text")
			.then((text) => {
				seed.phone_forms.forEach((form) => expect(text).not.to.contain(form));
			});
	});

	it("logs a call in place on a lead, and marks a follow up done from its row", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.intercept("POST", "**/api/method/sellos.crm.api.log_call*").as("logCall");
		menu(rowFor("new_leads", seed.mine_new), "Log a call");
		cy.getByTestId("today-log-outcome").select("Wrong number");
		cy.getByTestId("today-log-notes").type("Gate Today call");
		cy.getByTestId("today-log-save").click();
		cy.wait("@logCall").its("response.statusCode").should("eq", 200);
		cy.getByTestId("today-log-form").should("not.exist");

		cy.intercept("POST", "**/api/method/sellos.crm.api.complete_follow_up*").as("done");
		menu(rowFor("follow_ups", "Gate Today day only"), "Log a call");
		cy.getByTestId("today-log-notes").type("Gate Today done in place");
		cy.getByTestId("today-log-outcome").select("Wrong number");
		cy.getByTestId("today-log-save").click();
		cy.wait("@done").its("response.statusCode").should("eq", 200);
		cy.getByTestId("today-count-follow_ups").should("have.text", "1");
		cy.getByTestId("today-section-follow_ups")
			.find("[data-testid=sellos-today-row]")
			.should("have.length", 1);
	});

	it("shows a Sales Manager the team by agent, with counts that match", () => {
		cy.signInFresh("sales_manager");
		cy.visit("/sellos");
		cy.getByTestId("today-scope").should("contain", "team");
		cy.getByTestId("today-count-follow_ups").should("have.text", "3");
		cy.getByTestId("today-count-new_leads").should("have.text", "2");
		cy.getByTestId("today-count-visits_tomorrow").should("have.text", "2");
		cy.getByTestId("today-section-new_leads")
			.find("[data-testid=sellos-today-agent]")
			.should("have.length", 2);
		cy.getByTestId("today-section-new_leads")
			.find(`[data-testid=sellos-today-agent][data-agent="gate_today_agent@example.com"]`)
			.should("contain", seed.other_agent_name)
			.and("contain", seed.theirs_new);
		cy.getByTestId("today").should("not.contain", seed.admin);
	});
});
