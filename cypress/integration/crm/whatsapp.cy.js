// SOS-P6-11: the WhatsApp channel, against the real server and the fake provider. ui_fixtures.seed_whatsapp
// turns the fake provider on, saves the company's number with fake keys and one approved template, and makes
// a lead of the test agent whose customer has just written. The customer's later messages (an opt in, a
// stop request) are signed webhook bodies from ui_fixtures.whatsapp_signed_body, posted to the real webhook
// as the provider would. remove_whatsapp removes it all afterwards. No message leaves the machine.
context("SOS-P6-11: WhatsApp", () => {
	const WEBHOOK = "/api/method/sellos.whatsapp.webhook.whatsapp_event";
	const SECRET_TOKEN = "FAKEOK-SPEC-WHATSAPP-TOKEN";
	const SECRET_SIGNING = "spec-whatsapp-signing-secret-5d2";
	let seed;

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_whatsapp").then((made) => {
			seed = made;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_whatsapp");
	});

	// The provider posts a signed body. The page is signed in, so the post carries its CSRF token.
	const customerWrites = (text, id) => {
		cy.bench("sellos.tests.ui_fixtures.whatsapp_signed_body", { text, message_id: id }).then(
			({ body, signature }) => {
				cy.window().then((win) => {
					cy.request({
						url: WEBHOOK,
						method: "POST",
						body,
						headers: {
							"Content-Type": "application/json",
							"X-Hub-Signature-256": signature,
							"X-Frappe-CSRF-Token": win.csrf_token || win.frappe?.csrf_token,
						},
					})
						.its("body.message")
						.should("eq", "ok");
				});
			}
		);
	};
	const openThread = () => {
		cy.visit("/sellos/crm/whatsapp");
		cy.getByTestId("whatsapp-conversation")
			.filter(`[data-lead="${seed.lead}"]`)
			.should("be.visible")
			.within(() => {
				// SOS-LOOP: the lead's name as plain text, the phone under it masked, the state as a pill.
				cy.getByTestId("whatsapp-row-name").should("not.be.empty");
				cy.contains("***");
			})
			.click();
		cy.getByTestId("whatsapp-thread").should("be.visible");
	};

	it("takes a customer's message, replies with the consent warning, and never blocks", () => {
		cy.signInFresh("agent");
		openThread();
		// Decision 7: the page says a WhatsApp STOP stops what is sent unprompted, never "never stops a message".
		cy.contains("After a WhatsApp STOP nothing is sent unprompted").should("be.visible");
		cy.contains("never stops a message").should("not.exist");
		cy.getByTestId("whatsapp-message")
			.first()
			.should("have.attr", "data-direction", "Inbound")
			.and("contain.text", "Is a 3 BHK available?");
		cy.getByTestId("whatsapp-consent").should("have.attr", "data-level", "amber");
		cy.getByTestId("whatsapp-warning").should("be.visible");

		// Reply with free text: the customer wrote just now, so the 24 hour window is open.
		cy.get('textarea[data-testid="sellos-whatsapp-text"]').type(
			"Yes, we have one. Shall I send the brochure?"
		);
		cy.getByTestId("whatsapp-send").should("not.be.disabled").click();
		cy.getByTestId("whatsapp-result").should("contain.text", "Sent.");
		cy.getByTestId("whatsapp-message")
			.last()
			.should("have.attr", "data-direction", "Outbound")
			.and("contain.text", "Shall I send the brochure?");
		cy.getByTestId("whatsapp-message-consent")
			.last()
			.should("have.attr", "data-level", "amber")
			.and("contain.text", "Unknown");

		// An opt in is a Consent record whose evidence is a private file.
		customerWrites("START", "wamid-spec-optin");
		openThread();
		cy.getByTestId("whatsapp-consent").should("have.attr", "data-level", "none");
		cy.getByTestId("whatsapp-consent").should("contain.text", "Consented");
		cy.getByTestId("whatsapp-message")
			.filter('[data-intent="Opt in"]')
			.should("have.length", 1);
		cy.bench("sellos.tests.ui_fixtures.whatsapp_outcome", { lead: seed.lead }).then(
			(state) => {
				expect(state.consent_status).to.eq("Consented");
				expect(state.records).to.deep.eq([{ basis: "Consent", private: true }]);
			}
		);

		// A template can be sent at any time.
		cy.getByTestId("whatsapp-template").select(seed.template);
		cy.getByTestId("whatsapp-parameters").type("Meera, 4 pm");
		cy.getByTestId("whatsapp-send-template").click();
		cy.getByTestId("whatsapp-result").should("contain.text", "Sent.");
		cy.getByTestId("whatsapp-message")
			.last()
			.should("contain.text", "Hello Meera, your site visit is at 4 pm.");

		// A stop request is Opted out with a red warning, and the next message still goes.
		customerWrites("STOP", "wamid-spec-stop");
		openThread();
		cy.getByTestId("whatsapp-consent")
			.should("have.attr", "data-level", "red")
			.and("contain.text", "Opted out");
		cy.getByTestId("whatsapp-warning").should("have.class", "ui-text-error");
		cy.get('textarea[data-testid="sellos-whatsapp-text"]').type(
			"Understood. Your visit on Sunday stays booked."
		);
		cy.getByTestId("whatsapp-send").should("not.be.disabled").click();
		cy.getByTestId("whatsapp-result").should("contain.text", "Sent.");
		cy.getByTestId("whatsapp-message-consent")
			.last()
			.should("have.attr", "data-level", "red")
			.and("contain.text", "Opted out");
		cy.bench("sellos.tests.ui_fixtures.whatsapp_outcome", { lead: seed.lead }).then(
			(state) => {
				expect(state.consent_status).to.eq("Opted out");
				const sends = state.messages.filter((m) => m.direction === "Outbound");
				expect(sends).to.have.length(3);
				sends.forEach((m) => {
					expect(m.check.channel).to.eq("WhatsApp");
					expect(m.check.refused).to.eq(0);
					expect(m.check.enforcement).to.eq("Off");
				});
				expect(sends[2].check.consent_status).to.eq("Opted out");
			}
		);
	});

	it("hands the conversation to a human", () => {
		cy.signInFresh("agent");
		openThread();
		cy.getByTestId("whatsapp-note").type("Wants a call after 6 pm");
		cy.getByTestId("whatsapp-handoff").click();
		cy.getByTestId("whatsapp-state").should("contain.text", "With a human");
		cy.getByTestId("whatsapp-handoff-note")
			.should("contain.text", "Handed to")
			.and("contain.text", "Wants a call after 6 pm");
		cy.getByTestId("whatsapp-handoff").should("be.disabled");
		cy.bench("sellos.tests.ui_fixtures.whatsapp_outcome", { lead: seed.lead }).then(
			(state) => {
				expect(state.conversation.state).to.eq("With a human");
			}
		);
	});

	it("refuses a channel partner, and shows no phone number to an agent", () => {
		// The screen's route guard is covered by route_access.cy.js; here the server refuses the method.
		cy.signInFresh("channel_partner");
		cy.apiAs("sellos.whatsapp.conversations.list_whatsapp_conversations")
			.its("status")
			.should("eq", 403);
		cy.signInFresh("agent");
		openThread();
		// Read the visible page only: the page source carries a random CSRF token inside a script tag.
		cy.get("body").then(($body) => {
			const text = $body.clone().find("script").remove().end().text();
			expect(text).not.to.match(/\+91\s?\d{5}|\d{10}/);
		});
	});

	it("lets the Company Admin connect the number, never shows the keys again, and tests the connection", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.whatsapp.settings.*").as("whatsapp");
		cy.visit("/sellos/company/whatsapp");
		cy.wait("@whatsapp");
		cy.getByTestId("whatsapp-setup-token").type(SECRET_TOKEN);
		cy.getByTestId("whatsapp-setup-secret").type(SECRET_SIGNING);
		cy.getByTestId("whatsapp-setup-save").click();
		cy.getByTestId("whatsapp-setup-saved").should("be.visible");
		cy.getByTestId("whatsapp-setup-status")
			.should("contain.text", "Access token: saved")
			.and("contain.text", "Webhook signing secret: saved");
		cy.getByTestId("whatsapp-setup-token").should("have.value", "");
		cy.getByTestId("whatsapp-setup-test").click();
		cy.getByTestId("whatsapp-setup-test-ok").should("contain.text", "Connected");
		cy.get("body")
			.invoke("text")
			.then((text) => {
				expect(text).not.to.contain(SECRET_TOKEN);
				expect(text).not.to.contain(SECRET_SIGNING);
			});
		// The template form is a drawer, opened by Add template.
		cy.getByTestId("whatsapp-template-add").click();
		cy.getByTestId("whatsapp-template-name").type("gate_spec_template");
		cy.get('textarea[data-testid="sellos-whatsapp-template-body"]').type("Hello {{}1}}.");
		cy.getByTestId("whatsapp-template-save").click();
		cy.getByTestId("whatsapp-template-row")
			.filter('[data-name="gate_spec_template"]')
			.should("contain.text", "Approved");
		cy.get("@whatsapp.all").then((calls) => {
			calls.forEach((call) => {
				const text = JSON.stringify(call.response?.body || {});
				expect(text).not.to.contain(SECRET_TOKEN);
				expect(text).not.to.contain(SECRET_SIGNING);
			});
		});
	});

	it("does not offer WhatsApp setup to an agent", () => {
		cy.signInFresh("agent");
		cy.visit("/sellos/company/whatsapp");
		cy.getByTestId("whatsapp-setup-page").should("not.exist");
		cy.getByTestId("nav-whatsapp-setup").should("not.exist");
	});
});
