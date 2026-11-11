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

// SOS-SETUP-28: when the page is being left, the browser cancels its requests and each one fails
// with "Failed to fetch". That is not a fault of the app, and a page that is going away has nobody to
// tell, so it is not written to the console. Every other request failure still is.
// Chrome cancels them between beforeunload and pagehide (measured: beforeunload, the failure 8 ms
// later, then pagehide), so leaving starts at beforeunload. A beforeunload can also come without the
// page leaving (a download link), so that mark lapses after a second; a page that does go never runs
// the timer.
let leavingPage = false;
window.addEventListener("beforeunload", () => {
	leavingPage = true;
	setTimeout(() => {
		leavingPage = false;
	}, 1000);
});
window.addEventListener("pagehide", () => {
	leavingPage = true;
});
window.addEventListener("pageshow", () => {
	leavingPage = false;
});

export function logRequestError(label, error) {
	if (leavingPage) return;
	console.error(label, error);
}
