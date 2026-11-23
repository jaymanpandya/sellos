"""The source adapter interface for registration data (SOS-P3-01).

A source is wherever registration records (Index II, Department of Registration and Stamps exports, a
bought file) come from. SellOS works with whichever source is secured by writing one adapter for it. An
adapter does two things and nothing else:

* `fetch_batch(cursor)` returns one `Batch` of raw records and the cursor of the next batch, or None
  for the cursor when the source has no more. The first call gets `cursor=None`. A cursor is any value
  the adapter understands (an offset, a page token); the runner only hands it back.
* `map_fields(raw)` turns one raw record into the canonical shape below, or raises `RecordError` with a
  short reason when the record cannot be used. A bad record is rejected and counted. It never fails the run.

The canonical shape (`FIELDS`). No party names or other personal data are carried: a registration
record here is about a property and a price.

| field | type | required |
| --- | --- | --- |
| source_record_id | text, unique in the source | yes |
| registration_date | date (YYYY-MM-DD, DD-MM-YYYY or DD/MM/YYYY) | yes |
| document_type | text | no |
| sro_office | text | no |
| district | text | no |
| locality | text | no |
| property_description | text | no |
| survey_number | text | no |
| area_sqft | number | no |
| consideration_amount | rupees, commas allowed | no |
| market_value | rupees, commas allowed | no |
| stamp_duty | rupees, commas allowed | no |

An adapter reads what it is given. It never solves a captcha, never logs in as someone else and never
goes round an access control: a source that needs any of that is not a source SellOS uses. A new
adapter is a subclass registered with `register`, and is added to the Adapter list of Market Source.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

FIELDS = (
	"source_record_id",
	"registration_date",
	"document_type",
	"sro_office",
	"district",
	"locality",
	"property_description",
	"survey_number",
	"area_sqft",
	"consideration_amount",
	"market_value",
	"stamp_duty",
)
REQUIRED = ("source_record_id", "registration_date")
NUMBER_FIELDS = ("area_sqft", "consideration_amount", "market_value", "stamp_duty")
DATE_FIELD = "registration_date"
TEXT_LIMIT = 500
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y")


class RecordError(Exception):
	"""One raw record cannot be mapped. The message is a short reason, shown in the run's rejects."""


class SourceError(Exception):
	"""The source cannot be read at all (missing file, unreadable shape). It fails the run."""


@dataclass
class Batch:
	records: list = field(default_factory=list)
	next_cursor: object = None


class SourceAdapter:
	"""Subclass this. `kind` is the name a Market Source chooses."""

	kind = ""

	def __init__(self, config=None):
		self.config = config or {}

	def fetch_batch(self, cursor=None) -> Batch:
		raise NotImplementedError

	def map_fields(self, raw) -> dict:
		raise NotImplementedError


_ADAPTERS: dict[str, type[SourceAdapter]] = {}


def register(adapter_class):
	"""Class decorator: make an adapter available by its kind."""
	if not adapter_class.kind:
		raise ValueError("An adapter needs a kind")
	_ADAPTERS[adapter_class.kind] = adapter_class
	return adapter_class


def kinds() -> list[str]:
	return sorted(_ADAPTERS)


def get_adapter(kind, config=None) -> SourceAdapter:
	if kind not in _ADAPTERS:
		raise SourceError("There is no adapter for this source.")
	return _ADAPTERS[kind](config)


# --- the canonical mapping shared by every adapter ----------------------------------------------------


def _text(value) -> str:
	return " ".join(str(value).split())[:TEXT_LIMIT] if value is not None else ""


def parse_date(value) -> str:
	text = _text(value)
	for pattern in DATE_FORMATS:
		try:
			return datetime.strptime(text, pattern).date().isoformat()
		except ValueError:
			continue
	raise RecordError("registration_date is not a date")


def parse_number(name, value):
	text = _text(value).replace(",", "").replace("₹", "").strip()
	if not text:
		return None
	try:
		number = float(text)
	except ValueError:
		raise RecordError(f"{name} is not a number") from None
	if number < 0 or not math.isfinite(number):
		raise RecordError(f"{name} is not a usable number")
	return number


def to_canonical(values: dict) -> dict:
	"""Check and clean a dict that already uses the canonical names. Unknown keys are dropped."""
	out = {}
	for name in FIELDS:
		raw = values.get(name)
		if name == DATE_FIELD:
			out[name] = parse_date(raw) if _text(raw) else ""
		elif name in NUMBER_FIELDS:
			out[name] = parse_number(name, raw)
		else:
			out[name] = _text(raw)
	for name in REQUIRED:
		if not out[name]:
			raise RecordError(f"{name} is missing")
	return out
