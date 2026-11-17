// SOS-P2-01: a Company Admin enters the Plivo India account once. The keys are saved encrypted and
// are never shown again, the Test connection button reports success or the error (against the fake
// provider, never the real one), and no other role can open the screen. Real screen, real server.
context("SOS-P2-01: telephony settings", () => {
	const GOOD_ID = "FAKEOK-SPEC-0042";
	const GOOD_TOKEN = "spec-token-91d3c7a5e2";
	const BAD_ID = "WRONG-SPEC-0042";
	const secrets = [GOOD_ID, GOOD_TOKEN, BAD_ID];
	let numbers;

	// The keys are committed to the site, so remove them and the fake provider (SOS-SETUP-24).
	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_telephony_settings");
		cy.bench("sellos.tests.ui_fixtures.use_fake_telephony_provider");
		cy.bench("sellos.tests.ui_fixtures.telephony_landline").then((value) => {
			numbers = value;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_telephony_settings");
	});

	const expectNoSecrets = (text) => {
		secrets.forEach((secret) => expect(text, `no ${secret}`).not.to.contain(secret));
	};

	it("saves the account, never shows the keys again, and tests the connection", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.telephony.settings.*").as("telephony");
		cy.visit("/sellos/company/telephony");
		cy.wait("@telephony");
		cy.getByTestId("telephony-status")
			.should("contain.text", "Auth ID: not set")
			.and("contain.text", "Auth token: not set");

		cy.getByTestId("telephony-test").click();
		cy.getByTestId("telephony-test-error").should("contain.text", "Save the auth ID");

		cy.getByTestId("telephony-auth-id").type(GOOD_ID);
		cy.getByTestId("telephony-auth-token").type(GOOD_TOKEN);
		cy.getByTestId("telephony-number").type(numbers.number);
		cy.getByTestId("telephony-save").click();
		cy.getByTestId("telephony-saved").should("be.visible");
		cy.getByTestId("telephony-error").should("not.exist");
		cy.getByTestId("telephony-status")
			.should("contain.text", "Auth ID: saved")
			.and("contain.text", "Auth token: saved");
		cy.getByTestId("telephony-auth-id").should("have.value", "");
		cy.getByTestId("telephony-auth-token").should("have.value", "");
		cy.getByTestId("telephony-number").should("have.value", numbers.stored);
		cy.get("body")
			.invoke("text")
			.then((text) => expectNoSecrets(text));

		cy.getByTestId("telephony-test").click();
		cy.getByTestId("telephony-test-ok").should("contain.text", "Connected");

		// A fresh load shows no key either.
		cy.reload();
		cy.getByTestId("telephony-status").should("contain.text", "Auth ID: saved");
		cy.getByTestId("telephony-auth-id").should("have.value", "");
		cy.get("body")
			.invoke("text")
			.then((text) => expectNoSecrets(text));
		cy.get("@telephony.all").then((calls) => {
			expect(calls.length).to.be.greaterThan(2);
			calls.forEach((call) => {
				expectNoSecrets(JSON.stringify(call.response?.body || {}));
			});
		});
	});

	it("shows the provider's error when it refuses the keys", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/telephony");
		cy.getByTestId("telephony-auth-id").type(BAD_ID);
		cy.getByTestId("telephony-save").click();
		cy.getByTestId("telephony-saved").should("be.visible");
		cy.getByTestId("telephony-test").click();
		cy.getByTestId("telephony-test-error")
			.should("contain.text", "refused")
			.and("not.contain.text", BAD_ID);
		cy.getByTestId("telephony-test-ok").should("not.exist");
	});

	it("refuses a number that is not a 022 number", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/telephony");
		cy.expectApiStatus("save_telephony_settings", 417);
		cy.getByTestId("telephony-number").clear().type("012345");
		cy.getByTestId("telephony-save").click();
		cy.getByTestId("telephony-error").should("contain.text", "022");
		cy.getByTestId("telephony-saved").should("not.exist");
	});

	it("is closed to every other role", () => {
		["agent", "client", "channel_partner", "platform_admin"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/company/telephony");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("telephony-page").should("not.exist");
			cy.getByTestId("nav-telephony").should("not.exist");
			cy.apiAs("sellos.telephony.settings.get_telephony_settings").then((res) => {
				expect(res.status, `${role} is refused by the API`).to.be.oneOf([401, 403]);
			});
		});
	});
});
