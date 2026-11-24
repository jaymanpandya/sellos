// SOS-UI-2B follow up: the button hierarchy, the lead page's two columns, the Leads list's stats and
// columns, Indian grouping in budget boxes, and the sidebar icons (docs/UI_STYLE.md).
context("SOS-UI-2B: layout, buttons, budgets and icons", () => {
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	it("shows the Leads list with four stat cards, column headings and a sidebar icon on every item", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads").then(() => {
			cy.signInFresh("company_admin");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("leads-stats").find("[data-tone]").should("have.length", 4);
			cy.getByTestId("leads-stats")
				.should("contain", "Total leads")
				.and("contain", "New this week")
				.and("contain", "Overdue follow ups")
				.and("contain", "Untouched");
			cy.getByTestId("leads-list").should("contain", "All leads");
			["Name", "Source", "Stage", "Next follow up", "Flags"].forEach((heading) =>
				cy.getByTestId("leads-list").find('[role="row"]').should("contain", heading)
			);
			cy.getByTestId("nav")
				.filter(":visible")
				.find("a")
				.each(($a) => expect($a.find('[class*="lucide-"]').length, "icon").to.eq(1));
			// The list uses the whole content width, not a narrow column.
			cy.getByTestId("leads-page").invoke("outerWidth").should("be.greaterThan", 900);
		});
	});

	it("puts Assigned agent and Consent in the right rail of the lead page, with the timeline under Activity and a solid main button", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads").then(({ own }) => {
			cy.signInFresh("company_admin");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("lead-row").contains(own).click();
			cy.getByTestId("lead-page")
				.find("aside")
				.within(() => {
					cy.getByTestId("reassign").should("exist");
					cy.getByTestId("lead-consent").should("exist");
				});
			// The history is under the Activity tab, in the main column, not in the rail.
			cy.getByTestId("tab-activity").click();
			cy.getByTestId("lead-page")
				.find("aside")
				.find('[data-testid="sellos-lead-timeline"]')
				.should("not.exist");
			cy.getByTestId("lead-timeline").should("exist");
			cy.getByTestId("tab-requirements").click();
			cy.getByTestId("lead-requirements").parents("aside").should("have.length", 0);
			// The main action of a card is the solid accent with white text.
			cy.getByTestId("lead-req-save")
				.should("have.css", "background-color", "rgb(15, 76, 53)")
				.and("have.css", "color", "rgb(255, 255, 255)");
			cy.getByTestId("tab-calls").click();
			cy.getByTestId("lead-call").parents("aside").should("have.length", 0);
			// A secondary action is the outline button: white, with the brand border at 35 percent.
			cy.getByTestId("lead-optout")
				.should("have.css", "background-color", "rgb(255, 255, 255)")
				.and(
					"have.css",
					"border-top-color",
					"color(srgb 0.0588235 0.298039 0.207843 / 0.35)"
				);
		});
	});

	it("groups a budget the Indian way and still submits a plain number", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads").then(({ own }) => {
			cy.signInFresh("agent");
			cy.intercept("**/api/method/sellos.crm.api.save_lead*").as("save");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("lead-row").contains(own).click();
			cy.getByTestId("tab-requirements").click();
			cy.getByTestId("lead-req-budget-from").clear().type("7500000");
			cy.getByTestId("lead-req-budget-from").should("have.value", "75,00,000");
			cy.getByTestId("lead-req-budget-to").clear().type("12000000");
			cy.getByTestId("lead-req-budget-to").should("have.value", "1,20,00,000");
			cy.getByTestId("lead-req-save").click();
			cy.wait("@save").then(({ request }) => {
				const body = JSON.stringify(request.body);
				expect(body).to.contain("7500000").and.to.contain("12000000");
				expect(body).not.to.contain("75,00,000");
			});
		});
	});

	it("shows one row of filters, and the rest under More filters", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/crm/leads");
		["search", "filter-stage", "filter-agent", "filter-source"].forEach((id) =>
			cy.getByTestId(`leads-${id}`).should("be.visible")
		);
		cy.getByTestId("leads-filter-budget-min").should("not.be.visible");
		cy.getByTestId("leads-filter-contacted-from").should("not.be.visible");
		cy.getByTestId("leads-filters-toggle").should("contain", "More filters").click();
		cy.getByTestId("leads-filter-budget-min").should("be.visible");
		cy.getByTestId("leads-filter-contacted-from").should("be.visible");
		cy.getByTestId("leads-filters-toggle")
			.should("have.attr", "aria-expanded", "true")
			.click();
		cy.getByTestId("leads-filter-budget-min").should("not.be.visible");
		// A bookmarked view that uses a hidden filter opens the panel by itself.
		cy.visit("/sellos/crm/leads?budget_min=5000000");
		cy.getByTestId("leads-filter-budget-min")
			.should("be.visible")
			.and("have.value", "50,00,000");
		// A native checkbox is the brand box, not the browser's.
		cy.getByTestId("leads-filter-untouched").check();
		cy.getByTestId("leads-filter-untouched").should(
			"have.css",
			"background-color",
			"rgb(15, 76, 53)"
		);
	});

	it("shows a disabled button differently from a ghost button, and the bulk bar only with a selection", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads").then(() => {
			cy.signInFresh("company_admin");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("lead-row").should("have.length.greaterThan", 0);
			// No row is selected: no bulk bar, and no Clear button while no filter is on.
			cy.getByTestId("bulk").should("not.exist");
			cy.getByTestId("leads-filter-clear").should("not.exist");
			cy.getByTestId("lead-select").first().check();
			cy.getByTestId("bulk").should("be.visible");
			cy.getByTestId("bulk-agent").select("Gate Agent");
			cy.getByTestId("bulk-reassign").should("not.be.disabled");
			cy.getByTestId("bulk-clear").click();
			cy.getByTestId("bulk").should("not.exist");
			cy.getByTestId("leads-search").type("Gate");
			cy.getByTestId("leads-filter-clear").should("have.css", "border-top-style", "solid");
			// A disabled button is 50 percent opacity (the merge button waits for a duplicate client to be chosen).
			cy.getByTestId("lead-row").first().click();
			cy.getByTestId("merge-save").should("be.disabled").and("have.css", "opacity", "0.5");
		});
	});
});
