"""The raw transaction table (SOS-P3-02): every record stored exactly as received.

`store` is the runner's sink (`sellos.intel.runner`). For each accepted record it keeps the record as the
adapter read it (`raw_record`, the same keys and values, as JSON), the Market Source it came from, the
time it was fetched and a SHA-256 hash of the record. Cleaning (SOS-P3-03) reads from here and can be
repeated at any time, because nothing here is ever changed or deleted.

* **No duplicates.** The duplicate check key is the hash of the source and the record's hash. Ingesting the
  same batch again finds every key already stored and adds nothing. A record the source later corrects has
  a different hash, so the corrected version is stored beside the original, never over it.
* **Control site.** The table is on the control site. A company site never holds these rows and reads
  them only through the role checked API in `sellos.intel.api`.
* **No personal data.** The canonical shape carries none (`sellos.intel.adapters`), but a source may add
  columns. Only the canonical fields are kept from a file's record, and the rest are dropped before
  hashing, so a stray column never reaches the table.
"""

import hashlib
import json

import frappe
from frappe.utils import now_datetime

from sellos.intel import adapters

RAW = "Raw Transaction"


def received_record(raw) -> dict:
	"""The record as received, limited to the canonical field names and otherwise unchanged."""
	return {name: raw[name] for name in adapters.FIELDS if name in raw}


def record_json(record) -> str:
	return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def record_hash(record) -> str:
	return hashlib.sha256(record_json(record).encode("utf-8")).hexdigest()


def dedupe_key(source_name, hash_value) -> str:
	return hashlib.sha256(f"{source_name}\n{hash_value}".encode()).hexdigest()


def store(source_name, items) -> int:
	"""Store `items`, a list of `(raw, mapped)` pairs from one batch. Returns how many were new."""
	fetched = now_datetime()
	added = 0
	for raw, mapped in items:
		record = received_record(raw)
		digest = record_hash(record)
		key = dedupe_key(source_name, digest)
		if frappe.db.exists(RAW, key):
			continue
		doc = frappe.get_doc(
			{
				"doctype": RAW,
				"source": source_name,
				"source_record_id": mapped["source_record_id"],
				"fetch_time": fetched,
				"record_hash": digest,
				"dedupe_key": key,
				"raw_record": record_json(record),
			}
		)
		try:
			doc.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			continue  # another run stored it first
		added += 1
	return added
