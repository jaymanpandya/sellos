// SOS-P4-02: an Agent makes a listing typed Primary or Direct, cannot publish it until it is complete,
// publishes and withdraws it, and sees its change history; a Sales Manager only reads. The records the spec
// makes (names start with "Gate Inventory ") are removed afterwards.
context("SOS-P4-02: listings", () => {
	const row = (title) => cy.get(`[data-testid="sellos-listing-row"][data-title="${title}"]`);
	const openListings = () => {
		cy.intercept("POST", "**/sellos.inventory.listings.listing_overview*").as("overview");
		cy.visit("/sellos/inventory/listings");
		cy.wait("@overview");
	};

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory"));

	it("makes a Direct listing, refuses to publish it until complete, then publishes and withdraws it", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_listings").then((made) => {
			const title = `Gate Inventory Spec Direct ${made.tag}`;
			const flat = `Property: Gate Inventory Listing Flat ${made.tag}`;
			cy.signInFresh("agent");
			openListings();

			cy.intercept("POST", "**/sellos.inventory.listings.save_listing*").as("save");
			cy.intercept("POST", "**/sellos.inventory.listings.publish_listing*").as("publish");
			cy.getByTestId("listing-new").click();
			cy.getByTestId("listing-title").type(title);
			cy.getByTestId("listing-type-field").select("Direct");
			cy.getByTestId("listing-target-field").select(flat);
			cy.getByTestId("listing-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);

			// An incomplete listing is a draft, and publishing it is refused with what it lacks.
			row(title).should("contain", "Draft").and("contain", "Direct");
			row(title)
				.find('[data-testid="sellos-listing-missing"]')
				.should("contain", "an asking price")
				.and("contain", "a description");
			cy.expectApiStatus("sellos.inventory.listings.publish_listing", 417);
			row(title).find('[data-testid="sellos-listing-publish"]').click();
			cy.wait("@publish").its("response.statusCode").should("eq", 417);
			cy.getByTestId("listing-error").should("contain", "an asking price");
			row(title).should("have.attr", "data-published", "0");

			// Completed, it publishes.
			row(title).find('[data-testid="sellos-listing-edit"]').click();
			cy.getByTestId("listing-price-field").type("8200000");
			cy.getByTestId("listing-description").type("A resale flat near the market.");
			cy.getByTestId("listing-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);
			row(title).should("contain", "Rs 82,00,000");
			row(title).find('[data-testid="sellos-listing-publish"]').click();
			cy.wait("@publish").its("response.statusCode").should("eq", 200);
			row(title).should("have.attr", "data-published", "1").and("contain", "Published");
			cy.getByTestId("listing-notice").should("contain", "is published");

			// The change history says who published it.
			row(title).find("summary").click();
			row(title)
				.find('[data-testid="sellos-listing-change"]')
				.last()
				.should("contain", "set published")
				.and("contain", "to Yes");

			cy.getByTestId("listing-error").should("not.exist");
			row(title).find('[data-testid="sellos-listing-unpublish"]').click();
			row(title).should("have.attr", "data-published", "0").and("contain", "Draft");

			cy.bench("sellos.tests.ui_fixtures.gate_listing_state", { title }).then((state) => {
				expect(state.listing_type).to.eq("Direct");
				expect(state.published).to.eq(0);
				expect(state.asking_price).to.eq(8200000);
				expect(state.changes.map((c) => c[0])).to.include.members([
					"Published",
					"Asking price",
				]);
			});
		});
	});

	it("makes a Primary listing of a unit and offers only units for it", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_listings").then((made) => {
			const title = `Gate Inventory Spec Primary ${made.tag}`;
			cy.signInFresh("company_admin");
			openListings();
			cy.intercept("POST", "**/sellos.inventory.listings.save_listing*").as("save");
			cy.getByTestId("listing-new").click();
			cy.getByTestId("listing-title").type(title);
			cy.getByTestId("listing-type-field").select("Primary");
			cy.getByTestId("listing-target-field").select(`Unit: ${made.project_name}, unit 1201`);
			cy.getByTestId("listing-price-field").type("10500000");
			cy.getByTestId("listing-description").type("A two bedroom flat on the 12th floor.");
			cy.getByTestId("listing-save").click();
			cy.wait("@save").its("response.statusCode").should("eq", 200);
			cy.intercept("POST", "**/sellos.inventory.listings.publish_listing*").as("publish");
			row(title).find('[data-testid="sellos-listing-publish"]').click();
			cy.wait("@publish").its("response.statusCode").should("eq", 200);
			row(title).should("have.attr", "data-published", "1").and("contain", "Primary");
			row(title)
				.find('[data-testid="sellos-listing-target"]')
				.should("contain", "unit 1201");
			cy.bench("sellos.tests.ui_fixtures.gate_listing_state", { title }).then((state) => {
				expect(state.listing_type).to.eq("Primary");
				expect(state.published).to.eq(1);
			});
		});
	});

	it("lets a Sales Manager read listings but not change them", () => {
		cy.signInFresh("sales_manager");
		openListings();
		cy.getByTestId("listing-form").should("not.exist");
		cy.getByTestId("listing-publish").should("not.exist");
		cy.getByTestId("listing-edit").should("not.exist");
	});
});
