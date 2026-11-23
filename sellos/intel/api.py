"""The role checked API to the raw transaction table (SOS-P3-02).

The table lives on the control site. A company site never holds these rows and reads them only through
this method, which names its roles (`sellos_api`), is in the permission matrix, and answers on the control
site only. Each row is returned as stored: the record as received, its source, fetch time and hash.
"""

import json

import frappe
from frappe import _

from sellos.access.registry import sellos_api
from sellos.access.roles import PLATFORM_ADMIN
from sellos.provisioning.control import is_control_site

RAW = "Raw Transaction"
MAX_PAGE = 200
FIELDS = ("name", "source", "source_record_id", "fetch_time", "record_hash")


@sellos_api(PLATFORM_ADMIN)
def list_raw_transactions(source=None, start=0, page_length=50):
	"""One page of raw records, oldest first, optionally for one Market Source."""
	if not is_control_site():
		frappe.throw(_("Market data is read on the control site."), frappe.PermissionError)
	start = max(int(start or 0), 0)
	page_length = min(max(int(page_length or 50), 1), MAX_PAGE)
	filters = {"source": source} if source else {}
	rows = frappe.get_all(
		RAW,
		filters=filters,
		fields=[*FIELDS, "raw_record"],
		order_by="creation asc, name asc",
		offset=start,
		limit=page_length + 1,
	)
	more = len(rows) > page_length
	rows = rows[:page_length]
	for row in rows:
		row["record"] = json.loads(row.pop("raw_record"))
	return {"rows": rows, "has_more": more}
