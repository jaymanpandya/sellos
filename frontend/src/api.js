import { frappeRequest } from "frappe-ui";

import { session } from "./session";

// The one place every request goes through. A 401 sends the user to sign in again, and a 403
// is passed on so pages can show the no access screen.
export async function apiRequest(options) {
	try {
		return await frappeRequest(options);
	} catch (error) {
		if (error?.response?.status === 401) {
			session.user = null;
			window.location.href =
				"/login?redirect-to=" + encodeURIComponent(window.location.pathname);
		}
		throw error;
	}
}
