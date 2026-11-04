// P0.10 navigation per role, sign out and session expiry.
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AppShell from "./components/AppShell.vue";
import { PERSONAS, inAreas, navFor, personaFor } from "./personas";
import { session, sessionExpired, signOut, watchSession } from "./session";

function shellFor(role) {
	session.roles = [role];
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/", component: {} }],
	});
	return mount(AppShell, { global: { plugins: [router] } });
}

describe("navigation per role", () => {
	beforeEach(() => {
		session.company = { name: "Pandya Realtors", logo: "", brandColor: "" };
	});

	for (const persona of PERSONAS) {
		it(`${persona.role} sees only navigation inside its own areas`, () => {
			const items = navFor(persona);
			expect(items.length).toBeGreaterThan(0);
			for (const item of items) expect(inAreas(persona, item.area)).toBe(true);
			const wrapper = shellFor(persona.role);
			expect(wrapper.text()).toContain("Home");
			expect(wrapper.text()).toContain("Pandya Realtors");
			expect(wrapper.text()).toContain("Sign out");
		});
	}

	it("a user with no SellOS role gets no navigation", () => {
		expect(personaFor(["Desk User"])).toBeNull();
		expect(navFor(null)).toEqual([]);
	});

	it("hides a nav item whose area the persona does not have", () => {
		const persona = {
			areas: ["home"],
			nav: [{ key: "x", label: "X", to: "/x", area: "platform" }],
		};
		expect(navFor(persona)).toEqual([]);
	});

	it("shows the company logo when settings have one", () => {
		session.company = { name: "Pandya Realtors", logo: "/files/logo.png", brandColor: "" };
		const wrapper = shellFor("SellOS Agent");
		expect(wrapper.find("img").attributes("src")).toBe("/files/logo.png");
	});
});

describe("sign out and session expiry", () => {
	it("sign out posts to logout, clears the session and goes to login", async () => {
		session.user = "a@x.com";
		session.roles = ["SellOS Agent"];
		const fetchFn = vi.fn().mockResolvedValue({});
		const redirect = vi.fn();
		await signOut({ fetchFn, redirect });
		expect(fetchFn.mock.calls[0][0]).toBe("/api/method/logout");
		expect(fetchFn.mock.calls[0][1].method).toBe("POST");
		expect(session.user).toBeNull();
		expect(session.roles).toEqual([]);
		expect(redirect).toHaveBeenCalled();
	});

	it("treats Guest and 401 as expired and a failed network call as not expired", async () => {
		const reply =
			(message, status = 200) =>
			async () => ({ status, json: async () => ({ message }) });
		expect(await sessionExpired(reply("Guest"))).toBe(true);
		expect(await sessionExpired(reply("a@x.com"))).toBe(false);
		expect(await sessionExpired(reply("", 401))).toBe(true);
		expect(await sessionExpired(async () => Promise.reject(new Error("offline")))).toBe(false);
	});

	it("sends the user to sign in again when the session has expired", async () => {
		session.user = "a@x.com";
		const onExpired = vi.fn();
		const stop = watchSession({
			fetchFn: async () => ({ status: 200, json: async () => ({ message: "Guest" }) }),
			onExpired,
			every: 10,
		});
		await new Promise((resolve) => setTimeout(resolve, 60));
		stop();
		expect(onExpired).toHaveBeenCalledTimes(1);
		expect(session.user).toBeNull();
	});
});
