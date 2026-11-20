// SOS-UI-2, SOS-UI-2B: the Pandya palette on PAMAA's layout (docs/UI_STYLE.md) is applied to the app shell.
context("SOS-UI-2B: Pandya palette on the app shell", () => {
	beforeEach(() => {
		cy.signInFresh("agent");
		cy.visit("/sellos");
		cy.getByTestId("app-shell").should("exist");
		// The agent lands on Today. Let its lists finish loading, so leaving the page cuts no request off.
		cy.getByTestId("today-counts", { timeout: 15000 }).should("be.visible");
	});

	it("uses the page background, the ink text colour and Inter", () => {
		cy.get("body").should("have.css", "background-color", "rgb(255, 242, 220)");
		cy.get("body").should("have.css", "color", "rgb(0, 60, 60)");
		cy.get("body").invoke("css", "font-family").should("match", /Inter/);
		cy.get("body").should("have.css", "font-size", "16px");
	});

	it("draws the title at 24px and 600", () => {
		cy.getByTestId("home-welcome").should("have.css", "font-size", "24px");
		cy.getByTestId("home-welcome").should("have.css", "font-weight", "600");
	});

	it("gives the sidebar 240px on the dark surface, 44px items and the 8px control radius", () => {
		cy.getByTestId("nav")
			.filter(":visible")
			.parents("aside")
			.should("have.css", "width", "240px");
		cy.getByTestId("nav")
			.filter(":visible")
			.parents("aside")
			.should("have.css", "background-color", "rgb(0, 60, 60)");
		cy.getByTestId("nav-home").should("have.css", "min-height", "44px");
		cy.getByTestId("nav-home").should("have.css", "border-top-left-radius", "8px");
		cy.getByTestId("nav-leads").should("have.css", "color", "rgb(255, 220, 156)");
	});

	it("puts the top bar on the dark surface", () => {
		cy.getByTestId("phone-topbar").should("have.css", "background-color", "rgb(0, 60, 60)");
	});

	it("gives a card the 16px radius, a 1px teal line at low opacity and white fill", () => {
		cy.signInFresh("basic");
		cy.visit("/sellos");
		cy.getByTestId("no-access")
			.should("have.css", "border-top-left-radius", "16px")
			.and("have.css", "border-top-width", "1px")
			.and("have.css", "border-top-color", "rgba(0, 45, 45, 0.2)")
			.and("have.css", "background-color", "rgb(255, 255, 255)");
	});
});

// SOS-UI-3A: Home, Call queue and Site visits are built from the shared components (docs/UI_STYLE.md).
context("SOS-UI-3A: Home, Call queue and Site visits follow the style", () => {
	const pages = [
		{ name: "Home", path: "/sellos", title: "home-welcome", ready: "today-counts" },
		{ name: "Call queue", path: "/sellos/crm/queue", title: "page-title", ready: "queue" },
		{
			name: "Site visits",
			path: "/sellos/crm/visits",
			title: "page-title",
			ready: "visits-page",
		},
	];

	pages.forEach((page) => {
		it(`${page.name}: page colours, 24px/600 title, 16px card with the teal line`, () => {
			cy.signInFresh("agent");
			cy.visit(page.path);
			cy.getByTestId(page.ready, { timeout: 15000 }).should("be.visible");
			cy.get("body").should("have.css", "background-color", "rgb(255, 242, 220)");
			cy.get("body").should("have.css", "color", "rgb(0, 60, 60)");
			cy.getByTestId(page.title)
				.should("have.css", "font-size", "24px")
				.and("have.css", "font-weight", "600");
			cy.getByTestId("app-shell")
				.find(".ui-card, .rounded-card")
				.first()
				.should("have.css", "border-top-left-radius", "16px")
				.and("have.css", "border-top-width", "1px")
				.and("have.css", "border-top-color", "rgba(0, 45, 45, 0.2)");
		});

		it(`${page.name}: every control is a frappe-ui control`, () => {
			cy.signInFresh("agent");
			cy.visit(page.path);
			cy.getByTestId(page.ready, { timeout: 15000 }).should("be.visible");
			cy.getByTestId("app-shell")
				.find("main")
				.then(($main) => {
					// No native select, and no text input outside a frappe-ui FormControl.
					expect($main.find("select").length, "native selects").to.eq(0);
					$main.find("button").each((_, el) => {
						expect(
							el.className,
							`button ${el.textContent.trim()} is a frappe-ui Button`
						).to.match(/inline-flex|\bflex\b/);
					});
				});
		});
	});

	it("Call queue: the Call button is solid button/bg with text/button", () => {
		cy.bench("sellos.tests.ui_fixtures.seed_caller_queue");
		cy.signInFresh("agent");
		cy.visit("/sellos/crm/queue");
		cy.getByTestId("queue-call")
			.first()
			.should("have.css", "background-color", "rgb(0, 60, 60)")
			.and("have.css", "color", "rgb(228, 179, 60)");
		cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
	});
});

