// SOS-P5-02: the Company Admin's business reports and the agent reports, against the real server.
// ui_fixtures.seed_report_engine makes four leads of the gate agent and returns what the Lead table itself
// holds (read with SQL that shares no code with the reports): buyer leads by source, and the agent's count.
context("SOS-P5-02: the agent and Company Admin reports", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_report_engine").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.visit("/sellos");
		cy.bench("sellos.tests.ui_fixtures.remove_report_engine");
	});

	const total = (figures) => Object.values(figures).reduce((n, c) => n + c, 0);
	const openBusiness = () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/reports/business");
		cy.getByTestId("business-leads").should("be.visible");
	};

	it("shows the funnel and the source performance that the Lead table holds", () => {
		openBusiness();
		cy.getByTestId("business-leads").should(
			"have.text",
			String(total(seed.figures.buyer_sources))
		);
		cy.getByTestId("business-conversion").should("be.visible");
		cy.getByTestId("business-stage")
			.filter('[data-stage="New"]')
			.find("[data-col=reached]")
			.should("have.text", String(total(seed.figures.buyer_sources)));
		Object.entries(seed.figures.buyer_sources).forEach(([source, count]) => {
			cy.getByTestId("business-source")
				.filter(`[data-source="${source}"]`)
				.find("[data-col=leads]")
				.should("have.text", String(count));
		});
	});

	it("shows agent productivity with the gate agent's leads", () => {
		openBusiness();
		cy.getByTestId("business-agents").should("be.visible");
		cy.getByTestId("business-agent").then(($rows) => {
			const leads = [...$rows].reduce(
				(n, row) => n + Number(row.querySelector("[data-col=leads]").textContent),
				0
			);
			expect(leads).to.eq(total(seed.figures.buyer_sources));
		});
	});

	it("filters by date: a range with no lead shows nothing", () => {
		openBusiness();
		cy.getByTestId("business-from").clear().type("2020-01-01");
		cy.getByTestId("business-to").clear().type("2020-01-02");
		cy.getByTestId("business-from").closest("form").find("button[type=submit]").click();
		cy.getByTestId("business-range").should("contain", "2020-01-02");
		cy.getByTestId("business-leads").should("have.text", "0");
		cy.getByTestId("business-source").should("not.exist");
	});

	it("shows the listing and mandate ageing bands", () => {
		openBusiness();
		cy.getByTestId("business-listing-band").should("have.length", 4);
		cy.getByTestId("business-mandate-band").should("have.length", 4);
	});

	it("gives an Agent the pipeline and calls reports and keeps the business reports from them", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/reports");
		cy.getByTestId("reports-report").should("be.visible").select("My pipeline by stage");
		cy.getByTestId("reports-total").should("be.visible");
		cy.getByTestId("reports-row").should("have.length.greaterThan", 0);
		cy.getByTestId("reports-report").select("Calls by outcome");
		cy.getByTestId("reports-scope").should("contain", "Your own records");
		cy.visit("/sellos/reports/business");
		cy.getByTestId("no-access").should("be.visible");
		cy.getByTestId("business-page").should("not.exist");
	});
});
