context("SOS-FIX-1: an unknown path shows page not found", () => {
	["platform_admin", "company_admin", "agent", "channel_partner", "client", "basic"].forEach(
		(role) => {
			it(`shows the not found screen to ${role}`, () => {
				cy.signInFresh(role);
				cy.visit("/sellos/does/not/exist");
				cy.getByTestId("not-found").should("be.visible");
				cy.getByTestId("not-found-home")
					.should("be.visible")
					.and("have.attr", "href", "/sellos/");
				cy.getByTestId("not-found-home").click();
				cy.location("pathname").should("not.contain", "does/not/exist");
				cy.getByTestId("not-found").should("not.exist");
			});
		}
	);
});
