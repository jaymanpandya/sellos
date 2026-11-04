// SOS-P0-10: the five roles and what each may see. Replaces personas.test.js and the logic half of
// shell.test.js. personas.js has no framework in it, so the real module is imported and checked here.
import {
	PERSONAS,
	inAreas,
	navFor,
	navLabel,
	personaFor,
	routeArea,
} from "../../../frontend/src/personas";

context("SOS-P0-10: personas", () => {
	it("defines the five roles, highest priority first", () => {
		expect(PERSONAS.map((p) => p.role)).to.deep.equal([
			"SellOS Platform Admin",
			"SellOS Company Admin",
			"SellOS Agent",
			"SellOS Channel Partner",
			"SellOS Client",
		]);
	});

	it("gives no persona to a user without a SellOS role", () => {
		expect(personaFor([])).to.be.null;
		expect(personaFor(undefined)).to.be.null;
		expect(personaFor(["System Manager", "Guest"])).to.be.null;
	});

	it("maps each SellOS role to its own persona", () => {
		for (const persona of PERSONAS) {
			expect(personaFor([persona.role]).key).to.eq(persona.key);
		}
	});

	it("gives a user with several roles the highest priority persona", () => {
		expect(personaFor(["SellOS Agent", "SellOS Company Admin"]).key).to.eq("company_admin");
		expect(personaFor(["SellOS Client", "SellOS Platform Admin"]).key).to.eq("platform_admin");
	});

	it("keeps clients and partners out of the CRM area", () => {
		expect(inAreas(personaFor(["SellOS Agent"]), "crm")).to.eq(true);
		expect(inAreas(personaFor(["SellOS Client"]), "crm")).to.eq(false);
		expect(inAreas(personaFor(["SellOS Channel Partner"]), "crm")).to.eq(false);
		expect(inAreas(null, "home")).to.eq(false);
	});

	it("shows leads to agents, company admins and partners only, each in their own area", () => {
		const leads = (role) => personaFor([role]).nav.find((i) => i.key === "leads");
		expect(leads("SellOS Agent").to).to.eq("/crm/leads");
		expect(leads("SellOS Company Admin").to).to.eq("/crm/leads");
		expect(leads("SellOS Channel Partner").to).to.eq("/partner/leads");
		expect(leads("SellOS Client")).to.be.undefined;
		expect(leads("SellOS Platform Admin")).to.be.undefined;
	});

	it("falls back to the home area when a route has none", () => {
		expect(routeArea({ meta: { area: "crm" } })).to.eq("crm");
		expect(routeArea({ meta: {} })).to.eq("home");
		expect(routeArea(undefined)).to.eq("home");
	});

	it("labels navigation items, and falls back to the key", () => {
		const agent = personaFor(["SellOS Agent"]);
		expect(navLabel(agent, "home")).to.eq("Home");
		expect(navLabel(agent, "unknown")).to.eq("unknown");
	});

	it("gives every persona navigation that sits inside its own areas", () => {
		for (const persona of PERSONAS) {
			const items = navFor(persona);
			expect(items.length, persona.role).to.be.greaterThan(0);
			for (const item of items) expect(inAreas(persona, item.area), item.key).to.eq(true);
		}
	});

	it("a user with no SellOS role gets no navigation", () => {
		expect(personaFor(["Desk User"])).to.be.null;
		expect(navFor(null)).to.deep.equal([]);
	});

	it("hides a nav item whose area the persona does not have", () => {
		const persona = {
			areas: ["home"],
			nav: [{ key: "x", label: "X", to: "/x", area: "platform" }],
		};
		expect(navFor(persona)).to.deep.equal([]);
	});
});
