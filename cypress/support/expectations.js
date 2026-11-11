// SOS-SETUP-28: what a test declared with cy.expectApiStatus and cy.expectConsoleError, judged against
// what happened during that test. cypress/support/e2e.js calls judgeExpectations after every test,
// and cypress/integration/support/expectations.cy.js tests it.
//
// An answer of 400 or more, or a console error, that no declaration covers fails the test, as
// before (SOS-SETUP-27). A declaration that nothing matched also fails it: "declared but never
// happened". A declaration that is never met is either stale or hides that the test never reached
// the refusal it says it checks.

export function judgeExpectations({
	expectedApi = [],
	apiFailures = [],
	expectedConsole = [],
	consoleErrors = [],
}) {
	const apiMatches = (e, f) => f.url.includes(e.urlPart) && e.status === f.status;
	const consoleMatches = (part, text) => text.includes(part);

	const unexpectedApi = apiFailures
		.filter((f) => !expectedApi.some((e) => apiMatches(e, f)))
		.map((f) => `${f.method} ${f.url} answered ${f.status}`);
	const unexpectedConsole = consoleErrors.filter(
		(text) => !expectedConsole.some((part) => consoleMatches(part, text))
	);
	const neverHappened = [
		...expectedApi
			.filter((e) => !apiFailures.some((f) => apiMatches(e, f)))
			.map((e) => `cy.expectApiStatus(${JSON.stringify(e.urlPart)}, ${e.status})`),
		...expectedConsole
			.filter((part) => !consoleErrors.some((text) => consoleMatches(part, text)))
			.map((part) => `cy.expectConsoleError(${JSON.stringify(part)})`),
	];
	return { unexpectedApi, unexpectedConsole, neverHappened };
}

// The three checks, as the after each hook runs them. Each fails with its own message.
export function assertExpectations(state) {
	const { unexpectedApi, unexpectedConsole, neverHappened } = judgeExpectations(state);
	expect(unexpectedApi, "API calls that failed without being expected").to.deep.equal([]);
	expect(unexpectedConsole, "errors written to the browser console").to.deep.equal([]);
	expect(neverHappened, "declared but never happened").to.deep.equal([]);
}
