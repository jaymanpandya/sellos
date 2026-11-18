# SOS-P1-03 a pipeline stage a company chose in the setup wizard. The buyer pipeline (SOS-P1-07) uses them.
import frappe
from frappe.model.document import Document

from sellos.crm import pipeline


class PipelineStage(Document):
	def on_trash(self):
		# A stage with leads is never deleted (SOS-P1-07). The message says how many leads are on it.
		pipeline.ensure_deletable(self.name)
		# SOS-P1-21: an outcome that suggested this stage simply stops suggesting one.
		frappe.db.set_value("Call Outcome", {"suggested_stage": self.name}, "suggested_stage", None)
