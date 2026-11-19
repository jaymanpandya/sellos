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

export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts}",
	],
	theme: {
		extend: {
			colors,
			fontFamily,
			fontSize: typography,
			spacing,
			borderRadius: radius,
			boxShadow,
		},
	},
	plugins: [
		plugin(({ addBase }) => {
			addBase({ ":root": cssVariables() });
		}),
	],
};
