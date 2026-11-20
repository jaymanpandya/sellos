// Screen size switches (07_MOBILE_AND_OFFLINE.md). Phones and tablets get the bottom bar and the
// More drawer instead of the sidebar; phones get cards instead of tables. Kept in one place so the
// layout and its tests use the same widths.
import { reactive } from "vue";

// Widths in pixels where the layout changes: tablet from 768, computer from 1024.
export const BREAKPOINTS = Object.freeze({ tablet: 768, desktop: 1024 });

export const PHONE_QUERY = `(max-width: ${BREAKPOINTS.tablet - 0.02}px)`;
export const COMPACT_QUERY = `(max-width: ${BREAKPOINTS.desktop - 0.02}px)`;
// A finger rather than a mouse: the camera button shows only here.
export const TOUCH_QUERY = "(pointer: coarse)";

/** 'phone', 'tablet' or 'desktop' for a screen width. */
export function layoutFor(width) {
	const value = Number(width) || 0;
	if (value >= BREAKPOINTS.desktop) return "desktop";
	if (value >= BREAKPOINTS.tablet) return "tablet";
	return "phone";
}

/**
 * The switches for a window. A window that cannot answer (as in unit tests) counts as a computer
 * with a mouse, the layout that shows everything.
 */
export function readViewport(win) {
	const matches = (query) =>
		Boolean(win && typeof win.matchMedia === "function" && win.matchMedia(query).matches);
	const phone = matches(PHONE_QUERY);
	return { phone, compact: phone || matches(COMPACT_QUERY), touch: matches(TOUCH_QUERY) };
}

const browser = () => (typeof window === "undefined" ? undefined : window);

export const viewport = reactive(readViewport(browser()));

export function updateViewport(win = browser()) {
	Object.assign(viewport, readViewport(win));
}

let listening = false;

/**
 * The live switches; they follow the window as it turns or is resized, and the pointer when a
 * mouse or keyboard is added to a tablet (that changes no width, so the queries are watched too).
 */
export function useViewport() {
	const win = browser();
	if (!listening && win) {
		listening = true;
		const update = () => updateViewport(win);
		win.addEventListener("resize", update);
		win.addEventListener("orientationchange", update);
		if (typeof win.matchMedia === "function") {
			for (const query of [PHONE_QUERY, COMPACT_QUERY, TOUCH_QUERY]) {
				const list = win.matchMedia(query);
				if (list && typeof list.addEventListener === "function")
					list.addEventListener("change", update);
			}
		}
	}
	updateViewport(win);
	return viewport;
}
