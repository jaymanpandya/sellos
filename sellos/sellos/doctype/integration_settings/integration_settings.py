# SOS-INT-1: the company's own provider keys that have no DocType of their own (Meta Lead Ads, email, LegiScore),
# and the last result of each Test connection. Every secret is a Password field; sellos.config.integrations is
# the only code that reads or writes it, and no method returns a secret.
from frappe.model.document import Document


class IntegrationSettings(Document):
	pass
