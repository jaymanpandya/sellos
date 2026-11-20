// SOS-UI-2, SOS-UI-2B: the Pandya palette on PAMAA's layout (docs/UI_STYLE.md) is applied to the app shell.
context("SOS-UI-2B: Pandya palette on the app shell", () => {
	beforeEach(() => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("app-shell").should("exist");
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
		// The agent's Today lists must finish loading before the page is left, so no request is cut off.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
		cy.signInFresh("basic");
		cy.visit("/sellos");
		cy.getByTestId("no-access")
			.should("have.css", "border-top-left-radius", "16px")
			.and("have.css", "border-top-width", "1px")
			.and("have.css", "border-top-color", "rgba(0, 45, 45, 0.2)")
			.and("have.css", "background-color", "rgb(255, 255, 255)");
	});
});
