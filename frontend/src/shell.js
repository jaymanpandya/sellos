// State of the app frame shared by the top bar, the screens and the toasts. Copied from PAMAA's
// frontend/src/shell.js (SOS-UI-2B); the app name is SellOS and there is no drawer state (the sidebar
// is CSS, see AppShell.vue).
import { reactive } from "vue";

export const APP_TITLE = "SellOS";

export const shell = reactive({
	// Last part of the breadcrumb in the top bar, set by each screen.
	title: "",
	// The More drawer of the bottom bar on a phone or tablet.
	menuOpen: false,
	// A search asked for in the top bar while the Leads screen is open: { q, at }.
	searchRequest: null,
});

// The text of the browser tab: the app name, then the screen, as in SellOS - Leads.
export function documentTitle(title) {
	const name = String(title || "").trim();
	return name ? `${APP_TITLE} - ${name}` : APP_TITLE;
}

export function setPageTitle(title) {
	shell.title = title || "";
	if (typeof document !== "undefined") document.title = documentTitle(shell.title);
}

export function closeMenu() {
	shell.menuOpen = false;
}

// Toasts: short messages that slide in at the corner after an action, such as "Saved", and go by
// themselves.
export const TOAST_TIME = 3500;

export const toasts = reactive([]);

let next = 1;

/** Show a toast. `tone` is success, warning, danger or info. Returns its id. */
export function showToast(text, { tone = "success", time = TOAST_TIME } = {}) {
	const id = next++;
	toasts.push({ id, text, tone });
	if (time) setTimeout(() => dismissToast(id), time);
	return id;
}

export function dismissToast(id) {
	const at = toasts.findIndex((toast) => toast.id === id);
	if (at !== -1) toasts.splice(at, 1);
}
