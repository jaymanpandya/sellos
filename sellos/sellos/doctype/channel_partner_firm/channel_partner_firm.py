# SOS-P7-01 a channel partner firm: invited, approved by a Company Admin, suspended when it leaves.
import re

import frappe
from frappe import _
from frappe.utils import now_datetime, validate_email_address

from sellos.crm.base import ArchiveOnly, mask_phone

INVITED = "Invited"
PENDING = "Pending approval"
APPROVED = "Approved"
SUSPENDED = "Suspended"
STATUSES = (INVITED, PENDING, APPROVED, SUSPENDED)

# The moves a Company Admin or the partner may make, and nothing else.
MOVES = {
	(INVITED, PENDING),
	(PENDING, APPROVED),
	(INVITED, SUSPENDED),
	(PENDING, SUSPENDED),
	(APPROVED, SUSPENDED),
	(SUSPENDED, APPROVED),
}

# MahaRERA agent numbers are A and eleven digits (A51800012345). Other states write theirs in three or more
# parts joined by / or - (for example PRM/KA/RERA/1251/309/AG/190101/000123).
_RERA = re.compile(r"^(A\d{11}|[A-Z0-9]{1,12}(?:[/-][A-Z0-9]{1,12}){2,9})$")
# Five letters, four digits and a letter. The fourth letter says who holds the PAN (a person, company, firm...).
_PAN = re.compile(r"^[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]$")


def clean_rera(value) -> str:
	"""The RERA agent registration number in capitals with no spaces, or "" when blank. Refused when the format is wrong."""
	value = re.sub(r"\s+", "", str(value or "")).upper()
	if value and not _RERA.match(value):
		frappe.throw(
			_("Enter the RERA agent registration number as it is printed, for example A51800012345.")
		)
	return value


def clean_pan(value) -> str:
	"""The PAN in capitals, or "" when blank. Refused unless it is five letters, four digits and a letter."""
	value = re.sub(r"\s+", "", str(value or "")).upper()
	if value and not _PAN.match(value):
		frappe.throw(_("Enter the PAN as five letters, four digits and a letter, for example ABCPD1234E."))
	return value


class ChannelPartnerFirm(ArchiveOnly):
	def before_insert(self):
		self.status = INVITED
		self.status_reason = ""
		self.append(
			"status_log",
			{
				"changed_on": now_datetime(),
				"changed_by": frappe.session.user,
				"from_status": "",
				"to_status": INVITED,
			},
		)

	def validate(self):
		self.firm_name = " ".join((self.firm_name or "").split())
		self.contact_person = " ".join((self.contact_person or "").split())
		if not validate_email_address(self.email or ""):
			frappe.throw(_("Enter a valid email address."))
		self.email = self.email.strip().lower()
		self.rera_number = clean_rera(self.rera_number)
		self.pan = clean_pan(self.pan)
		if self.phone:
			from sellos.access.users import normalize_mobile

			self.phone = normalize_mobile(self.phone)
		self.phone_masked = mask_phone(self.phone)
		# The code is the record's name, from a counter that only goes up, so it is never given twice.
		self.partner_code = self.name
		self._check_status()

	def _check_status(self):
		if self.is_new() or not self.has_value_changed("status"):
			return
		old = self.get_doc_before_save().status
		if not self.flags.via_transition or (old, self.status) not in MOVES:
			frappe.throw(
				_("A firm's status changes only by inviting, approving, suspending or reinstating it."),
				frappe.PermissionError,
			)

	def missing_details(self) -> list[str]:
		"""What the firm still has to give before a Company Admin can look at it."""
		need = {
			_("firm name"): self.firm_name,
			_("contact person"): self.contact_person,
			_("phone"): self.phone,
			_("RERA agent registration number"): self.rera_number,
			_("PAN"): self.pan,
			_("signed agreement"): self.agreement,
		}
		return [label for label, value in need.items() if not value]

	def change_status(self, to, reason=""):
		"""Move the firm to a status and log who did it and when. Only the API methods in
		sellos.access.partner_firms call this, after checking the role."""
		reason = (reason or "").strip()
		if (self.status, to) not in MOVES:
			frappe.throw(_("A firm that is {0} can not become {1}.").format(self.status, to))
		if to == SUSPENDED and not reason:
			frappe.throw(_("Give a reason for the suspension."))
		if to == PENDING and (missing := self.missing_details()):
			frappe.throw(_("Complete the firm's details first: {0}.").format(", ".join(missing)))
		self.append(
			"status_log",
			{
				"changed_on": now_datetime(),
				"changed_by": frappe.session.user,
				"from_status": self.status,
				"to_status": to,
				"reason": reason,
			},
		)
		self.status = to
		self.status_reason = reason if to == SUSPENDED else ""
		self.flags.via_transition = True
		self.flags.ignore_permissions = True
		self.save()
