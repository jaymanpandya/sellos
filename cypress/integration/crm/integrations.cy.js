// SOS-INT-1: the Integrations screen. A Company Admin saves a key, sees only "Saved, ending xxxx" after a reload, and
// gets Connected or Failed with a plain reason from Test connection. The fake keys (FAKEOK, FAKEBAD) are answered by the
// test site's fake provider: no real provider is called. No other role opens the screen.
context("SOS-INT-1: the Integrations screen in Company settings", () => {
	const reset = () => cy.bench("sellos.tests.ui_fixtures.reset_integrations");
	const GOOD_KEY = "FAKEOK-legiscore-spec-1357";
	const BAD_KEY = "FAKEBAD-legiscore-spec-2468";
	before(reset);
	after(reset);

	beforeEach(() => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.config.integrations.list_integrations*").as("load");
		cy.intercept("POST", "**/sellos.config.integrations.save_integration*").as("save");
		cy.intercept("POST", "**/sellos.config.integrations.check_integration*").as("check");
	});

	it("lists every provider card, the webhook address for Meta and the link to Telephony", () => {
		cy.visit("/sellos/company/integrations");
		cy.wait("@load");
		["whatsapp", "meta_lead_ads", "email", "docuseal", "legiscore"].forEach((provider) =>
			cy.getByTestId(`integration-${provider}`).should("be.visible")
		);
		cy.getByTestId("integration-whatsapp-webhook").should(
			"contain",
			"sellos.whatsapp.webhook.whatsapp_event"
		);
		cy.getByTestId("integration-voice-link").click();
		cy.location("pathname").should("eq", "/sellos/company/telephony");
	});

	it("saves a key, shows it masked after a reload, replaces it and shows a failed test", () => {
		cy.visit("/sellos/company/integrations");
		cy.wait("@load");
		cy.getByTestId("integration-legiscore-status").should("contain", "Not set");
		cy.getByTestId("integration-legiscore-api_key").type(GOOD_KEY);
		cy.getByTestId("integration-legiscore-save").click();
		cy.wait("@save").its("response.statusCode").should("eq", 200);
		cy.get("@save")
			.its("response.body")
			.then((body) => expect(JSON.stringify(body)).to.not.contain(GOOD_KEY));
		cy.getByTestId("integration-legiscore-status").should("contain", "Not tested");

		cy.reload();
		cy.wait("@load");
		cy.getByTestId("integration-legiscore-api_key").should("have.value", "");
		cy.getByTestId("integration-legiscore")
			.should("contain", "Saved, ending 1357")
			.and("not.contain", GOOD_KEY);

		cy.getByTestId("integration-legiscore-test").click();
		cy.wait("@check").its("response.statusCode").should("eq", 200);
		cy.getByTestId("integration-legiscore-status").should("contain", "Connected");

		cy.getByTestId("integration-legiscore-api_key").type(BAD_KEY);
		cy.getByTestId("integration-legiscore-test").click();
		cy.wait("@check");
		cy.getByTestId("integration-legiscore-status").should("contain", "Failed");
		cy.getByTestId("integration-legiscore-reason").should("contain", "refused these keys");
		cy.getByTestId("integration-legiscore").should("contain", "Saved, ending 2468");
		cy.get("@check")
			.its("response.body")
			.then((body) => expect(JSON.stringify(body)).to.not.contain(BAD_KEY));
	});

	it("is closed to every other role", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/company/integrations");
		cy.getByTestId("integrations-page").should("not.exist");
		cy.getByTestId("integration-legiscore").should("not.exist");
	});
});
