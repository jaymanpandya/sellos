// frappe-ui takes every colour from the Tailwind config: its components read CSS variables such as
// --surface-gray-7 and static ramps such as gray-500. This file remaps both to the SellOS tokens, so a
// frappe-ui Button, Input, Badge, Dialog or Toast picks the Pandya palette up with no extra classes.
// tailwind.config.js adds `frappeVariables` to :root and `frappePalette` to theme.extend.colors.
import { derived, lines, primitives, status } from "./ui-tokens.js";

const hex = (h) =>
	h
		.replace("#", "")
		.match(/../g)
		.map((v) => parseInt(v, 16));
const toHex = (c) => "#" + c.map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
const mix = (a, b, t) => {
	const [x, y] = [hex(a), hex(b)];
	return toHex(x.map((v, i) => v * (1 - t) + y[i] * t));
};

// A ramp from `light` to `dark` through `mid` (the 500 step).
function ramp(light, mid, dark) {
	return {
		50: mix(mid, light, 0.94),
		100: mix(mid, light, 0.88),
		200: mix(mid, light, 0.76),
		300: mix(mid, light, 0.58),
		400: mix(mid, light, 0.3),
		500: mid,
		600: mix(mid, dark, 0.2),
		700: mix(mid, dark, 0.4),
		800: mix(mid, dark, 0.62),
		900: mix(mid, dark, 0.82),
	};
}

const T900 = primitives["teal-900"];
const WHITE = primitives.white;

// Static ramps (bg-gray-100, text-red-700 ...). Neutrals are teal tinted, blue is teal.
export const frappePalette = {
	gray: ramp(WHITE, "#5F7F7F", T900),
	blue: ramp(WHITE, primitives["teal-500"], T900),
	green: ramp(WHITE, status.success.ink, "#06251A"),
	red: ramp(WHITE, status.danger.ink, "#3A0F0A"),
	orange: ramp(WHITE, status.warning.ink, "#2E1C00"),
	amber: ramp(WHITE, primitives["gold-500"], "#3A2A00"),
	yellow: ramp(WHITE, primitives["gold-500"], "#3A2A00"),
	cyan: ramp(WHITE, status.info.ink, "#0A2230"),
};

// Semantic variables (bg-surface-gray-7, text-ink-gray-8, border-outline-gray-2 ...), light mode.
// Brand variables follow --sos-brand so a company's own colour still reaches frappe-ui buttons.
export const frappeVariables = {
	// Surfaces
	"--surface-white": WHITE,
	"--surface-cards": WHITE,
	"--surface-modal": WHITE,
	"--surface-selected": derived["brand-soft"],
	"--surface-menu-bar": primitives["cream-100"],
	"--surface-gray-1": derived.faint,
	"--surface-gray-2": derived["brand-soft"],
	"--surface-gray-3": "#DDE5E4",
	"--surface-gray-4": "#CBD7D6",
	"--surface-gray-5": T900, // solid button, pressed
	"--surface-gray-6": "var(--sos-brand-mid)", // solid button, hover
	"--surface-gray-7": "var(--sos-brand)", // solid button: button/bg
	"--surface-blue-1": derived["tag-bg"],
	"--surface-blue-2": status.info.bg,
	"--surface-green-1": "#EFF7F0",
	"--surface-green-2": status.success.bg,
	"--surface-green-3": status.success.ink,
	"--surface-amber-1": status.warning.bg,
	"--surface-amber-2": status.warning.ink,
	"--surface-orange-1": status.warning.bg,
	"--surface-cyan-1": status.info.bg,
	"--surface-red-1": "#FDF1EF",
	"--surface-red-2": status.danger.bg,
	"--surface-red-3": "#F5C9C2",
	"--surface-red-4": status.danger.ink,
	"--surface-red-5": "#8A2016", // solid danger button: gold/500 on it is 5.1
	"--surface-red-6": "#6F180F",
	// Text
	"--text-ink-white": "var(--sos-on-brand-accent)", // text/button on the solid button
	"--text-ink-gray-9": T900,
	"--text-ink-gray-8": primitives["teal-700"], // text/onLight
	"--text-ink-gray-7": primitives["teal-500"],
	"--text-ink-gray-6": primitives["teal-500"],
	"--text-ink-gray-5": derived.muted,
	"--text-ink-gray-4": "#577777", // placeholder: 4.9 on white
	"--text-ink-gray-3": "#8DA5A3",
	"--text-ink-gray-2": "#B8C7C5",
	"--text-ink-gray-1": "#D8E1DF",
	"--text-ink-blue-1": WHITE,
	"--text-ink-blue-2": status.info.ink,
	"--text-ink-blue-3": primitives["teal-700"], // links
	"--text-ink-blue-4": T900,
	"--text-ink-blue-link": primitives["teal-700"],
	"--text-ink-green-1": WHITE,
	"--text-ink-green-2": status.success.ink,
	"--text-ink-green-3": status.success.ink,
	"--text-ink-amber-1": WHITE,
	"--text-ink-amber-2": status.warning.ink,
	"--text-ink-amber-3": status.warning.ink,
	"--text-ink-cyan-1": status.info.ink,
	"--text-ink-red-1": WHITE,
	"--text-ink-red-2": status.danger.ink,
	"--text-ink-red-3": status.danger.ink,
	"--text-ink-red-4": status.danger.ink,
	// Borders
	"--outline-white": WHITE,
	"--outline-gray-1": lines.soft,
	"--outline-gray-2": lines.field, // input border: 3.6 on white
	"--outline-gray-3": "rgba(0, 45, 45, 0.7)",
	"--outline-gray-4": primitives["teal-700"], // focused field
	"--outline-gray-5": T900,
	"--outline-gray-modals": lines.card,
	"--outline-blue-1": status.info.line,
	"--outline-blue-2": status.info.ink,
	"--outline-green-1": status.success.line,
	"--outline-green-2": status.success.line,
	"--outline-amber-1": status.warning.line,
	"--outline-amber-2": status.warning.line,
	"--outline-orange-1": status.warning.line,
	"--outline-red-1": status.danger.line,
	"--outline-red-2": status.danger.line,
	"--outline-red-3": status.danger.ink,
	"--outline-red-4": status.danger.ink,
};
