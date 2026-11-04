import path from "path";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

// Unit tests only. The real vite.config.js is left out because its frappe-ui plugin builds into the app.
export default defineConfig({
	plugins: [vue()],
	resolve: { alias: { "@": path.resolve(__dirname, "src") } },
	test: { environment: "jsdom", include: ["src/**/*.test.js"] },
});
