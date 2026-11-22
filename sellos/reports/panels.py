"""Report panels that wait for data another task builds (SOS-P5-03).

The Channel Partner's deals and commission statements, and the Platform Admin's revenue, churn and failed
payment panels, read records that do not exist until their own tasks (SOS-P4-06, SOS-P7-04 and the billing
tasks of P6) are done. Each panel names the function that reads its records. While that module or function
does not exist the panel is shown as waiting, with a plain message, and the day the task adds it the panel
switches on with no change here.

A reader is called as `reader(start, end, **context)` with two dates, and returns
`{"columns": [{"field", "label", "unit"}], "rows": [{"key", "label", "values": [...]}], "stats": [{"label",
"value", "unit"}]}`. A partner's reader also gets `firm` (the partner code) and `user`, and must read only
that partner's records. A reader returns no phone number.
"""

import importlib


def reader(path):
	"""The function at a dotted path, or None while its module or the function is not there yet."""
	module, _dot, name = path.rpartition(".")
	try:
		function = getattr(importlib.import_module(module), name, None)
	except ModuleNotFoundError as error:
		# Only a module that is not built yet means "waiting". A broken import inside it is a real error.
		if error.name and (module == error.name or module.startswith(f"{error.name}.")):
			return None
		raise
	return function if callable(function) else None


def run_panel(panel, start, end, **context) -> dict:
	"""One panel: its figures when its reader exists, otherwise the waiting message."""
	function = reader(panel["reader"])
	head = {"key": panel["key"], "title": panel["title"], "description": panel["description"]}
	if function is None:
		return {**head, "available": False, "message": panel["waiting"]}
	return {**head, "available": True, **function(start, end, **context)}
