# SOS-P1-03 a pipeline stage a company chose in the setup wizard. The buyer pipeline (SOS-P1-07) uses them.
import frappe
from frappe.model.document import Document

from sellos.crm import pipeline

STAGE_DOCTYPE = "Pipeline Stage"


class PipelineStage(Document):
	def autoname(self):
		# SOS-P4-04: a buyer stage is named as it always was. A seller stage is named "Seller <stage>", so
		# Qualified, Nurture and Closed lost can exist on both pipelines.
		self.stage_name = (self.stage_name or "").strip()
		self.name = pipeline.stage_doc_name(self.pipeline, self.stage_name)

	def validate(self):
		self.pipeline = self.pipeline or pipeline.BUYER
		if self.pipeline not in pipeline.PIPELINES:
			frappe.throw(frappe._("A stage belongs to the Buyer or the Seller pipeline."))
		same = {"pipeline": self.pipeline, "stage_name": self.stage_name}
		if not self.is_new():
			same["name"] = ["!=", self.name]
		if frappe.db.exists(STAGE_DOCTYPE, same):
			frappe.throw(
				frappe._("The {0} pipeline already has a stage named {1}.").format(
					self.pipeline, self.stage_name
				)
			)

	def on_trash(self):
		# A stage with leads is never deleted (SOS-P1-07). The message says how many leads are on it.
		pipeline.ensure_deletable(self.name)
		# SOS-P1-21: an outcome that suggested this stage simply stops suggesting one.
		frappe.db.set_value("Call Outcome", {"suggested_stage": self.name}, "suggested_stage", None)
