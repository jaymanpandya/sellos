# SOS-P7-09 a list of listings and units that an agent builds for one client, in an order, with a note on each
# item, and shares with the client. The client reads it in their own view, and the agent sees which items the
# client opened and when. A shortlist is archived, never deleted.
import frappe
from frappe import _
from frappe.utils import now_datetime

from sellos.crm.base import ArchiveOnly, stamp_archive

MAX_ITEMS = 50
MAX_NOTE = 500


def clean_note(value) -> str:
	return " ".join(str(value or "").split())[:MAX_NOTE]


class Shortlist(ArchiveOnly):
	def validate(self):
		self.title = " ".join(str(self.title or "").split())
		if not self.title:
			frappe.throw(_("Enter a title for the shortlist."))
		if self.is_new() and not self.agent:
			self.agent = frappe.session.user
		self.note = clean_note(self.note)
		self.check_lead()
		self.check_items()
		stamp_archive(self)

	def check_lead(self):
		if self.lead and frappe.db.get_value("Lead", self.lead, "client") != self.client:
			frappe.throw(_("The lead belongs to another client."))

	def check_items(self):
		if len(self.items) > MAX_ITEMS:
			frappe.throw(_("A shortlist can have up to {0} homes.").format(MAX_ITEMS))
		seen = set()
		for row in self.items:
			target = row.unit if row.kind == "Unit" else row.listing if row.kind == "Listing" else None
			if not target or (row.kind == "Unit" and row.listing) or (row.kind == "Listing" and row.unit):
				frappe.throw(_("Each home on a shortlist is one unit or one listing."))
			if (row.kind, target) in seen:
				frappe.throw(_("That home is already on the shortlist."))
			seen.add((row.kind, target))
			row.note = clean_note(row.note)

	def note_opened(self, row):
		"""Mark an item as opened by the client now: the first time, the last time and how many times."""
		now = now_datetime()
		row.db_set("open_count", (row.open_count or 0) + 1, update_modified=False)
		if not row.first_opened_on:
			row.db_set("first_opened_on", now, update_modified=False)
		row.db_set("last_opened_on", now, update_modified=False)
		self.db_set("client_last_opened_on", now, update_modified=False)
