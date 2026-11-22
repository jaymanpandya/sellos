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

// SOS-FLAKE: a request that was cut off (the browser dropped it before any answer: "Failed to fetch",
// an abort, a network drop) has no response. A server answer of 400 and above does have one, and stays a
// real error. Reads that are best effort (the bell, the lists a page asks for as it opens) use
// logBackgroundError: a cut off one is a warning, since the next poll or visit asks again, and anything
// the server answered is still console.error.
export function isCutOff(error) {
	return !error?.response && !error?.status;
}

export function logBackgroundError(label, error) {
	if (leavingPage) return;
	if (isCutOff(error)) {
		console.warn(label, error);
		return;
	}
	console.error(label, error);
}

// True once the page is being left. A poller checks it so it does not start a request that will be cut.
// SOS-P4-04: signing out counts as leaving too, so no poll starts between the click and the redirect.
let signingOut = false;
export const markSigningOut = () => {
	signingOut = true;
};
export const isLeavingPage = () => leavingPage || signingOut;

// SOS-P4-04: a poll that was already on its way when the user clicked Sign out would be answered 401 by the
// logged out session. Background reads are tracked here, and signOut waits for them (at most two seconds)
// before it logs out, so nothing is in flight to be refused.
const inflight = new Set();
export function trackBackground(promise) {
	inflight.add(promise);
	const done = () => inflight.delete(promise);
	promise.then(done, done);
	return promise;
}
export function settleBackground(limitMs = 2000) {
	return Promise.race([
		Promise.allSettled([...inflight]),
		new Promise((resolve) => setTimeout(resolve, limitMs)),
	]);
}
