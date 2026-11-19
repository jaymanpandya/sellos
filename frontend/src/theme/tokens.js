// Design tokens for SellOS. SOS-UI-2 moved the defaults to the PAMAA values of docs/UI_STYLE.md
// (the raw values are in ui-tokens.js and ui-tokens.css, SOS-UI-1). The brand colours stay CSS
// variables so each company can still set its own brand at runtime (see applyCompanyTheme in
// session.js); everything else is the PAMAA token.
import {
	colors as ui,
	fontFamily as uiFont,
	radius as uiRadius,
	shadows,
	typography as uiType,
} from "./ui-tokens.js";

const defaults = {
	"--sos-brand": ui.brand,
	"--sos-brand-dark": ui.brand,
	"--sos-brand-mid": ui["brand-2"],
	"--sos-brand-light": ui["brand-soft"],
	"--sos-accent": ui["brand-2"],
	"--sos-surface": ui.white,
	"--sos-surface-muted": ui.page,
	"--sos-ink": ui.ink,
	"--sos-ink-muted": ui.muted,
	"--sos-line": ui.line,
};

export const colors = {
	brand: {
		DEFAULT: "var(--sos-brand)",
		dark: "var(--sos-brand-dark)",
		mid: "var(--sos-brand-mid)",
		light: "var(--sos-brand-light)",
		soft: ui["brand-soft"],
	},
	accent: "var(--sos-accent)",
	surface: {
		DEFAULT: "var(--sos-surface)",
		muted: "var(--sos-surface-muted)",
		faint: ui.faint,
		subtle: ui.subtle,
	},
	ink: {
		DEFAULT: "var(--sos-ink)",
		body: ui.body,
		muted: "var(--sos-ink-muted)",
	},
	line: {
		DEFAULT: "var(--sos-line)",
		soft: ui["line-soft"],
		field: ui.field,
	},
	danger: { DEFAULT: ui.danger, bg: ui["danger-bg"] },
	tone: {
		success: "#08724E",
		"success-bg": "#ECFAF5",
		"success-line": "#9FE5CD",
		warn: "#8A4B00",
		"warn-bg": "#FEF8ED",
		"warn-line": "#F5D48A",
		"danger-ink": "#BE3910",
		"danger-bg": "#FEF0EC",
		"danger-line": "#F8B5A1",
		neutral: "#3F4A5C",
		"neutral-bg": "#F0F3F9",
		"neutral-line": "#D5DBE6",
		info: "#1E248B",
		"info-bg": "#F3F4FF",
		"info-line": "#ABB1F6",
	},
};

export const fontFamily = {
	sans: uiFont.sans,
	heading: uiFont.sans,
};

export const radius = {
	card: uiRadius.card,
	input: uiRadius.control,
	badge: uiRadius.pill,
};

export const boxShadow = shadows;

export const spacing = {
	touch: "44px",
	sidebar: "15rem",
	topbar: "61px",
};

export const typography = {
	title: uiType.title,
	heading: uiType.heading,
	stat: uiType.stat,
	xs: uiType.xs,
	sm: uiType.sm,
	base: uiType.base,
};

export function cssVariables() {
	return { ...defaults };
}
