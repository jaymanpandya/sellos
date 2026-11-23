"""SOS-P3-03: the normaliser gives English fields with the original kept, standard dates, rupees and
carpet square feet with the rule recorded, and puts records it cannot read on the review list."""

import json
import uuid
from datetime import date
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from sellos.intel import marathi, normalise_store, normaliser, raw_store, runner
from sellos.intel.test_p3_01_source_adapter import record

GOLDEN = Path(__file__).with_name("golden_normaliser.json")
TODAY = date(2026, 11, 24)
FIELDS = (
	"registration_date",
	"document_type_en",
	"sro_office_en",
	"district_en",
	"locality_en",
	"property_description_en",
	"survey_number",
	"carpet_area_sqft",
	"consideration_amount",
	"market_value",
	"stamp_duty",
)


def golden():
	return json.loads(GOLDEN.read_text(encoding="utf-8"))["records"]


class TestGoldenFile(UnitTestCase):
	"""The gate's check: 100 verified records, at least 95 percent of fields correct."""

	def test_the_golden_file_has_100_records(self):
		self.assertEqual(len(golden()), 100)

	def test_at_least_95_percent_of_fields_are_correct(self):
		right = total = 0
		wrong = []
		for item in golden():
			if "expect" not in item:
				continue
			fields = normaliser.normalise(item["raw"], TODAY).fields
			for name in FIELDS:
				total += 1
				if fields.get(name) == item["expect"][name]:
					right += 1
				else:
					wrong.append(
						(item["raw"]["source_record_id"], name, fields.get(name), item["expect"][name])
					)
		self.assertGreaterEqual(right / total, 0.95, wrong[:20])

	def test_every_unreadable_golden_record_is_sent_to_review_with_its_field(self):
		bad = [i for i in golden() if "review" in i]
		self.assertEqual(len(bad), 8)
		for item in bad:
			result = normaliser.normalise(item["raw"], TODAY)
			self.assertFalse(result.ok, item["raw"]["source_record_id"])
			self.assertEqual({n for n, _ in result.problems}, set(item["review"]))
			self.assertEqual(result.fields, {})


class TestNormaliserRules(UnitTestCase):
	def test_dates_become_iso(self):
		for text in (
			"15-01-2024",
			"15/01/2024",
			"15.01.2024",
			"15 Jan 2024",
			"January 15, 2024",
			"१५/०१/२०२४",
		):
			self.assertEqual(normaliser.parse_date(text, TODAY), "2024-01-15", text)
		for text in ("31/02/2024", "1950-01-01", "2030-01-01", "soon"):
			with self.assertRaises(ValueError):
				normaliser.parse_date(text, TODAY)

	def test_money(self):
		cases = {
			"1,25,00,000": 12500000.0,
			"₹ 1.25 Cr": 12500000.0,
			"Rs. 45,00,000/-": 4500000.0,
			"४५ लाख": 4500000.0,
			"2.5 कोटी": 25000000.0,
			"": None,
			"-": None,
			12500000: 12500000.0,
		}
		for text, expected in cases.items():
			self.assertEqual(normaliser.parse_money(text), expected, text)
		with self.assertRaises(ValueError):
			normaliser.parse_money("a lot")

	def test_area_conversion_records_the_rule(self):
		self.assertEqual(normaliser.parse_area("75 sq.m")[0], 807.29)
		self.assertIn("x10.7639", normaliser.parse_area("75 sq.m")[1])
		self.assertEqual(normaliser.parse_area("1200 sqft built up")[0], 1000.0)
		self.assertIn("built up divided by 1.2", normaliser.parse_area("1200 sqft built up")[1])
		self.assertEqual(normaliser.parse_area("1500 sq ft super built up")[0], 1071.43)
		self.assertEqual(normaliser.parse_area("2 guntha")[0], 2178.0)
		self.assertIn("carpet area as given", normaliser.parse_area("850")[1])
		self.assertIsNone(normaliser.parse_area(""))
		for text in ("500 yards", "large plot", "0", "10 and 20 sqft"):
			with self.assertRaises(ValueError, msg=text):
				normaliser.parse_area(text)

	def test_marathi_to_english_keeps_other_text(self):
		self.assertEqual(marathi.to_english("Flat 12, Pune"), "Flat 12, Pune")
		self.assertEqual(marathi.to_english("सदनिका क्र. 5, कोथरूड"), "Flat No. 5, Kothrud")
		self.assertEqual(marathi.to_english("शिवाजीनगर"), "Shivajinagar")
		self.assertEqual(marathi.transliterate("लक्ष्मी"), "lakshmi")
		self.assertEqual(marathi.transliterate("ओंकार"), "onkar")

	def test_the_original_is_kept_in_the_result_and_the_input_is_unchanged(self):
		raw = {
			"source_record_id": "X1",
			"registration_date": "१५/०१/२०२४",
			"locality": "कोथरूड",
			"area_sqft": "५० चौ.मी.",
		}
		before = dict(raw)
		result = normaliser.normalise(raw, TODAY)
		self.assertEqual(raw, before)
		self.assertEqual(result.fields["locality_en"], "Kothrud")
		self.assertEqual(result.fields["originals"]["locality"], "कोथरूड")
		self.assertEqual(result.fields["originals"]["area_sqft"], "५० चौ.मी.")
		self.assertEqual(result.fields["rules_version"], normaliser.RULES_VERSION)


