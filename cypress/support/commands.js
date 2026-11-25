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

// Change the boot data the server writes into the app page before the app reads it, so a spec can
// reach a state a real sign in does not give (a blank company name, a logo, a colour):
// cy.bootOverride((boot) => { boot.company.name = ""; }). Call it before cy.visit.
Cypress.Commands.add("bootOverride", (mutate) => {
	cy.intercept(
		{ method: "GET", resourceType: "document", url: /\/sellos(\/[^.?]*)?(\?.*)?$/ },
		(req) => {
			req.continue((res) => {
				res.body = String(res.body).replace(
					/(window\["sellos_boot"\] = )(\{.*?\});/s,
					(_all, head, json) => {
						const boot = JSON.parse(json);
						mutate(boot);
						return `${head}${JSON.stringify(boot)};`;
					}
				);
			});
		}
	);
});

// A request body as an object, whether the app sent JSON or a form: values that are JSON text are
// parsed, so a spec can assert on what the app asked the server to do.
Cypress.Commands.add("bodyOf", (body) => {
	let data = body;
	if (typeof data === "string") {
		try {
			data = JSON.parse(data);
		} catch {
			data = Object.fromEntries(new URLSearchParams(data));
		}
	}
	Object.keys(data || {}).forEach((key) => {
		if (typeof data[key] === "string") {
			try {
				const parsed = JSON.parse(data[key]);
				if (parsed && typeof parsed === "object") data[key] = parsed;
			} catch {
				// a plain string stays as it is
			}
		}
	});
	return cy.wrap(data, { log: false });
});

// Open the New lead form and fill it in, without saving: the spec then clicks lead-form-save or
// submits the form. Every lead needs a source from the list (SOS-P1-20), so this always chooses
// one, "Website" unless the spec names another standard source. Every spec that creates a lead
// through the form goes through here, so a change to the form is fixed once.
// cy.fillNewLead({ name: "Asha Rao", phone, email, campaign, source: "Referral" }).
Cypress.Commands.add(
	"fillNewLead",
	({ name, phone, email, campaign, source = "Website" } = {}) => {
		cy.getByTestId("leads-new").click();
		if (name) cy.getByTestId("lead-form-name").type(name);
		if (phone) cy.getByTestId("lead-form-phone").type(phone);
		if (email) cy.getByTestId("lead-form-email").type(email);
		cy.getByTestId("lead-form-source").select(source);
		cy.getByTestId("lead-form-source").should("have.value", source);
		if (campaign) cy.getByTestId("lead-form-campaign").type(campaign);
	}
);

// SOS-UI-2B: the screens use frappe-ui's Select, which is a button that opens a list, not a native
// <select>. cy.select() keeps working on both: on a native <select> it is Cypress's own command; on the
// frappe-ui trigger it opens the list and clicks the option whose text is the label. A value that is not
// a label (a user's email, a record name) is looked up in the trigger's data-option-values map, which
// FormField writes ({ value: label }), so a spec may pass either, as it could with a native select.
Cypress.Commands.overwrite("select", (original, subject, valueOrText, options) => {
	const $el = Cypress.$(subject);
	if ($el.is("select")) return original(subject, valueOrText, options);
	const tidy = (text) => String(text).replace(/\s+/g, " ").trim();
	// Read on every retry: a list that loads when it opens (the merge choices) fills the map late.
	const labelNow = () => {
		try {
			const map = JSON.parse($el.attr("data-option-values") || "{}");
			if (map[String(valueOrText)] !== undefined) return tidy(map[String(valueOrText)]);
		} catch (e) {
			// no map: the label is the text given
		}
		return tidy(valueOrText);
	};
	cy.wrap(subject, { log: false }).click();
	// A click can miss when the list is still settling (it opens with a short animation). If the list is
	// still open after the click, click again, up to three times.
	const pick = (attempt) => {
		cy.get('[role="option"]', { log: false })
			.filter((_, el) => tidy(el.innerText) === labelNow())
			.first()
			.then(($option) => {
				// Scroll only as far as needed inside the list (the eleven stages do not all fit), so the
				// list itself does not move, then click where the option is.
				$option[0].scrollIntoView({ block: "nearest" });
				cy.wrap($option, { log: false }).click({ scrollBehavior: false });
			});
		cy.wait(300, { log: false });
		cy.get("body", { log: false }).then(($body) => {
			if ($body.find('[role="listbox"]').length && attempt < 3) pick(attempt + 1);
		});
	};
	pick(1);
	return cy.wrap(subject, { log: false });
});

// SOS-UI-2B: the texts of a frappe-ui Select's options, in order. Opens the list, reads it, closes it.
// cy.optionTexts("lead-stage-select").should("deep.eq", [...]).
Cypress.Commands.add("optionTexts", (testId) => {
	cy.getByTestId(testId).click();
	// The list renders as it opens: give it a moment, so the texts are read from the whole list.
	cy.wait(300, { log: false });
	return cy
		.get('[role="option"]', { log: false })
		.then(($options) => [...$options].map((o) => o.innerText.trim()))
		.then((texts) => {
			cy.get("body", { log: false }).type("{esc}", { log: false });
			return cy.wrap(texts, { log: false });
		});
});

// SOS-UI-2B: the Leads filters show one row (search, stage, agent, source); the rest are under "More
// filters". cy.openMoreFilters() opens them if they are closed, so a spec may call it more than once.
Cypress.Commands.add("openMoreFilters", () => {
	cy.getByTestId("leads-filters-toggle").then(($toggle) => {
		if ($toggle.attr("aria-expanded") !== "true") cy.wrap($toggle).click();
	});
	cy.getByTestId("filters-more").should("be.visible");
});

// SOS-P7-10: the lead page shows a booking panel for the roles that may book. A spec that stubs get_lead for a
// lead that does not exist stubs the panel too, so the page makes no real call that the server would refuse.
Cypress.Commands.add("stubBookingPanel", () => {
	cy.intercept("**/api/method/sellos.inventory.bookings.booking_panel*", {
		body: {
			message: {
				units: [],
				active: [],
				cancelled: [],
				can_book: false,
				partner: null,
				consent: { status: "Unknown", warning: false, message: "" },
			},
		},
	});
});
