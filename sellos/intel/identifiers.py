"""Which identifiers a building shows (SOS-P3-04). They follow the building's country and come from the data file
`fixtures/identifier_profiles.json`, never from code. Every identifier is stored whatever the country, and none is
required. Data adapters stay pluggable by country (SOS-P3-01); this only says what to show."""

import json
from pathlib import Path

PROFILES = Path(__file__).parent / "fixtures" / "identifier_profiles.json"
EVERY_IDENTIFIER = (
	"cts_numbers",
	"village",
	"tahsil",
	"district",
	"rera_number",
	"uae_community",
	"dld_number",
	"au_lot",
	"au_plan",
)


def _profiles() -> dict:
	return json.loads(PROFILES.read_text(encoding="utf-8"))


def default_country() -> str:
	return _profiles()["default_country"]


def identifier_fields(country) -> list[str]:
	"""The identifiers to show for a building of this country. A country with no profile shows the default's."""
	profiles = _profiles()
	return list(
		profiles["countries"].get(country or "") or profiles["countries"][profiles["default_country"]]
	)


def profiles() -> dict:
	"""Every country's identifier fields, and the default country, for a screen that shows them as the country changes."""
	data = _profiles()
	return {"default_country": data["default_country"], "countries": data["countries"]}
