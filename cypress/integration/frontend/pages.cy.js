// SOS-P0-10: the home and no access pages. Replaces pages.test.js.
context("SOS-P0-10: pages", () => {
	it("greets the signed in user by name", () => {
		cy.signInFresh("agent");
		cy.bootOverride((boot) => {
			boot.full_name = "Jayman";
		});
		cy.visit("/sellos");
		cy.getByTestId("home-welcome").should("contain", "Welcome, Jayman");
	});

	it("greets with the email when the boot data has no name", () => {
		// The app falls back to the email, so the greeting is never left without a name. The old
		// unit test also checked the greeting for an empty name; no sign in reaches that state.
		cy.signInFresh("agent");
		cy.bootOverride((boot) => {
			boot.full_name = "";
		});
		cy.visit("/sellos");
		cy.getByTestId("home-welcome")
			.should("contain", "Welcome")
			.and("contain", "sos_test_agent@example.com");
	});

	it("explains the no access page", () => {
		cy.signInFresh("basic");
		cy.visit("/sellos");
		cy.getByTestId("no-access").should("contain", "You do not have access to this page");
	});
});
