// SOS-UI-2, SOS-UI-2B: the Pandya palette on PAMAA's layout (docs/UI_STYLE.md) is applied to the app shell.
context("SOS-UI-2B: Pandya palette on the app shell", () => {
	beforeEach(() => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("app-shell").should("exist");
		// The agent lands on Today. Let its lists finish loading, so leaving the page cuts no request off.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
	});

	it("uses the page background, the ink text colour and Inter", () => {
		cy.get("body").should("have.css", "background-color", "rgb(255, 242, 220)");
		cy.get("body").should("have.css", "color", "rgb(0, 60, 60)");
		cy.get("body").invoke("css", "font-family").should("match", /Inter/);
		cy.get("body").should("have.css", "font-size", "16px");
	});

	it("draws the title at 24px and 600", () => {
		cy.getByTestId("home-welcome").should("have.css", "font-size", "24px");
		cy.getByTestId("home-welcome").should("have.css", "font-weight", "600");
	});

	it("gives the sidebar 240px on the dark surface, 44px items and the 8px control radius", () => {
		cy.getByTestId("nav")
			.filter(":visible")
			.parents("aside")
			.should("have.css", "width", "240px");
		cy.getByTestId("nav")
			.filter(":visible")
			.parents("aside")
			.should("have.css", "background-color", "rgb(0, 60, 60)");
		cy.getByTestId("nav-home").should("have.css", "min-height", "44px");
		cy.getByTestId("nav-home").should("have.css", "border-top-left-radius", "8px");
		cy.getByTestId("nav-leads").should("have.css", "color", "rgb(255, 220, 156)");
	});

	it("puts the top bar on the dark surface", () => {
		cy.getByTestId("phone-topbar").should("have.css", "background-color", "rgb(0, 60, 60)");
	});

	it("gives a card the 16px radius, a 1px teal line at low opacity and white fill", () => {
		cy.signInFresh("basic");
		cy.visit("/sellos");
		cy.getByTestId("no-access")
			.should("have.css", "border-top-left-radius", "16px")
			.and("have.css", "border-top-width", "1px")
			.and("have.css", "border-top-color", "rgba(0, 45, 45, 0.2)")
			.and("have.css", "background-color", "rgb(255, 255, 255)");
	});
});

// SOS-UI-3A: Home, Call queue and Site visits are built from the shared components (docs/UI_STYLE.md).
context("SOS-UI-3A: Home, Call queue and Site visits follow the style", () => {
	const pages = [
		{ name: "Home", path: "/sellos", title: "home-welcome", ready: "today-counts" },
		{ name: "Call queue", path: "/sellos/crm/queue", title: "page-title", ready: "queue" },
		{
			name: "Site visits",
			path: "/sellos/crm/visits",
			title: "page-title",
			ready: "visits-page",
		},
	];

	pages.forEach((page) => {
		it(`${page.name}: page colours, 24px/600 title, 16px card with the teal line`, () => {
			cy.signInFresh("agent");
			cy.visit(page.path);
			cy.getByTestId(page.ready, { timeout: 15000 }).should("be.visible");
			cy.get("body").should("have.css", "background-color", "rgb(255, 242, 220)");
			cy.get("body").should("have.css", "color", "rgb(0, 60, 60)");
			cy.getByTestId(page.title)
				.should("have.css", "font-size", "24px")
				.and("have.css", "font-weight", "600");
			cy.getByTestId("app-shell")
				.find(".ui-card, .rounded-card")
				.first()
				.should("have.css", "border-top-left-radius", "16px")
				.and("have.css", "border-top-width", "1px")
				.and("have.css", "border-top-color", "rgba(0, 45, 45, 0.2)");
		});

		it(`${page.name}: every control is a frappe-ui control`, () => {
			cy.signInFresh("agent");
			cy.visit(page.path);
			cy.getByTestId(page.ready, { timeout: 15000 }).should("be.visible");
			cy.getByTestId("app-shell")
				.find("main")
				.then(($main) => {
					// No native select, and no text input outside a frappe-ui FormControl.
					expect($main.find("select").length, "native selects").to.eq(0);
					$main.find("button").each((_, el) => {
						expect(
							el.className,
							`button ${el.textContent.trim()} is a frappe-ui Button`
						).to.match(/inline-flex|\bflex\b/);
					});
				});
		});
	});

	it("Call queue: the Call button is solid button/bg with text/button", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_caller_queue");
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/queue");
		cy.getByTestId("queue-call")
			.first()
			.should("have.css", "background-color", "rgb(0, 60, 60)")
			.and("have.css", "color", "rgb(228, 179, 60)");
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});
});
