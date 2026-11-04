import { reactive } from "vue";

export const base = "/sellos";

// Filled from the boot data the server writes into the page. In the dev server there is no boot
// data, so the user stays null and the app shows the no access page.
export const session = reactive({
	user: null,
	fullName: "",
	roles: [],
	company: { name: "", logo: "", brandColor: "" },
	loaded: false,
});

export function applyCompanyTheme(company) {
	if (!company?.brandColor) return;
	const root = document.documentElement;
	root.style.setProperty("--sos-brand", company.brandColor);
	// The dark and light shades are derived from the company colour in a later story.
	root.style.setProperty("--sos-brand-dark", company.brandColor);
	root.style.setProperty("--sos-brand-mid", company.brandColor);
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
