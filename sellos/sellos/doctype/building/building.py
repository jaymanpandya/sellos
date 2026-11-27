# SOS-P3-04 a building a company groups under a micro market. A person reviews it before it counts.
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from sellos.inventory.base import clean_rera_number, squash

NEEDS_REVIEW = "Needs review"
CONFIRMED = "Confirmed"

# The fields a reviewer corrects. Each change to one is saved with who, when and the old value.
CORRECTABLE = (
	"building_name",
	"micro_market",
	"project",
	"country",
	"cts_numbers",
	"village",
	"tahsil",
	"district",
	"rera_number",
	"uae_community",
	"dld_number",
	"au_lot",
	"au_plan",
	"platform_building",
)
TEXT_FIELDS = ("village", "tahsil", "district", "uae_community", "dld_number", "au_lot", "au_plan")


def field_text(doc, fieldname) -> str:
	"""A field as text for the correction log. The CTS numbers are one line each."""
	if fieldname == "cts_numbers":
		return "\n".join(row.cts_number for row in doc.get("cts_numbers") or [])
	return str(doc.get(fieldname) or "")


class Building(Document):
	def validate(self):
		self.building_name = squash(self.building_name)
		if not self.building_name:
			frappe.throw(_("Enter the building's name."))
		self.rera_number = clean_rera_number(self.rera_number)
		for fieldname in TEXT_FIELDS:
			self.set(fieldname, squash(self.get(fieldname)))
		self.platform_building = squash(self.platform_building)
		self.clean_cts()
		self.set_country()
		self.check_market()
		self.track_market()
		if self.status == CONFIRMED:
			if not self.confirmed_on:
				self.confirmed_by = frappe.session.user
				self.confirmed_on = now_datetime()
		else:
			self.confirmed_by = None
			self.confirmed_on = None

	def clean_cts(self):
		seen, rows = set(), []
		for row in self.get("cts_numbers") or []:
			number = squash(row.cts_number).upper()
			if number and number not in seen:
				seen.add(number)
				row.cts_number = number
				rows.append(row)
		self.set("cts_numbers", rows)

	def set_country(self):
		"""A building with no country takes its micro market's."""
		if not self.country and self.micro_market:
			self.country = frappe.db.get_value("Micro Market", self.micro_market, "country")

	def moved(self) -> bool:
		before = None if self.is_new() else self.get_doc_before_save()
		return before is None or before.micro_market != self.micro_market

	def check_market(self):
		"""A building may only be put under an active micro market. Leaving an archived one is allowed."""
		if not self.micro_market or not self.moved():
			return
		if frappe.db.get_value("Micro Market", self.micro_market, "status") != "Active":
			frappe.throw(_("Choose an active micro market."))

	def track_market(self):
		"""Keep which micro market the building belonged to, and when, across every move."""
		if not self.moved():
			return
		now = now_datetime()
		for row in self.get("market_history") or []:
			if not row.to_on:
				row.to_on = now
		if self.micro_market:
			self.append(
				"market_history",
				{
					"micro_market": self.micro_market,
					"from_on": now,
					"reason": self.flags.market_reason or ("Added" if self.is_new() else "Moved"),
				},
			)

	def on_update(self):
		"""Save every correction with who, when and the old value, whichever way the building was saved."""
		before = self.get_doc_before_save()
		if not before:
			return
		for fieldname in CORRECTABLE:
			old, new = field_text(before, fieldname), field_text(self, fieldname)
			if old != new:
				frappe.get_doc(
					{
						"doctype": "Building Correction",
						"building": self.name,
						"fieldname": fieldname,
						"old_value": old,
						"new_value": new,
						"corrected_by": frappe.session.user,
						"corrected_on": now_datetime(),
					}
				).insert(ignore_permissions=True)

	def on_trash(self):
		frappe.throw(_("A building is never deleted."), frappe.PermissionError)
