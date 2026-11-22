"""The one has_permission hook for File (hooks.py). Frappe reads the hook's answer as a verdict, so a list of two
hooks would let the first one's "True" be undone by the second one's None. This asks the rule that owns the file
and returns its answer as it is.

* A mandate's signed document and Private Sale Dossier files are the Mandate's (SOS-P4-05).
* Every other file keeps the partner firm rule's answer (SOS-P7-01) exactly as before.
"""

from sellos.access import partner_firms
from sellos.inventory import mandates


def has_file_permission(doc, ptype=None, user=None, **kwargs):
	if doc.get("attached_to_doctype") == "Mandate":
		return mandates.has_file_permission(doc, ptype, user, **kwargs)
	return partner_firms.has_file_permission(doc, ptype, user, **kwargs)
