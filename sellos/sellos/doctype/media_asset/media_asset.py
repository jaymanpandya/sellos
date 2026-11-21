# SOS-P4-03 a photo or a video in the company's asset library: the uploaded file with its title, type, content
# type and size. A listing links to it (Listing Media). An asset is archived, never deleted.
import frappe
from frappe import _

from sellos.inventory.base import InventoryRecord, squash

MEDIA_TYPES = ("Photo", "Video")


class MediaAsset(InventoryRecord):
	def validate(self):
		self.stamp_archive()
		self.title = squash(self.title)
		if not self.title:
			frappe.throw(_("Enter a title for the file."))
		if self.media_type not in MEDIA_TYPES:
			frappe.throw(_("A file is a Photo or a Video."))
