// SOS-SETUP-28: a declared expectation (cy.expectApiStatus, cy.expectConsoleError) must happen at
// least once during its own test, or the test fails with "declared but never happened". The after
// each hook in cypress/support/e2e.js runs assertExpectations; these tests run the same function.
import { assertExpectations, judgeExpectations } from "../../support/expectations";

const failure = (url, status) => ({
	method: "POST",
	url: `http://site/api/method/${url}`,
	status,
});

context("SOS-SETUP-28: declared expectations must happen", () => {
	describe("judging a test", () => {
		it("a declaration met by an answer passes", () => {
			const state = {
				expectedApi: [{ urlPart: "sellos.crm.api.record_consent", status: 417 }],
				apiFailures: [failure("sellos.crm.api.record_consent", 417)],
			};
			expect(judgeExpectations(state)).to.deep.equal({
				unexpectedApi: [],
				unexpectedConsole: [],
				neverHappened: [],
			});
			expect(() => assertExpectations(state)).not.to.throw();
		});

		it("an API declaration nothing answered fails as declared but never happened", () => {
			const state = { expectedApi: [{ urlPart: "sellos.crm.api.list_leads", status: 500 }] };
			expect(judgeExpectations(state).neverHappened).to.deep.equal([
				'cy.expectApiStatus("sellos.crm.api.list_leads", 500)',
			]);
			expect(() => assertExpectations(state)).to.throw("declared but never happened");
		});

		it("an answer with another status does not meet the declaration, and is itself unexpected", () => {
			const state = {
				expectedApi: [{ urlPart: "sellos.crm.api.list_leads", status: 500 }],
				apiFailures: [failure("sellos.crm.api.list_leads", 403)],
			};
			const judged = judgeExpectations(state);
			expect(judged.neverHappened).to.have.length(1);
			expect(judged.unexpectedApi).to.deep.equal([
				"POST http://site/api/method/sellos.crm.api.list_leads answered 403",
			]);
			expect(() => assertExpectations(state)).to.throw(
				"API calls that failed without being expected"
			);
		});

		it("a console declaration that never came fails, and one that came passes", () => {
			const missing = { expectedConsole: ["list_leads"], consoleErrors: [] };
			expect(judgeExpectations(missing).neverHappened).to.deep.equal([
				'cy.expectConsoleError("list_leads")',
			]);
			expect(() => assertExpectations(missing)).to.throw("declared but never happened");
			const met = {
				expectedConsole: ["list_leads"],
				consoleErrors: ["list_leads PermissionError"],
			};
			expect(() => assertExpectations(met)).not.to.throw();
		});

		it("an undeclared console error still fails", () => {
			const state = { consoleErrors: ["TypeError: x is undefined"] };
			expect(() => assertExpectations(state)).to.throw(
				"errors written to the browser console"
			);
		});

		it("each declaration is judged on its own: one met does not cover another", () => {
			const state = {
				expectedApi: [
					{ urlPart: "sellos.crm.api.record_consent", status: 417 },
					{ urlPart: "sellos.crm.api.get_lead", status: 403 },
				],
				apiFailures: [failure("sellos.crm.api.record_consent", 417)],
			};
			expect(judgeExpectations(state).neverHappened).to.deep.equal([
				'cy.expectApiStatus("sellos.crm.api.get_lead", 403)',
			]);
		});

		it("nothing declared and nothing failed passes", () => {
			expect(() => assertExpectations({})).not.to.throw();
		});
	});

	describe("the hook, against the real server", () => {
		const current = (consoleErrors) => ({
			expectedApi: Cypress.env("__expectedApi"),
			apiFailures: Cypress.env("__apiFailures"),
			expectedConsole: Cypress.env("__expectedConsole"),
			consoleErrors,
		});

		it("a declared refusal is not met until the server answers it, then the test passes", () => {
			cy.signOut();
			cy.visit("/login");
			cy.expectApiStatus("sellos.crm.api.list_leads", 403);
			cy.then(() => {
				expect(() => assertExpectations(current([]))).to.throw(
					"declared but never happened"
				);
			});
			cy.intercept("**/sellos.crm.api.list_leads*").as("listLeads");
			cy.window().then((win) => {
				win.fetch("/api/method/sellos.crm.api.list_leads", {
					headers: { Accept: "application/json" },
				});
			});
			cy.wait("@listLeads").its("response.statusCode").should("eq", 403);
		});

		it("a declared console error is met once the page writes it", () => {
			cy.visit("/login");
			cy.expectConsoleError("SOS-SETUP-28 probe");
			cy.window().then((win) =>
				win.console.error("SOS-SETUP-28 probe: written by the test")
			);
		});
	});
});
