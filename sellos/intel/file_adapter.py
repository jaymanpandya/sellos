"""The file adapter (SOS-P3-01): a batch from an export file, CSV or JSON, in the shape documented in
`sellos.intel.adapters`. Jayman supplies Index II or DoRS exports; the file sits in the control site's
private files folder and the Market Source names it by its file name.

* CSV: a header row with the canonical field names (extra columns are ignored), one record per row.
* JSON: a list of objects with the canonical field names, or `{"records": [...]}`.

The file is read once per run and served in batches of `BATCH_SIZE`; the cursor is the offset.
"""

import csv
import io
import json
from pathlib import Path

import frappe

from sellos.intel import adapters
from sellos.intel.adapters import Batch, SourceAdapter, SourceError

BATCH_SIZE = 500
MAX_FILE_BYTES = 50 * 1024 * 1024


def resolve(file_name) -> Path:
	"""The file inside this site's private files folder. Anything outside it is refused."""
	folder = Path(frappe.get_site_path("private", "files")).resolve()
	name = str(file_name or "").strip()
	if not name or Path(name).name != name:
		raise SourceError("The file name is not valid. Use a file in the private files folder.")
	path = (folder / name).resolve()
	if not path.is_relative_to(folder) or not path.is_file():
		raise SourceError("The export file was not found in the private files folder.")
	if path.stat().st_size > MAX_FILE_BYTES:
		raise SourceError("The export file is too large.")
	return path


@adapters.register
class FileAdapter(SourceAdapter):
	kind = "File"

	def __init__(self, config=None):
		super().__init__(config)
		self._rows = None

	def _load(self):
		if self._rows is not None:
			return self._rows
		path = resolve(self.config.get("file_name"))
		text = path.read_text(encoding="utf-8-sig")
		if path.suffix.lower() == ".json":
			self._rows = self._from_json(text)
		elif path.suffix.lower() == ".csv":
			self._rows = self._from_csv(text)
		else:
			raise SourceError("The export file must be a CSV or a JSON file.")
		return self._rows

	@staticmethod
	def _from_json(text):
		try:
			data = json.loads(text)
		except ValueError:
			raise SourceError("The JSON file could not be read.") from None
		if isinstance(data, dict):
			data = data.get("records")
		if not isinstance(data, list):
			raise SourceError("The JSON file must be a list of records, or an object with a records list.")
		return data

	@staticmethod
	def _from_csv(text):
		reader = csv.DictReader(io.StringIO(text))
		names = set(reader.fieldnames or [])
		missing = [name for name in adapters.REQUIRED if name not in names]
		if missing:
			raise SourceError("The CSV header is missing: " + ", ".join(missing))
		return list(reader)

	def fetch_batch(self, cursor=None) -> Batch:
		rows = self._load()
		start = int(cursor or 0)
		end = start + BATCH_SIZE
		return Batch(records=rows[start:end], next_cursor=end if end < len(rows) else None)

	def map_fields(self, raw) -> dict:
		if not isinstance(raw, dict):
			raise adapters.RecordError("The record is not an object")
		return adapters.to_canonical(raw)
