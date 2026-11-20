// SOS-P1-18: a Company Admin makes sales teams, and a Sales Manager sees their own team's leads and not
// another team's, with masked phone numbers. The teams and leads are made through the production API
// by the seed, and removed afterwards (a team left behind would put the test agent in two teams).
context("SOS-P1-18: sales teams and the Sales Manager", () => {
	let seed;
	const teamName = `Gate Team UI ${Date.now()}`;

	before(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_sales_teams");
		cy.bench("sellos.tests.ui_fixtures.seed_sales_teams").then((value) => {
			seed = value;
		});
	});
	after(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_sales_teams");
	});

	it("a manager sees their team's leads and not another team's", () => {
		cy.signInFresh("sales_manager");
		cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("listLeads");
		cy.visit("/sellos/crm/leads");
		cy.wait("@listLeads");
		cy.getByTestId("lead-row").contains(seed.own).should("be.visible");
		cy.getByTestId("lead-row").contains(seed.other).should("not.exist");
		cy.getByTestId("nav-leads").should("be.visible");
		cy.getByTestId("nav-team-report").should("be.visible");
		cy.getByTestId("nav-users").should("not.exist");
		cy.getByTestId("nav-teams").should("not.exist");
	});

	it("shows a manager the lead with a masked phone number, and lets them pick only their own agents", () => {
		cy.signInFresh("sales_manager");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("lead-row").contains(seed.own).click();
		cy.getByTestId("lead-page").should("be.visible");
		cy.getByTestId("lead-phone")
			.invoke("text")
			.then((text) => {
				expect(text.trim()).to.match(/^\*+\d{3}$/);
				seed.phone_forms.forEach((form) => expect(text).not.to.contain(form));
			});
		cy.getByTestId("reassign-select").should("be.visible");
		cy.optionTexts("reassign-select").should("include", seed.agent_name);
		cy.optionTexts("reassign-select")
			.should("not.include", seed.other_agent_name)
			.and("not.include", seed.spare_name);
		cy.getByTestId("merge").should("not.exist");
	});

	it("refuses a manager another team's lead", () => {
		cy.signInFresh("sales_manager");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("lead-row").contains(seed.own).should("be.visible");
		cy.apiAs("sellos.crm.api.list_leads").then((res) => {
			expect(res.status).to.eq(200);
			const text = JSON.stringify(res.body);
			expect(text).to.contain(seed.own);
			expect(text).not.to.contain(seed.other);
		});
		cy.apiAs("sellos.access.teams.save_team", { values: "{}" })
			.its("status")
			.should("eq", 403);
	});

	it("shows a manager the report of their own team", () => {
		cy.signInFresh("sales_manager");
		cy.visit("/sellos/reports/team");
		cy.getByTestId("teamreport-total").should("contain", "Leads: 1");
		cy.getByTestId("teamreport-teams").should("contain", seed.team_a);
		cy.getByTestId("teamreport-teams").should("not.contain", seed.team_b);
		cy.getByTestId("teamreport-agent")
			.should("have.length", 1)
			.and("contain", seed.agent_name);
	});

	it("lets the Company Admin make a team, and keeps an agent in one team only", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.access.teams.list_teams*").as("listTeams");
		cy.visit("/sellos/company/teams");
		cy.wait("@listTeams");
		cy.getByTestId("teams-team").contains(seed.team_a).should("be.visible");
		cy.getByTestId("teams-team").contains(seed.team_b).should("be.visible");
		cy.get(`[data-testid="sellos-teams-agent"]`).filter(":disabled").should("have.length", 2);

		cy.getByTestId("teams-name").type(teamName);
		cy.getByTestId("teams-manager-select").select(seed.other_manager_name);
		cy.getByTestId("teams-agents")
			.contains("label", seed.spare_name)
			.parent()
			.find("input")
			.check();
		cy.getByTestId("teams-add").click();
		cy.wait("@listTeams");
		cy.getByTestId("teams-error").should("not.exist");
		cy.getByTestId("teams-team")
			.contains(teamName)
			.closest("[data-testid='sellos-teams-team']")
			.within(() => {
				cy.getByTestId("teams-manager").should("contain", seed.other_manager_name);
				cy.getByTestId("teams-members").should("contain", seed.spare_name);
			});
		cy.get(`[data-testid="sellos-teams-agent"]`).filter(":disabled").should("have.length", 3);
	});

	it("keeps the teams screen and the report from agents, and the teams screen from a manager", () => {
		cy.signInFresh("sales_manager");
		cy.visit("/sellos/company/teams");
		cy.getByTestId("no-access").should("be.visible");
		cy.getByTestId("teams-page").should("not.exist");
		cy.signInFresh("agent");
		cy.visit("/sellos/reports/team");
		cy.getByTestId("no-access").should("be.visible");
		cy.getByTestId("teamreport-page").should("not.exist");
	});
});
