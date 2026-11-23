// SOS-P5-01: the report engine, against the real server. ui_fixtures.seed_report_engine makes four leads of
// the gate agent and returns what the Lead table itself holds by stage for the last 30 days (read with SQL
// that shares no code with the engine), for the company and for the agent. The spec checks every figure
// against that, every figure against the records it opens, and what each role may read.
context("SOS-P5-01: the report engine", () => {
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

	const open = (role, title) => {
		cy.signInFresh(role);
		cy.visit("/sellos/reports");
		cy.getByTestId("reports-report").should("be.visible").select(title);
		cy.getByTestId("reports-row").should("have.length.greaterThan", 0);
	};
	const rowCount = (group) =>
		cy.getByTestId("reports-row").filter(`[data-group="${group}"]`).find("[data-col=count]");
	const sum = (figures) => Object.values(figures).reduce((n, c) => n + c, 0);

	it("shows a Company Admin every lead by stage, as many as the Lead table holds", () => {
		open("company_admin", "Leads by stage");
		cy.getByTestId("reports-scope").should("contain", "All records");
		cy.getByTestId("reports-total").should("have.text", String(sum(seed.figures.all)));
		Object.entries(seed.figures.all).forEach(([stage, count]) => {
			rowCount(stage).should("have.text", String(count));
		});
		cy.getByTestId("reports-row").should("have.length", Object.keys(seed.figures.all).length);
	});

	it("opens the records behind every figure, with the same count", () => {
		open("company_admin", "Leads by stage");
		cy.getByTestId("reports-open-all").click();
		cy.getByTestId("reports-drill").should(
			"have.attr",
			"data-count",
			String(sum(seed.figures.all))
		);
		cy.getByTestId("reports-row").each(($row) => {
			const count = $row.find("[data-col=count]").text();
			cy.wrap($row).find("[data-testid=sellos-reports-open]").click();
			cy.getByTestId("reports-drill").should("have.attr", "data-count", count);
			cy.getByTestId("reports-record").should("have.length", Number(count));
		});
		cy.getByTestId("reports-record")
			.first()
			.find("a")
			.should("have.attr", "href")
			.and("contain", "/crm/leads/");
	});

	it("filters by date: a range with no lead shows nothing", () => {
		open("company_admin", "Leads by stage");
		cy.getByTestId("reports-from").clear().type("2020-01-01");
		cy.getByTestId("reports-to").clear().type("2020-01-02");
		cy.getByTestId("reports-from").closest("form").find("button[type=submit]").click();
		cy.getByTestId("reports-about").should("contain", "2020-01-02");
		cy.getByTestId("reports-total").should("have.text", "0");
		cy.getByTestId("reports-row").should("not.exist");
	});

	it("refreshes the summary table and the figures do not change", () => {
		open("company_admin", "Leads by source");
		cy.getByTestId("reports-total").should("have.text", String(sum(seed.figures.all)));
		cy.getByTestId("reports-refresh").click();
		cy.getByTestId("reports-refreshed").should("contain", "Summary table refreshed");
		cy.getByTestId("reports-total").should("have.text", String(sum(seed.figures.all)));
	});

	it("shows an Agent only their own leads and only the reports made visible to the role", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/reports");
		cy.optionTexts("reports-report").should("deep.eq", [
			"Calls by outcome",
			"Follow ups by status",
			"Leads by stage",
			"My pipeline by stage",
			"Site visits by status",
		]);
		cy.getByTestId("reports-report").select("Leads by stage");
		cy.getByTestId("reports-scope").should("contain", "Your own records");
		cy.getByTestId("reports-total").should("have.text", String(sum(seed.figures.agent)));
		Object.entries(seed.figures.agent).forEach(([stage, count]) => {
			rowCount(stage).should("have.text", String(count));
		});
		cy.getByTestId("reports-refresh").should("not.exist");
		cy.getByTestId("reports-open-all").click();
		cy.getByTestId("reports-drill").should(
			"have.attr",
			"data-count",
			String(sum(seed.figures.agent))
		);
	});

	it("keeps the reports from a channel partner", () => {
		cy.signInFresh("channel_partner");
		cy.visit("/sellos/reports");
		cy.getByTestId("no-access").should("be.visible");
		cy.getByTestId("reports-page").should("not.exist");
	});
});
