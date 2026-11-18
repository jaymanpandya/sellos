import { reactive } from "vue";

import { apiRequest, logRequestError } from "../api";
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

export async function refreshNotifications() {
	try {
		apply(await call("list_notifications"));
	} catch (error) {
		logRequestError("Could not load notifications", error);
	}
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

// Read the list now and then every minute while a bell is on screen.
export function watchNotifications() {
	watchers += 1;
	if (watchers === 1) {
		refreshNotifications();
		timer = setInterval(refreshNotifications, POLL_MS);
	}
	return () => {
		watchers -= 1;
		if (watchers === 0) {
			clearInterval(timer);
			timer = null;
		}
	};
}
