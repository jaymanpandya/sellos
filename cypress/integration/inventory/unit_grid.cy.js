// SOS-P7-06: an Agent holds an Available unit for their own lead on the availability grid and releases it;
// a Company Admin blocks and unblocks a unit with a reason, and the grid filters by status and
// configuration; a Sales Manager only reads. The project (names start with "Gate Inventory ") and the
// lead are removed afterwards.
context("SOS-P7-06: unit availability grid with holds and bookings", () => {
	let grid;
	const unit = (number) => cy.get(`[data-testid="sellos-grid-unit"][data-number="${number}"]`);
	const openGrid = () => {
		cy.intercept("POST", "**/sellos.inventory.holds.unit_grid*").as("grid");
		cy.visit(`/sellos/inventory/projects/${encodeURIComponent(grid.project)}`);
		cy.wait("@grid");
		cy.getByTestId("grid-legend").should("be.visible");
	};

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.make_gate_grid").then((made) => {
			grid = made;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory");
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});

	it("shows the floors and units with a legend of the five statuses", () => {
		cy.signInFresh("agent");
		openGrid();
		cy.getByTestId("grid-legend-item").should("have.length", 5);
		cy.get('[data-testid="sellos-grid-floor"][data-floor="2"]')
			.find('[data-testid="sellos-grid-unit"]')
			.should("have.length", 1);
		unit("G101").should("have.attr", "data-status", "Available");
	});

	it("lets an Agent hold a unit for their lead and release it", () => {
		cy.signInFresh("agent");
		openGrid();
		unit("G101").click();
		cy.intercept("POST", "**/sellos.inventory.holds.hold_unit*").as("hold");
		cy.getByTestId("grid-hold-lead").select(grid.lead);
		cy.getByTestId("grid-hold").click();
		cy.wait("@hold").its("response.statusCode").should("eq", 200);
		unit("G101").should("have.attr", "data-status", "Held");
		cy.getByTestId("grid-detail-holder")
			.should("contain", "Held by")
			.and("contain", grid.lead);
		cy.bench("sellos.tests.ui_fixtures.gate_unit_state", {
			project: grid.project,
			unit_number: "G101",
		}).then((state) => {
			expect(state.status).to.eq("Held");
			expect(state.has_end).to.eq(true);
			expect(state.held_by).to.not.eq("");
			expect(state.log.map((row) => row[0])).to.deep.eq(["Available", "Held"]);
		});

		cy.intercept("POST", "**/sellos.inventory.holds.release_hold*").as("release");
		cy.getByTestId("grid-release").click();
		cy.wait("@release").its("response.statusCode").should("eq", 200);
		unit("G101").should("have.attr", "data-status", "Available");
		cy.bench("sellos.tests.ui_fixtures.gate_unit_state", {
			project: grid.project,
			unit_number: "G101",
		}).then((state) => {
			expect(state.status).to.eq("Available");
			expect(state.held_by).to.eq("");
			expect(state.log.map((row) => row[0])).to.deep.eq(["Available", "Held", "Available"]);
		});
	});

	it("lets a Company Admin block and unblock a unit with a reason and filter the grid", () => {
		cy.signInFresh("company_admin");
		openGrid();
		unit("G102").click();
		cy.intercept("POST", "**/sellos.inventory.holds.block_unit*").as("block");
		cy.getByTestId("grid-reason").type("Gate legal check");
		cy.getByTestId("grid-block").click();
		cy.wait("@block").its("response.statusCode").should("eq", 200);
		unit("G102").should("have.attr", "data-status", "Blocked");
		cy.getByTestId("grid-detail-reason").should("contain", "Gate legal check");

		cy.intercept("POST", "**/sellos.inventory.holds.unit_grid*").as("filtered");
		cy.getByTestId("grid-filter-status").select("Blocked");
		cy.wait("@filtered");
		cy.getByTestId("grid-unit").should("have.length", 1);
		cy.getByTestId("grid-filter-status").select("Any status");
		cy.getByTestId("grid-filter-configuration").select("1 BHK");
		cy.wait("@filtered");
		cy.getByTestId("grid-unit").should("have.length", 1);
		unit("G201").should("be.visible");
		cy.getByTestId("grid-filter-configuration").select("Any configuration");
		cy.wait("@filtered");

		unit("G102").click();
		cy.intercept("POST", "**/sellos.inventory.holds.unblock_unit*").as("unblock");
		cy.getByTestId("grid-reason").type("Gate cleared");
		cy.getByTestId("grid-unblock").click();
		cy.wait("@unblock").its("response.statusCode").should("eq", 200);
		unit("G102").should("have.attr", "data-status", "Available");
	});

	it("lets a Sales Manager read the grid but not hold or block", () => {
		cy.signInFresh("sales_manager");
		openGrid();
		unit("G101").click();
		cy.getByTestId("grid-detail").should("be.visible");
		cy.getByTestId("grid-hold").should("not.exist");
		cy.getByTestId("grid-block").should("not.exist");
		cy.getByTestId("grid-hours-save").should("not.exist");
	});
});
