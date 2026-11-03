import { reactive } from "vue";

export const base = "/sellos";

// Filled from the boot data the server writes into the page. In the dev server there is no boot
// data, so the user stays null and the app shows the no access page.
export const session = reactive({
	user: null,
	fullName: "",
	roles: [],
	company: { name: "", brandColor: "" },
	loaded: false,
});

export function applyCompanyTheme(company) {
	if (!company?.brandColor) return;
	const root = document.documentElement;
	root.style.setProperty("--sos-brand", company.brandColor);
	// The dark and light shades are derived from the company colour in a later story.
	root.style.setProperty("--sos-brand-dark", company.brandColor);
}

export async function loadSession() {
	const boot = window.boot || window.sellos_boot || null;
	if (boot?.user && boot.user !== "Guest") {
		session.user = boot.user;
		session.fullName = boot.full_name || boot.user;
		session.roles = boot.roles || [];
		session.company = {
			name: boot.company?.name || "",
			brandColor: boot.company?.brand_color || "",
		};
		applyCompanyTheme(session.company);
	}
	session.loaded = true;
}
