// A phone number is personal data. The screen masks it, but Frappe has other paths to the same
// record: the form loader, the document info, the generic client and resource calls, the report
// view and the search. BuildOS found a leak this way (the change history held the old and new
// values), so every path is tried as every role, for the current number and the one it replaced.
context("SOS-P1-06: phone numbers do not leak", () => {
	let seeded;

	before(() => {
		// The fixture makes a client that the test agent may read, gives it a phone number, and
		// changes the number once so a Version row holds both the old and the new value.
		cy.bench("sellos.tests.ui_fixtures.seed_client_with_phone", { seed: 21 }).then((s) => {
			seeded = s;
		});
	});

	const mustNotSeeTheNumber = ["agent", "channel_partner", "client", "platform_admin"];

	mustNotSeeTheNumber.forEach((role) => {
		it(`${role} gets the full number from no generic path, now or from history`, () => {
			cy.signInFresh(role);
			cy.genericReads("Client", seeded.client).then((results) => {
				results.forEach(({ path, text }) => {
					seeded.phone_forms.forEach((form) => {
						expect(text, `${path} as ${role}`).to.not.contain(form);
					});
				});
				if (role === "agent") {
					// Not vacuous: the agent can read this client, so the check above had something to find.
					expect(
						results.some(
							(r) => r.status === 200 && r.text.includes(seeded.client_name)
						),
						"the agent can read the client on at least one path"
					).to.eq(true);
				}
			});
		});
	});

	it("the agent's screen shows the number masked", () => {
		cy.signInFresh("agent");
		cy.visit(`/sellos/crm/leads/${seeded.lead}`);
		cy.getByTestId("lead-phone").should("be.visible");
		seeded.phone_forms.forEach((form) => {
			cy.getByTestId("lead-phone").should("not.contain", form);
		});
	});

	it("the company admin sees the full number", () => {
		cy.signInFresh("company_admin");
		cy.visit(`/sellos/crm/leads/${seeded.lead}`);
		cy.getByTestId("lead-phone").should("contain", seeded.phone_forms[0]);
	});
});
