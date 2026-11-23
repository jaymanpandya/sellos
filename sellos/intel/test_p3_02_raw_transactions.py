"""SOS-P3-02: the raw transaction table stores each record untouched, with its source, fetch time and
hash, never twice, on the control site, read only through a role checked API."""

import json
import uuid
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.matrix import MATRIX
from sellos.access.registry import allowed_roles
from sellos.access.roles import PLATFORM_ADMIN, ensure_roles
from sellos.intel import api, raw_store, runner
from sellos.intel.fake_source import FakeSource
from sellos.intel.test_p3_01_source_adapter import record
from sellos.testing.users import TEST_USERS, create_test_users

RAW = "Raw Transaction"


class RawCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		self.tag = uuid.uuid4().hex[:8]
		self.addCleanup(self._cleanup)
		self.source = self.make_source("a")

	def _cleanup(self):
		frappe.set_user("Administrator")
		runner.set_sink(raw_store.store)
		for name in frappe.get_all(
			"Market Source", filters={"source_name": ["like", f"t{self.tag}%"]}, pluck="name"
		):
			for run in frappe.get_all("Market Source Run", filters={"source": name}, pluck="name"):
				frappe.db.delete("App Notification", {"dedupe_key": ["like", f"market-run-failed:{run}:%"]})
			frappe.db.delete(RAW, {"source": name})
			frappe.db.delete("Market Source Run", {"source": name})
			frappe.db.delete("Market Source", {"name": name})

	def make_source(self, suffix):
		return (
			frappe.get_doc(
				{
					"doctype": "Market Source",
					"source_name": f"t{self.tag}{suffix}",
					"adapter": "File",
					"file_name": "x.csv",
					"frequency": "Daily",
					"enabled": 1,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def rows(self, source=None):
		return frappe.get_all(RAW, filters={"source": source or self.source}, fields=["*"])

	def ingest(self, records, source=None):
		return runner.run_adapter(source or self.source, FakeSource(records, batch_size=2))


class TestRawTransactions(RawCase):
	def test_original_fields_are_unchanged(self):
		original = record(
			1, area_sqft="850", consideration_amount="1,25,00,000", registration_date="05/03/2026"
		)
		self.ingest([original])
		(row,) = self.rows()
		self.assertEqual(json.loads(row.raw_record), original)  # strings, commas and date format kept
		self.assertEqual(row.source_record_id, "R1")

	def test_source_fetch_time_and_hash_are_stored(self):
		original = record(2)
		self.ingest([original])
		(row,) = self.rows()
		self.assertEqual(row.source, self.source)
		self.assertIsNotNone(row.fetch_time)
		self.assertEqual(row.record_hash, raw_store.record_hash(original))
		self.assertEqual(len(row.record_hash), 64)

	def test_ingesting_the_same_batch_twice_makes_no_duplicates(self):
		batch = [record(i) for i in range(5)]
		self.ingest(batch)
		self.ingest(batch)
		self.assertEqual(len(self.rows()), 5)
		self.assertEqual(raw_store.store(self.source, [(r, r) for r in batch]), 0)

	def test_a_corrected_record_is_stored_beside_the_original(self):
		self.ingest([record(3)])
		self.ingest([record(3, consideration_amount="1,40,00,000")])
		rows = self.rows()
		self.assertEqual(len(rows), 2)
		self.assertEqual(len({r.record_hash for r in rows}), 2)

	def test_the_same_record_from_two_sources_is_kept_for_each(self):
		other = self.make_source("b")
		self.ingest([record(4)])
		self.ingest([record(4)], other)
		self.assertEqual((len(self.rows()), len(self.rows(other))), (1, 1))

	def test_other_columns_are_dropped_and_rejected_records_are_not_stored(self):
		self.ingest([record(5, owner="A Person"), record(6, registration_date="never")])
		(row,) = self.rows()
		self.assertNotIn("owner", json.loads(row.raw_record))
		self.assertEqual(row.source_record_id, "R5")

	def test_a_raw_row_is_never_changed_or_deleted(self):
		self.ingest([record(7)])
		doc = frappe.get_doc(RAW, self.rows()[0].name)
		doc.raw_record = "{}"
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(RAW, doc.name, force=True)
		self.assertEqual(len(self.rows()), 1)

	def test_cleared_sink_stores_nothing(self):
		runner.set_sink(None)
		self.assertEqual(self.ingest([record(8)])["accepted"], 1)
		self.assertEqual(self.rows(), [])


class TestRawTransactionApi(RawCase):
	"""SOS-P3-02: company sites read the table only through the role checked API."""

	def test_the_method_is_declared_for_the_platform_admin_only_and_in_the_matrix(self):
		path = "sellos.intel.api.list_raw_transactions"
		self.assertEqual(allowed_roles(path), frozenset({PLATFORM_ADMIN}))
		self.assertEqual(MATRIX[path], frozenset({PLATFORM_ADMIN}))
		perms = frappe.get_meta(RAW).permissions
		self.assertEqual(
			[(p.role, bool(p.write), bool(p.create), bool(p.delete)) for p in perms],
			[(PLATFORM_ADMIN, False, False, False)],
		)

	def test_it_answers_on_the_control_site_with_the_records_as_stored(self):
		self.ingest([record(i) for i in range(3)])
		with patch.object(api, "is_control_site", return_value=True):
			page = api.list_raw_transactions(source=self.source, page_length=2)
			rest = api.list_raw_transactions(source=self.source, start=2, page_length=2)
		self.assertEqual((len(page["rows"]), page["has_more"]), (2, True))
		self.assertEqual((len(rest["rows"]), rest["has_more"]), (1, False))
		first = page["rows"][0]
		self.assertEqual(first["record"], record(0))
		self.assertEqual(first["record_hash"], raw_store.record_hash(record(0)))
		self.assertEqual(
			set(first), {"name", "source", "source_record_id", "fetch_time", "record_hash", "record"}
		)

	def test_the_page_is_capped(self):
		with patch.object(api, "is_control_site", return_value=True):
			with patch.object(api.frappe, "get_all", return_value=[]) as get_all:
				api.list_raw_transactions(page_length=10**6)
		self.assertEqual(get_all.call_args.kwargs["limit"], api.MAX_PAGE + 1)

	def test_a_company_site_is_refused(self):
		with patch.object(api, "is_control_site", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				api.list_raw_transactions()

	def test_other_roles_are_refused(self):
		for key in ("company_admin", "agent", "client", "channel_partner"):
			frappe.set_user(TEST_USERS[key]["email"])
			with self.subTest(role=key), patch.object(api, "is_control_site", return_value=True):
				with self.assertRaises(frappe.PermissionError):
					api.list_raw_transactions()
		frappe.set_user(TEST_USERS["platform_admin"]["email"])
		with patch.object(api, "is_control_site", return_value=True):
			self.assertEqual(api.list_raw_transactions(source=self.source)["rows"], [])
