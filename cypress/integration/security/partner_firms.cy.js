// SOS-P7-01: a Company Admin invites a channel partner firm, its contact person completes it, and the
// admin approves, suspends and reinstates it, in the web app against the real server. A partner whose firm
// is not Approved is sent to a page that says so. The firms and logins the spec makes are removed afterwards.
// No mail is sent: this site has no outgoing email account (real mail is SOS-P0-13).
context("SOS-P7-01: onboard and approve channel partners", () => {
	const tag = Date.now();
	const invitedEmail = `gate_invited_${tag}p@example.com`;
	const firmName = `Gate Firm Alpha ${tag}`;
	let gate; // the firm of the gate channel partner, made by the backend fixture

	const row = (name) => cy.get(`[data-testid="sellos-partners-row"][data-name="${name}"]`);
	// A row action is in the row menu (three dots), the only control in a row.
	const menu = (name, label) => {
		row(name).find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', label).click();
	};
	const openPartners = () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.access.partner_firms.list_partner_firms*").as("list");
		cy.visit("/sellos/company/partners");
		cy.wait("@list");
		cy.getByTestId("partners-page").should("be.visible");
	};

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_partner_firms");
		cy.bench("sellos.tests.ui_fixtures.seed_gate_partner_firm", { stage: "pending" }).then(
			(made) => {
				gate = made;
			}
		);
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_partner_firms");
		cy.bench("sellos.tests.ui_fixtures.remove_gate_users");
	});

	it("invites a firm by email: it is Invited with a partner code, and the invitation is logged", () => {
		openPartners();
		cy.intercept("POST", "**/sellos.access.partner_firms.invite_partner_firm*").as("invite");
		cy.getByTestId("partners-new").click();
		cy.getByTestId("partners-firm").type(firmName);
		cy.getByTestId("partners-contact").type("Gate Contact");
		cy.getByTestId("partners-email").type(invitedEmail);
		cy.getByTestId("partners-invite").click();
		cy.wait("@invite").its("response.statusCode").should("eq", 200);
		cy.getByTestId("partners-notice").should("contain", "was invited");
		cy.contains('[data-testid="sellos-partners-row"]', firmName)
			.should("have.attr", "data-status", "Invited")
			.within(() => {
				cy.getByTestId("partners-code")
					.invoke("text")
					.should("match", /CP-\d{5}/);
				cy.getByTestId("partners-no-agreement").should("be.visible");
				cy.get('[data-testid="sellos-row-menu-button"]').click();
			});
		// An Invited firm has nothing to approve yet; its status log is in a drawer.
		cy.contains('[role="menuitem"]', "Approve").should("not.exist");
		cy.contains('[role="menuitem"]', "Agreement and status log").click();
		cy.getByTestId("partners-log-row").should("have.length", 1);
		cy.getByTestId("partners-history-close").click();
		// It is saved: a fresh load shows it.
		cy.reload();
		cy.contains('[data-testid="sellos-partners-row"]', firmName).should("be.visible");
	});

	it("shows a firm with its PAN and agreement to the Company Admin and approves it", () => {
		cy.bench("sellos.tests.ui_fixtures.gate_partner_firm_state", { name: gate.name }).then(
			(state) => {
				openPartners();
				row(gate.name)
					.should("have.attr", "data-status", "Pending approval")
					.within(() => {
						cy.getByTestId("partners-pan").should("contain", state.pan);
						cy.getByTestId("partners-has-agreement").should("be.visible");
						cy.getByTestId("partners-phone").should("be.visible");
					});
				menu(gate.name, "Agreement and status log");
				cy.getByTestId("partners-agreement")
					.should("have.attr", "href")
					.and("include", "/private/files/");
				cy.getByTestId("partners-history-close").click();
				cy.intercept("POST", "**/sellos.access.partner_firms.approve_partner_firm*").as(
					"approve"
				);
				menu(gate.name, "Approve");
				cy.wait("@approve").its("response.statusCode").should("eq", 200);
				row(gate.name).should("have.attr", "data-status", "Approved");
			}
		);
		cy.bench("sellos.tests.ui_fixtures.gate_partner_firm_state", { name: gate.name }).then(
			(state) => {
				expect(state.status).to.eq("Approved");
				const last = state.log[state.log.length - 1];
				expect(last.slice(0, 2)).to.deep.eq(["Pending approval", "Approved"]);
				expect(last[2]).to.contain("company_admin"); // who approved
			}
		);
	});

	it("needs a reason to suspend, then suspends and reinstates the firm", () => {
		openPartners();
		cy.expectApiStatus("sellos.access.partner_firms.suspend_partner_firm", 417);
		cy.intercept("POST", "**/sellos.access.partner_firms.suspend_partner_firm*").as("suspend");
		menu(gate.name, "Suspend");
		cy.getByTestId("partners-suspend").click();
		cy.wait("@suspend");
		cy.getByTestId("partners-error").should("contain", "reason");
		cy.getByTestId("partners-reason-input").type("Left the business");
		cy.getByTestId("partners-suspend").click();
		cy.wait("@suspend").its("response.statusCode").should("eq", 200);
		row(gate.name)
			.should("have.attr", "data-status", "Suspended")
			.within(() => {
				cy.getByTestId("partners-reason").should("contain", "Left the business");
			});
		cy.intercept("POST", "**/sellos.access.partner_firms.reinstate_partner_firm*").as(
			"reinstate"
		);
		menu(gate.name, "Reinstate");
		cy.wait("@reinstate").its("response.statusCode").should("eq", 200);
		row(gate.name).should("have.attr", "data-status", "Approved");
		menu(gate.name, "Agreement and status log");
		cy.getByTestId("partners-log-row").should("have.length", 4);
	});

	it("sends a partner whose firm is not Approved to a page that says so, and lets an approved one work", () => {
		cy.signInFresh("channel_partner");
		cy.visit("/sellos/partner/leads");
		cy.location("pathname").should("eq", "/sellos/partner/firm");
		cy.getByTestId("partner-firm-state").should(
			"have.attr",
			"data-status",
			"Pending approval"
		);
		cy.getByTestId("partner-firm-message").should("contain", "can not register leads");
		// The partner's own page never shows the PAN.
		cy.bench("sellos.tests.ui_fixtures.gate_partner_firm_state", { name: gate.name }).then(
			(state) => {
				cy.get("body").should("not.contain", state.pan);
			}
		);

		openPartners();
		cy.intercept("POST", "**/sellos.access.partner_firms.approve_partner_firm*").as("approve");
		menu(gate.name, "Approve");
		cy.wait("@approve").its("response.statusCode").should("eq", 200);

		cy.signInFresh("channel_partner");
		cy.visit("/sellos/partner/leads");
		cy.location("pathname").should("eq", "/sellos/partner/leads");

		// Suspended again: the page says so, with the reason.
		openPartners();
		menu(gate.name, "Suspend");
		cy.getByTestId("partners-reason-input").type("Agreement ended");
		cy.getByTestId("partners-suspend").click();
		row(gate.name).should("have.attr", "data-status", "Suspended");
		cy.signInFresh("channel_partner");
		cy.visit("/sellos/partner/leads");
		cy.location("pathname").should("eq", "/sellos/partner/firm");
		cy.getByTestId("partner-firm-message")
			.should("contain", "suspended")
			.and("contain", "Agreement ended");
	});

	it("keeps the page from every other role", () => {
		["agent", "channel_partner"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/company/partners");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("partners-page").should("not.exist");
		});
	});
});
