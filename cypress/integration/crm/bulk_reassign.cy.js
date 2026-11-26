// SOS-P1-19: a Company Admin moves a filtered set of leads to another agent in one go, and their open
// follow ups and future site visits move with them. The leads, follow ups and visits are made through the
// production API by seed_bulk_reassign, and the result is read back from the server, not from the screen.
context("SOS-P1-19: bulk reassignment", () => {
	let seed;

	// Each test makes its own data, so none depends on another test having run (SOS-SETUP-24).
	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_assignment");
		cy.bench("sellos.tests.ui_fixtures.seed_bulk_reassign").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_assignment");
	});

	const openLeads = () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.crm.api.list_leads*").as("listLeads");
		cy.visit(`/sellos/crm/leads?assigned_to=${encodeURIComponent(seed.holder)}`);
		cy.wait("@listLeads");
		cy.getByTestId("lead-row").should("have.length", 3);
	};
	const select = (index) => cy.getByTestId("lead-select").eq(index).check();

	it("moves the selected leads with their follow ups and visits to the chosen agent", () => {
		openLeads();
		select(0);
		select(1);
		cy.getByTestId("bulk-count").should("contain", "2 selected");
		cy.getByTestId("bulk-agent").select(seed.to_name);
		cy.intercept("POST", "**/sellos.crm.api.bulk_reassign_leads*").as("bulk");
		cy.getByTestId("bulk-reassign").click();
		cy.wait("@bulk").its("response.statusCode").should("eq", 200);
		cy.getByTestId("bulk-result")
			.should("contain", "2 leads reassigned")
			.and("contain", "2 follow ups")
			.and("contain", "2 site visits");
		// The list is filtered by the old agent, so only the lead that stayed is left.
		cy.getByTestId("lead-row").should("have.length", 1);
		cy.getByTestId("lead-row")
			.invoke("text")
			.then((text) => {
				const stayed = seed.leads.find((name) => text.includes(name));
				expect(stayed, "the lead still shown").to.be.a("string");
				cy.bench("sellos.tests.ui_fixtures.assignment_state", { names: seed.leads }).then(
					(state) => {
						const moved = Object.values(state.leads).filter(
							(agent) => agent === seed.taker
						);
						expect(moved).to.have.length(2);
						expect(state.leads[stayed]).to.eq(seed.holder);
						expect(state["Lead Task"][seed.taker]).to.eq(2);
						expect(state["Lead Task"][seed.holder]).to.eq(1);
						expect(state["Site Visit"][seed.taker]).to.eq(2);
						expect(state["Site Visit"][seed.holder]).to.eq(1);
						expect(state.log).to.have.length(2);
					}
				);
			});
	});

	it("selects every lead shown, and an agent cannot reassign", () => {
		openLeads();
		cy.getByTestId("bulk-select-all").check();
		cy.getByTestId("bulk-count").should("contain", "3 selected");
		cy.getByTestId("bulk-reassign").should("be.enabled");
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/leads");
		cy.getByTestId("leads-page").should("be.visible");
		cy.getByTestId("bulk").should("not.exist");
		cy.getByTestId("lead-select").should("not.exist");
		cy.apiAs("sellos.crm.api.bulk_reassign_leads", {
			assigned_to: seed.taker,
			leads: "[]",
		})
			.its("status")
			.should("eq", 403);
	});

	it("lets the Company Admin add and remove an assignment rule", () => {
		cy.signInFresh("company_admin");
		cy.intercept("POST", "**/sellos.crm.api.list_assignment_rules*").as("rules");
		cy.visit("/sellos/company/assignment");
		cy.wait("@rules");
		cy.getByTestId("assignment-page").should("be.visible");
		// The rule form is a drawer, opened by Add rule.
		cy.getByTestId("assignment-new").click();
		cy.getByTestId("assignment-name").type("Gate Assign Rule");
		cy.getByTestId("assignment-type").select("Locality");
		cy.getByTestId("assignment-locality").type("Gate Assign Locality");
		cy.getByTestId("assignment-team").select(seed.team);
		cy.getByTestId("assignment-add").click();
		const rule = () =>
			cy.get('[data-testid="sellos-assignment-rule"][data-name="Gate Assign Rule"]');
		rule().should("contain", "Locality Gate Assign Locality").and("contain", seed.team);
		rule().find('[data-testid="sellos-row-menu-button"]').click();
		cy.contains('[role="menuitem"]', "Remove").click();
		rule().should("not.exist");
	});
});
