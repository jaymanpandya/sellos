import { reactive } from "vue";
import { markSigningOut, settleBackground } from "./signout";

export const base = "/sellos";

// Filled from the boot data the server writes into the page. In the dev server there is no boot
// data, so the user stays null and the app shows the no access page.
export const session = reactive({
	user: null,
	fullName: "",
	roles: [],
	company: { name: "", logo: "", brandColor: "" },
	setupComplete: true,
	loaded: false,
});

// A company's own brand colour replaces the Pandya default for the sidebar and top bar band, the main
// button and links' accent. Text on it flips to white or near black so it stays readable (4.5:1) on any colour.
function luminance(hex) {
	const n = parseInt(hex.slice(1), 16);
	const channel = (v) => {
		v /= 255;
		return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
	};
	return (
		0.2126 * channel((n >> 16) & 255) +
		0.7152 * channel((n >> 8) & 255) +
		0.0722 * channel(n & 255)
	);
}

export function applyCompanyTheme(company) {
	if (!company?.brandColor) return;
	const root = document.documentElement;
	const colour = company.brandColor;
	root.style.setProperty("--sos-brand", colour);
	root.style.setProperty("--sos-brand-dark", colour);
	// The current sidebar item and button hover sit a little lighter than the band.
	const mid = `color-mix(in srgb, ${colour} 85%, white)`;
	root.style.setProperty("--sos-brand-mid", mid);
	if (/^#[0-9a-f]{6}$/i.test(colour)) {
		const text = luminance(colour) > 0.4 ? "#111111" : "#FFFFFF";
		root.style.setProperty("--sos-on-brand", text);
		root.style.setProperty("--sos-on-brand-accent", text);
	}
}

export async function loadSession() {
	const boot = window.boot || window.sellos_boot || null;
	if (boot?.user && boot.user !== "Guest") {
		session.user = boot.user;
		session.fullName = boot.full_name || boot.user;
		session.roles = boot.roles || [];
		session.company = {
			name: boot.company?.name || "",
			logo: boot.company?.logo || "",
			brandColor: boot.company?.brand_color || "",
		};
		session.setupComplete = boot.setup_complete !== false;
		applyCompanyTheme(session.company);
	}
	session.loaded = true;
}

const LOGIN_URL = "/login?redirect-to=" + base;

export function goToLogin() {
	window.location.href = LOGIN_URL;
}

// Asks the server who is signed in. Frappe answers "Guest" once the session has expired.
export async function sessionExpired(fetchFn = fetch) {
	try {
		const response = await fetchFn("/api/method/frappe.auth.get_logged_user", {
			credentials: "same-origin",
		});
		if (response.status === 401 || response.status === 403) return true;
		const data = await response.json();
		return data.message === "Guest";
	} catch {
		return false; // offline is not an expiry
	}
}

// Checks for expiry when the tab comes back and every five minutes (P0.10).
export function watchSession({
	fetchFn = fetch,
	onExpired = () => signOut({ fetchFn }),
	every = 300000,
} = {}) {
	const check = async () => {
		if (session.user && (await sessionExpired(fetchFn))) {
			session.user = null;
			onExpired();
		}
	};
	const onVisible = () => document.visibilityState === "visible" && check();
	document.addEventListener("visibilitychange", onVisible);
	const timer = setInterval(check, every);
	return () => {
		document.removeEventListener("visibilitychange", onVisible);
		clearInterval(timer);
	};
}

export async function signOut({ fetchFn = fetch, redirect = goToLogin } = {}) {
	markSigningOut();
	await settleBackground();
	const token = window.csrf_token || window.boot?.csrf_token || "";
	try {
		await fetchFn("/api/method/logout", {
			method: "POST",
			credentials: "same-origin",
			headers: { "X-Frappe-CSRF-Token": token },
		});
	} finally {
		session.user = null;
		session.roles = [];
		redirect();
	}
}
