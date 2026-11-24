// SellOS UI tokens (SOS-UI-2B, restated by docs/UI_STANDARD.md). The system SellOS shares with BuildOS and
// PAMAA: a neutral page, white cards with a soft shadow, Inter, one 14px radius, a pill
// for the current menu item. Only the accent is SellOS's own: the approved brand green of docs/BRAND.md.
// Pure data; tokens.js and tailwind.config.js read it, ui-tokens.css repeats it as CSS variables.

// The shared neutrals (BuildOS neutral ramp, PAMAA ink, body, muted, line).
export const neutrals = {
	ink: "#1D222B", // text, strong borders
	body: "#3F4A5C", // secondary text, field labels
	muted: "#525F78", // small print, table headings, breadcrumb
	field: "#778399", // input borders: 3.8:1 on white (PAMAA's #8A96AD is 3.0 and misses 3:1)
	line: "#DDE2EC", // card and top bar borders
	"line-soft": "#EBEEF4", // table row lines
	page: "#F4F5F7", // page background (BuildOS neutral-grey, PAMAA tint-from)
	subtle: "#EEF1F6", // locked or switched off areas
	faint: "#F8F9FB", // quiet boxes
	white: "#FFFFFF",
};

// SellOS's own colour, the accent only: primary button, current menu pill, links, focus ring, selected tint.
// A company's brand_color replaces `brand` at runtime (session.js applyCompanyTheme).
export const brand = {
	DEFAULT: "#0F4C35", // --sos-brand
	dark: "#0A3626", // --sos-brand-dark
	mid: "#2A7A5A", // --sos-brand-mid: avatar, hover
	light: "#E3F0EA", // --sos-brand-light: selected, hover tint
};

// Semantic names kept from SOS-UI-2B so every component keeps working.
export const semantic = {
	"surface-page": neutrals.page,
	"surface-card": neutrals.white,
	"surface-shell": neutrals.white, // sidebar and top bar: light
	"text-on-light": neutrals.ink,
	"text-on-brand": neutrals.white,
	"border-default": neutrals.line,
};

// Hover and selected tint of a row or a menu item, over white.
export const derived = {
	body: neutrals.body,
	muted: neutrals.muted,
	faint: neutrals.faint,
	subtle: neutrals.subtle,
	"brand-soft": brand.light,
	"tag-bg": "#EEF1F6",
};

// Cards and top bar: a solid 1px line. Fields: the stronger line that meets 3:1 on white (WCAG 1.4.11).
export const lines = {
	card: neutrals.line,
	soft: neutrals["line-soft"],
	field: neutrals.field,
};

// Status colours, PAMAA's with BuildOS's secondary for info. Each badge also has a word and an icon.
export const status = {
	success: { ink: "#08724E", bg: "#ECFAF5", line: "#9FE5CD", icon: "lucide-circle-check" },
	warning: { ink: "#8A4B00", bg: "#FEF8ED", line: "#F5D48A", icon: "lucide-triangle-alert" },
	danger: { ink: "#BE3910", bg: "#FEF0EC", line: "#F8B5A1", icon: "lucide-circle-alert" },
	info: { ink: "#1A6175", bg: "#EEF8FA", line: "#AADAE7", icon: "lucide-circle-dot" },
	// Not a status colour: a badge with no tone.
	neutral: { ink: "#3F4A5C", bg: "#F0F3F9", line: "#D5DBE6", icon: "lucide-circle-dashed" },
};

export const colors = {
	ink: neutrals.ink,
	body: neutrals.body,
	muted: neutrals.muted,
	line: lines.card,
	"line-soft": lines.soft,
	dash: "#D5DBE6", // dashed list separators
	field: lines.field,
	page: neutrals.page,
	subtle: neutrals.subtle,
	faint: neutrals.faint,
	link: brand.DEFAULT,
	"info-bg": derived["tag-bg"],
	danger: status.danger.ink, // required mark, error text
	"danger-bg": status.danger.bg,
	brand: brand.DEFAULT,
	"brand-2": brand.mid,
	"brand-soft": brand.light,
	white: neutrals.white,
	// Shell: white, with the current item a brand pill.
	"shell-bg": semantic["surface-shell"],
	"shell-ink": neutrals.body,
	"shell-current-bg": brand.DEFAULT,
	"shell-current-ink": neutrals.white,
	"shell-line": lines.card,
	"button-ink": neutrals.white,
	"ghost-bg": neutrals.white,
	"ghost-border": "#C9D0DD", // secondary button edge
};

export const gradients = {
	// Used with restraint: the empty state card only. No gradient behind tables, forms or buttons.
	"grad-brand": "none",
	"grad-empty": `linear-gradient(135deg, #FAFBFD 0%, ${neutrals.subtle} 100%)`,
};

// Fonts: Inter, self hosted (ui-tokens.css).
export const fontFamily = {
	sans: ["Inter", "InterVar", "system-ui", '"Segoe UI"', "sans-serif"],
};

// Type scale (PAMAA's): 16px body, 14px small, 24px title, 13px uppercase card heading, 24px stat.
export const typography = {
	title: ["1.5rem", { lineHeight: "1.25", fontWeight: "600" }],
	heading: ["0.8125rem", { lineHeight: "1.4", letterSpacing: "0.06em", fontWeight: "600" }],
	xs: ["0.875rem", { lineHeight: "1.35rem" }],
	sm: ["1rem", { lineHeight: "1.55rem" }],
	base: ["1rem", { lineHeight: "1.6rem" }],
	stat: ["1.5rem", { lineHeight: "2rem", fontWeight: "600" }],
};

// Spacing scale: 4px base. Names carry a ui- prefix so they cannot clash with Tailwind's own xs..xl.
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

// Radius: one value for every card, panel, input, select, button, menu, drawer and modal (`--radius`, 14px).
// Only a status badge is a full pill. Nothing else may set a radius (scripts/check-guards.sh, guard "radius").
export const radius = {
	DEFAULT: "14px",
	pill: "9999px",
};

// Soft shadows, shared by BuildOS and PAMAA (neutral grey, not tinted).
export const shadows = {
	card: "0 1px 2px rgba(17, 24, 39, 0.04), 0 6px 20px -8px rgba(17, 24, 39, 0.10)",
	lift: "0 2px 4px rgba(17, 24, 39, 0.05), 0 14px 32px -12px rgba(17, 24, 39, 0.18)",
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
	"focus-ring": "0 0 0 3px rgba(15, 76, 53, 0.18)", // a soft brand ring (BuildOS)
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
	vars["--radius"] = radius.DEFAULT;
	vars["--radius-pill"] = radius.pill;
	for (const [k, v] of Object.entries(shadows)) vars[`--ui-shadow-${k}`] = v;
	vars["--ui-ease"] = motion.ease;
	return vars;
}
