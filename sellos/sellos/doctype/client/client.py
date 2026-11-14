# P1.06 a buyer, seller, investor or NRI. SOS-P1-16 keeps the normalised numbers the duplicate match uses.
from sellos.crm.base import ArchiveOnly, mask_phone, stamp_archive
from sellos.crm.duplicates import normalise_phone


class Client(ArchiveOnly):
	def validate(self):
		self.phone_masked = mask_phone(self.phone)
		self.overseas_phone_masked = mask_phone(self.overseas_phone)
		self.phone_key = normalise_phone(self.phone)
		self.overseas_phone_key = normalise_phone(self.overseas_phone)
		stamp_archive(self)
