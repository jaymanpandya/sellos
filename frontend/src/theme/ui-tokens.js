// SellOS UI tokens (SOS-UI-2B). Colours, radius and spacing are the Pandya Realtors website tokens,
// copied from docs/ui-reference/pandya-website-design-tokens.md. Fonts and the type scale stay PAMAA's
// (Inter, 16px body). docs/UI_STYLE.md says where each value is used and records every contrast ratio.
// Pure data; tokens.js and tailwind.config.js read it, ui-tokens.css repeats it as CSS variables.

// Primitives, as the website names them (color/teal/900 and so on).
export const primitives = {
	"teal-900": "#002D2D",
	"teal-700": "#003C3C",
	"teal-500": "#004848",
	"gold-200": "#FFDC9C",
	"gold-500": "#E4B33C",
	"cream-100": "#FFF2DC",
	"teal-700-a25": "rgba(0, 60, 60, 0.25)",
	white: "#FFFFFF",
};

// Semantic colours, the website's own names. The `surface/dark` token is `surface-dark` here.
export const semantic = {
	"surface-dark": primitives["teal-700"], // sidebar and top bar
	"surface-darkest": primitives["teal-900"],
	"surface-accent": primitives["teal-500"], // current sidebar item
	"surface-gold": primitives["gold-200"],
	"surface-cream": primitives["cream-100"], // page background
	"text-on-dark": primitives["gold-200"],
	"text-on-light": primitives["teal-700"],
	"text-accent": primitives["gold-500"], // only on teal, never on gold/200 (1.5:1)
	"text-button": primitives["gold-500"],
	"border-default": primitives["teal-900"],
	"border-on-dark": primitives["gold-500"],
	"button-bg": primitives["teal-700"],
	"button-ghost-bg": primitives["teal-700-a25"],
	"button-ghost-border": primitives["teal-900"],
};

// Values the website tokens do not give. Each is derived from the palette; docs/UI_STYLE.md lists them.
export const derived = {
	body: primitives["teal-500"], // labels and secondary text (9.4 on cream)
	muted: "#3F6767", // small print, table headings, breadcrumb (5.7 on cream, 6.3 on white)
	faint: "#FFF8EE", // quiet boxes: cream at 50% over white
	subtle: "#F0E7D2", // locked areas: teal/700 at 6% over cream
	"brand-soft": "#EBEFEF", // hover and selected tint: teal/700 at 8% over white
	"tag-bg": "#E1E9E8",
};

// Jayman's call (20 Nov 2026): cards and inputs are white with a thin teal/900 line at low opacity.
// The field line is stronger because an input's edge must reach 3:1 against white (WCAG 1.4.11).
export const lines = {
	card: "rgba(0, 45, 45, 0.20)", // cards, top bar, dividers on light
	soft: "rgba(0, 45, 45, 0.10)", // table row lines
	field: "rgba(0, 45, 45, 0.55)", // input borders: 3.6:1 on white
};

// The website has no status colours. These four fit the palette; each has a word and an icon as well.
export const status = {
	success: { ink: "#0B5D3B", bg: "#DDEFDF", line: "#8FC4A0", icon: "lucide-circle-check" },
	warning: { ink: "#7A4A00", bg: "#FFEBC0", line: "#E4B33C", icon: "lucide-triangle-alert" },
	danger: { ink: "#A4281B", bg: "#FBE1DC", line: "#E0958B", icon: "lucide-circle-alert" },
	info: { ink: "#1B5A78", bg: "#DCEAF2", line: "#8DB6CC", icon: "lucide-circle-dot" },
	// Not a status colour: a badge with no tone, built from the palette (teal/700 on the ghost fill).
	neutral: {
		ink: "#003C3C",
		bg: "#E1E9E8",
		line: "rgba(0, 45, 45, 0.20)",
		icon: "lucide-circle-dashed",
	},
};

export const colors = {
	ink: semantic["text-on-light"],
	body: derived.body,
	muted: derived.muted,
	line: lines.card,
	"line-soft": lines.soft,
	dash: lines.card,
	field: lines.field,
	page: semantic["surface-cream"],
	subtle: derived.subtle,
	faint: derived.faint,
	link: primitives["teal-700"], // underlined
	"info-bg": derived["tag-bg"],
	danger: status.danger.ink, // required mark, error text
	"danger-bg": status.danger.bg,
	brand: primitives["teal-700"],
	"brand-2": primitives["teal-500"],
	"brand-soft": derived["brand-soft"],
	white: primitives.white,
	// Shell
	"shell-bg": semantic["surface-dark"],
	"shell-ink": semantic["text-on-dark"],
	"shell-current-bg": semantic["surface-accent"],
	"shell-current-ink": semantic["text-accent"],
	"shell-line": "rgba(255, 255, 255, 0.15)", // dividers on the dark band
	"button-ink": semantic["text-button"],
	"ghost-bg": semantic["button-ghost-bg"],
	"ghost-border": semantic["button-ghost-border"],
};

export const gradients = {
	// Text is solid colour only and so are buttons: the website keeps gradients to photo shapes.
	"grad-brand": "none",
	"grad-empty": `linear-gradient(135deg, ${primitives.white} 0%, ${primitives["cream-100"]} 100%)`,
};

// Fonts stay PAMAA's: Inter, self hosted (ui-tokens.css), not the website's stangith or Figtree.
export const fontFamily = {
	sans: ["Inter", "system-ui", '"Segoe UI"', "sans-serif"],
};

// Type scale stays PAMAA's: 16px body, 14px small, 24px title.
export const typography = {
	title: ["1.5rem", { lineHeight: "1.25", fontWeight: "600" }],
	heading: ["0.8125rem", { lineHeight: "1.4", letterSpacing: "0.06em", fontWeight: "600" }],
	xs: ["0.875rem", { lineHeight: "1.35rem" }],
	sm: ["1rem", { lineHeight: "1.55rem" }],
	base: ["1rem", { lineHeight: "1.6rem" }],
	stat: ["1.5rem", { lineHeight: "2rem", fontWeight: "600" }],
};

// Spacing is the website scale: xs 4, sm 8, md 14, lg 24, xl 48. The website's page margin is 69 on a 1728
// canvas; the app uses the scale instead (docs/UI_STYLE.md). Names carry a ui- prefix so they cannot clash
// with Tailwind's own xs..xl.
export const spacing = {
	"ui-xs": "4px",
	"ui-sm": "8px",
	"ui-md": "14px",
	"ui-lg": "24px",
	"ui-xl": "48px",
	touch: "44px", // minimum height and width of any control (PAMAA)
	sidebar: "15rem",
	topbar: "61px",
};

// Radius is the website's: 8 for buttons and inputs, 16 for cards, 100 for round chips.
export const radius = {
	card: "16px",
	control: "8px",
	pill: "9999px",
};

export const shadows = {
	card: "0 1px 2px rgba(0, 45, 45, 0.05), 0 6px 20px -8px rgba(0, 45, 45, 0.12)",
	lift: "0 2px 4px rgba(0, 45, 45, 0.06), 0 14px 32px -12px rgba(0, 45, 45, 0.22)",
	button: "none",
};

export const motion = {
	fast: 120,
	base: 180,
	slow: 250,
	ease: "cubic-bezier(0.16, 1, 0.3, 1)",
};

export const controls = {
	height: "44px",
	"font-size": "1rem",
	"focus-ring": "0 0 0 2px rgba(228, 179, 60, 0.9)", // gold/500 ring on teal and cream
};

// The same values as CSS variables, for plain CSS and for frappe-ui (see tailwind.config.js).
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
