# SOS-P5-01 a report, defined by configuration. The checks are in sellos.reports.engine.
from frappe.model.document import Document

from sellos.reports import engine


class ReportDefinition(Document):
	def validate(self):
		engine.validate_definition(self)