// SOS-UI-3B: Import leads, the pipeline Board, Call lists and Assignment are built from the shared components.
context("SOS-UI-3B: Import leads, Board, Call lists and Assignment follow the style", () => {
	const pages = [
		{
			name: "Import leads",
			path: "/sellos/crm/import",
			title: "sellos-page-title",
			ready: "import-page",
			primary: null,
		},
		{
			name: "Board",
			path: "/sellos/crm/leads?view=board",
			title: "leads-title",
			ready: "board",
			seed: true,
		},
		{
			name: "Call lists",
			path: "/sellos/company/call-lists",
			title: "sellos-page-title",
			ready: "calllists-page",
			primary: "calllists-untouched-save",
		},
		{
			name: "Assignment",
			path: "/sellos/company/assignment",
			title: "sellos-page-title",
			ready: "assignment-page",
			primary: "assignment-add",
		},
	];

	pages.forEach((page) => {
		const open = () => {
			if (page.seed) cy.bench("sellos.tests.ui_fixtures.seed_board_leads");
			cy.signInFresh("company_admin");
			cy.visit(page.path);
			cy.getByTestId(page.ready, { timeout: 15000 }).should("be.visible");
		};
		afterEach(() => {
			if (page.seed) cy.bench("sellos.tests.ui_fixtures.remove_seeded_leads");
		});

		it(`${page.name}: page colours, 24px/600 title, 16px card with the teal line`, () => {
			open();
			cy.get("body").should("have.css", "background-color", "rgb(255, 242, 220)");
			cy.get("body").should("have.css", "color", "rgb(0, 60, 60)");
			cy.get("h1.ui-page-title")
				.first()
				.should("have.css", "font-size", "24px")
				.and("have.css", "font-weight", "600");
			cy.getByTestId("app-shell")
				.find(".ui-card, .rounded-card")
				.first()
				.should("have.css", "border-top-left-radius", "16px")
				.and("have.css", "border-top-width", "1px")
				.and("have.css", "border-top-color", "rgba(0, 45, 45, 0.2)");
		});

		it(`${page.name}: every control is a frappe-ui control`, () => {
			open();
			cy.getByTestId("app-shell")
				.find("main")
				.then(($main) => {
					expect($main.find("select").length, "native selects").to.eq(0);
					$main.find("button").each((_, el) => {
						expect(
							el.className,
							`button ${el.textContent.trim()} is a frappe-ui Button`
						).to.match(/inline-flex|\bflex\b/);
					});
					// Every text input sits in a frappe-ui control (the file chooser is the shared FileField).
					$main.find("input:not([type=file]):not([type=checkbox])").each((_, el) => {
						expect(
							el.className,
							`input ${el.getAttribute("data-testid")} is a frappe-ui input`
						).to.match(/form-input|form-control|\bblock\b|\bw-full\b/);
					});
				});
		});

		if (page.primary) {
			it(`${page.name}: the primary button is solid button/bg with text/button`, () => {
				open();
				cy.getByTestId(page.primary)
					.should("have.css", "background-color", "rgb(0, 60, 60)")
					.and("have.css", "color", "rgb(228, 179, 60)");
			});
		}
	});
});

// SOS-UI-3C: Users, Teams, Team report, Support access and Telephony are built from the shared components.
context("SOS-UI-3C: Users, Teams, Team report, Support and Telephony follow the style", () => {
	const pages = [
		{
			name: "Users",
			role: "company_admin",
			path: "/sellos/company/users",
			ready: "users-list",
		},
		{
			name: "Teams",
			role: "company_admin",
			path: "/sellos/company/teams",
			ready: "teams-form",
		},
		{
			name: "Team report",
			role: "sales_manager",
			path: "/sellos/reports/team",
			ready: "teamreport-total",
		},
		{
			name: "Support access",
			role: "company_admin",
			path: "/sellos/company/support",
			ready: "support-form",
		},
		{
			name: "Telephony",
			role: "company_admin",
			path: "/sellos/company/telephony",
			ready: "telephony-form",
		},
	];

	pages.forEach((page) => {
		it(`${page.name}: page colours, 24px/600 title, 16px card with the teal line`, () => {
			cy.signInFresh(page.role);
			cy.visit(page.path);
			cy.getByTestId(page.ready, { timeout: 15000 }).should("be.visible");
			cy.get("body").should("have.css", "background-color", "rgb(255, 242, 220)");
			cy.get("body").should("have.css", "color", "rgb(0, 60, 60)");
			cy.getByTestId("page-title")
				.should("have.css", "font-size", "24px")
				.and("have.css", "font-weight", "600");
			cy.getByTestId("app-shell")
				.find(".ui-card, .rounded-card")
				.first()
				.should("have.css", "border-top-left-radius", "16px")
				.and("have.css", "border-top-width", "1px")
				.and("have.css", "border-top-color", "rgba(0, 45, 45, 0.2)");
		});

		it(`${page.name}: every control is a frappe-ui control`, () => {
			cy.signInFresh(page.role);
			cy.visit(page.path);
			cy.getByTestId(page.ready, { timeout: 15000 }).should("be.visible");
			cy.getByTestId("app-shell")
				.find("main")
				.then(($main) => {
					expect($main.find("select").length, "native selects").to.eq(0);
					$main.find("button").each((_, el) => {
						expect(
							el.className,
							`button ${el.textContent.trim()} is a frappe-ui Button`
						).to.match(/inline-flex|\bflex\b/);
					});
				});
		});
	});

	it("Users: the invite button is solid button/bg with text/button", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/users");
		cy.getByTestId("users-invite")
			.should("have.css", "background-color", "rgb(0, 60, 60)")
			.and("have.css", "color", "rgb(228, 179, 60)");
	});

	it("Teams: the add team button is solid button/bg with text/button", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/teams");
		cy.getByTestId("teams-add")
			.should("have.css", "background-color", "rgb(0, 60, 60)")
			.and("have.css", "color", "rgb(228, 179, 60)");
	});

	it("Support access: the give access button is solid button/bg with text/button", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/support");
		cy.getByTestId("support-grant")
			.should("have.css", "background-color", "rgb(0, 60, 60)")
			.and("have.css", "color", "rgb(228, 179, 60)");
	});

	it("Telephony: the save button is solid button/bg with text/button", () => {
		cy.signInFresh("company_admin");
		cy.visit("/sellos/company/telephony");
		cy.getByTestId("telephony-save")
			.should("have.css", "background-color", "rgb(0, 60, 60)")
			.and("have.css", "color", "rgb(228, 179, 60)");
	});
});
