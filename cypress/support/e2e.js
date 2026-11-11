// The browser reports a ResizeObserver that could not deliver every size change in one frame as an
// error. It is harmless, Chrome gives it no stack, and it can be raised in the runner's own top
// window as well as in the app, so Cypress blames it on the spec. These two wordings are the only
// errors ignored anywhere in the suite. This block is copied from BuildOS (BOS-303).
const RESIZE_OBSERVER_MESSAGES = [
	"ResizeObserver loop completed with undelivered notifications",
	"ResizeObserver loop limit exceeded",
];

function isResizeObserverLoop(message) {
	const text = String(message || "");
	return RESIZE_OBSERVER_MESSAGES.some((wording) => text.includes(wording));
}

function swallowResizeObserverLoop(win) {
	if (!win || win.__sellosResizeObserverGuard) return;
	try {
		win.__sellosResizeObserverGuard = true;
		win.addEventListener(
			"error",
			(event) => {
				if (!isResizeObserverLoop(event.message || event.error?.message)) return;
				event.preventDefault();
				event.stopImmediatePropagation();
			},
			true
		);
		win.addEventListener(
			"unhandledrejection",
			(event) => {
				if (!isResizeObserverLoop(event.reason?.message || event.reason)) return;
				event.preventDefault();
				event.stopImmediatePropagation();
			},
			true
		);
	} catch {
		// A window from another origin cannot take listeners; nothing to guard there.
	}
}

swallowResizeObserverLoop(window);
try {
	swallowResizeObserverLoop(window.top);
} catch {
	// The runner is the same origin as the spec; this only guards an unexpected setup.
}

// Console errors raised by the app are collected on its window, and checked after every test.
Cypress.on("window:before:load", (win) => {
	swallowResizeObserverLoop(win);
	win.__sellosConsoleErrors = [];
	const original = win.console.error.bind(win.console);
	win.console.error = (...args) => {
		const text = args.map((a) => (a && a.message) || String(a)).join(" ");
		if (!isResizeObserverLoop(text)) win.__sellosConsoleErrors.push(text);
		original(...args);
	};
});

// Every route (runner, spec and app window) goes through cy.onUncaughtException, so the same two
// wordings are dropped there as well.
const failOnUncaught = cy.onUncaughtException;
cy.onUncaughtException = function onUncaughtException(options, ...rest) {
	if (isResizeObserverLoop(options?.err?.message)) return true;
	return failOnUncaught.call(this, options, ...rest);
};

// Reuse the stock helpers (cy.login, cy.call, ...). Their npm dependencies resolve from
// apps/frappe/node_modules because the import path lives there.
import "../../../frappe/cypress/support/commands";
import "./commands";

// BuildOS ends this file with Cypress.on("uncaught:exception", () => false), which hides every
// error the app throws. SellOS does not. An uncaught error fails the spec, so a page that breaks
// quietly (an empty list where the call failed) can never pass.
Cypress.on("uncaught:exception", (err) => {
	if (isResizeObserverLoop(err.message)) return false;
	return true;
});

// Three things fail a test even when its own assertions pass: an API call that answered 4xx or
// 5xx without the spec saying it expected that, an error written to the console, and a request
// that never got an answer. cy.expectApiStatus(urlPart, status) declares an expected one.
//
// Every 4xx and 5xx answer is recorded as it arrives, and compared with the declarations only after
// the test, so the order in which the answer and cy.expectApiStatus happen to run cannot decide the
// result. CI run 42925739766 failed when a 417 arrived before the declaration that came after the
// submit had run (SOS-SETUP-27). A declaration still covers only its own test.
beforeEach(() => {
	Cypress.env("__expectedApi", []);
	Cypress.env("__expectedConsole", []);
	Cypress.env("__apiFailures", []);
	cy.intercept({ url: "**/api/**" }, (req) => {
		req.continue((res) => {
			if (res.statusCode < 400) return;
			const failures = Cypress.env("__apiFailures");
			failures.push({ method: req.method, url: req.url, status: res.statusCode });
		});
	});
});

afterEach(() => {
	const expected = Cypress.env("__expectedApi") || [];
	const failures = (Cypress.env("__apiFailures") || [])
		.filter((f) => !expected.some((e) => f.url.includes(e.urlPart) && e.status === f.status))
		.map((f) => `${f.method} ${f.url} answered ${f.status}`);
	expect(failures, "API calls that failed without being expected").to.deep.equal([]);
	cy.window({ log: false }).then((win) => {
		const expected = Cypress.env("__expectedConsole") || [];
		const errors = (win.__sellosConsoleErrors || []).filter(
			(text) => !expected.some((part) => text.includes(part))
		);
		expect(errors, "errors written to the browser console").to.deep.equal([]);
	});
});
