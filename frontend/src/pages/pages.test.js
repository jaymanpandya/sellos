import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import { session } from "../session";
import HomePage from "./HomePage.vue";
import NoAccessPage from "./NoAccessPage.vue";

describe("pages", () => {
	it("greets the signed in user by name", () => {
		session.fullName = "Jayman";
		expect(mount(HomePage).text()).toContain("Welcome, Jayman");
	});

	it("greets without a name when there is none", () => {
		session.fullName = "";
		const text = mount(HomePage).text();
		expect(text).toContain("Welcome");
		expect(text).not.toContain("Welcome,");
	});

	it("explains the no access page", () => {
		expect(mount(NoAccessPage).text()).toContain("You do not have access to this page");
	});
});
