# SOS-P4-05 a mandate: an owner's agreement that the company sells a property, Exclusive or Open, with a term
# and a fee. It is signed only with the signed document uploaded, and it then keeps its terms. The Private Sale
# Dossier (the files and notes attached to it) is released only once it is signed, and each view is logged.
# A mandate is archived, never deleted, and the dossier and its view log only ever grow.
import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, getdate, now_datetime, today

from sellos.inventory.base import InventoryRecord, squash

EXCLUSIVE = "Exclusive"
OPEN = "Open"
TYPES = (EXCLUSIVE, OPEN)
DRAFT = "Draft"
SIGNED = "Signed"
MAX_TERM_MONTHS = 120
TERMS = ("lead", "mandate_type", "start_date", "term_months", "fee_percent")


class Mandate(InventoryRecord):
	def validate(self):
		before = None if self.is_new() else self.get_doc_before_save()
		self.stamp_archive()
		self.check_terms()
		self.check_signature(before)
		self.check_dossier(before)

	def check_terms(self):
		if not self.lead or not frappe.db.exists("Lead", self.lead):
			frappe.throw(_("Choose the seller lead this mandate is for."))
		if frappe.db.get_value("Lead", self.lead, "pipeline") != "Seller":
			frappe.throw(_("A mandate is for a seller. {0} is not on the Seller pipeline.").format(self.lead))
		if self.mandate_type not in TYPES:
			frappe.throw(_("A mandate is Exclusive or Open."))
		self.term_months = cint(self.term_months)
		if not 1 <= self.term_months <= MAX_TERM_MONTHS:
			frappe.throw(_("The term is from 1 to {0} months.").format(MAX_TERM_MONTHS))
		self.fee_percent = flt(self.fee_percent)
		if not 0 < self.fee_percent <= 100:
			frappe.throw(_("The fee is a percentage of the sale price, above 0 and up to 100."))
		self.start_date = getdate(self.start_date or today())

	@property
	def ends_on(self):
		return add_months(getdate(self.start_date), cint(self.term_months)) if self.start_date else None

	def check_signature(self, before):
		if self.status not in (DRAFT, SIGNED):
			frappe.throw(_("A mandate is a Draft or Signed."))
		if self.status == SIGNED and not self.signed_document:
			frappe.throw(_("Upload the signed document to sign the mandate."))
		if not before or before.status != SIGNED:
			return
		if self.status != SIGNED or self.signed_document != before.signed_document:
			frappe.throw(_("A signed mandate stays signed, with its signed document."))
		for field in TERMS:
			if str(self.get(field) or "") != str(before.get(field) or ""):
				frappe.throw(_("A signed mandate keeps its terms. Sign a new mandate to change them."))

	def check_dossier(self, before):
		"""Notes and files are added, never changed or removed, and a note or a file has its content."""
		for row in self.dossier:
			row.title = squash(row.title)
			if not row.title:
				frappe.throw(_("Enter a title for the dossier item."))
			if row.kind == "Note" and not (row.note or "").strip():
				frappe.throw(_("Write the note."))
			if row.kind == "File" and not row.file:
				frappe.throw(_("A dossier file needs its file."))
			if row.kind not in ("Note", "File"):
				frappe.throw(_("A dossier item is a Note or a File."))
		if not before:
			return
		for table, fields in (
			("dossier", ("kind", "title", "note", "file", "added_by")),
			("views", ("viewed_by",)),
		):
			old, new = before.get(table), self.get(table)
			same = len(new) >= len(old) and all(
				a.name == b.name and all((a.get(f) or "") == (b.get(f) or "") for f in fields)
				for a, b in zip(old, new, strict=False)
			)
			if not same:
				frappe.throw(_("Nothing is removed from or changed in a dossier or its view log."))

	def sign(self, file_url):
		self.status = SIGNED
		self.signed_document = file_url
		self.signed_on = now_datetime()
		self.signed_by = frappe.session.user
