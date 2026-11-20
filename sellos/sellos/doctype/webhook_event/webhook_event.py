# SOS-P2-06: one row per provider webhook event already handled, so a replay changes nothing.
from frappe.model.document import Document


class WebhookEvent(Document):
	pass
