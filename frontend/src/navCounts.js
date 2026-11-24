// The count badges of the sidebar (docs/UI_STANDARD.md, "Sidebar"): Call queue and WhatsApp unread.
// Both come from calls the screens already make, so no new endpoint and no new audit entry:
//  * WhatsApp: the sidebar asks the conversation list (no phone number in it) and counts the open
//    conversations whose last message came from the person and has no reply yet.
//  * Call queue: the queue screen sets its own total when it loads (the queue call logs the numbers it
//    shows to a Company Admin, so the sidebar never asks for it by itself).
import { reactive } from "vue";

import { logBackgroundError } from "./api";
import { whatsappApi } from "./whatsapp/whatsappApi";

export const navCounts = reactive({ queue: 0, whatsapp: 0 });

export function setQueueCount(total) {
	navCounts.queue = Number(total) || 0;
}

export async function refreshWhatsAppCount() {
	try {
		const rows = (await whatsappApi.conversations()) || [];
		navCounts.whatsapp = rows.filter(
			(row) => row.last_direction === "Inbound" && row.state !== "Closed"
		).length;
	} catch (e) {
		logBackgroundError("whatsapp unread count failed", e);
	}
}
