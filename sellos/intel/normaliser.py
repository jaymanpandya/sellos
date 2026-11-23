"""The normaliser (SOS-P3-03): clean, comparable figures from a raw transaction.

`normalise(record)` takes one record as received (the canonical field names of `sellos.intel.adapters`,
values exactly as the source gave them, so they may carry Devanagari digits, Marathi words, "Cr" or "lakh"
amounts or an area with its unit) and returns a `Result`: the clean fields, or the list of fields it could not
read. It is pure: no database, so the same record always gives the same answer and cleaning can be repeated
from the raw table at any time (SOS-P3-02).

* **English.** Marathi text is translated from a glossary of document types, property words and well known
  places (`sellos.intel.marathi`), and any other Devanagari word is transliterated by rule. The original text
  is kept beside the English one. Transliteration of an unknown name is mechanical, so a person may correct
  it on the review list; it never blocks a record.
* **Dates.** Every date becomes YYYY-MM-DD. Day comes first (Indian order). A date that cannot be read, or
  is outside 1980 up to a year from today, is a problem.
* **Money.** Consideration, market value and stamp duty become rupees: commas, Rs, rupee sign, "/-",
  Devanagari digits, "lakh" and "crore" (and the Marathi words) are understood.
* **Area.** Every area becomes square feet of carpet area, with the rule recorded in `area_rule`:
  square feet and square metres as given (carpet), built up area divided by 1.2, super built up area divided
  by 1.4, and land units (guntha, acre, hectare, are) converted to square feet with no carpet adjustment.
  The two ratios are the usual rules of thumb for Maharashtra and are named constants below.
* **Review.** A record with any problem returns no clean fields. The caller puts it on the review list
  with the problems (`sellos.intel.normalise_store`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from sellos.intel import marathi

RULES_VERSION = "1"

BUILT_UP_TO_CARPET = Decimal("1.2")
SUPER_TO_CARPET = Decimal("1.4")
SQM_TO_SQFT = Decimal("10.7639")
LAND_UNITS = {  # unit -> (square feet in one unit, name used in the rule)
	"guntha": (Decimal("1089"), "guntha"),
	"acre": (Decimal("43560"), "acre"),
	"hectare": (Decimal("107639"), "hectare"),
	"are": (Decimal("1076.39"), "are"),
}
MIN_YEAR = 1980

TEXT_FIELDS = ("document_type", "sro_office", "district", "locality", "property_description")
MONEY_FIELDS = ("consideration_amount", "market_value", "stamp_duty")

_MONTHS = {
	"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
	"may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
	"september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
	"जानेवारी": 1, "फेब्रुवारी": 2, "मार्च": 3, "एप्रिल": 4, "मे": 5, "जून": 6, "जुलै": 7,
	"ऑगस्ट": 8, "सप्टेंबर": 9, "ऑक्टोबर": 10, "नोव्हेंबर": 11, "डिसेंबर": 12,
}  # fmt: skip

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_MULTIPLIERS = (
	(re.compile(r"(?<![a-z])(?:cr|crs|crore|crores)(?![a-z])|कोटी"), Decimal(10**7)),
	(re.compile(r"(?<![a-z])(?:lakh|lakhs|lac|lacs|l)(?![a-z])|लाख"), Decimal(10**5)),
	(re.compile(r"(?<![a-z])(?:thousand|k)(?![a-z])|हजार"), Decimal(1000)),
)
_NONE = frozenset({"-", "--", "na", "n/a", "nil"})  # a source's way of saying there is no figure
_CURRENCY = re.compile(r"₹|(?<![a-z])(?:rs|inr|rupees)(?![a-z])\.?|रु\.?|रुपये|/-")


@dataclass
class Result:
	fields: dict = field(default_factory=dict)
	problems: list = field(default_factory=list)  # (field name, short reason)

	@property
	def ok(self) -> bool:
		return not self.problems


def _clean(value) -> str:
	return " ".join(str(value).split()) if value is not None else ""


def _digits(text) -> str:
	return text.translate(_DEVANAGARI_DIGITS)


# --- dates --------------------------------------------------------------------------------------------


def parse_date(value, today=None) -> str:
	"""Return YYYY-MM-DD or raise ValueError."""
	text = _digits(_clean(value)).lower().replace(",", " ")
	text = " ".join(text.split())
	day = month = year = None
	if m := re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text):
		year, month, day = (int(g) for g in m.groups())
	elif m := re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})", text):
		day, month, year = (int(g) for g in m.groups())
		if len(m.group(3)) == 2:
			year += 2000
	elif m := re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[ -]([^\d\s-]+)\.?[ -](\d{4})", text):
		day, month, year = int(m.group(1)), _MONTHS.get(m.group(2)), int(m.group(3))
	elif m := re.fullmatch(r"([^\d\s-]+)\.? (\d{1,2})(?:st|nd|rd|th)? (\d{4})", text):
		month, day, year = _MONTHS.get(m.group(1)), int(m.group(2)), int(m.group(3))
	if not (day and month and year):
		raise ValueError("not a date")
	try:
		parsed = date(year, month, day)
	except ValueError:
		raise ValueError("not a date") from None
	today = today or date.today()
	if parsed.year < MIN_YEAR or parsed > today + timedelta(days=366):
		raise ValueError("date out of range")
	return parsed.isoformat()


# --- money --------------------------------------------------------------------------------------------


def parse_money(value) -> float | None:
	"""Rupees as a number, None for an empty value, ValueError when it cannot be read."""
	if isinstance(value, bool):
		raise ValueError("not an amount")
	if isinstance(value, int | float):
		text = repr(value)
	else:
		text = _digits(_clean(value)).lower()
	text = _CURRENCY.sub(" ", text)
	if text.strip() in _NONE or not text.strip():
		return None
	multiplier = Decimal(1)
	for pattern, factor in _MULTIPLIERS:
		if pattern.search(text):
			multiplier = factor
			text = pattern.sub(" ", text)
			break
	text = text.replace(",", "").strip()
	if not re.fullmatch(r"\d+(?:\.\d+)?", text):
		raise ValueError("not an amount")
	try:
		amount = Decimal(text) * multiplier
	except InvalidOperation:
		raise ValueError("not an amount") from None
	return float(amount.quantize(Decimal("0.01")))


# --- area ---------------------------------------------------------------------------------------------

_AREA = re.compile(r"(\d+(?:\.\d+)?)")
_SQM = re.compile(
	r"sq\.?\s*(?:m|mt|mtr|mtrs|meter|meters|metre|metres)\b\.?|sqm|sqmt|चौ\.?\s*मी\.?|चौरस\s*मीटर"
)
_SQFT = re.compile(r"sq\.?\s*(?:ft|feet|foot)\b\.?|sqft|चौ\.?\s*फू[टत]\.?|चौरस\s*फूट")
_LAND = (
	(re.compile(r"gunth[ae]s?|गुंठे|गुंठा"), "guntha"),
	(re.compile(r"acres?|एकर"), "acre"),
	(re.compile(r"hectares?|हेक्टर"), "hectare"),
	(re.compile(r"(?<![a-z])ares?(?![a-z])|(?<!\S)आर(?!\S)"), "are"),
)
_SUPER = re.compile(r"super\s*-?\s*built\s*-?\s*up|सुपर\s*बिल्ट\s*अप")
_BUILT = re.compile(r"built\s*-?\s*up|बिल्ट\s*अप|बांधीव")
_KIND_WORDS = re.compile(r"carpet|कार्पेट|चटई|super|सुपर|built|बिल्ट|बांधीव|up\b|अप|area|क्षेत्र")


def _q2(number: Decimal) -> float:
	return float(number.quantize(Decimal("0.01")))


def parse_area(value) -> tuple[float, str] | None:
	"""(carpet square feet, the rule used) for an area, None for an empty value, ValueError otherwise."""
	if isinstance(value, bool):
		raise ValueError("not an area")
	if isinstance(value, int | float):
		text = repr(value)
	else:
		text = _digits(_clean(value)).lower().replace(",", "")
	if text.strip() in _NONE or not text.strip():
		return None
	found = _AREA.findall(text)
	if len(found) != 1:
		raise ValueError("not an area")
	number = Decimal(found[0])
	if number <= 0:
		raise ValueError("not an area")
	rest = text.replace(found[0], " ")
	kind = "super" if _SUPER.search(rest) else "built" if _BUILT.search(rest) else "carpet"
	for pattern, unit in _LAND:
		if pattern.search(rest):
			factor, name = LAND_UNITS[unit]
			return _q2(number * factor), f"{name} to sq ft x{factor}; land area, no carpet adjustment"
	if _SQM.search(rest):
		unit_text, to_sqft = "sq m to sq ft x10.7639", number * SQM_TO_SQFT
	elif _SQFT.search(rest) or not re.sub(r"[\W_]", "", _KIND_WORDS.sub("", rest)):
		unit_text, to_sqft = "sq ft as given", number
	else:
		raise ValueError("unknown area unit")
	if kind == "carpet":
		return _q2(to_sqft), f"{unit_text}; carpet area as given"
	divisor = BUILT_UP_TO_CARPET if kind == "built" else SUPER_TO_CARPET
	label = "built up" if kind == "built" else "super built up"
	return _q2(to_sqft / divisor), f"{unit_text}; {label} divided by {divisor} to carpet"


# --- the record ---------------------------------------------------------------------------------------


def normalise(record: dict, today=None) -> Result:
	"""Clean one raw record. Nothing is changed in `record`."""
	result = Result()
	out = {"source_record_id": _clean(record.get("source_record_id"))}
	try:
		out["registration_date"] = parse_date(record.get("registration_date"), today)
	except ValueError as e:
		result.problems.append(("registration_date", str(e)))
	originals = {}
	for name in TEXT_FIELDS:
		original = _clean(record.get(name))
		originals[name] = original
		out[f"{name}_en"] = marathi.to_english(original)
	out["survey_number"] = _digits(_clean(record.get("survey_number")))
	originals["survey_number"] = _clean(record.get("survey_number"))
	for name in MONEY_FIELDS:
		try:
			out[name] = parse_money(record.get(name))
		except ValueError as e:
			result.problems.append((name, str(e)))
	try:
		area = parse_area(record.get("area_sqft"))
	except ValueError as e:
		result.problems.append(("area_sqft", str(e)))
		area = None
	out["carpet_area_sqft"], out["area_rule"] = area if area else (None, "")
	originals["area_sqft"] = _clean(record.get("area_sqft"))
	if not result.problems:
		result.fields = {**out, "originals": originals, "rules_version": RULES_VERSION}
	return result
