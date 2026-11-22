# SOS-P6-11: the company's WhatsApp number. The access token and the signing secret are Password
# fields, so they are stored encrypted and read only by sellos.whatsapp.settings, never sent to a screen.
from frappe.model.document import Document


class WhatsAppSettings(Document):
	pass
