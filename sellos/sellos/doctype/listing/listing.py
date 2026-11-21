# SOS-P4-02 a listing of a unit or a property, typed Primary, Direct or Partner, which the website shows only once
# it is published. A draft may be incomplete; publishing needs every required field. Every change is logged with who
# made it and when, whichever way the record is saved. A listing is archived, never deleted.
import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from sellos.inventory.base import AVAILABLE, HELD, InventoryRecord, squash

PRIMARY = "Primary"
LISTING_TYPES = (PRIMARY, "Direct", "Partner")
# A unit or property in one of these can be offered; a Sold, Booked or Blocked one can not.
OFFERABLE = (AVAILABLE, HELD)

# What the change history watches, with the words a person reads.
AUDITED = {
	"title": "Title",
	"listing_type": "Type",
	"unit": "Unit",
	"property": "Property",
	"asking_price": "Asking price",
	"description": "Description",
	"published": "Published",
	"archived": "Archived",
}
_FLAGS = ("published", "archived")


def _shown(field, value) -> str:
	if field in _FLAGS:
		return "Yes" if value else "No"
	if field == "asking_price":
		amount = flt(value)
		return "" if not amount else f"{amount:.0f}" if amount == int(amount) else f"{amount:.2f}"
	return "" if value is None else str(value)


class Listing(InventoryRecord):
	def validate(self):
		before = None if self.is_new() else self.get_doc_before_save()
		self.stamp_archive()
		self.title = squash(self.title)
		if not self.title:
			frappe.throw(_("Enter a title for the listing."))
		self.description = (self.description or "").strip()
		self.asking_price = flt(self.asking_price)
		self.check_target()
		if self.archived:
			self.published = 0  # an archived listing is never shown
		if self.published:
			self.check_publishable()
			if not (before and before.published):
				self.published_on = now_datetime()
				self.published_by = frappe.session.user
		else:
			self.published_on = None
			self.published_by = None
		self.log_changes(before)

	def check_target(self):
		"""The unit or property it offers: one of them, matching the type, offered once."""
		if self.unit and self.property:
			frappe.throw(_("A listing is of a unit or of a property, not both."))
		if self.listing_type == PRIMARY and self.property:
			frappe.throw(_("A Primary listing is of a unit of a project. Choose a unit, not a property."))
		target = ("unit", self.unit) if self.unit else ("property", self.property) if self.property else None
		if not target:
			return
		field, name = target
		if self.is_new() or self.get_doc_before_save().get(field) != name:
			other = frappe.db.get_value("Listing", {field: name, "archived": 0, "name": ["!=", self.name]})
			if other and not self.archived:
				frappe.throw(_("{0} is already listed as {1}.").format(name, other))

	def missing_for_publish(self) -> list[str]:
		"""What a listing still needs before it can be published, in words."""
		missing = []
		if not self.title:
			missing.append(_("a title"))
		if self.listing_type not in LISTING_TYPES:
			missing.append(_("a type"))
		if not (self.unit or self.property):
			missing.append(_("a unit") if self.listing_type == PRIMARY else _("a unit or a property"))
		if flt(self.asking_price) <= 0:
			missing.append(_("an asking price"))
		if not (self.description or "").strip():
			missing.append(_("a description"))
		return missing

	def check_publishable(self):
		missing = self.missing_for_publish()
		if missing:
			frappe.throw(_("A listing needs {0} before it can be published.").format(", ".join(missing)))
		doctype, name = ("Unit", self.unit) if self.unit else ("Property", self.property)
		status, archived = frappe.db.get_value(doctype, name, ["status", "archived"])
		if archived:
			frappe.throw(_("{0} is archived, so it can not be published.").format(name))
		if status not in OFFERABLE:
			frappe.throw(
				_("{0} is {1}. Only an Available or Held one can be published.").format(name, status)
			)

	def log_changes(self, before):
		who, when = frappe.session.user, now_datetime()
		for field, label in AUDITED.items():
			old = "" if before is None else _shown(field, before.get(field))
			new = _shown(field, self.get(field))
			if before is None and field in ("published", "archived") and new == "No":
				continue  # a new listing starts unpublished and not archived: nothing changed
			if before is not None and old == new:
				continue
			if before is None and not new:
				continue
			self.append(
				"changes",
				{
					"changed_on": when,
					"changed_by": who,
					"field_label": label,
					"old_value": old,
					"new_value": new,
				},
			)
