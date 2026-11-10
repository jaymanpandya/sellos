// The browser tab shows the company logo when SellOS Settings has one, otherwise the SellOS icon.
context("SOS-P1-06A: tab icon", () => {
	const iconHref = () => cy.get('head link[rel="icon"]').invoke("attr", "href");

	after(() => {
		cy.bench("sellos.tests.ui_fixtures.set_company_branding", { logo: "" });
	});

	it("shows the SellOS icon when the company has no logo", () => {
		cy.bench("sellos.tests.ui_fixtures.set_company_branding", { logo: "" });
		cy.signInFresh("agent");
		cy.visit("/sellos");
		iconHref().should("contain", "sellos-favicon.svg").and("not.eq", "data:,");
	});

	it("shows the company logo when SellOS Settings has one", () => {
		cy.bench("sellos.tests.ui_fixtures.set_company_branding", {
			company_name: "Pandya Realtors",
			logo: "/files/company-logo-spec.svg",
		});
		cy.signInFresh("agent");
		cy.visit("/sellos");
		iconHref().should("eq", "/files/company-logo-spec.svg").and("not.eq", "data:,");
	});
});
