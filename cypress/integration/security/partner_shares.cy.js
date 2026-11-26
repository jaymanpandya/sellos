// SOS-P7-03: a Company Admin shares a project with a partner firm and withdraws it, in the web app against the
// real server, and the partner sees only what is shared. The projects, firm and brochure the spec makes are
// removed afterwards.
context("SOS-P7-03: share projects, units and collateral with channel partners", () => {
	let made;

	const row = (project) =>
		cy.get(`[data-testid="sellos-shares-row"][data-project="${project}"]`);
	// A row action is in the row menu (three dots), the only control in a row.
	const menu = (project, label) => {
		row(project).find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', label).click();
	};
	const openShares = () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.inventory.partner_shares.partner_share_options*").as(
			"options"
		);
		cy.visit("/sellos/company/shares");
		cy.wait("@options");
		cy.getByTestId("shares-page").should("be.visible");
	};
	const openShared = () => {
		cy.signInFresh("channel_partner");
		cy.intercept("POST", "**/sellos.inventory.partner_shares.my_shared_projects*").as("mine");
		cy.visit("/sellos/partner/shared");
		cy.wait("@mine");
		cy.getByTestId("partner-shared-page").should("be.visible");
	};

	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_partner_shares");
		cy.bench("sellos.tests.ui_fixtures.make_gate_partner_shares").then((result) => {
			made = result;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_partner_shares");
		cy.bench("sellos.tests.ui_fixtures.remove_gate_users");
	});

	it("shares a project with chosen units, its price list and a brochure, and the partner sees only that", () => {
		const [shared, other] = made.projects;
		const [firstUnit, secondUnit] = made.units[shared];
		openShares();
		cy.getByTestId("shares-new").click();
		cy.getByTestId("shares-project").select(shared);
		cy.getByTestId("shares-all-units").uncheck();
		cy.getByTestId(`shares-unit-${firstUnit}`).check();
		cy.getByTestId("shares-price-list").check();
		cy.getByTestId(`shares-brochure-${made.brochure}`).check();
		cy.getByTestId(`shares-firm-${made.firm}`).check();
		cy.intercept("POST", "**/sellos.inventory.partner_shares.share_project*").as("share");
		cy.getByTestId("shares-submit").click();
		cy.wait("@share").its("response.statusCode").should("eq", 200);
		cy.getByTestId("shares-notice").should("contain", "was shared");
		row(shared).should("have.attr", "data-status", "Active");
		menu(shared, "Log");
		cy.getByTestId("shares-log-row").should("have.length", 1);
		cy.getByTestId("shares-log-close").click();

		openShared();
		cy.getByTestId("partner-shared-row").should("have.length", 1);
		cy.get(`[data-testid="sellos-partner-shared-row"][data-name="${shared}"]`).should("exist");
		cy.get(`[data-testid="sellos-partner-shared-row"][data-name="${other}"]`).should(
			"not.exist"
		);
		cy.getByTestId("partner-shared-row")
			.find('[data-testid="sellos-row-menu-button"]')
			.click();
		cy.contains('[role="menuitem"]', "Open").click();
		cy.getByTestId("partner-shared-unit").should("have.length", 1);
		cy.getByTestId("partner-shared-price").should("contain", "12000");
		cy.getByTestId("partner-shared-brochure").should("have.length", 1);
		cy.get("body").should("not.contain", secondUnit);
	});

	it("withdraws the share and it stops showing to the partner at once", () => {
		const [shared] = made.projects;
		openShares();
		cy.getByTestId("shares-new").click();
		cy.getByTestId("shares-project").select(shared);
		cy.getByTestId(`shares-firm-${made.firm}`).check();
		cy.intercept("POST", "**/sellos.inventory.partner_shares.share_project*").as("share");
		cy.getByTestId("shares-submit").click();
		cy.wait("@share");
		// The page reads the shares back after saving: wait for that read before switching user.
		row(shared).should("have.attr", "data-status", "Active");
		openShared();
		cy.getByTestId("partner-shared-row").should("have.length", 1);

		openShares();
		cy.intercept("POST", "**/sellos.inventory.partner_shares.withdraw_partner_share*").as(
			"withdraw"
		);
		menu(shared, "Withdraw");
		cy.getByTestId("shares-reason").type("Sold out");
		cy.getByTestId("shares-withdraw").click();
		cy.wait("@withdraw").its("response.statusCode").should("eq", 200);
		row(shared).should("have.attr", "data-status", "Withdrawn");
		menu(shared, "Log");
		cy.getByTestId("shares-log-row").should("have.length", 2);
		cy.getByTestId("shares-log-close").click();
		cy.bench("sellos.tests.ui_fixtures.gate_partner_shares_state", { project: shared }).then(
			(state) => {
				expect(state[0][0]).to.eq("Withdrawn");
				expect(state[0][1]).to.deep.eq(["Shared", "Withdrawn"]);
			}
		);

		openShared();
		cy.getByTestId("partner-shared-row").should("not.exist");
		cy.contains("Nothing is shared with your firm yet").should("be.visible");
	});

	it("keeps the sharing page from every other role", () => {
		["agent", "channel_partner"].forEach((role) => {
			cy.signInFresh(role);
			cy.visit("/sellos/company/shares");
			cy.getByTestId("no-access").should("be.visible");
			cy.getByTestId("shares-page").should("not.exist");
		});
	});
});
