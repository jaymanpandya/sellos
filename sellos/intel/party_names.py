"""Party names (SOS-P3-12). Decided by Jayman, SOS-SETUP-34, question 7 (SOS-N13 is Not Needed).

* **Who sees them.** Index II buyer and seller names are visible only to a Company Admin, through
  `get_party_names`. The Party Name DocType grants no permission to any role, so no generic call (get,
  get_list, report, export, link search) returns a name, whoever asks.
* **Never searchable.** No field of Party Name is indexed, filterable, in the list view or in global search,
  the DocType has no search fields, and no method here takes a name to look for. There is no setting that
  turns name search on.
* **Every view is logged.** `get_party_names` writes a Party Name Access Log row (who, when, which record,
  how many names) before it answers. The log never holds a name.
* **Five years.** A name is kept until `RETENTION_YEARS` after it was stored, then `purge_expired` (daily)
  deletes it.
* **Facebook posters.** A poster's name and number are kept only on the draft Listing and are cleared when
  the draft is rejected or published (`sellos.inventory.poster`).
"""

import frappe
from frappe import _
from frappe.utils import add_years, now_datetime, today

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN

PARTY = "Party Name"
LOG = "Party Name Access Log"
ROLES = ("Buyer", "Seller")
RETENTION_YEARS = 5
NAME_LIMIT = 200


def store_party_names(source_record_id, buyer=None, seller=None) -> int:
	"""Keep the names of one registration record. Returns how many were stored. A name already stored for
	the record and party is not stored again."""
	stored = 0
	for party_role, name in (("Buyer", buyer), ("Seller", seller)):
		name = " ".join(str(name or "").split())[:NAME_LIMIT]
		if not name:
			continue
		if frappe.db.exists(PARTY, {"source_record_id": source_record_id, "party_role": party_role}):
			continue
		frappe.get_doc(
			{
				"doctype": PARTY,
				"source_record_id": source_record_id,
				"party_role": party_role,
				"party_name": name,
				"retain_until": add_years(today(), RETENTION_YEARS),
			}
		).insert(ignore_permissions=True)
		stored += 1
	return stored


# POST only: a GET request is rolled back, and the access log row must be kept.
@sellos_api(COMPANY_ADMIN, methods=["POST"])
def get_party_names(source_record_id):
	"""The buyer and seller names of one registration record. Logged, for a Company Admin only."""
	source_record_id = str(source_record_id or "").strip()
	if not source_record_id:
		frappe.throw(_("Choose a record."))
	rows = frappe.get_all(
		PARTY,
		filters={"source_record_id": source_record_id},
		fields=["party_role", "party_name"],
		order_by="party_role asc",
	)
	frappe.get_doc(
		{
			"doctype": LOG,
			"viewer": frappe.session.user,
			"viewed_on": now_datetime(),
			"source_record_id": source_record_id,
			"names_shown": len(rows),
		}
	).insert(ignore_permissions=True)
	return [{"party": row.party_role, "name": row.party_name} for row in rows]


def purge_expired() -> int:
	"""Delete every name whose retention has ended (daily). Returns how many were deleted."""
	expired = frappe.get_all(PARTY, filters={"retain_until": ["<", today()]}, pluck="name")
	for name in expired:
		frappe.delete_doc(PARTY, name, ignore_permissions=True, force=True)
	return len(expired)
