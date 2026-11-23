"""Run a market data source and raise an alert when it fails (SOS-P3-01).

`run_source(name)` reads every batch of a Market Source through its adapter, maps each record to the
canonical shape (`sellos.intel.adapters`) and hands the good ones to the sink. One Market Source Run
records the result. `run_scheduled`, hooked to the hourly scheduler, runs the sources that are due, on
the control site only (market data lives there).

* A record that cannot be mapped is rejected and counted; the first `REJECT_SAMPLE` reasons are kept.
* A run fails when the source cannot be read, or when it read records and not one was usable. A failed
  run alerts every enabled Platform Admin once (App Notification, event "Market data run failed").
  The alert carries the source name and a short reason, never a path, a stack or a secret.
* The sink is where accepted records go. SOS-P3-02 (the raw transaction table) registers its sink with
  `set_sink`; until then records are counted and not stored.
* Nothing here solves a captcha or goes round an access control; an adapter only reads what it is given.
"""

import frappe
from frappe.utils import add_to_date, now_datetime

from sellos.access.roles import PLATFORM_ADMIN
from sellos.crm import notifications
from sellos.intel import adapters
from sellos.intel.adapters import RecordError, SourceError
from sellos.intel.file_adapter import FileAdapter
from sellos.provisioning.control import is_control_site

SOURCE = "Market Source"
RUN = "Market Source Run"
MARKET_RUN_FAILED = "Market data run failed"
REJECT_SAMPLE = 20
INTERVALS = {"Hourly": {"hours": 1}, "Daily": {"days": 1}, "Weekly": {"weeks": 1}}
MAX_BATCHES = 10_000  # a source that never ends its cursor stops here

# The adapters a Market Source can choose; importing them registers them.
BUILT_IN_ADAPTERS = (FileAdapter,)

_sink = None


def set_sink(sink):
	"""Register the function that stores accepted records: `sink(source_name, records)`. None clears it."""
	global _sink
	_sink = sink


def _store(source_name, records):
	if _sink and records:
		_sink(source_name, records)


def _reason(error) -> str:
	return str(error)[:300] or "The run stopped."


def _platform_admins() -> list[str]:
	users = frappe.get_all("Has Role", filters={"role": PLATFORM_ADMIN, "parenttype": "User"}, pluck="parent")
	return frappe.get_all("User", filters={"name": ["in", users or [""]], "enabled": 1}, pluck="name")


def alert_failure(source_name, run_name, reason) -> int:
	"""Tell every enabled Platform Admin that a run failed. One notification each, once per run."""
	sent = 0
	for user in _platform_admins():
		made = notifications.notify(
			user,
			MARKET_RUN_FAILED,
			f"Market data run failed: {source_name}",
			message=reason,
			dedupe_key=f"market-run-failed:{run_name}:{user}",
		)
		sent += 1 if made else 0
	return sent


def run_adapter(source_name, adapter, now=None) -> dict:
	"""Run one adapter for the named Market Source and record the run. Returns the run's summary.
	This is the shared core: `run_source` builds the adapter from the source, tests pass a fake."""
	started = now or now_datetime()
	run = frappe.get_doc({"doctype": RUN, "source": source_name, "status": "Running", "started_at": started})
	run.insert(ignore_permissions=True)
	read = accepted = rejected = batches = 0
	rejects, error = [], None
	try:
		cursor = None
		while batches < MAX_BATCHES:
			batch = adapter.fetch_batch(cursor)
			batches += 1
			good = []
			for raw in batch.records:
				read += 1
				try:
					good.append(adapter.map_fields(raw))
				except RecordError as e:
					rejected += 1
					if len(rejects) < REJECT_SAMPLE:
						rejects.append(f"record {read}: {_reason(e)}")
			_store(source_name, good)
			accepted += len(good)
			cursor = batch.next_cursor
			if cursor is None:
				break
		else:
			raise SourceError("The source did not end.")
		if read and not accepted:
			raise SourceError("Every record in the source was rejected.")
	except SourceError as e:
		error = _reason(e)
	except Exception:
		frappe.log_error(title="Market source run failed")
		error = "The source could not be read."
	run.update(
		{
			"status": "Failed" if error else "Succeeded",
			"finished_at": now_datetime(),
			"batches": batches,
			"records_read": read,
			"records_accepted": accepted,
			"records_rejected": rejected,
			"error": error,
			"rejects": "\n".join(rejects),
		}
	)
	run.save(ignore_permissions=True)
	if error:
		alert_failure(source_name, run.name, error)
	return {
		"run": run.name,
		"status": run.status,
		"read": read,
		"accepted": accepted,
		"rejected": rejected,
		"error": error,
	}


def run_source(source_name, now=None) -> dict:
	"""Run one Market Source through the adapter it names, then set its last status and next run."""
	source = frappe.get_doc(SOURCE, source_name)
	try:
		adapter = adapters.get_adapter(source.adapter, {"file_name": source.file_name})
	except SourceError as e:
		adapter = _Broken(str(e))
	result = run_adapter(source_name, adapter, now=now)
	failed = result["status"] == "Failed"
	source.reload()
	source.last_run_at = now or now_datetime()
	source.last_status = result["status"]
	source.consecutive_failures = (source.consecutive_failures or 0) + 1 if failed else 0
	source.next_run_at = add_to_date(source.last_run_at, **INTERVALS[source.frequency])
	source.save(ignore_permissions=True)
	return result


class _Broken(adapters.SourceAdapter):
	"""Stands in for an adapter that does not exist, so the failure is a recorded, alerted run."""

	kind = "Broken"

	def __init__(self, message):
		super().__init__()
		self.message = message

	def fetch_batch(self, cursor=None):
		raise SourceError(self.message)


def run_due_sources(now=None) -> list[dict]:
	"""Run every enabled source whose next run has come (or that never ran). Safe to call again."""
	now = now or now_datetime()
	due = frappe.get_all(
		SOURCE,
		filters={"enabled": 1},
		or_filters=[["next_run_at", "is", "not set"], ["next_run_at", "<=", now]],
		pluck="name",
		order_by="creation asc",
	)
	return [run_source(name, now=now) for name in due]


def run_scheduled():
	"""Hourly scheduler hook (hooks.py). Market data lives on the control site only."""
	if is_control_site():
		run_due_sources()
