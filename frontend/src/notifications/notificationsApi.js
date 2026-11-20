import { reactive } from "vue";

import { apiRequest, isLeavingPage, logBackgroundError, logRequestError } from "../api";
import { personaFor } from "../personas";

// The bell (SOS-P1-23). Each call is one whitelisted method of sellos.crm.api that returns the signed in
// user's own notifications and no one else's.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/sellos.crm.api.${method}`, method: "POST", params });

// The roles that have leads, and so a bell. The server refuses the rest.
export const NOTIFIED_ROLES = [
	"SellOS Company Admin",
	"SellOS Sales Manager",
	"SellOS Agent",
	"SellOS Channel Partner",
];

export const hasBell = (roles = []) => NOTIFIED_ROLES.some((role) => roles.includes(role));

// Where a notification's lead opens. A partner's leads are in their own area.
export function leadPath(roles, lead) {
	const base = personaFor(roles)?.key === "channel_partner" ? "/partner/leads" : "/crm/leads";
	return `${base}/${lead}`;
}

// One list for every bell on screen (the sidebar and the phone bar show the same one).
export const notificationState = reactive({ unread: 0, items: [], loaded: false });

function apply(result) {
	notificationState.unread = result.unread;
	notificationState.items = result.items || [];
	notificationState.loaded = true;
}

// A background poll is best effort: a cut off one is a warning (the next poll asks again) and a server
// error (400 and above) is still an error. It is not started while the page is hidden or being left.
export async function refreshNotifications() {
	if (isLeavingPage()) return;
	try {
		const result = await call("list_notifications");
		if (isLeavingPage()) return;
		apply(result);
	} catch (error) {
		logBackgroundError("Could not load notifications", error);
	}
}

function poll() {
	if (document.visibilityState === "hidden") return;
	refreshNotifications();
}

function stopTimer() {
	clearInterval(timer);
	timer = null;
}

// Hidden pages do not poll; coming back reads the list at once. Leaving the page stops the timer.
function onVisibility() {
	if (document.visibilityState === "visible") refreshNotifications();
}

// Opening one marks it read. The list is updated at once and then read again from the server.
export async function markNotificationRead(name) {
	notificationState.items = notificationState.items.filter((item) => item.name !== name);
	notificationState.unread = Math.max(0, notificationState.unread - 1);
	try {
		await call("mark_notification_read", { name });
	} catch (error) {
		logRequestError("Could not mark the notification read", error);
	}
	await refreshNotifications();
}

export async function markAllNotificationsRead() {
	try {
		await call("mark_all_notifications_read");
	} catch (error) {
		logRequestError("Could not mark the notifications read", error);
	}
	await refreshNotifications();
}

const POLL_MS = 60000;
let timer = null;
let watchers = 0;
window.addEventListener("pagehide", () => stopTimer());

// Read the list now and then every minute while a bell is on screen.
export function watchNotifications() {
	watchers += 1;
	if (watchers === 1) {
		refreshNotifications();
		timer = setInterval(poll, POLL_MS);
		document.addEventListener("visibilitychange", onVisibility);
	}
	return () => {
		watchers -= 1;
		if (watchers === 0) {
			stopTimer();
			document.removeEventListener("visibilitychange", onVisibility);
		}
	};
}
