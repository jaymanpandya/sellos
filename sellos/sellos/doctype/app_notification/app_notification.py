# SOS-P1-23 an in-app notification for one user. Customer roles reach it only through the notification
# API in sellos.crm.api, which filters on the signed in user.
from sellos.crm.base import ArchiveOnly


class AppNotification(ArchiveOnly):
	pass
