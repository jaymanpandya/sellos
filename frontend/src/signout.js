// SOS-P4-04: the sign out guard. It imports nothing, so session.js and its Cypress spec can load it
// without pulling in frappe-ui (api.js does, and Cypress's webpack cannot resolve frappe-ui).
let signingOut = false;
export const markSigningOut = () => {
	signingOut = true;
};
export const isSigningOut = () => signingOut;

// A poll that was already on its way when the user clicked Sign out would be answered 401 by the
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
