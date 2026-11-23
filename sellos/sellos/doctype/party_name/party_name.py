# SOS-P3-12 the buyer or seller name of one registration record. No role holds a permission on it: the only
# way to read a name is `sellos.intel.party_names.get_party_names`, which is for Company Admins and logs the
# view. It is never searchable, and `sellos.intel.party_names.purge_expired` deletes it after five years.
import frappe
from frappe import _
from frappe.model.document import Document


class PartyName(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("A party name is never changed."))
