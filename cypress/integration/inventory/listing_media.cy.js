// SOS-P4-03: an Agent puts photos on a listing, is refused an invalid file, links a file from the library,
// changes the order and takes a file off, and a Sales Manager only reads. The records the spec makes (names
// start with "Gate Inventory ") are removed afterwards.
context("SOS-P4-03: photos and videos of a listing", () => {
	// A real 1 by 1 PNG.
	const PNG =
		"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
	const picture = (fileName) => ({
		contents: Cypress.Buffer.from(PNG, "base64"),
		fileName,
		mimeType: "image/png",
	});
	const row = (title) => cy.get(`[data-testid="sellos-listing-row"][data-title="${title}"]`);
	const mediaRow = (title) => cy.get(`[data-testid="sellos-media-row"][data-title="${title}"]`);
	const openMedia = (title) => {
		cy.intercept("POST", "**/sellos.inventory.listings.listing_overview*").as("overview");
		cy.intercept("POST", "**/sellos.inventory.media.listing_media*").as("media");
		cy.visit("/sellos/inventory/listings");
		cy.wait("@overview");
		row(title).find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', "Photos and videos").click();
		cy.wait("@media");
	};
	const titles = () =>
		cy
			.get('[data-testid="sellos-media-row"]')
			.then(($rows) => [...$rows].map((r) => r.dataset.title));

	before(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory"));
	after(() => cy.bench("sellos.tests.ui_fixtures.remove_gate_inventory"));

	it("uploads photos, refuses invalid files, links from the library, reorders and removes", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_media_listing").then((made) => {
			const listing = made.listing;
			const first = `Gate Inventory First ${made.tag}`;
			const second = `Gate Inventory Second ${made.tag}`;
			const library = `Gate Inventory Library Photo ${made.tag}`;
			cy.signInFresh("agent");
			openMedia(listing);
			cy.getByTestId("media-empty").should("contain", "No photos or videos yet");

			// Two valid photos attach, in the order they were added.
			cy.intercept("POST", "**/sellos.inventory.media.upload_listing_media*").as("upload");
			cy.getByTestId("media-title-field").type(first);
			cy.getByTestId("media-file").selectFile(picture("first.png"));
			cy.wait("@upload").its("response.statusCode").should("eq", 200);
			mediaRow(first).should("contain", "Photo").and("have.attr", "data-position", "1");
			cy.getByTestId("media-picture")
				.should("have.attr", "src")
				.and("match", /\/files\/media-/);
			cy.getByTestId("media-title-field").type(second);
			cy.getByTestId("media-file").selectFile(picture("second.png"));
			cy.wait("@upload").its("response.statusCode").should("eq", 200);
			mediaRow(second).should("have.attr", "data-position", "2");
			row(listing).find('[data-testid="sellos-row-menu-button"]').click();
			cy.contains('[role="menuitem"]', "Photos and videos").should("contain", "(2)");
			cy.get("body").type("{esc}");

			// Invalid files are refused, with the reason, and nothing is added.
			cy.expectApiStatus("sellos.inventory.media.upload_listing_media", 417);
			cy.getByTestId("media-file").selectFile({
				contents: Cypress.Buffer.from("%PDF-1.4 a brochure"),
				fileName: "brochure.pdf",
				mimeType: "application/pdf",
			});
			cy.wait("@upload").its("response.statusCode").should("eq", 417);
			cy.getByTestId("media-error").should("contain", "JPG, PNG, WEBP, MP4, MOV or WEBM");
			cy.getByTestId("media-file").selectFile({
				contents: Cypress.Buffer.from("<html>not a picture</html>"),
				fileName: "fake.png",
				mimeType: "image/png",
			});
			cy.wait("@upload").its("response.statusCode").should("eq", 417);
			cy.getByTestId("media-error").should("contain", "not a real PNG");
			cy.getByTestId("media-file").selectFile({
				contents: Cypress.Buffer.concat([
					Cypress.Buffer.from(PNG, "base64"),
					Cypress.Buffer.alloc(5 * 1024 * 1024),
				]),
				fileName: "big.png",
				mimeType: "image/png",
			});
			cy.wait("@upload").its("response.statusCode").should("eq", 417);
			cy.getByTestId("media-error").should("contain", "up to 5 MB");
			cy.get('[data-testid="sellos-media-row"]').should("have.length", 2);

			// The order can be changed, and it is the saved order after a reload.
			cy.intercept("POST", "**/sellos.inventory.media.reorder_listing_media*").as("reorder");
			mediaRow(first).find('[data-testid="sellos-media-down"]').click();
			cy.wait("@reorder").its("response.statusCode").should("eq", 200);
			cy.getByTestId("media-notice").should("contain", "order was saved");
			titles().should("deep.equal", [second, first]);
			openMedia(listing);
			titles().should("deep.equal", [second, first]);

			// A file from the library links, and taking it off keeps it in the library.
			cy.intercept("POST", "**/sellos.inventory.media.link_listing_media*").as("link");
			cy.intercept("POST", "**/sellos.inventory.media.unlink_listing_media*").as("unlink");
			cy.getByTestId("media-library").select(`${library} (Photo)`);
			cy.getByTestId("media-link").click();
			cy.wait("@link").its("response.statusCode").should("eq", 200);
			mediaRow(library).should("have.attr", "data-position", "3");
			mediaRow(library).find('[data-testid="sellos-media-remove"]').click();
			cy.wait("@unlink").its("response.statusCode").should("eq", 200);
			mediaRow(library).should("not.exist");
			cy.getByTestId("media-library").select(`${library} (Photo)`); // offered again

			cy.bench("sellos.tests.ui_fixtures.gate_media_state", { title: listing }).then(
				(state) => {
					expect(state.media.map((m) => m[0])).to.deep.equal([second, first]);
					expect(state.media.every((m) => m[1] === "Photo" && m[2] > 0 && m[3])).to.eq(
						true
					);
					expect(state.changes.map((c) => c[1])).to.include.members([
						`Added ${first}`,
						`Added ${second}`,
						"Order changed",
						`Added ${library}`,
						`Removed ${library}`,
					]);
				}
			);
		});
	});

	it("lets a Sales Manager see a listing's photos but not change them", () => {
		cy.bench("sellos.tests.ui_fixtures.make_gate_media_listing").then((made) => {
			cy.signInFresh("agent");
			openMedia(made.listing);
			cy.intercept("POST", "**/sellos.inventory.media.upload_listing_media*").as("upload");
			cy.getByTestId("media-file").selectFile(picture("seen.png"));
			cy.wait("@upload").its("response.statusCode").should("eq", 200);
			cy.signInFresh("sales_manager");
			openMedia(made.listing);
			cy.get('[data-testid="sellos-media-row"]').should("have.length", 1);
			cy.getByTestId("media-file").should("not.exist");
			cy.getByTestId("media-library").should("not.exist");
			cy.getByTestId("media-up").should("not.exist");
			cy.getByTestId("media-remove").should("not.exist");
		});
	});
});
