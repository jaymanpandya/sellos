# P1.06 a buyer, seller, investor or NRI.
from sellos.crm.base import ArchiveOnly, mask_phone, stamp_archive


class Client(ArchiveOnly):
	def validate(self):
		self.phone_masked = mask_phone(self.phone)
		self.overseas_phone_masked = mask_phone(self.overseas_phone)
		stamp_archive(self)
