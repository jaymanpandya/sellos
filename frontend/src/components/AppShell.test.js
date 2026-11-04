import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";
import { h } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

import { session } from "../session";
import AppShell from "./AppShell.vue";

async function render() {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/", component: { render: () => null } }],
	});
	await router.push("/");
	await router.isReady();
	return mount(AppShell, {
		global: { plugins: [router] },
		slots: { default: () => h("p", "page body") },
	});
}

beforeEach(() => {
	session.roles = [];
	session.company = { name: "", brandColor: "" };
});

describe("AppShell", () => {
	it("shows the product name and no links without a role", async () => {
		const wrapper = await render();
		expect(wrapper.text()).toContain("SellOS");
		expect(wrapper.findAll("a")).toHaveLength(0);
		expect(wrapper.text()).toContain("page body");
	});

	it("shows the company name and the home link for an agent", async () => {
		session.roles = ["SellOS Agent"];
		session.company = { name: "Pandya Realtors", brandColor: "" };
		const wrapper = await render();
		expect(wrapper.text()).toContain("Pandya Realtors");
		expect(new Set(wrapper.findAll("a").map((a) => a.text()))).toEqual(new Set(["Home"]));
	});
});
