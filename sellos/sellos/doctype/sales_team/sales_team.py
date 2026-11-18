# SOS-P1-18 a sales team: a manager and the agents they run. An agent is in at most one team.
import frappe
from frappe import _
from frappe.model.document import Document

from sellos.access.roles import AGENT, SALES_MANAGER


class SalesTeam(Document):
	def validate(self):
		self.team_name = " ".join((self.team_name or "").split())
		self._check_manager()
		self._check_members()

	def _check_manager(self):
		if SALES_MANAGER not in frappe.get_roles(self.manager):
			frappe.throw(_("{0} does not have the Sales Manager role.").format(self.manager))

	def _check_members(self):
		seen = set()
		for row in self.members:
			agent = row.agent
			if agent in seen:
				frappe.throw(_("{0} is listed twice in this team.").format(agent))
			seen.add(agent)
			if agent == self.manager:
				frappe.throw(_("The manager cannot also be an agent of the team."))
			if AGENT not in frappe.get_roles(agent):
				frappe.throw(_("{0} is not an agent.").format(agent))
		for agent in seen:
			other = frappe.db.get_value(
				"Sales Team Member",
				{"agent": agent, "parenttype": "Sales Team", "parent": ["!=", self.name or ""]},
				"parent",
			)
			if other:
				frappe.throw(
					_("{0} is already in the team {1}. An agent is in one team only.").format(agent, other)
				)
