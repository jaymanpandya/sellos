// SOS-UI-2: the PAMAA tokens of docs/UI_STYLE.md are applied to the app shell.
context("SOS-UI-2: PAMAA style on the app shell", () => {
	beforeEach(() => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("app-shell").should("exist");
	});

	it("uses the page background, the ink text colour and Inter", () => {
		cy.get("body").should("have.css", "background-color", "rgb(244, 245, 247)");
		cy.get("body").should("have.css", "color", "rgb(29, 34, 43)");
		cy.get("body").invoke("css", "font-family").should("match", /Inter/);
		cy.get("body").should("have.css", "font-size", "16px");
	});

	it("draws the title at 24px and 600", () => {
		cy.getByTestId("home-welcome").should("have.css", "font-size", "24px");
		cy.getByTestId("home-welcome").should("have.css", "font-weight", "600");
	});

	it("gives the sidebar 240px, 44px navigation items and the 10px control radius", () => {
		cy.getByTestId("nav").filter(":visible").parent().should("have.css", "width", "240px");
		cy.getByTestId("nav-home").should("have.css", "min-height", "44px");
		cy.getByTestId("nav-home").should("have.css", "border-top-left-radius", "10px");
	});

	it("gives a card the 14px radius, a 1px line border and the card shadow", () => {
		cy.signInFresh("basic");
		cy.visit("/sellos");
		cy.getByTestId("no-access")
			.should("have.css", "border-top-left-radius", "14px")
			.and("have.css", "border-top-width", "1px")
			.and("have.css", "border-top-color", "rgb(221, 226, 236)")
			.and("have.css", "background-color", "rgb(255, 255, 255)");
	});
});