class TestNormaliseStore(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.tag = uuid.uuid4().hex[:8]
		self.addCleanup(self._cleanup)
		self.source = (
			frappe.get_doc(
				{
					"doctype": "Market Source",
					"source_name": f"t{self.tag}",
					"adapter": "File",
					"file_name": "x.csv",
					"frequency": "Daily",
					"enabled": 1,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def _cleanup(self):
		frappe.set_user("Administrator")
		for doctype in (normalise_store.NORMAL, normalise_store.REVIEW, normalise_store.RAW):
			frappe.db.delete(doctype, {"source": self.source})
		frappe.db.delete("Market Source Run", {"source": self.source})
		frappe.db.delete("Market Source", {"name": self.source})

	def store(self, *records):
		raw_store.store(self.source, [(r, r) for r in records])

	def test_clean_records_are_written_and_the_raw_row_is_untouched(self):
		original = record(1, locality="कोथरूड", area_sqft="५० चौ.मी.", consideration_amount="४५ लाख")
		self.store(original)
		counts = normalise_store.normalise_pending(self.source, today=TODAY)
		self.assertEqual(counts, {"clean": 1, "review": 0})
		(raw,) = frappe.get_all(normalise_store.RAW, filters={"source": self.source}, fields=["*"])
		self.assertEqual(json.loads(raw.raw_record)["locality"], "कोथरूड")
		doc = frappe.get_doc(normalise_store.NORMAL, raw.name)
		self.assertEqual(doc.locality_en, "Kothrud")
		self.assertEqual(doc.consideration_amount, 4500000)
		self.assertEqual(doc.carpet_area_sqft, 538.2)
		self.assertIn("sq m to sq ft", doc.area_rule)
		self.assertEqual(json.loads(doc.original_fields)["locality"], "कोथरूड")

	def test_an_unreadable_record_goes_to_the_review_list_and_is_resolved_later(self):
		self.store(record(2, consideration_amount="TBD"))
		self.assertEqual(normalise_store.normalise_pending(self.source), {"clean": 0, "review": 1})
		(name,) = frappe.get_all(normalise_store.REVIEW, filters={"source": self.source}, pluck="name")
		review = frappe.get_doc(normalise_store.REVIEW, name)
		self.assertEqual(review.status, "Open")
		self.assertIn("consideration_amount", review.problems)
		self.assertFalse(frappe.db.exists(normalise_store.NORMAL, name))
		# the same rules find nothing new, so a repeat run leaves it alone
		self.assertEqual(normalise_store.normalise_pending(self.source), {"clean": 0, "review": 0})
		# a rules change that can read it resolves it
		with_patch = normaliser.parse_money
		normaliser.parse_money = lambda value: 1.0
		self.addCleanup(setattr, normaliser, "parse_money", with_patch)
		self.assertEqual(
			normalise_store.normalise_pending(self.source, force=True), {"clean": 1, "review": 0}
		)
		self.assertEqual(frappe.db.get_value(normalise_store.REVIEW, name, "status"), "Resolved")
		self.assertTrue(frappe.db.exists(normalise_store.NORMAL, name))

	def test_running_twice_makes_no_duplicates(self):
		self.store(record(3), record(4))
		normalise_store.normalise_pending(self.source)
		self.assertEqual(normalise_store.normalise_pending(self.source), {"clean": 0, "review": 0})
		self.assertEqual(frappe.db.count(normalise_store.NORMAL, {"source": self.source}), 2)
		normalise_store.normalise_pending(self.source, force=True)
		self.assertEqual(frappe.db.count(normalise_store.NORMAL, {"source": self.source}), 2)

	def test_a_normalised_row_is_never_deleted(self):
		self.store(record(5))
		normalise_store.normalise_pending(self.source)
		(name,) = frappe.get_all(normalise_store.NORMAL, filters={"source": self.source}, pluck="name")
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(normalise_store.NORMAL, name, force=True)
