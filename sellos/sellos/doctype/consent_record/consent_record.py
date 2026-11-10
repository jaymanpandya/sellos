# P1.08 the lawful basis a lead gave for being contacted, with the proof of it and when it lapses.
from sellos.crm.base import ArchiveOnly, stamp_archive
from sellos.crm.consent import log_renewal, prepare_record, sync_lead_status


class ConsentRecord(ArchiveOnly):
	def validate(self):
		prepare_record(self)
		stamp_archive(self)

	def on_update(self):
		sync_lead_status(self.lead)

	def after_insert(self):
		log_renewal(self)
