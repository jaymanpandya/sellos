// SOS-P1-17: a Company Admin invites an agent, sets the mobile number, and deactivates the agent, in
// the web app and against the real server. The invited users are removed afterwards (SOS-SETUP-24). No
// mail is sent: this site has no outgoing email account (real mail is SOS-P0-13), so the screen says the
// invitation was saved and not sent. The invitation link itself is tested in sellos/access/test_p1_17_users.py.
context("SOS-P1-17: manage users as a Company Admin", () => {
	const tag = Date.now();
	const agent = `gate_invited_${tag}@example.com`;
	const noMobile = `gate_invited_${tag}b@example.com`;
	let mobile;

	// The table scrolls inside its card (sticky header), so a row further down is scrolled into view first.
	const row = (email) =>
		cy.get(`[data-testid="sellos-users-row"][data-email="${email}"]`).scrollIntoView();

	// A row action is in the row menu (three dots), the only control in a row.
	const menu = (email, label) => {
		row(email).find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', label).click();
	};

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		cy.bench("sellos.tests.ui_fixtures.remove_gate_users");
		cy.bench("sellos.tests.ui_fixtures.fresh_phone", { seed: 1701 }).then((value) => {
			mobile = value.phone;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		cy.bench("sellos.tests.ui_fixtures.remove_gate_users");
	});

	const open = () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.access.users.list_users*").as("listUsers");
		cy.visit("/sellos/company/users");
		cy.wait("@listUsers");
		cy.getByTestId("users-page").should("be.visible");
	};

	it("offers the three roles and never the Platform Admin", () => {
		open();
		cy.getByTestId("users-add").click();
		cy.optionTexts("users-role").should("deep.eq", [
			"Company Admin",
			"Agent",
			"Channel Partner",
		]);
	});

	it("invites an agent with a mobile number and one without", () => {
		open();
		cy.intercept("POST", "**/sellos.access.users.invite_user*").as("invite");
		// The invite form is a drawer, opened by Add user.
		cy.getByTestId("users-add").click();
		cy.getByTestId("users-email").type(agent);
		cy.getByTestId("users-first-name").type("Gate Invited");
		cy.getByTestId("users-mobile").type(mobile);
		cy.getByTestId("users-invite").click();
		cy.wait("@invite").its("response.statusCode").should("eq", 200);
		cy.getByTestId("users-notice").should("contain", "was added").and("contain", "not sent");
		row(agent)
			.should("have.attr", "data-status", "Invited")
			.within(() => {
				cy.getByTestId("users-row-mobile").should("contain", mobile);
				cy.getByTestId("users-click-to-call").should("be.visible");
				cy.getByTestId("users-no-click-to-call").should("not.exist");
				cy.getByTestId("users-role-label").should("contain", "Agent");
			});

		cy.getByTestId("users-add").click();
		cy.getByTestId("users-email").type(noMobile);
		cy.getByTestId("users-first-name").type("Gate No Mobile");
		cy.getByTestId("users-invite").click();
		cy.wait("@invite").its("response.statusCode").should("eq", 200);
		row(noMobile).within(() => {
			cy.getByTestId("users-no-click-to-call").should("contain", "click to call");
		});
		// It is all saved: a fresh load shows both.
		cy.reload();
		row(agent).should("be.visible");
		row(noMobile).find('[data-testid="sellos-users-no-click-to-call"]').should("exist");
	});

	it("refuses a mobile number that is not +91 and ten digits, and saves a good one", () => {
		open();
		cy.expectApiStatus("sellos.access.users.save_user", 417);
		menu(noMobile, "Change mobile number");
		cy.getByTestId("users-mobile-input").clear().type("12345");
		cy.getByTestId("users-save-mobile").click();
		cy.getByTestId("users-error").should("contain", "+91 and ten digits");
		row(noMobile).find('[data-testid="sellos-users-no-click-to-call"]').should("exist");
		cy.bench("sellos.tests.ui_fixtures.fresh_phone", { seed: 1702 }).then(({ phone }) => {
			cy.getByTestId("users-mobile-input").clear().type(phone);
			cy.getByTestId("users-save-mobile").click();
			cy.getByTestId("users-notice").should("contain", "Saved the number");
			row(noMobile).within(() => {
				cy.getByTestId("users-no-click-to-call").should("not.exist");
				cy.getByTestId("users-row-mobile").should("contain", phone);
			});
		});
	});

	it("deactivates the agent after asking who takes the open leads and tasks: sign in stops", () => {
		cy.bench("sellos.tests.ui_fixtures.set_gate_user_password", { email: agent }).then(
			({ user, password }) => {
				cy.request({
					url: "/api/method/login",
					method: "POST",
					body: { usr: user, pwd: password },
				})
					.its("status")
					.should("eq", 200);
			}
		);
		cy.bench("sellos.tests.ui_fixtures.seed_user_work", { email: agent });
		open();
		row(agent).within(() => {
			cy.getByTestId("users-open-leads").should("contain", "1 open leads");
			cy.getByTestId("users-open-tasks").should("contain", "1 open tasks");
		});
		cy.intercept("POST", "**/sellos.access.users.deactivate_user*").as("deactivate");
		menu(agent, "Deactivate");
		// SOS-P1-19: an agent with open work is asked where it goes, and nothing is deactivated yet.
		cy.wait("@deactivate").its("response.statusCode").should("eq", 200);
		// The open work and the handover choice sit in a panel above the table, not inside the row.
		row(agent).should("have.attr", "data-status", "Active"); // the agent signed in above, and is still on
		cy.getByTestId("users-work-lead").should("have.length", 1);
		cy.getByTestId("users-work-task")
			.should("have.length", 1)
			.and("contain", "Gate users task");
		cy.getByTestId("users-handover-agent").select(noMobile);
		cy.getByTestId("users-handover-confirm").click();
		cy.wait("@deactivate").its("response.statusCode").should("eq", 200);
		row(agent).should("have.attr", "data-status", "Deactivated");
		// The menu now offers Turn back on and no Deactivate.
		row(agent).find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', "Turn back on").should("be.visible");
		cy.contains('[role="menuitem"]', "Deactivate").should("not.exist");
		cy.get("body").type("{esc}");
		cy.getByTestId("users-work").should("be.visible");
		cy.getByTestId("users-handed-over").should("contain", "1 leads");
		cy.getByTestId("users-work-lead").should("not.exist");
		cy.getByTestId("users-work-task").should("not.exist");
		row(noMobile).within(() => {
			cy.getByTestId("users-open-leads").should("contain", "1 open leads");
		});
		// Sign in stops at once, over the real login.
		cy.bench("sellos.tests.ui_fixtures.set_gate_user_password", { email: agent }).then(
			({ user, password }) => {
				cy.request({
					url: "/api/method/login",
					method: "POST",
					body: { usr: user, pwd: password },
					failOnStatusCode: false,
				})
					.its("status")
					.should("be.oneOf", [401, 403]);
			}
		);
	});

	it("does not let a Company Admin deactivate themselves", () => {
		open();
		cy.get('[data-testid="sellos-users-row"]').should("have.length.greaterThan", 1);
		cy.roleUser("company_admin").then(({ user }) => {
			row(user).find('[data-testid="sellos-row-menu-button"]').click();
			cy.contains('[role="menuitem"]', "Change mobile number").should("be.visible");
			cy.contains('[role="menuitem"]', "Deactivate").should("not.exist");
		});
	});

	it("is closed to every other role", () => {
		["agent", "client", "channel_partner", "platform_admin"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/company/users");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("users-page").should("not.exist");
			cy.getByTestId("nav-users").should("not.exist");
			cy.apiAs("sellos.access.users.list_users").then((res) => {
				expect(res.status, `${role} is refused by the API`).to.be.oneOf([401, 403]);
			});
		});
	});
});
