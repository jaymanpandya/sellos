// SOS-P7-02: a partner of an approved firm registers a buyer in the web app, and a Company Admin approves it.
// A buyer the company already has is answered with one sentence. The firms, buyers and leads the spec makes
// are removed afterwards. The numbers come from the backend fixture, never from the spec.
context("SOS-P7-02: register a lead as a channel partner", () => {
	const NOT_ACCEPTED = "Not accepted: this buyer is already registered with the company.";
	const newName = "Gate Registration New";
	let numbers;
	let firm;

	const cleanUp = () => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_partner_registrations");
		cy.bench("sellos.tests.ui_fixtures.remove_gate_partner_firms");
	};
	const fillBuyer = (name, phone) => {
		cy.getByTestId("partner-register-name").clear().type(name);
		cy.getByTestId("partner-register-phone").clear().type(phone);
	};
	const submit = () => {
		cy.intercept("POST", "**/sellos.access.partner_registrations.register_buyer*").as(
			"register"
		);
		cy.getByTestId("partner-register-submit").click();
		return cy.wait("@register");
	};
	const openRegister = () => {
		cy.signInFresh("channel_partner");
		cy.intercept(
			"POST",
			"**/sellos.access.partner_registrations.my_partner_registrations*"
		).as("mine");
		cy.visit("/sellos/partner/register");
		cy.wait("@mine");
		cy.getByTestId("partner-register-page").should("be.visible");
	};
	const openRegistrations = () => {
		cy.signInFresh("company_admin");
		cy.intercept(
			"POST",
			"**/sellos.access.partner_registrations.list_partner_registrations*"
		).as("list");
		cy.visit("/sellos/company/registrations");
		cy.wait("@list");
		cy.getByTestId("registrations-page").should("be.visible");
	};
	const row = (name) => cy.contains('[data-testid="sellos-registrations-row"]', name);

	beforeEach(() => {
		cleanUp();
		cy.bench("sellos.tests.ui_fixtures.seed_gate_partner_firm", { stage: "approved" }).then(
			(made) => {
				firm = made;
			}
		);
		cy.bench("sellos.tests.ui_fixtures.seed_gate_partner_buyer").then((made) => {
			numbers = made;
		});
	});
	after(() => {
		cleanUp();
		cy.bench("sellos.tests.ui_fixtures.remove_gate_users");
	});

	it("registers a new buyer: the consent wording is shown, the phone is masked and the registration waits", () => {
		openRegister();
		cy.getByTestId("partner-register-wording").should("contain", "agreed to be contacted");
		fillBuyer(newName, numbers.new_phone);
		cy.getByTestId("partner-register-project").type("Gate Tower");
		cy.get('textarea[data-testid="sellos-partner-register-note"]').type(
			"Wants a three bedroom flat"
		);
		cy.getByTestId("partner-register-agreed").check();
		submit().its("response.statusCode").should("eq", 200);
		cy.getByTestId("partner-register-notice").should("contain", "was registered");
		cy.contains('[data-testid="sellos-partner-register-row"]', newName)
			.should("have.attr", "data-status", "Registered")
			.and("not.contain", numbers.new_phone);
		cy.get("body").should("not.contain", numbers.new_phone);
		cy.bench("sellos.tests.ui_fixtures.gate_partner_registration_state", {
			buyer_name: newName,
		}).then((state) => {
			expect(state.status).to.eq("Registered");
			expect(state.lead_partner).to.eq(firm.name);
			expect(state.lead_source).to.eq("Channel partner");
			expect(state.consent_status).to.eq("Consented");
			expect(state.log).to.have.length(1);
		});
	});

	it("tells the partner only one sentence about a buyer the company already has, and makes no lead", () => {
		cy.bench("sellos.tests.ui_fixtures.count_gate_partner_leads").then((before) => {
			openRegister();
			fillBuyer("Gate Registration Other", numbers.existing_phone);
			submit().its("response.statusCode").should("eq", 200);
			cy.getByTestId("partner-register-error").should("have.text", NOT_ACCEPTED);
			cy.get("body").should("not.contain", numbers.existing_name);
			cy.get('[data-testid="sellos-partner-register-row"]').should("have.length", 0);
			cy.bench("sellos.tests.ui_fixtures.count_gate_partner_leads").then((after) => {
				expect(after).to.deep.eq(before);
			});
		});
	});

	it("lets a Company Admin approve the registration, which is then protected, and reject another with a reason", () => {
		openRegister();
		fillBuyer(newName, numbers.new_phone);
		submit();
		cy.getByTestId("partner-register-notice").should("be.visible");

		openRegistrations();
		row(newName)
			.should("have.attr", "data-status", "Registered")
			.within(() => {
				cy.getByTestId("registrations-phone").should("be.visible");
				cy.getByTestId("registrations-consent").should("contain", "Unknown");
			});
		// A rejection needs a reason.
		cy.expectApiStatus("sellos.access.partner_registrations.reject_partner_registration", 417);
		cy.intercept(
			"POST",
			"**/sellos.access.partner_registrations.reject_partner_registration*"
		).as("reject");
		row(newName).find('[data-testid="sellos-registrations-reject"]').click();
		cy.wait("@reject").its("response.statusCode").should("eq", 417);
		cy.getByTestId("registrations-error").should("contain", "reason");
		row(newName).should("have.attr", "data-status", "Registered");

		cy.intercept(
			"POST",
			"**/sellos.access.partner_registrations.approve_partner_registration*"
		).as("approve");
		row(newName).find('[data-testid="sellos-registrations-approve"]').click();
		cy.wait("@approve").its("response.statusCode").should("eq", 200);
		row(newName)
			.should("have.attr", "data-status", "Approved")
			.and("contain", "Protected until");
		cy.bench("sellos.tests.ui_fixtures.gate_partner_registration_state", {
			buyer_name: newName,
		}).then((state) => {
			expect(state.status).to.eq("Approved");
			expect(state.protected_until).to.not.eq("");
			expect(state.log.map((l) => l[1])).to.deep.eq(["Registered", "Approved"]);
			expect(state.log[1][2]).to.contain("company_admin");
		});

		// The partner follows it.
		openRegister();
		cy.contains('[data-testid="sellos-partner-register-row"]', newName)
			.should("have.attr", "data-status", "Approved")
			.and("contain", "Protected in your firm's name");
	});

	it("shows a rejection and its reason to the partner", () => {
		openRegister();
		fillBuyer(newName, numbers.new_phone);
		submit();
		openRegistrations();
		row(newName)
			.find('[data-testid="sellos-registrations-reason-input"]')
			.type("Not a genuine buyer");
		cy.intercept(
			"POST",
			"**/sellos.access.partner_registrations.reject_partner_registration*"
		).as("reject");
		row(newName).find('[data-testid="sellos-registrations-reject"]').click();
		cy.wait("@reject").its("response.statusCode").should("eq", 200);
		row(newName).should("have.attr", "data-status", "Rejected");
		openRegister();
		cy.contains('[data-testid="sellos-partner-register-row"]', newName)
			.should("have.attr", "data-status", "Rejected")
			.and("contain", "Not a genuine buyer");
	});

	it("keeps the Company Admin's page from the agent and the partner", () => {
		["agent", "channel_partner"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/company/registrations");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("registrations-page").should("not.exist");
		});
	});
});
