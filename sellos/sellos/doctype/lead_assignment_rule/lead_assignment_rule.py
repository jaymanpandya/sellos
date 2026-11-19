# SOS-P1-19 a rule that sends new leads to a team: round robin, by source or by locality.
import frappe
from frappe import _
from frappe.model.document import Document


class LeadAssignmentRule(Document):
	def validate(self):
		self.rule_name = " ".join((self.rule_name or "").split())
		if self.rule_type == "Source":
			self.locality = None
			if not self.source:
				frappe.throw(_("Choose the source this rule is for."))
		elif self.rule_type == "Locality":
			self.source = None
			self.locality = " ".join((self.locality or "").split())
			if not self.locality:
				frappe.throw(_("Enter the locality this rule is for."))
		else:
			self.source = self.locality = None
