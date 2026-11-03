import { createApp } from "vue";
import { FrappeUI, setConfig } from "frappe-ui";

import App from "./App.vue";
import { apiRequest } from "./api";
import { loadSession } from "./session";
import { createAppRouter } from "./router";
import "./index.css";

setConfig("resourceFetcher", apiRequest);

async function start() {
	await loadSession();
	const app = createApp(App);
	app.use(FrappeUI, { socketio: false });
	app.use(createAppRouter());
	app.mount("#app");
}

start();
