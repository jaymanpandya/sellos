// SellOS specific Cypress commands. Add shared helpers here, not in individual specs.
// See cypress/README.md.

// Select an element by its SellOS test id: cy.getByTestId("lead-row").
Cypress.Commands.add("getByTestId", (testId, options) => {
	return cy.get(`[data-testid="sellos-${testId}"]`, options);
});

// Run a server side helper through `bench execute` and yield its JSON result:
// cy.bench("sellos.tests.ui_fixtures.ensure_role_user", { role: "agent" }).
// Helpers live in sellos/tests/ui_fixtures.py and are never exposed over HTTP.
// CYPRESS_site picks the site (scripts/run-tests.sh sets it); CYPRESS_benchDir the bench folder,
// relative to this app, if it isn't two levels up.
Cypress.Commands.add("bench", (method, kwargs) => {
	const site = Cypress.env("site") || "sellos_test.localhost";
	const benchDir = Cypress.env("benchDir") || "../..";
	const args = kwargs ? ` --kwargs '${JSON.stringify(kwargs)}'` : "";
	return cy
		.exec(`cd ${benchDir} && bench --site ${site} execute ${method}${args}`, {
			log: false,
			timeout: 120000,
			failOnNonZeroExit: false,
		})
		.then((result) => {
			const code = result.exitCode ?? result.code;
			if (code) {
				const output = `${result.stdout}\n${result.stderr}`
					.trim()
					.split("\n")
					.slice(-60)
					.join("\n");
				throw new Error(`${method} exited with code ${code}:\n${output}`);
			}
			const lines = result.stdout.trim().split("\n");
			return JSON.parse(lines[lines.length - 1]);
		});
});

// Create (or refresh) the test user for a role and yield { user, password, full_name }.
// Roles: platform_admin, company_admin, agent, channel_partner, client, basic.
Cypress.Commands.add("roleUser", (role) => {
	return cy.bench("sellos.tests.ui_fixtures.ensure_role_user", { role });
});

// Sign in as a role, the way a person does, through the login endpoint. The session is cached per
// role. Use cy.signInFresh where a spec switches between users inside one test.
Cypress.Commands.add("loginAs", (role) => {
	return cy.roleUser(role).then(({ user, password }) => {
		return cy.session(["role", role], () => {
			cy.request({
				url: "/api/method/login",
				method: "POST",
				body: { usr: user, pwd: password },
			});
		});
	});
});

// Sign in as a role, always fresh: no cached session is restored.
Cypress.Commands.add("signInFresh", (role) => {
	cy.clearAllCookies();
	cy.clearAllLocalStorage();
	cy.clearAllSessionStorage();
	return cy.roleUser(role).then(({ user, password }) => {
		return cy
			.request({
				url: "/api/method/login",
				method: "POST",
				body: { usr: user, pwd: password },
			})
			.its("status")
			.should("be.lessThan", 400);
	});
});

// End the current session on the server, then drop the cookies, and check the server now sees a
// guest. Clearing cookies alone is not enough while an app page is still open (testIsolation is
// off): the page keeps polling, and a late answer sets the old session cookie again.
Cypress.Commands.add("signOut", () => {
	cy.window({ log: false }).then((win) => {
		const token = [win.csrf_token, win.frappe && win.frappe.csrf_token].find(
			(value) => value && value !== "{{ csrf_token }}"
		);
		cy.request({
			url: "/api/method/logout",
			method: "POST",
			headers: token ? { "X-Frappe-CSRF-Token": token } : {},
			failOnStatusCode: false,
		});
	});
	cy.clearAllCookies();
	return cy
		.request({ url: "/api/method/frappe.auth.get_logged_user", failOnStatusCode: false })
		.its("status")
		.should("not.eq", 200);
});

// Declare an API answer the spec expects, so the global 4xx and 5xx check lets it through:
// cy.expectApiStatus("sellos.crm.api.list_leads", 403).
Cypress.Commands.add("expectApiStatus", (urlPart, status) => {
	const expected = Cypress.env("__expectedApi") || [];
	expected.push({ urlPart, status });
	Cypress.env("__expectedApi", expected);
});

// Declare a console error the spec expects, such as the one the app writes when it shows a refusal:
// cy.expectConsoleError("list_leads PermissionError").
Cypress.Commands.add("expectConsoleError", (textPart) => {
	const expected = Cypress.env("__expectedConsole") || [];
	expected.push(textPart);
	Cypress.env("__expectedConsole", expected);
});

// Call a whitelisted method as the signed in user and yield the response without failing on a
// refusal, so a spec can assert on the refusal itself. The method path is the dotted path, so
// overrides answer exactly as they would a request from the app.
Cypress.Commands.add("apiAs", (method, params = {}) => {
	const query = new URLSearchParams(params).toString();
	return cy.request({
		url: `/api/method/${method}${query ? `?${query}` : ""}`,
		failOnStatusCode: false,
	});
});

// The generic Frappe paths that can return a record, called as the signed in user. Each yields
// { path, status, text } so a spec can assert that a value appears in none of them.
Cypress.Commands.add("genericReads", (doctype, name) => {
	const encode = (v) => encodeURIComponent(JSON.stringify(v));
	const urls = [
		`/api/method/frappe.desk.form.load.getdoc?doctype=${doctype}&name=${name}`,
		`/api/method/frappe.desk.form.load.get_docinfo?doctype=${doctype}&name=${name}`,
		`/api/method/frappe.client.get?doctype=${doctype}&name=${name}`,
		`/api/method/frappe.client.get_list?doctype=${doctype}&fields=${encode([
			"*",
		])}&limit_page_length=200`,
		`/api/method/frappe.client.get_value?doctype=${doctype}&filters=${encode({
			name,
		})}&fieldname=${encode(["*"])}`,
		`/api/method/frappe.desk.reportview.get?doctype=${doctype}&fields=${encode([
			"*",
		])}&limit_page_length=200`,
		`/api/method/frappe.desk.search.search_link?doctype=${doctype}&txt=`,
		`/api/resource/${doctype}/${name}`,
		`/api/resource/${doctype}?fields=${encode(["*"])}&limit_page_length=200`,
		`/api/method/frappe.desk.reportview.get_count?doctype=${doctype}`,
	];
	const results = [];
	urls.forEach((url) => {
		cy.request({ url, failOnStatusCode: false }).then((res) => {
			results.push({
				path: url.split("?")[0],
				status: res.status,
				text: JSON.stringify(res.body),
			});
		});
	});
	return cy.wrap(results);
});
