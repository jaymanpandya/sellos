# P1.06 an interaction on a lead.
from sellos.crm.base import ArchiveOnly, stamp_archive


class LeadActivity(ArchiveOnly):
	def validate(self):
		stamp_archive(self)
