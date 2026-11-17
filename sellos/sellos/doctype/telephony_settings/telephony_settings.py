# SOS-P2-01: the company's Plivo India account. The auth ID and auth token are Password fields, so
# they are stored encrypted and read back only by sellos.telephony.settings, never sent to a screen.
from frappe.model.document import Document


class TelephonySettings(Document):
	pass
