// Design tokens for SellOS (approved by Jayman, SOS-P1-06A). Colours are CSS variables so each
// company can set its own brand at runtime (see applyCompanyTheme in session.js). The defaults
// below are the approved SellOS brand: green #0f4c35, amber #e8954a, Syne headings, DM Sans body.
const defaults = {
	"--sos-brand": "#0f4c35",
	"--sos-brand-dark": "#0a3626",
	"--sos-brand-mid": "#2a7a5a",
	"--sos-brand-light": "#e3f0ea",
	"--sos-accent": "#e8954a",
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
		mid: "var(--sos-brand-mid)",
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
	sans: ['"DM Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
	heading: ["Syne", "ui-sans-serif", "system-ui", "sans-serif"],
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
