# P1.06 a visit to a property.
import frappe

from sellos.crm.base import ArchiveOnly, stamp_archive


class SiteVisit(ArchiveOnly):
	def validate(self):
		stamp_archive(self)
