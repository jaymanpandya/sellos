// SOS-P0-10: the signed in session, sign out and session expiry. Replaces session.test.js and the
// sign out half of shell.test.js. session.js is imported, with fake fetch functions where the old
// tests used them, so the same cases run against the same code.
import {
	applyCompanyTheme,
	loadSession,
	session,
	sessionExpired,
	signOut,
	watchSession,
} from "../../../frontend/src/session";

context("SOS-P0-10: session", () => {
	beforeEach(() => {
		session.user = null;
		session.fullName = "";
		session.roles = [];
		session.company = { name: "", brandColor: "" };
		session.loaded = false;
		delete window.sellos_boot;
		delete window.boot;
		document.documentElement.removeAttribute("style");
	});

	it("stays signed out when the page has no boot data", async () => {
		await loadSession();
		expect(session.user).to.be.null;
		expect(session.loaded).to.eq(true);
	});

	it("treats the Guest user as signed out", async () => {
		window.sellos_boot = { user: "Guest" };
		await loadSession();
		expect(session.user).to.be.null;
	});

	it("fills the session from the boot data and applies the company colour", async () => {
		window.sellos_boot = {
			user: "agent@example.com",
			full_name: "A Agent",
			roles: ["SellOS Agent"],
			company: { name: "Pandya Realtors", brand_color: "#112233" },
		};
		await loadSession();
		expect(session.user).to.eq("agent@example.com");
		expect(session.fullName).to.eq("A Agent");
		expect(session.roles).to.deep.equal(["SellOS Agent"]);
		expect(session.company.name).to.eq("Pandya Realtors");
		expect(document.documentElement.style.getPropertyValue("--sos-brand")).to.eq("#112233");
	});

	it("falls back to the email when the full name is missing", async () => {
		window.sellos_boot = { user: "agent@example.com" };
		await loadSession();
		expect(session.fullName).to.eq("agent@example.com");
		expect(session.roles).to.deep.equal([]);
	});

	it("leaves the default colours alone when the company has none", () => {
		applyCompanyTheme({ name: "X", brandColor: "" });
		expect(document.documentElement.style.getPropertyValue("--sos-brand")).to.eq("");
	});

	it("sign out posts to logout, clears the session and goes to login", async () => {
		session.user = "a@x.com";
		session.roles = ["SellOS Agent"];
		const fetchFn = Cypress.sinon.stub().resolves({});
		const redirect = Cypress.sinon.stub();
		await signOut({ fetchFn, redirect });
		expect(fetchFn.firstCall.args[0]).to.eq("/api/method/logout");
		expect(fetchFn.firstCall.args[1].method).to.eq("POST");
		expect(session.user).to.be.null;
		expect(session.roles).to.deep.equal([]);
		expect(redirect).to.have.been.called;
	});

	it("treats Guest and 401 as expired and a failed network call as not expired", async () => {
		const reply =
			(message, status = 200) =>
			async () => ({ status, json: async () => ({ message }) });
		expect(await sessionExpired(reply("Guest"))).to.eq(true);
		expect(await sessionExpired(reply("a@x.com"))).to.eq(false);
		expect(await sessionExpired(reply("", 401))).to.eq(true);
		expect(await sessionExpired(async () => Promise.reject(new Error("offline")))).to.eq(
			false
		);
	});

	it("sends the user to sign in again when the session has expired", async () => {
		session.user = "a@x.com";
		const onExpired = Cypress.sinon.stub();
		const stop = watchSession({
			fetchFn: async () => ({ status: 200, json: async () => ({ message: "Guest" }) }),
			onExpired,
			every: 10,
		});
		await new Promise((resolve) => setTimeout(resolve, 60));
		stop();
		expect(onExpired).to.have.callCount(1);
		expect(session.user).to.be.null;
	});
});
