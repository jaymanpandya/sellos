// SOS-P1-23: the notification bell, against the real server. The notifications come from
// sellos.crm.api through seed_notifications, so each one is the one the production code made: the test
// agent is given lead A and then lead B (two notifications, B the newer), and gives the company admin
// lead C (one notification for the admin, none for the agent).
context("SOS-P1-23: notification bell", () => {
	let seed;

	// Each test makes its own data, so none depends on another test having run (SOS-SETUP-24).
	beforeEach(() => {
		cy.bench("sellos.tests.ui_fixtures.seed_notifications").then((made) => {
			seed = made;
		});
	});
	afterEach(() => {
		cy.bench("sellos.tests.ui_fixtures.remove_gate_notifications");
	});

	const open = (role, path = "/sellos") => {
		cy.signInFresh(role);
		cy.intercept("POST", "**/sellos.crm.api.list_notifications*").as("notifications");
		cy.visit(path);
		cy.wait("@notifications").its("response.statusCode").should("eq", 200);
	};
	const bell = () => cy.getByTestId("notification-bell").filter(":visible");
	const count = () => cy.getByTestId("notification-count").filter(":visible");
	const items = () => cy.getByTestId("notification-item");

	it("shows an agent the unread count and, newest first, only their own notifications", () => {
		open("agent");
		count().should("have.text", "2");
		bell().click();
		cy.getByTestId("notification-panel").should("be.visible");
		items().should("have.length", 2);
		items()
			.eq(0)
			.should("contain", seed.b.client_name)
			.and("have.attr", "data-lead", seed.b.lead);
		items()
			.eq(1)
			.should("contain", seed.a.client_name)
			.and("have.attr", "data-lead", seed.a.lead);
		items().eq(0).should("have.attr", "data-event", "Lead assigned");
		cy.getByTestId("notification-panel").should("not.contain", seed.c.client_name);
		cy.apiAs("sellos.crm.api.list_notifications").then((res) => {
			expect(res.status).to.eq(200);
			expect(res.body.message.unread).to.eq(2);
			expect(JSON.stringify(res.body)).to.not.contain(seed.c.client_name);
		});
	});

	it("opens the lead from a notification and marks only that notification read", () => {
		open("agent");
		cy.intercept("POST", "**/sellos.crm.api.mark_notification_read*").as("read");
		bell().click();
		items().eq(1).click();
		cy.wait("@read").its("response.statusCode").should("eq", 200);
		cy.location("pathname").should("eq", `/sellos/crm/leads/${seed.a.lead}`);
		count().should("have.text", "1");
		bell().click();
		items().should("have.length", 1);
		items().eq(0).should("have.attr", "data-lead", seed.b.lead);
		cy.apiAs("sellos.crm.api.list_notifications").then((res) => {
			expect(res.body.message.unread).to.eq(1);
		});
	});

	it("marks every notification read, and they stay read after a reload", () => {
		open("agent");
		cy.intercept("POST", "**/sellos.crm.api.mark_all_notifications_read*").as("readAll");
		bell().click();
		cy.getByTestId("notification-mark-all").click();
		cy.wait("@readAll").its("response.statusCode").should("eq", 200);
		cy.getByTestId("notification-empty").should("be.visible");
		cy.getByTestId("notification-count").should("not.exist");
		cy.reload();
		cy.wait("@notifications");
		cy.getByTestId("notification-count").should("not.exist");
		bell().click();
		cy.getByTestId("notification-empty").should("be.visible");
	});

	it("shows the company admin their own notification and none of the agent's", () => {
		open("company_admin");
		count().should("have.text", "1");
		bell().click();
		items().should("have.length", 1);
		items()
			.eq(0)
			.should("have.attr", "data-lead", seed.c.lead)
			.and("contain", seed.c.client_name);
		cy.getByTestId("notification-panel").should("not.contain", seed.a.client_name);
		cy.getByTestId("notification-panel").should("not.contain", seed.b.client_name);
	});

	it("tells the agent a lead was reassigned away without naming it, and drops what they can no longer see", () => {
		cy.bench("sellos.tests.ui_fixtures.reassign_gate_notify_lead", { lead: seed.b.lead });
		open("agent");
		count().should("have.text", "2");
		bell().click();
		items().should("have.length", 2);
		items().eq(0).should("have.attr", "data-event", "Lead reassigned away");
		items().eq(0).should("not.have.attr", "data-lead");
		cy.getByTestId("notification-panel").should("not.contain", seed.b.client_name);
		items().eq(1).should("have.attr", "data-lead", seed.a.lead);
	});

	it("never lists another user's notification through the API", () => {
		open("agent");
		cy.apiAs("sellos.crm.api.list_notifications").then((res) => {
			expect(res.body.message.items.map((item) => item.lead)).to.not.include(seed.c.lead);
		});
	});

	it("works at phone width, where the bell is in the top bar", () => {
		cy.viewport(390, 844);
		open("agent");
		cy.getByTestId("phone-topbar")
			.find('[data-testid="sellos-notification-bell"]')
			.should("be.visible");
		count().should("have.text", "2");
		bell().click();
		cy.getByTestId("notification-panel").filter(":visible").should("be.visible");
		items().filter(":visible").should("have.length", 2);
		cy.document().then((doc) => {
			const root = doc.documentElement;
			expect(root.scrollWidth, "page width").to.be.at.most(root.clientWidth);
		});
	});

	it("gives a role with no leads no bell", () => {
		cy.signInFresh("client");
		cy.visit("/sellos");
		cy.getByTestId("app-shell").should("exist");
		cy.getByTestId("notification-bell").should("not.exist");
		cy.apiAs("sellos.crm.api.list_notifications").its("status").should("eq", 403);
	});
});
