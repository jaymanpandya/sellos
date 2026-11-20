// Design tokens for SellOS (SOS-UI-2B): the Pandya palette of ui-tokens.js as Tailwind theme values.
// The brand colours stay CSS variables so each company can still set its own brand at runtime (see
// applyCompanyTheme in session.js); the Pandya palette is the default. Everything else is the token.
import {
	colors as ui,
	fontFamily as uiFont,
	radius as uiRadius,
	shadows,
	spacing as uiSpacing,
	status,
	typography as uiType,
} from "./ui-tokens.js";

const defaults = {
	"--sos-brand": ui.brand, // button/bg, sidebar and top bar band
	"--sos-brand-dark": ui.brand,
	"--sos-brand-mid": ui["shell-current-bg"], // current sidebar item
	"--sos-brand-light": ui["brand-soft"],
	"--sos-accent": ui.danger, // legacy `accent` on pages not yet moved (SOS-UI-3): error text and alert badges
	"--sos-on-brand": ui["shell-ink"], // text/onDark: text on the brand band
	"--sos-on-brand-accent": ui["shell-current-ink"], // text/accent, text/button
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
	"on-brand": { DEFAULT: "var(--sos-on-brand)", accent: "var(--sos-on-brand-accent)" },
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
	ghost: { bg: ui["ghost-bg"], border: ui["ghost-border"] },
	link: ui.link,
	danger: { DEFAULT: ui.danger, bg: ui["danger-bg"] },
	tone: Object.fromEntries(
		Object.entries(status).flatMap(([tone, v]) => [
			[tone, v.ink],
			[`${tone}-bg`, v.bg],
			[`${tone}-line`, v.line],
		])
	),
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

export const spacing = uiSpacing;

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
