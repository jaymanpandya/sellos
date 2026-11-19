// SOS-P1-25: booking, confirming and finishing a site visit, against the real server. The leads come from
// sellos.crm.api through seed_board_leads: the test agent owns Gate Board Old (stage New) and Gate Board
// Agent A (stage Qualified), and the company admin owns Gate Board Admin. Every visit is made through the
// screen, and remove_seeded_leads removes the leads with their visits afterwards.
context("SOS-P1-25: site visits", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_board_leads").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	const pad = (n) => String(n).padStart(2, "0");
	// Tomorrow at ten, as the "datetime-local" box wants it.
	const tomorrowAt = () => {
		const day = new Date();
		day.setDate(day.getDate() + 1);
		return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}T10:00`;
	};

	// The row of tomorrow's list for one project, so other visits on the site do not matter.
	const rowFor = (project) =>
		cy
			.getByTestId("visits-tomorrow-item")
			.contains(project)
			.closest("[data-testid=sellos-visits-tomorrow-item]");

	const openLead = (role, key) => {
		cy.signInFresh(role);
		cy.visit(`/sellos/crm/leads/${seed.leads[key]}`);
		cy.getByTestId("lead-visit-form").should("be.visible");
	};

	const book = (project) => {
		cy.intercept("POST", "**/api/method/sellos.crm.api.save_site_visit*").as("book");
		cy.getByTestId("lead-visit-project").type(project);
		cy.getByTestId("lead-visit-when").type(tomorrowAt());
		cy.getByTestId("lead-visit-save").click();
		cy.wait("@book").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-timeline-item").contains(project).should("be.visible");
	};

	it("books a visit from the lead, moves the lead to Site visit booked and names the agent", () => {
		openLead("agent", "old");
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", "New");
		book("Gate Tower");
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", "Site visit booked");
		cy.getByTestId("lead-visit-confirmation")
			.should("contain", "Not confirmed")
			.and("contain", "sos_test_agent");
	});

	it("leaves a lead that is further on where it is", () => {
		openLead("agent", "agent_a");
		cy.getByTestId("lead-stage-select").select("Negotiation");
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", "Negotiation");
		book("Gate Heights");
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", "Negotiation");
	});

	it("lists tomorrow's visits, and the agent confirms one and reschedules another", () => {
		openLead("agent", "old");
		book("Gate Tower");
		cy.visit("/sellos/crm/visits");
		rowFor("Gate Tower").as("row");
		cy.get("@row")
			.find("[data-testid=sellos-visits-tomorrow-status]")
			.should("have.text", "Not confirmed");
		cy.intercept("POST", "**/api/method/sellos.crm.api.confirm_site_visit*").as("confirm");
		cy.get("@row").find("[data-testid=sellos-visit-confirm-status]").select("Confirmed");
		cy.wait("@confirm").its("response.statusCode").should("eq", 200);
		rowFor("Gate Tower")
			.find("[data-testid=sellos-visits-tomorrow-status]")
			.should("have.text", "Confirmed");
		// Rescheduled asks for the new time first.
		rowFor("Gate Tower")
			.find("[data-testid=sellos-visit-confirm-status]")
			.select("Rescheduled");
		cy.getByTestId("visit-reschedule-form").should("be.visible");
		cy.getByTestId("visit-reschedule-when").type("2030-06-14T15:00");
		cy.getByTestId("visit-reschedule-save").click();
		cy.wait("@confirm").its("response.statusCode").should("eq", 200);
		// It moved to another day, so it is no longer on tomorrow's list.
		cy.getByTestId("visits-tomorrow").should("not.contain", "Gate Tower");
	});

	it("shows a cancelled visit on tomorrow's list as Cancelled", () => {
		openLead("agent", "old");
		book("Gate Tower");
		cy.visit("/sellos/crm/visits");
		cy.intercept("POST", "**/api/method/sellos.crm.api.confirm_site_visit*").as("confirm");
		rowFor("Gate Tower").find("[data-testid=sellos-visit-confirm-status]").select("Cancelled");
		cy.wait("@confirm").its("response.statusCode").should("eq", 200);
		rowFor("Gate Tower")
			.find("[data-testid=sellos-visits-tomorrow-status]")
			.should("have.text", "Cancelled");
	});

	it("shows the agent's visit on the calendar by day and by week", () => {
		openLead("agent", "old");
		book("Gate Tower");
		cy.visit("/sellos/crm/visits");
		cy.getByTestId("visits-view-day").click();
		cy.getByTestId("visits-day").should("have.length", 1);
		cy.getByTestId("visits-next").click();
		cy.getByTestId("visits-item").should("contain", "Gate Tower");
		cy.getByTestId("visits-view-week").click();
		cy.getByTestId("visits-day").should("have.length", 7);
		cy.getByTestId("visits-today").click();
		cy.getByTestId("visits-range").should("not.be.empty");
	});

	it("shows the company admin every agent's visits and the agent only their own", () => {
		openLead("agent", "old");
		book("Gate Tower");
		cy.signInFresh("company_admin");
		cy.visit(`/sellos/crm/leads/${seed.leads.admin}`);
		cy.getByTestId("lead-visit-form").should("be.visible");
		book("Gate Admin Park");
		cy.visit("/sellos/crm/visits");
		cy.getByTestId("visits-tomorrow")
			.should("contain", "Gate Tower")
			.and("contain", "Gate Admin Park");
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/visits");
		cy.getByTestId("visits-tomorrow").should("contain", "Gate Tower");
		cy.getByTestId("visits-tomorrow").should("not.contain", "Gate Admin Park");
	});

	it("asks for the outcome when a visit is marked done, and offers the next stage", () => {
		openLead("agent", "old");
		book("Gate Tower");
		cy.getByTestId("lead-visit-done").click();
		cy.getByTestId("lead-visit-done-form").should("be.visible");
		// With no outcome it stays open and says what is needed.
		cy.getByTestId("lead-visit-done-save").click();
		cy.getByTestId("lead-visit-error").should("contain", "Choose the outcome of the visit.");
		cy.intercept("POST", "**/api/method/sellos.crm.api.complete_site_visit*").as("done");
		cy.getByTestId("lead-visit-outcome").select("Liked it");
		cy.getByTestId("lead-visit-outcome-notes").type("Wants the corner unit");
		cy.getByTestId("lead-visit-done-save").click();
		cy.wait("@done").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-visit-confirmation").should("contain", "outcome: Liked it");
		// The stage is offered and not applied until the agent accepts it.
		cy.getByTestId("lead-visit-offer").should("contain", "Negotiation");
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", "Site visit booked");
		cy.getByTestId("lead-visit-offer-use").click();
		cy.getByTestId("lead-stage").should("have.attr", "data-stage", "Negotiation");
	});
});
