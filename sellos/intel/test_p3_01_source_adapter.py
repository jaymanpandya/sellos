"""SOS-P3-01: the source adapter interface, the file adapter, the fake source, scheduled runs and
failure alerts."""

import json
import uuid
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from sellos.access.roles import ensure_roles
from sellos.intel import adapters, file_adapter, runner
from sellos.intel.fake_source import FakeSource
from sellos.testing.users import TEST_USERS, create_test_users

PLATFORM_ADMIN_EMAIL = TEST_USERS["platform_admin"]["email"]
COLUMNS = ",".join(adapters.FIELDS)


def record(n, **over):
	row = {
		"source_record_id": f"R{n}",
		"registration_date": "2026-03-05",
		"document_type": "Sale deed",
		"sro_office": "Andheri 3",
		"district": "Mumbai Suburban",
		"locality": "Lokhandwala",
		"property_description": "Flat 12, Sea View",
		"survey_number": "44/2",
		"area_sqft": "850",
		"consideration_amount": "1,25,00,000",
		"market_value": "1,30,00,000",
		"stamp_duty": "7,80,000",
	}
	row.update(over)
	return row


class SourceCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		self.tag = uuid.uuid4().hex[:8]
		self.files = []
		self.addCleanup(self._cleanup)

	def _cleanup(self):
		frappe.set_user("Administrator")
		runner.set_sink(None)
		for path in self.files:
			path.unlink(missing_ok=True)
		for name in frappe.get_all(
			"Market Source", filters={"source_name": ["like", f"t{self.tag}%"]}, pluck="name"
		):
			for run in frappe.get_all("Market Source Run", filters={"source": name}, pluck="name"):
				frappe.db.delete("App Notification", {"dedupe_key": ["like", f"market-run-failed:{run}:%"]})
			frappe.db.delete("Raw Transaction", {"source": name})  # SOS-P3-02
			frappe.db.delete("Market Source Run", {"source": name})
			frappe.db.delete("Market Source", {"name": name})

	def drop_file(self, suffix, text):
		folder = Path(frappe.get_site_path("private", "files"))
		folder.mkdir(parents=True, exist_ok=True)
		path = folder / f"t{self.tag}_{len(self.files)}{suffix}"
		path.write_text(text, encoding="utf-8")
		self.files.append(path)
		return path.name

	def make_source(self, file_name, suffix="", **over):
		doc = {
			"doctype": "Market Source",
			"source_name": f"t{self.tag}{suffix}",
			"adapter": "File",
			"file_name": file_name,
			"frequency": "Daily",
			"enabled": 1,
		}
		doc.update(over)
		return frappe.get_doc(doc).insert(ignore_permissions=True).name

	def admin_alerts(self):
		return frappe.get_all(
			"App Notification",
			filters={"recipient": PLATFORM_ADMIN_EMAIL, "event": runner.MARKET_RUN_FAILED},
			pluck="message",
		)


