// SOS-LOOP design system pass (25 November 2026): the pieces of docs/DESIGN_SYSTEM.md on the real screens.
// The list shape (search and Filters on one row, removable chips, stat tiles that are links), the record shape (record
// header, tabs above the main column, a side column that is never empty), the sidebar (area sections, a sliding
// highlight, open and closed state kept per person on the server) and the gallery.
context("SOS-LOOP: design system pieces", () => {
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	it("a list screen: search and Filters on one row, a chip for each filter that is on, tiles that are links", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_board_leads").then(() => {
			cy.signInFresh("company_admin");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("lead-row").should("have.length.greaterThan", 0);
			// One row: the search box and the Filters button have the same top edge.
			cy.getByTestId("leads-search").then(($search) => {
				cy.getByTestId("leads-filters-toggle").then(($toggle) => {
					const a = $search[0].getBoundingClientRect();
					const b = $toggle[0].getBoundingClientRect();
					expect(Math.abs(a.top - b.top), "same row").to.be.lessThan(8);
					expect(b.height, "button height").to.eq(44);
				});
			});
			cy.getByTestId("filter-chips").should("not.exist");
			cy.getByTestId("leads-filters-toggle").click();
			cy.getByTestId("leads-filter-stage").select("Qualified");
			cy.getByTestId("filter-chip").should("contain", "Stage: Qualified");
			cy.location("search").should("contain", "stage=Qualified");
			cy.getByTestId("filter-chip-remove").click();
			cy.getByTestId("filter-chips").should("not.exist");
			cy.location("search").should("not.contain", "stage=");
			// A stat tile is a link: the whole tile opens the filtered list.
			cy.getByTestId("leads-stats").contains("Overdue follow ups").closest("a").click();
			cy.location("search").should("contain", "follow_up=overdue");
		});
	});

	it("a record screen: record header, tabs, and a side column that is never empty", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_agent_leads").then(({ own }) => {
			cy.signInFresh("company_admin");
			cy.visit("/sellos/crm/leads");
			cy.getByTestId("lead-row").contains(own).click();
			cy.getByTestId("record-header").should("be.visible");
			cy.get("h1").should("have.length", 1);
			cy.getByTestId("lead-back").should("contain", "Back to leads");
			cy.getByTestId("tabs").should("be.visible");
			cy.getByTestId("page-main")
				.find("aside")
				.within(() => {
					cy.getByTestId("lead-follow-up").should("exist");
					cy.getByTestId("lead-consent").should("exist");
				});
			cy.getByTestId("lead-summary-stage").should(
				"have.css",
				"border-top-left-radius",
				"9999px"
			);
		});
	});

	it("the sidebar: area sections, a sliding highlight and an open or closed choice that is kept", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/crm/leads");
		["sales", "calls", "inventory", "money", "company"].forEach((area) =>
			cy.getByTestId(`nav-group-${area}`).should("exist")
		);
		// The open page is the solid gradient highlight; it sits over the open item.
		cy.getByTestId("nav-highlight")
			.should("have.css", "height", "44px")
			.and("not.have.css", "display", "none");
		cy.getByTestId("nav-leads")
			.should("have.css", "min-height", "44px")
			.and("have.css", "border-top-left-radius", "10px")
			.and("have.css", "color", "rgb(255, 255, 255)");
		// Closing a section is kept on the server: after a reload it is still closed.
		cy.intercept("**/sellos.access.preferences.set_nav_state*").as("saveNav");
		cy.getByTestId("nav-group-calls").click();
		cy.wait("@saveNav").its("response.statusCode").should("eq", 200);
		cy.getByTestId("nav-queue").should("not.be.visible");
		cy.reload();
		cy.getByTestId("nav-group-calls").should("have.attr", "aria-expanded", "false");
		cy.getByTestId("nav-queue").should("not.be.visible");
		cy.getByTestId("nav-group-calls").click();
		cy.wait("@saveNav");
		cy.getByTestId("nav-queue").should("be.visible");
	});

	it("the gallery shows every piece, in each area's colours", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/gallery");
		cy.getByTestId("gallery-page").should("be.visible");
		["buttons", "pills", "tiles", "table"].forEach((id) =>
			cy.getByTestId(`gallery-${id}`).should("exist")
		);
		cy.getByTestId("gallery-buttons").find("button").should("have.length.greaterThan", 6);
		cy.getByTestId("gallery-area").select("Money");
		cy.getByTestId("gallery-page").invoke("attr", "data-area").should("eq", "money");
		cy.getByTestId("gallery-tiles").find("[data-tone]").should("have.length", 4);
	});
});
