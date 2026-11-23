# SOS-P5-04 a saved report view: a person's report, dates and agent filter, kept under a name and shareable. It
# holds filters only, never figures, so whoever opens it reads the report with their own scope.
from frappe.model.document import Document

from sellos.reports import exports


class SavedReportView(Document):
	def validate(self):
		exports.validate_view(self)
