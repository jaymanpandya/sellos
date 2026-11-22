import { apiRequest } from "../api";

// The WhatsApp API (SOS-P6-11). Every call is one whitelisted method. No call returns a key or a phone
// number: the server says only whether each key is set, and a conversation is known by its lead.
const call = (module, method, params = {}) =>
	apiRequest({ url: `/api/method/sellos.whatsapp.${module}.${method}`, method: "POST", params });

export const whatsappApi = {
	conversations: (state) => call("conversations", "list_whatsapp_conversations", { state }),
	conversation: (conversation) =>
		call("conversations", "get_whatsapp_conversation", { conversation }),
	send: ({ lead, text, template, parameters }) =>
		call("conversations", "send_whatsapp_message", {
			lead,
			text: text || undefined,
			template: template || undefined,
			parameters: parameters && parameters.length ? JSON.stringify(parameters) : undefined,
		}),
	handOff: (conversation, note) =>
		call("conversations", "hand_off_whatsapp_conversation", { conversation, note }),
	close: (conversation) =>
		call("conversations", "close_whatsapp_conversation", { conversation }),
	templates: (includeDisabled = 0) =>
		call("settings", "list_whatsapp_templates", { include_disabled: includeDisabled }),
};

export const whatsappSetupApi = {
	get: () => call("settings", "get_whatsapp_settings"),
	save: ({ accessToken, appSecret, phoneNumberId, displayNumber }) =>
		call("settings", "save_whatsapp_settings", {
			access_token: accessToken,
			app_secret: appSecret,
			phone_number_id: phoneNumberId,
			display_number: displayNumber,
		}),
	check: () => call("settings", "check_whatsapp_connection"),
	saveTemplate: ({ name, body, language, category, status, enabled }) =>
		call("settings", "save_whatsapp_template", {
			name,
			body,
			language,
			category,
			status,
			enabled: enabled ? 1 : 0,
		}),
};
