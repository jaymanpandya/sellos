import path from "path";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";

// Builds into ../sellos/public/frontend (served at /assets/sellos/frontend/) and copies
// index.html to ../sellos/www/sellos.html, which serves every path under /sellos.
// frontendRoute must match the SPA route in website_route_rules in hooks.py.
export default defineConfig({
	plugins: [
		frappeui({
			frontendRoute: "/sellos",
			frappeProxy: true,
			jinjaBootData: true,
			buildConfig: {
				outDir: path.resolve(__dirname, "../sellos/public/frontend"),
				indexHtmlPath: path.resolve(__dirname, "../sellos/www/sellos.html"),
				baseUrl: "/assets/sellos/frontend/",
			},
		}),
		vue(),
	],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
		},
	},
	optimizeDeps: {
		include: ["feather-icons"],
	},
});