class TestContract(SourceCase):
	"""SOS-P3-01: contract tests with sample payloads."""

	def test_interface_is_documented(self):
		self.assertIn("fetch_batch", adapters.__doc__)
		self.assertIn("map_fields", adapters.__doc__)
		for name in adapters.FIELDS:
			self.assertIn(name, adapters.__doc__)

	def test_base_class_is_abstract(self):
		with self.assertRaises(NotImplementedError):
			adapters.SourceAdapter().fetch_batch()
		with self.assertRaises(NotImplementedError):
			adapters.SourceAdapter().map_fields({})

	def test_file_adapter_registered(self):
		self.assertIn("File", adapters.kinds())
		self.assertIsInstance(adapters.get_adapter("File", {}), file_adapter.FileAdapter)
		with self.assertRaises(adapters.SourceError):
			adapters.get_adapter("Nothing")

	def test_mapping_cleans_values(self):
		mapped = adapters.to_canonical(record(1, registration_date="05/03/2026", extra="x"))
		self.assertEqual(mapped["registration_date"], "2026-03-05")
		self.assertEqual(mapped["consideration_amount"], 12500000.0)
		self.assertEqual(mapped["area_sqft"], 850.0)
		self.assertNotIn("extra", mapped)
		self.assertEqual(set(mapped), set(adapters.FIELDS))

	def test_mapping_refuses_bad_records(self):
		for bad in (
			record(1, source_record_id=""),
			record(1, registration_date="next week"),
			record(1, area_sqft="big"),
			record(1, stamp_duty="-5"),
		):
			with self.assertRaises(adapters.RecordError):
				adapters.to_canonical(bad)

	def test_fake_source_serves_batches(self):
		fake = FakeSource([record(i) for i in range(5)], batch_size=2)
		first = fake.fetch_batch()
		self.assertEqual(len(first.records), 2)
		self.assertEqual(first.next_cursor, 2)
		last = fake.fetch_batch(4)
		self.assertEqual(len(last.records), 1)
		self.assertIsNone(last.next_cursor)

	def test_file_adapter_csv_batches_and_ignores_extra_columns(self):
		rows = [record(i) for i in range(file_adapter.BATCH_SIZE + 3)]
		lines = [COLUMNS + ",owner"] + [",".join(f'"{r[c]}"' for c in adapters.FIELDS) + ',"x"' for r in rows]
		adapter = file_adapter.FileAdapter({"file_name": self.drop_file(".csv", "\n".join(lines))})
		first = adapter.fetch_batch()
		self.assertEqual(len(first.records), file_adapter.BATCH_SIZE)
		second = adapter.fetch_batch(first.next_cursor)
		self.assertEqual(len(second.records), 3)
		self.assertIsNone(second.next_cursor)
		self.assertEqual(
			adapter.map_fields(second.records[0])["source_record_id"], f"R{file_adapter.BATCH_SIZE}"
		)

	def test_file_adapter_json_both_shapes(self):
		rows = [record(1), record(2)]
		for body in (json.dumps(rows), json.dumps({"records": rows})):
			adapter = file_adapter.FileAdapter({"file_name": self.drop_file(".json", body)})
			self.assertEqual(len(adapter.fetch_batch().records), 2)

	def test_file_adapter_refuses_bad_files(self):
		for config in (
			{"file_name": "../../site_config.json"},
			{"file_name": "/etc/passwd"},
			{"file_name": "missing.csv"},
			{"file_name": ""},
		):
			with self.assertRaises(adapters.SourceError):
				file_adapter.FileAdapter(config).fetch_batch()
		for suffix, body in (
			(".json", "{not json"),
			(".json", '"text"'),
			(".csv", "a,b\n1,2"),
			(".txt", "x"),
		):
			with self.assertRaises(adapters.SourceError):
				file_adapter.FileAdapter({"file_name": self.drop_file(suffix, body)}).fetch_batch()


