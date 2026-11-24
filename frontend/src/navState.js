// Which sidebar sections a person has closed, kept per person on the server (sellos.access.preferences, docs/DESIGN_SYSTEM.md).
import { apiRequest, logBackgroundError } from "./api";

const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/sellos.access.preferences.${method}`, method: "POST", params });

export async function loadNavState() {
	const result = await call("get_nav_state");
	return result?.closed || [];
}

// Saved as the person clicks. A failed save is not shown: the next click saves again.
export async function saveNavState(closed) {
	try {
		await call("set_nav_state", { closed: JSON.stringify(closed) });
	} catch (e) {
		logBackgroundError("set_nav_state failed", e);
	}
}
