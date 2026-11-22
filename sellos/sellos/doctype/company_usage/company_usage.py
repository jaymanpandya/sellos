# SOS-P5-03 one month of one company's totals on the control site: users, new leads, calls, talk time and
# calling spend. Numbers only. It holds no lead, client or call record and no phone number. The rows are
# written by sellos.reports.platform only, and nothing is deleted.
import frappe
from frappe import _
from frappe.model.document import Document


class CompanyUsage(Document):
	def on_trash(self):
		frappe.throw(_("Usage totals are kept as a record, never deleted."), frappe.PermissionError)
