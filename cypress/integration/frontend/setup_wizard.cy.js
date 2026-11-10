// SOS-P1-03: a Company Admin completes the setup wizard, can leave and resume it, and the branding
// shows in the app afterwards. Goes through the real screens and the real server.
context("SOS-P1-03: setup wizard", () => {
	// A 1 pixel PNG, so the spec holds no file.
	const PNG =
		"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
	const AGENT_EMAIL = "wizard_spec_agent@example.com";

	before(() => cy.bench("sellos.tests.ui_fixtures.reset_setup_wizard"));
	after(() => cy.bench("sellos.tests.ui_fixtures.reset_setup_wizard"));

	it("collects the four areas, resumes after leaving, and shows the branding afterwards", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos");
		cy.getByTestId("home-setup-banner").click();
		cy.location("pathname").should("eq", "/sellos/company/setup");

		// Step 1: the company profile.
		cy.getByTestId("setup-profile").should("be.visible");
		cy.getByTestId("setup-company-name").clear().type("Wizard Spec Realty");
		cy.getByTestId("setup-city").type("Pune");
		cy.getByTestId("setup-save-profile").click();

		// Step 2: the logo and colours.
		cy.getByTestId("setup-branding").should("be.visible");
		cy.getByTestId("setup-logo-file").selectFile({
			contents: Cypress.Buffer.from(PNG, "base64"),
			fileName: "logo.png",
			mimeType: "image/png",
		});
		cy.getByTestId("setup-logo-preview").should("be.visible");
		cy.getByTestId("setup-color").clear().type("#123abc");
		cy.getByTestId("setup-save-branding").click();

		// Step 3: the pipeline stages start from the defaults.
		cy.getByTestId("setup-stages").should("be.visible");
		cy.getByTestId("setup-stage-row").should("have.length", 7);
		cy.getByTestId("setup-stage-name").first().clear().type("Enquiry");
		cy.getByTestId("setup-save-stages").click();
		cy.getByTestId("setup-users").should("be.visible");

		// The admin leaves and comes back: the wizard opens where it stopped.
		cy.visit("/sellos");
		cy.getByTestId("home-setup-banner").click();
		cy.getByTestId("setup-resumed").should("be.visible");
		cy.getByTestId("setup-users").should("be.visible");
		["profile", "branding", "stages"].forEach((key) =>
			cy.getByTestId(`setup-step-${key}`).should("have.attr", "data-done", "true")
		);
		cy.getByTestId("setup-step-stages").click();
		cy.getByTestId("setup-stage-name").first().should("have.value", "Enquiry");

		// Step 4: the first users and roles.
		cy.getByTestId("setup-step-users").click();
		cy.getByTestId("setup-user-first-name").type("Wizard");
		cy.getByTestId("setup-user-email").type(AGENT_EMAIL);
		cy.getByTestId("setup-user-role").select("Agent");
		cy.getByTestId("setup-add-user").click();
		cy.getByTestId("setup-user-row")
			.should("contain.text", AGENT_EMAIL)
			.and("contain.text", "Agent");
		cy.getByTestId("setup-error").should("not.exist");

		cy.getByTestId("setup-finish").click();
		cy.getByTestId("setup-done").should("be.visible");
		// The branding shows at once, with no reload.
		cy.getByTestId("brand-name").should("contain.text", "Wizard Spec Realty");
		cy.getByTestId("brand-logo").should("be.visible");

		// What the server holds.
		cy.bench("sellos.tests.ui_fixtures.setup_wizard_result").then((result) => {
			expect(result.company_name).to.eq("Wizard Spec Realty");
			expect(result.city).to.eq("Pune");
			expect(result.brand_color).to.eq("#123abc");
			expect(result.logo).to.match(/^\/files\/company-logo.*\.png$/);
			expect(result.complete).to.eq(true);
			expect(result.stages[0]).to.eq("Enquiry");
			expect(result.stages).to.include("Booked");
			expect(result.users[AGENT_EMAIL]).to.include("SellOS Agent");
		});

		// After a reload the branding is still there and the banner has gone.
		cy.visit("/sellos");
		cy.getByTestId("home-setup-banner").should("not.exist");
		cy.getByTestId("brand-name").should("contain.text", "Wizard Spec Realty");
		cy.getByTestId("brand-logo")
			.should("have.attr", "src")
			.and("match", /^\/files\/company-logo/);
		cy.document().then((doc) => {
			const color = getComputedStyle(doc.documentElement)
				.getPropertyValue("--sos-brand")
				.trim();
			expect(color).to.eq("#123abc");
		});
	});

	it("refuses a pipeline with no Won stage and says why", () => {
		cy.bench("sellos.tests.ui_fixtures.reset_setup_wizard");
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/setup");
		cy.getByTestId("setup-step-stages").click();
		cy.getByTestId("setup-stage-type").each(($el) => {
			if ($el.val() === "Won") cy.wrap($el).select("Open");
		});
		cy.expectApiStatus("sellos.config.setup_wizard.save_stages", 417);
		cy.getByTestId("setup-save-stages").click();
		cy.getByTestId("setup-error").should("contain.text", "Won");
	});

	it("keeps the wizard from an agent", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/company/setup");
		cy.getByTestId("no-access").should("be.visible");
		cy.getByTestId("setup-page").should("not.exist");
	});
});
