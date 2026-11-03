// Design tokens for SellOS. Colours are CSS variables so each company can set its own brand at
// runtime from the setup wizard (see applyCompanyTheme in session.js). The defaults below are
// placeholders until the SellOS product brand is chosen.
const defaults = {
	"--sos-brand": "#1d4e5f",
	"--sos-brand-dark": "#143945",
	"--sos-brand-light": "#e6eff2",
	"--sos-accent": "#c98a2b",
	"--sos-surface": "#ffffff",
	"--sos-surface-muted": "#f6f7f8",
	"--sos-ink": "#1b1f23",
	"--sos-ink-muted": "#5b646d",
	"--sos-line": "#e3e6e9",
};

export const colors = {
	brand: {
		DEFAULT: "var(--sos-brand)",
		dark: "var(--sos-brand-dark)",
		light: "var(--sos-brand-light)",
	},
	accent: "var(--sos-accent)",
	surface: {
		DEFAULT: "var(--sos-surface)",
		muted: "var(--sos-surface-muted)",
	},
	ink: {
		DEFAULT: "var(--sos-ink)",
		muted: "var(--sos-ink-muted)",
	},
	line: "var(--sos-line)",
};

export const fontFamily = {
	sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
};

export const radius = {
	card: "12px",
	input: "8px",
	badge: "20px",
};

export const spacing = {};
export const typography = {};

export function cssVariables() {
	return { ...defaults };
}
