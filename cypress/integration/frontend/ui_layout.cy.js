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

	it("puts Assigned agent, Consent and Timeline in the side column of the lead page, with a solid main button", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads").then(({ own }) => {
			cy.signInFresh("company_admin");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("lead-row").contains(own).click();
			cy.getByTestId("lead-page")
				.find("aside")
				.within(() => {
					cy.getByTestId("reassign").should("exist");
					cy.getByTestId("lead-consent").should("exist");
					cy.getByTestId("lead-timeline").should("exist");
				});
			cy.getByTestId("lead-requirements").parents("aside").should("have.length", 0);
			cy.getByTestId("lead-call").parents("aside").should("have.length", 0);
			// The main action of a card is the solid accent with white text.
			cy.getByTestId("lead-req-save")
				.should("have.css", "background-color", "rgb(15, 76, 53)")
				.and("have.css", "color", "rgb(255, 255, 255)");
			// A secondary action is white with the secondary edge.
			cy.getByTestId("lead-optout").should(
				"have.css",
				"border-top-color",
				"rgb(201, 208, 221)"
			);
		});
	});

	it("groups a budget the Indian way and still submits a plain number", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads").then(({ own }) => {
			cy.signInFresh("agent");
			cy.intercept("**/api/method/sellos.crm.api.save_lead*").as("save");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("lead-row").contains(own).click();
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
		cy.getByTestId("leads-filters-toggle").should("contain", "Fewer filters").click();
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

	it("shows a disabled button differently from a ghost button", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("bulk-reassign")
			.should("be.disabled")
			.and("have.css", "border-top-style", "dashed");
		cy.getByTestId("leads-filter-clear").should("have.css", "border-top-style", "solid");
	});
});
