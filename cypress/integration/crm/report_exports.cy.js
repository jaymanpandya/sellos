// SOS-P5-04: saved views, export and scheduled email, against the real server. ui_fixtures.seed_report_engine
// makes four leads of the gate agent and returns what the Lead table holds by stage (read with SQL that shares
// no code with the report engine). The spec compares the files the Company Admin exports with that and with the
// rows on the screen, shares a view with the Agent, and schedules and runs an email.
context("SOS-P5-04: saved views, export and scheduling", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_report_engine").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.visit("/sellos");
		cy.bench("sellos.tests.ui_fixtures.remove_report_exports");
		cy.bench("sellos.tests.ui_fixtures.remove_report_engine");
	});

	const open = (role, title) => {
		cy.signInFresh(role);
		cy.visit("/sellos/reports");
		cy.getByTestId("reports-report").should("be.visible").select(title);
		cy.getByTestId("reports-row").should("have.length.greaterThan", 0);
	};
	const sum = (figures) => Object.values(figures).reduce((n, c) => n + c, 0);
	const csvRows = (result) =>
		atob(result.content)
			.trim()
			.split(/\r?\n/)
			.map((line) => line.split(","));

	it("exports a CSV with the same rows and total as the screen", () => {
		open("company_admin", "Leads by stage");
		cy.intercept("POST", "**/sellos.reports.exports.export_report*").as("export");
		cy.getByTestId("reports-export-csv").click();
		cy.wait("@export").then(({ response }) => {
			const made = response.body.message;
			expect(made.format).to.eq("CSV");
			const rows = csvRows(made);
			expect(rows[0]).to.deep.eq(["Stage", "Records"]);
			expect(rows.slice(-1)[0]).to.deep.eq(["Total", String(sum(seed.figures.all))]);
			Object.entries(seed.figures.all).forEach(([stage, count]) => {
				expect(rows.find((r) => r[0] === stage)).to.deep.eq([stage, String(count)]);
			});
			cy.getByTestId("reports-row").should("have.length", rows.length - 2);
			cy.getByTestId("reports-row").each(($row, at) => {
				expect($row.find("td").first().text().trim()).to.eq(rows[at + 1][0]);
				expect($row.find("[data-col=count]").text()).to.eq(rows[at + 1][1]);
			});
		});
		cy.getByTestId("reports-export-note").should("contain", "Exported");
	});

	it("exports a PDF", () => {
		open("company_admin", "Leads by stage");
		cy.intercept("POST", "**/sellos.reports.exports.export_report*").as("export");
		cy.getByTestId("reports-export-pdf").click();
		cy.wait("@export").then(({ response }) => {
			const made = response.body.message;
			expect(made.mime).to.eq("application/pdf");
			expect(atob(made.content).startsWith("%PDF")).to.eq(true);
			expect(made.totals.count).to.eq(sum(seed.figures.all));
		});
	});

	it("saves a shared view that an Agent opens with their own records", () => {
		open("company_admin", "Leads by stage");
		cy.getByTestId("reports-view-name").type("Gate P504 Shared view");
		cy.getByTestId("reports-view-shared").check();
		cy.getByTestId("reports-view-relative").check();
		cy.getByTestId("reports-view-save").click();
		cy.getByTestId("reports-view-note").should(
			"contain",
			"Saved the view Gate P504 Shared view"
		);
		cy.signOut();
		cy.signInFresh("agent");
		cy.intercept("POST", "**/sellos.reports.exports.list_report_views*").as("views");
		cy.visit("/sellos/reports");
		cy.wait("@views");
		cy.getByTestId("reports-export-csv").should("not.exist");
		cy.getByTestId("reports-schedule-save").should("not.exist");
		cy.optionTexts("reports-view").should("deep.eq", [
			"No saved view",
			"Gate P504 Shared view (Leads by stage, shared by Gate Company Admin)",
		]);
		cy.getByTestId("reports-view").select(
			"Gate P504 Shared view (Leads by stage, shared by Gate Company Admin)"
		);
		cy.getByTestId("reports-scope").should("contain", "Your own records");
		cy.getByTestId("reports-total").should("have.text", String(sum(seed.figures.agent)));
		cy.getByTestId("reports-view-delete").should("not.exist");
	});

	it("schedules a report for the Company Admin and runs it", () => {
		cy.roleUser("company_admin").then(({ full_name: name }) => {
			open("company_admin", "Leads by stage");
			cy.getByTestId("reports-schedule-title").type("Gate P504 Weekly leads");
			cy.contains("label", name).click();
			cy.getByTestId("reports-schedule-save").click();
			cy.getByTestId("reports-schedule-note").should(
				"contain",
				"Scheduled Gate P504 Weekly leads"
			);
			cy.getByTestId("reports-schedule")
				.should("have.length", 1)
				.and("contain", "Gate P504 Weekly leads");
			cy.getByTestId("reports-schedule-send").click();
			cy.getByTestId("reports-schedule-note").should("contain", "of 1 sent");
			cy.getByTestId("reports-schedule")
				.find("[data-col=result]")
				.should("contain", "of 1 sent");
			cy.getByTestId("reports-schedule-delete").click();
			cy.getByTestId("reports-schedule").should("not.exist");
		});
	});

	it("refuses a schedule that has nobody to send to", () => {
		cy.expectApiStatus("sellos.reports.exports.save_report_schedule", 417);
		cy.signInFresh("company_admin");
		cy.visit("/sellos/reports");
		cy.getByTestId("reports-report").should("be.visible").select("Call cost by agent");
		cy.getByTestId("reports-schedule-title").type("Gate P504 Cost");
		cy.getByTestId("reports-schedule-save").click();
		cy.getByTestId("reports-schedule-note").should("contain", "at least one person");
	});
});
