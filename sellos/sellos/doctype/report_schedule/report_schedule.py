# SOS-P5-04 a report emailed on a schedule to named people, each getting only what they may see. The rules are
# in sellos.reports.exports.
from frappe.model.document import Document

from sellos.reports import exports


class ReportSchedule(Document):
	def validate(self):
		exports.validate_schedule(self)
