import frappeUIPreset from "frappe-ui/tailwind";
import plugin from "tailwindcss/plugin";

import {
	colors,
	boxShadow,
	cssVariables,
	fontFamily,
	radius,
	spacing,
	typography,
} from "./src/theme/tokens.js";
import { frappePalette, frappeVariables } from "./src/theme/frappe-ui-map.js";
import { gradients } from "./src/theme/ui-tokens.js";

export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts}",
	],
	theme: {
		// Replaces, not extends: no other radius exists (docs/UI_STANDARD.md, Radius).
		borderRadius: radius,
		extend: {
			// frappe-ui's own palette, remapped to the SellOS tokens (src/theme/frappe-ui-map.js).
			colors: { ...frappePalette, ...colors },
			fontFamily,
			fontSize: typography,
			spacing,
			boxShadow,
			backgroundImage: gradients,
		},
	},
	plugins: [
		plugin(({ addBase }) => {
			// After the frappe-ui preset's own :root block, so these win.
			addBase({ ":root": { ...frappeVariables, ...cssVariables() } });
		}),
	],
};
