// SOS-P5-03: the Channel Partner's own report and the Platform Admin's reports, against the real server.
// ui_fixtures.seed_portal_reports makes four leads (three of the gate partner and one of the gate agent) and
// three tenants with a month of usage each, and returns what the tables hold for them (read with SQL that
// shares no code with the reports). The spec checks every figure against that and what each role may open.
context("SOS-P5-03: the Channel Partner and Platform reports", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_portal_reports").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.visit("/sellos");
		cy.bench("sellos.tests.ui_fixtures.remove_portal_reports");
	});

	// The one money format (frontend/src/format.js): "Rs 1.2 lakh", and the full amount below a lakh, no paise.
	const rupees = (value) => {
		const n = Number(value);
		const trim = (x) => String(Math.round(x * 100) / 100);
		if (n >= 1e7) return `Rs ${trim(n / 1e7)} crore`;
		if (n >= 1e5) return `Rs ${trim(n / 1e5)} lakh`;
		return `Rs ${Math.round(n).toLocaleString("en-IN")}`;
	};
	const sum = (figures) => Object.values(figures).reduce((n, c) => n + c, 0);

	context("a channel partner", () => {
		const open = () => {
			cy.signInFresh("channel_partner");
			cy.visit("/sellos/partner/reports");
			cy.getByTestId("partner-reports-total").should("be.visible");
		};

		it("sees their own leads by stage, as many as the Lead table holds for them", () => {
			open();
			cy.getByTestId("partner-reports-total").should("have.text", String(sum(seed.partner)));
			Object.entries(seed.partner).forEach(([stage, count]) => {
				cy.getByTestId("partner-reports-stage")
					.filter(`[data-stage="${stage}"]`)
					.find("[data-col=count]")
					.should("have.text", String(count));
			});
			cy.getByTestId("partner-reports-stage").should(
				"have.length",
				Object.keys(seed.partner).length
			);
			cy.getByTestId("partner-reports-lead").should("have.length", sum(seed.partner));
			cy.getByTestId("partner-reports-about").should("contain", "Your own records only");
		});

		it("shows no phone number and no one else's lead", () => {
			open();
			cy.getByTestId("partner-reports-page")
				.invoke("text")
				.should("not.match", /\+91|\d{10}/);
			cy.getByTestId("partner-reports-lead").each(($lead) => {
				expect($lead.text()).to.contain("Gate Portal Report");
			});
		});

		it("filters by date: a range with no lead shows nothing", () => {
			open();
			cy.getByTestId("partner-reports-from").clear().type("2020-01-01");
			cy.getByTestId("partner-reports-to").clear().type("2020-01-02");
			cy.getByTestId("partner-reports-from")
				.closest("form")
				.find("button[type=submit]")
				.click();
			cy.getByTestId("partner-reports-about").should("contain", "2020-01-02");
			cy.getByTestId("partner-reports-total").should("have.text", "0");
			cy.getByTestId("partner-reports-stage").should("not.exist");
		});

		it("shows deals as waiting until their records exist, and the commission statement live (SOS-P7-04)", () => {
			open();
			cy.getByTestId("report-panel").should("have.length", 2);
			cy.getByTestId("report-panel")
				.filter('[data-panel="deals"]')
				.should("have.attr", "data-available", "no")
				.and("contain", "Not live yet");
			cy.getByTestId("report-panel")
				.filter('[data-panel="commission"]')
				.should("have.attr", "data-available", "yes")
				.and("not.contain", "Not live yet");
		});

		it("has Your results in the navigation, and no other role can open the page", () => {
			open();
			cy.getByTestId("nav").contains("a", "Your results").should("be.visible");
			["agent", "company_admin"].forEach((role) => {
				cy.signInFresh(role);
				cy.visit("/sellos/partner/reports");
				cy.getByTestId("no-access").should("be.visible");
				cy.getByTestId("partner-reports-page").should("not.exist");
			});
		});
	});

	context("the Platform Admin", () => {
		const open = (title) => {
			cy.signInFresh("platform_admin");
			cy.visit("/sellos/control/reports");
			cy.getByTestId("platform-reports-report").should("be.visible").select(title);
			cy.getByTestId("report-row").should("have.length.greaterThan", 0);
		};
		const cells = (tenant) =>
			cy
				.getByTestId("platform-reports-page")
				.find(`[data-testid="sellos-report-row"][data-key="${tenant}"]`);

		it("shows usage as totals per company, as recorded", () => {
			open("Usage");
			Object.entries(seed.usage).forEach(([tenant, [users, leads, calls, seconds]]) => {
				cells(tenant).should("contain", seed.tenants[tenant]);
				cells(tenant).find("[data-col=users]").should("have.text", String(users));
				cells(tenant).find("[data-col=leads]").should("have.text", String(leads));
				cells(tenant).find("[data-col=calls]").should("have.text", String(calls));
				cells(tenant)
					.find("[data-col=call_seconds]")
					.should(
						"have.text",
						seconds >= 60
							? `${Math.floor(seconds / 60)}m ${seconds % 60}s`
							: `${seconds}s`
					);
			});
			cy.getByTestId("platform-reports-months").should("contain", "Months from");
		});

		it("shows calling spend per company in rupees", () => {
			open("Calling spend");
			Object.entries(seed.usage).forEach(([tenant, [, , calls, , cost]]) => {
				cells(tenant).find("[data-col=calls]").should("have.text", String(calls));
				cells(tenant).find("[data-col=call_cost]").should("have.text", rupees(cost));
			});
			cy.get('[data-stat="Calling spend"]').should("contain", "Rs");
			cy.get('[data-stat="Calls"]').should("exist");
		});

		it("lists every company with its status in the Companies report", () => {
			open("Companies");
			Object.entries(seed.tenants).forEach(([tenant, name]) => {
				cells(tenant).should("contain", name).and("contain", "Requested");
			});
			cy.getByTestId("platform-reports-from").should("not.exist");
		});

		it("filters by date: months with no usage show zeros", () => {
			open("Usage");
			cy.getByTestId("platform-reports-from").clear().type("2020-01-01");
			cy.getByTestId("platform-reports-to").clear().type("2020-01-31");
			cy.getByTestId("platform-reports-from")
				.closest("form")
				.find("button[type=submit]")
				.click();
			cy.getByTestId("platform-reports-months").should("contain", "2020-01 to 2020-01");
			Object.keys(seed.usage).forEach((tenant) => {
				cells(tenant).find("[data-col=leads]").should("have.text", "0");
			});
		});

		it("shows revenue, churn and failed payments as waiting until billing is live", () => {
			open("Usage");
			cy.getByTestId("report-panel").should("have.length", 3);
			["revenue", "churn", "failed-payments"].forEach((key) => {
				cy.getByTestId("report-panel")
					.filter(`[data-panel="${key}"]`)
					.should("have.attr", "data-available", "no")
					.and("contain", "billing is live");
			});
		});

		it("holds no lead, client or call record and no phone number", () => {
			open("Usage");
			cy.getByTestId("platform-reports-page")
				.invoke("text")
				.should("not.match", /\+91|\d{10}|Gate Portal Report/);
		});

		it("is open to the Platform Admin only", () => {
			["company_admin", "agent", "channel_partner"].forEach((role) => {
				cy.signInFresh(role);
				cy.visit("/sellos/control/reports");
				cy.getByTestId("no-access").should("be.visible");
				cy.getByTestId("platform-reports-page").should("not.exist");
			});
		});
	});
});
