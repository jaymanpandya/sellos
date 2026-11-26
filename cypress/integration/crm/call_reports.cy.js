// SOS-P2-11: the call reports, against the real server. ui_fixtures.seed_call_reports places seven calls
// through the fake provider (six inside the range, one 40 days old) and returns the range and what the
// Call Log table itself holds for it, read with SQL that shares no code with the report. The spec checks
// each total against that, and each figure against the calls it lists. remove_call_reports removes it all.
context("SOS-P2-11: the call reports", () => {
	let seed;

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_call_reports").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.visit("/sellos");
		cy.bench("sellos.tests.ui_fixtures.remove_call_reports");
	});

	const text = (testId) => cy.getByTestId(testId).invoke("text");
	const open = () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.reports.calls.call_report*").as("callReport");
		cy.visit("/sellos/reports/calls");
		cy.getByTestId("callreports-total-calls").should("be.visible");
		cy.wait("@callReport");
	};
	const setRange = (from, to) => {
		cy.getByTestId("callreports-from").clear().type(from);
		cy.getByTestId("callreports-to").clear().type(to);
		cy.getByTestId("callreports-from").closest("form").find("button[type=submit]").click();
		// The page writes the answer's dates back into the boxes: wait for it before the next edit.
		cy.wait("@callReport");
	};

	it("shows totals that match the Call Log for the dates", () => {
		open();
		cy.getByTestId("callreports-range").should("contain", seed.from_date.slice(0, 4));
		setRange(seed.from_date, seed.to_date);
		cy.getByTestId("callreports-range").should("contain", seed.from_date);
		cy.getByTestId("callreports-total-calls").should("have.text", String(seed.totals.calls));
		cy.getByTestId("callreports-total-connect-rate").should(
			"contain",
			`${Math.round((seed.totals.connected * 1000) / seed.totals.calls) / 10}%`
		);
		cy.getByTestId("callreports-total-cost").should("contain", "Rs");
		// The sums of the rows are the totals.
		cy.getByTestId("callreports-agent").then(($rows) => {
			const calls = [...$rows].reduce(
				(n, r) => n + Number(r.querySelector("[data-col=calls]").textContent),
				0
			);
			expect(calls).to.equal(seed.totals.calls);
		});
		cy.getByTestId("callreports-purpose").then(($rows) => {
			const calls = [...$rows].reduce(
				(n, r) => n + Number(r.querySelector("[data-col=calls]").textContent),
				0
			);
			expect(calls).to.equal(seed.totals.calls);
		});
	});

	it("filters by date: the old call is only in a range that reaches back to it", () => {
		open();
		setRange(seed.from_date, seed.to_date);
		cy.getByTestId("callreports-total-calls").should("have.text", String(seed.totals.calls));
		const old = seed.calls.find((c) => c.lead_key === "opted");
		setRange(old.day, old.day);
		cy.getByTestId("callreports-range").should("contain", old.day);
		cy.getByTestId("callreports-total-calls").should(
			"not.have.text",
			String(seed.totals.calls)
		);
		cy.getByTestId("callreports-open-calls").click();
		cy.getByTestId("callreports-call")
			.filter(`[data-call="${old.log}"]`)
			.should("have.length", 1);
	});

	it("opens the calls behind every figure, with the same count", () => {
		open();
		setRange(seed.from_date, seed.to_date);
		cy.getByTestId("callreports-total-calls").should("have.text", String(seed.totals.calls));
		cy.getByTestId("callreports-open-calls").click();
		cy.getByTestId("callreports-drill").should(
			"have.attr",
			"data-count",
			String(seed.totals.calls)
		);
		cy.getByTestId("callreports-open-connect-rate").click();
		cy.getByTestId("callreports-drill").should(
			"have.attr",
			"data-count",
			String(seed.totals.connected)
		);
		cy.getByTestId("callreports-purpose").each(($row) => {
			const count = $row.find("[data-col=calls]").text();
			cy.wrap($row).find("[data-testid=sellos-row-menu-button]").click();
			cy.contains("[role=menuitem]", "Show calls").click();
			cy.getByTestId("callreports-drill").should("have.attr", "data-count", count);
		});
		cy.getByTestId("callreports-agent").each(($row) => {
			const count = $row.find("[data-col=calls]").text();
			cy.wrap($row).find("[data-testid=sellos-row-menu-button]").click();
			cy.contains("[role=menuitem]", "Show calls").click();
			cy.getByTestId("callreports-drill").should("have.attr", "data-count", count);
		});
		cy.getByTestId("callreports-consent").each(($row) => {
			const count = $row.find("[data-col=calls]").text().trim().split(" ")[0];
			cy.wrap($row).find("[data-testid=sellos-row-menu-button]").click();
			cy.contains("[role=menuitem]", "Show calls").click();
			cy.getByTestId("callreports-drill").should("have.attr", "data-count", count);
		});
	});

	it("counts calls to Opted out and Registered DND leads: consent never blocks", () => {
		open();
		setRange(seed.from_date, seed.to_date);
		cy.getByTestId("callreports-consent")
			.filter('[data-status="Registered DND"]')
			.find("[data-col=calls]")
			.should("contain", "1 (");
		cy.getByTestId("callreports-consent")
			.filter('[data-status="Consented"]')
			.find("[data-testid=sellos-row-menu-button]")
			.click();
		cy.contains("[role=menuitem]", "Show calls").click();
		cy.getByTestId("callreports-call").each(($row) => {
			expect($row.text()).to.contain("Consented");
		});
	});

	it("keeps the reports from an agent", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/reports/calls");
		cy.getByTestId("no-access").should("be.visible");
		cy.getByTestId("callreports-page").should("not.exist");
	});
});
