"""A fake source adapter (SOS-P3-01): feeds tests and a first look without any real source.

It serves the records it is given, in batches of `batch_size`, and can be told to fail at a batch to
test a failed run. It is not in the list a Market Source chooses from.
"""

from sellos.intel import adapters
from sellos.intel.adapters import Batch, SourceAdapter, SourceError


class FakeSource(SourceAdapter):
	kind = "Fake"

	def __init__(self, records=None, batch_size=2, fail_at_batch=None):
		super().__init__()
		self.records = list(records or [])
		self.batch_size = batch_size
		self.fail_at_batch = fail_at_batch

	def fetch_batch(self, cursor=None) -> Batch:
		start = int(cursor or 0)
		if self.fail_at_batch is not None and start // self.batch_size == self.fail_at_batch:
			raise SourceError("The fake source stopped.")
		end = start + self.batch_size
		return Batch(records=self.records[start:end], next_cursor=end if end < len(self.records) else None)

	def map_fields(self, raw) -> dict:
		return adapters.to_canonical(raw)
