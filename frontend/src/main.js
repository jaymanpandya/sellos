import { createApp } from "vue";
import { FrappeUI, setConfig } from "frappe-ui";

import App from "./App.vue";
import { apiRequest } from "./api";
import { base, loadSession, watchSession } from "./session";
import { createAppRouter } from "./router";
import "./index.css";

setConfig("resourceFetcher", apiRequest);

async function start() {
	await loadSession();
	const app = createApp(App);
	app.use(FrappeUI, { socketio: false });
	const router = createAppRouter();
	app.use(router);
	await router.isReady();
	// The home route is "/", which the router writes as "/sellos/". Keep the address without it.
	if (window.location.pathname === base + "/") {
		const { search, hash } = window.location;
		window.history.replaceState(window.history.state, "", base + search + hash);
	}
	app.mount("#app");
	watchSession();
}

start();
