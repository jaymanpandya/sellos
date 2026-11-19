// SellOS UI tokens, taken from PAMAA's frontend/src/tokens.js and frontend/tailwind.config.js (SOS-UI-1).
// Pure data: nothing imports this yet. SOS-UI-2 wires it into tailwind.config.js and applies it.
// Values are PAMAA's own; docs/UI_STYLE.md says where each one is used.

export const brand = {
	indigo: "#323CE9",
	violet: "#5962ED",
	"tint-from": "#F4F5F7",
	"tint-to": "#EEF1F8",
};

export const colors = {
	ink: "#1D222B", // text and strong borders
	body: "#3F4A5C", // secondary text, field labels
	muted: "#525F78", // small print, table headings, breadcrumb
	line: "#DDE2EC", // card and top bar borders
	"line-soft": "#EBEEF4", // table row lines, skeleton rows
	dash: "#D5DBE6",
	field: "#8A96AD", // input borders
	page: brand["tint-from"], // page background
	subtle: "#EEF1F6", // locked or switched off areas
	faint: "#F8F9FB", // quiet boxes
	link: brand.indigo,
	"info-bg": "#E4E7FD", // small tags
	danger: "#B42318", // required mark, error text
	"danger-bg": "#FEF0EC",
	brand: brand.indigo,
	"brand-2": brand.violet,
	"brand-soft": "#F0F1FE", // hover and selected tint of the brand
	white: "#FFFFFF",
};

// Each tone has a word and an icon as well as a colour, never colour alone.
export const status = {
	success: { ink: "#08724E", bg: "#ECFAF5", line: "#9FE5CD", icon: "lucide-circle-check" },
	warn: { ink: "#8A4B00", bg: "#FEF8ED", line: "#F5D48A", icon: "lucide-triangle-alert" },
	danger: { ink: "#BE3910", bg: "#FEF0EC", line: "#F8B5A1", icon: "lucide-circle-alert" },
	neutral: { ink: "#3F4A5C", bg: "#F0F3F9", line: "#D5DBE6", icon: "lucide-circle-dashed" },
	info: { ink: "#1E248B", bg: "#F3F4FF", line: "#ABB1F6", icon: "lucide-circle-dot" },
};

export const gradients = {
	"grad-brand": `linear-gradient(135deg, ${brand.indigo} 0%, #4650EC 100%)`, // primary button, active nav item, brand tile
	"grad-tint": `linear-gradient(180deg, ${brand["tint-from"]} 0%, ${brand["tint-to"]} 100%)`,
	"grad-empty": `linear-gradient(135deg, #FAFBFD 0%, ${brand["tint-to"]} 100%)`, // empty states
};

export const fontFamily = {
	sans: ["Inter", "InterVar", "system-ui", '"Segoe UI"', "sans-serif"],
};

// Type scale. PAMAA raises Tailwind's sizes: its "small" is 16px and its "extra small" is 14px.
export const typography = {
	title: ["1.5rem", { lineHeight: "1.25", fontWeight: "600" }], // page title, card title on sign in
	heading: ["0.8125rem", { lineHeight: "1.4", letterSpacing: "0.06em", fontWeight: "600" }], // card heading, uppercase
	xs: ["0.875rem", { lineHeight: "1.35rem" }], // table heading, label under a value, badge, hint
	sm: ["1rem", { lineHeight: "1.55rem" }], // body text, buttons, fields
	base: ["1rem", { lineHeight: "1.6rem" }],
	stat: ["1.5rem", { lineHeight: "2rem", fontWeight: "600" }], // number on a stat card, tabular figures
};

// Spacing is Tailwind's 4px scale. These are the sizes PAMAA fixes.
export const spacing = {
	touch: "44px", // minimum height and width of any control
	sidebar: "15rem", // 240px
	topbar: "61px", // minimum height of the header and the sidebar logo row
	"page-x": "1rem", // page side padding, 1.5rem from 640px
	"page-x-sm": "1.5rem",
	"page-y": "1.25rem",
	card: "1rem", // card padding, 1.25rem from 640px
	"card-sm": "1.25rem",
	"card-sign-in": "2rem",
};

export const radius = {
	card: "14px", // cards, banners, empty states, menus
	control: "10px", // buttons, fields, menu rows, nav items
	"sign-in-input": "8px", // frappe-ui text input on the sign in page (its radius step 4)
	tile: "10px", // brand tile in the sidebar (9px in the compact header)
	pill: "9999px", // status badges, chips, avatars
};

export const shadows = {
	card: "0 1px 2px rgba(17, 24, 39, 0.04), 0 6px 20px -8px rgba(17, 24, 39, 0.10)",
	lift: "0 2px 4px rgba(17, 24, 39, 0.05), 0 14px 32px -12px rgba(17, 24, 39, 0.18)", // sign in card, menus, toasts
	button: "0 1px 2px rgba(30, 36, 139, 0.25), 0 4px 12px -4px rgba(50, 60, 233, 0.4)",
};

export const motion = {
	fast: 120,
	base: 180,
	slow: 250,
	ease: "cubic-bezier(0.16, 1, 0.3, 1)",
};

export const controls = {
	height: "44px", // fields and buttons inside the app
	"sign-in-input-height": "32px",
	"font-size": "1rem",
	"focus-ring": "0 0 0 2px rgba(50, 60, 233, 0.4)", // plus a 1px offset
};

// The same values as CSS variables, for plain CSS and for the page background.
export function uiCssVariables() {
	const vars = {};
	for (const [k, v] of Object.entries(colors)) vars[`--ui-${k}`] = v;
	for (const [tone, v] of Object.entries(status)) {
		vars[`--ui-${tone}`] = v.ink;
		vars[`--ui-${tone}-bg`] = v.bg;
		vars[`--ui-${tone}-line`] = v.line;
	}
	for (const [k, v] of Object.entries(radius)) vars[`--ui-radius-${k}`] = v;
	for (const [k, v] of Object.entries(shadows)) vars[`--ui-shadow-${k}`] = v;
	vars["--ui-ease"] = motion.ease;
	return vars;
}
