# SOS-P5-01 one row of a report's nightly summary table: the records of one day in one group. The rows are
# written by sellos.reports.engine only, and no role reads them directly.
from frappe.model.document import Document


class ReportSummary(Document):
	pass
