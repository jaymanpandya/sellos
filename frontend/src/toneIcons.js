// The icon of a status tone (lucide class names, from the status tokens). Colour is never the only sign.
import { status } from "./theme/ui-tokens.js";

export function toneIcon(tone) {
	return (status[tone] || status.neutral).icon;
}

// frappe-ui's Badge knows five themes; SellOS tones map onto them (and onto the status tokens in
// frappe-ui-map.js, so a Badge comes out in the SellOS colours).
export const BADGE_THEME = {
	success: "green",
	warning: "orange",
	danger: "red",
	info: "blue",
	neutral: "gray",
};
