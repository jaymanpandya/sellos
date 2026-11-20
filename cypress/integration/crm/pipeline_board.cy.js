// SOS-P1-24: the pipeline board and the lead list filters, against the real server. The leads come from
// sellos.crm.api through seed_board_leads, so their stage, budget, consent status and last contact are the
// ones the production code computed.
context("SOS-P1-24: pipeline board and lead list filters", () => {
	let seed;

	// Each test makes its own leads, so none depends on another test having run (SOS-SETUP-24).
	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_board_leads").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	const column = (stage) => cy.get(`[data-testid="sellos-board-column"][data-stage="${stage}"]`);
	const card = (name) => cy.contains('[data-testid="sellos-board-card"]', name);

	const openBoard = (role, query = "?view=board") => {
		cy.signInFresh(role);
		cy.intercept("POST", "**/sellos.crm.api.get_board*").as("board");
		cy.visit(`/sellos/crm/leads${query}`);
		cy.wait("@board").its("response.statusCode").should("eq", 200);
	};

	const openList = (role, query = "") => {
		cy.signInFresh(role);
		cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("list");
		cy.visit(`/sellos/crm/leads${query}`);
		cy.wait("@list").its("response.statusCode").should("eq", 200);
		cy.getByTestId("lead-row").should("have.length.greaterThan", 0);
	};

	const rows = () => cy.getByTestId("lead-row");

	it("shows an agent only their own leads on the board, with the count and total budget per column", () => {
		openBoard("agent");
		cy.getByTestId("board").should("be.visible");
		cy.getByTestId("board-column").should("have.length", 11);
		column("Qualified").within(() => {
			cy.contains('[data-testid="sellos-board-card"]', seed.agent_a).should("be.visible");
			cy.contains('[data-testid="sellos-board-card"]', seed.agent_b).should("be.visible");
			cy.getByTestId("board-total")
				.invoke("attr", "data-rupees")
				.then((total) => {
					expect(Number(total)).to.be.at.least(seed.qualified_total);
				});
			cy.getByTestId("board-card").then(($cards) => {
				const sum = [...$cards].reduce((n, c) => n + Number(c.dataset.budget), 0);
				cy.getByTestId("board-total").should("have.attr", "data-rupees", String(sum));
				cy.getByTestId("board-count").should("have.text", String($cards.length));
			});
		});
		cy.contains('[data-testid="sellos-board-card"]', seed.admin).should("not.exist");
		cy.apiAs("sellos.crm.api.get_board").then((res) => {
			expect(JSON.stringify(res.body)).to.not.contain(seed.admin);
		});
	});

	it("drags a card to another stage whatever its consent status, with the warning, and logs the move", () => {
		openBoard("agent");
		card(seed.agent_b).should("have.attr", "data-stage", "Qualified");
		card(seed.agent_b)
			.find('[data-testid="sellos-board-card-consent"]')
			.should("have.attr", "data-status", "Opted out");
		cy.intercept("POST", "**/sellos.crm.api.move_lead_stage*").as("move");
		const transfer = new DataTransfer();
		card(seed.agent_b).trigger("dragstart", { dataTransfer: transfer });
		column("Contacted").trigger("dragover", { dataTransfer: transfer });
		column("Contacted").trigger("drop", { dataTransfer: transfer });
		cy.wait("@move").its("response.statusCode").should("eq", 200);
		cy.getByTestId("board-notice").should("contain", "Opted out");
		column("Contacted").contains('[data-testid="sellos-board-card"]', seed.agent_b);
		column("Qualified")
			.contains('[data-testid="sellos-board-card"]', seed.agent_b)
			.should("not.exist");
		cy.apiAs("sellos.crm.api.get_lead", { name: seed.leads.agent_b }).then((res) => {
			const log = res.body.message.pipeline.log;
			expect(log[0].from_stage).to.eq("Qualified");
			expect(log[0].to_stage).to.eq("Contacted");
			expect(log[0].warning).to.contain("Opted out");
		});
	});

	it("moves a card with the box on it, and asks for a lost reason before a Lost stage", () => {
		openBoard("agent");
		cy.intercept("POST", "**/sellos.crm.api.move_lead_stage*").as("move");
		card(seed.agent_a).find('[data-testid="sellos-board-card-move"]').select("Negotiation");
		cy.wait("@move").its("response.statusCode").should("eq", 200);
		column("Negotiation").contains('[data-testid="sellos-board-card"]', seed.agent_a);
		card(seed.agent_a).find('[data-testid="sellos-board-card-move"]').select("Closed lost");
		cy.getByTestId("board-lost-form").should("be.visible");
		cy.getByTestId("board-lost-reason").select("Other");
		cy.getByTestId("board-lost-save").click();
		cy.wait("@move").its("response.statusCode").should("eq", 200);
		column("Closed lost").contains('[data-testid="sellos-board-card"]', seed.agent_a);
	});

	it("marks an untouched lead on both views", () => {
		openBoard("agent");
		card(seed.old).find('[data-testid="sellos-untouched"]').should("contain", "7 days");
		card(seed.agent_a).find('[data-testid="sellos-untouched"]').should("not.exist");
		cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("list");
		cy.getByTestId("leads-view-list").click();
		cy.wait("@list");
		rows()
			.contains(seed.old)
			.closest('[data-testid="sellos-lead-row"]')
			.find('[data-testid="sellos-untouched"]')
			.should("be.visible");
		rows()
			.contains(seed.agent_a)
			.closest('[data-testid="sellos-lead-row"]')
			.find('[data-testid="sellos-untouched"]')
			.should("not.exist");
	});

	it("filters by stage, and keeps the filter in the address", () => {
		openList("agent");
		cy.getByTestId("leads-filter-stage").select("Qualified");
		cy.wait("@list");
		rows()
			.should("contain", seed.agent_a)
			.and("contain", seed.agent_b)
			.and("not.contain", seed.old);
		cy.location("search").should("contain", "stage=Qualified");
	});

	it("filters by agent and by source", () => {
		openList("company_admin");
		cy.getByTestId("leads-filter-agent").select(seed.agent_email);
		cy.wait("@list");
		rows().should("contain", seed.agent_a).and("not.contain", seed.admin);
		cy.getByTestId("leads-filter-source").select("Referral");
		cy.wait("@list");
		rows().should("contain", seed.agent_a).and("not.contain", seed.agent_b);
		cy.location("search").should("contain", "source=Referral");
	});

	it("filters by consent status", () => {
		openList("agent");
		cy.openMoreFilters();
		cy.getByTestId("leads-filter-consent").select("Opted out");
		cy.wait("@list");
		rows().should("have.length", 1).and("contain", seed.agent_b);
	});

	it("filters by last contacted and by untouched", () => {
		openList("agent");
		// Five days ago by the site's date and time zone, never the browser clock.
		cy.openMoreFilters();
		cy.bench("sellos.tests.ui_fixtures.site_date", { days: -5 }).then((r) =>
			cy.getByTestId("leads-filter-contacted-from").type(r.date)
		);
		cy.wait("@list");
		rows().should("have.length", 1).and("contain", seed.agent_a);
		cy.getByTestId("leads-filter-clear").click();
		cy.wait("@list");
		cy.getByTestId("leads-filter-untouched").check();
		cy.wait("@list");
		rows().should("have.length", 1).and("contain", seed.old);
	});

	it("filters by budget, and the filters combine", () => {
		openList("agent");
		cy.openMoreFilters();
		cy.getByTestId("leads-filter-budget-min").type("5000000");
		cy.getByTestId("leads-filter-apply").click();
		cy.wait("@list");
		rows().should("have.length", 1).and("contain", seed.agent_b);
		cy.getByTestId("leads-filter-source").select("Referral");
		cy.wait("@list");
		cy.getByTestId("lead-row").should("not.exist");
		cy.getByTestId("leads-empty").should("be.visible");
	});

	it("opens a bookmarked filtered view with the filters set, in the list and on the board", () => {
		openList("agent", "?stage=Qualified&consent_status=Opted%20out");
		rows().should("have.length", 1).and("contain", seed.agent_b);
		cy.getByTestId("leads-filter-stage").should("have.value", "Qualified");
		cy.getByTestId("leads-filter-consent").should("have.value", "Opted out");
		cy.intercept("POST", "**/sellos.crm.api.get_board*").as("board");
		cy.visit("/sellos/crm/leads?view=board&source=Referral");
		cy.wait("@board");
		cy.getByTestId("leads-filter-source").should("have.value", "Referral");
		card(seed.agent_a).should("be.visible");
		card(seed.agent_b).should("not.exist");
	});
});