class TestRuns(SourceCase):
	"""SOS-P3-01: runs record their result, are scheduled, and a failed run raises an alert."""

	def test_fake_run_succeeds_and_hands_records_to_sink(self):
		stored = []
		before = len(self.admin_alerts())
		runner.set_sink(lambda name, rows: stored.extend(rows))
		name = self.make_source(".")
		fake = FakeSource([record(i) for i in range(5)] + [record(9, registration_date="x")], batch_size=2)
		result = runner.run_adapter(name, fake)
		self.assertEqual(
			(result["status"], result["read"], result["accepted"], result["rejected"]), ("Succeeded", 6, 5, 1)
		)
		self.assertEqual(len(stored), 5)
		run = frappe.get_doc("Market Source Run", result["run"])
		self.assertEqual(run.batches, 3)
		self.assertIn("record 6", run.rejects)
		self.assertEqual(len(self.admin_alerts()), before)

	def test_failed_run_raises_alert_once_per_run(self):
		name = self.make_source(".")
		before = len(self.admin_alerts())
		result = runner.run_adapter(
			name, FakeSource([record(i) for i in range(4)], batch_size=2, fail_at_batch=1)
		)
		self.assertEqual(result["status"], "Failed")
		self.assertEqual(result["error"], "The fake source stopped.")
		alerts = self.admin_alerts()
		self.assertEqual(len(alerts), before + 1)
		self.assertIn("The fake source stopped.", alerts)
		self.assertEqual(frappe.db.get_value("Market Source Run", result["run"], "status"), "Failed")
		runner.alert_failure(name, result["run"], result["error"])
		self.assertEqual(len(self.admin_alerts()), before + 1)  # the same run alerts once

	def test_all_rejected_is_a_failure(self):
		name = self.make_source(".")
		result = runner.run_adapter(name, FakeSource([record(1, registration_date="x")]))
		self.assertEqual(result["status"], "Failed")
		self.assertIn("rejected", result["error"])

	def test_empty_source_succeeds(self):
		name = self.make_source(".")
		self.assertEqual(runner.run_adapter(name, FakeSource([]))["status"], "Succeeded")

	def test_run_source_with_file_sets_state(self):
		file_name = self.drop_file(".json", json.dumps([record(1), record(2)]))
		name = self.make_source(file_name)
		now = now_datetime()
		result = runner.run_source(name, now=now)
		self.assertEqual(result["status"], "Succeeded")
		source = frappe.get_doc("Market Source", name)
		self.assertEqual(source.last_status, "Succeeded")
		self.assertEqual(source.consecutive_failures, 0)
		self.assertGreater(source.next_run_at, now)

	def test_run_source_missing_file_fails_and_alerts(self):
		name = self.make_source("gone.csv")
		before = len(self.admin_alerts())
		result = runner.run_source(name)
		self.assertEqual(result["status"], "Failed")
		self.assertEqual(len(self.admin_alerts()), before + 1)
		self.assertEqual(frappe.db.get_value("Market Source", name, "consecutive_failures"), 1)
		runner.run_source(name)
		self.assertEqual(frappe.db.get_value("Market Source", name, "consecutive_failures"), 2)
		self.assertNotIn("/", frappe.db.get_value("Market Source Run", {"source": name}, "error"))

	def test_unexpected_error_is_a_failed_run_without_details(self):
		name = self.make_source(".")
		fake = FakeSource([record(1)])
		with patch.object(fake, "fetch_batch", side_effect=RuntimeError("secret path /x")):
			result = runner.run_adapter(name, fake)
		self.assertEqual(result["status"], "Failed")
		self.assertNotIn("secret", result["error"])

	def test_scheduler_runs_only_due_sources(self):
		file_name = self.drop_file(".json", json.dumps([record(1)]))
		due = self.make_source(file_name, "a")
		off = self.make_source(file_name, "b", enabled=0)
		later = self.make_source(file_name, "c")
		frappe.db.set_value("Market Source", later, "next_run_at", add_to_date(now_datetime(), hours=5))
		ran = runner.run_due_sources()
		names = {r["run"] for r in ran}
		sources = {frappe.db.get_value("Market Source Run", n, "source") for n in names}
		self.assertIn(due, sources)
		self.assertNotIn(off, sources)
		self.assertNotIn(later, sources)
		again = runner.run_due_sources()
		self.assertNotIn(due, {frappe.db.get_value("Market Source Run", r["run"], "source") for r in again})

	def test_schedule_is_hooked_and_on_control_site_only(self):
		self.assertIn("sellos.intel.runner.run_scheduled", frappe.get_hooks("scheduler_events")["hourly"])
		with (
			patch.object(runner, "is_control_site", return_value=False),
			patch.object(runner, "run_due_sources") as run,
		):
			runner.run_scheduled()
			run.assert_not_called()
		with (
			patch.object(runner, "is_control_site", return_value=True),
			patch.object(runner, "run_due_sources") as run,
		):
			runner.run_scheduled()
			run.assert_called_once()

	def test_source_and_run_are_never_deleted(self):
		name = self.make_source(".")
		result = runner.run_adapter(name, FakeSource([]))
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Market Source Run", result["run"], force=True)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Market Source", name, force=True)

	def test_source_needs_a_file_and_a_known_adapter(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_source("", "x")
