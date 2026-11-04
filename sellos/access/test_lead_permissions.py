# P1.04, P1.06 agents see their own leads unless shared. Unit tests of the permission queries.
import unittest
from unittest.mock import patch

import frappe

from sellos.access import lead_permissions as lp
from sellos.access.roles import AGENT, CHANNEL_PARTNER, CLIENT, COMPANY_ADMIN, PLATFORM_ADMIN


class TestLeadScope(unittest.TestCase):
	def test_scope_by_role(self):
		self.assertEqual(lp.scope_for([COMPANY_ADMIN]), "all")
		self.assertEqual(lp.scope_for([PLATFORM_ADMIN]), "none")  # P1.06: no company CRM data
		self.assertEqual(lp.scope_for(["System Manager"]), "all")
		self.assertEqual(lp.scope_for([AGENT]), "own")
		self.assertEqual(lp.scope_for([CHANNEL_PARTNER]), "own")
		self.assertEqual(lp.scope_for([CLIENT]), "none")
		self.assertEqual(lp.scope_for([]), "none")

	def test_the_widest_scope_wins(self):
		self.assertEqual(lp.scope_for([AGENT, COMPANY_ADMIN]), "all")
		self.assertEqual(lp.scope_for([CLIENT, AGENT]), "own")


class TestLeadQueries(unittest.TestCase):
	def _conditions(self, roles, user="a@x.com"):
		with patch.object(frappe, "get_roles", return_value=roles):
			return lp.get_permission_query_conditions(user)

	def test_admins_have_no_restriction(self):
		self.assertEqual(self._conditions([COMPANY_ADMIN]), "")
		self.assertEqual(self._conditions([PLATFORM_ADMIN]), "1=0")
		self.assertEqual(lp.get_permission_query_conditions("Administrator"), "")

	def test_a_client_sees_nothing(self):
		self.assertEqual(self._conditions([CLIENT]), "1=0")

	def test_an_agent_sees_own_assigned_and_shared_leads(self):
		sql = self._conditions([AGENT])
		self.assertIn("`tabLead`.`owner` = 'a@x.com'", sql)
		self.assertIn("`tabLead`.`assigned_to` = 'a@x.com'", sql)
		self.assertIn("`tabDocShare`", sql)
		self.assertIn("`share_doctype` = 'Lead'", sql)

	def test_the_user_is_escaped(self):
		sql = self._conditions([AGENT], user="x' or '1'='1")
		self.assertNotIn("= 'x' or '1'='1'", sql)

	def test_the_condition_is_valid_sql(self):
		sql = self._conditions([AGENT])
		frappe.db.sql(
			f"select 1 from `tabDocShare` as `tabLead` where {sql.replace('`tabLead`.`assigned_to`', '`tabLead`.`user`').replace('`tabLead`.`owner`', '`tabLead`.`user`')} limit 1"
		)


class TestLeadHasPermission(unittest.TestCase):
	def _doc(self, **fields):
		return frappe._dict({"doctype": "Lead", "name": "L1", **fields})

	def _check(self, roles, doc, ptype="read", user="a@x.com", shared=False):
		with (
			patch.object(frappe, "get_roles", return_value=roles),
			patch.object(frappe.db, "exists", return_value=shared),
		):
			return lp.has_permission(doc, ptype, user)

	def test_agent_sees_own_and_assigned_leads(self):
		self.assertTrue(self._check([AGENT], self._doc(owner="a@x.com")))
		self.assertTrue(self._check([AGENT], self._doc(owner="b@x.com", assigned_to="a@x.com")))

	def test_agent_cannot_see_another_agents_lead(self):
		self.assertFalse(self._check([AGENT], self._doc(owner="b@x.com", assigned_to="b@x.com")))

	def test_agent_sees_another_agents_lead_when_shared(self):
		self.assertTrue(self._check([AGENT], self._doc(owner="b@x.com"), shared=True))

	def test_company_admin_sees_all_and_client_sees_none(self):
		self.assertTrue(self._check([COMPANY_ADMIN], self._doc(owner="b@x.com")))
		self.assertFalse(self._check([CLIENT], self._doc(owner="a@x.com")))


class TestRecordsThatFollowTheLead(unittest.TestCase):
	"""P1.06 clients, activities, tasks and visits."""

	def _sql(self, fn, roles, user="a@x.com", **kw):
		with patch.object(frappe, "get_roles", return_value=roles):
			return fn(user, **kw)

	def test_children_follow_the_lead(self):
		sql = self._sql(lp.get_child_query_conditions, [AGENT], doctype="Lead Task")
		self.assertIn("`tabLead Task`.`lead` in (select `name` from `tabLead` where", sql)
		self.assertIn("`tabLead`.`assigned_to` = 'a@x.com'", sql)
		self.assertEqual(self._sql(lp.get_child_query_conditions, [CLIENT]), "1=0")
		self.assertEqual(self._sql(lp.get_child_query_conditions, [PLATFORM_ADMIN]), "1=0")
		self.assertEqual(self._sql(lp.get_child_query_conditions, [COMPANY_ADMIN]), "")

	def test_a_client_record_is_seen_through_its_leads_or_its_creator(self):
		sql = self._sql(lp.get_client_query_conditions, [CHANNEL_PARTNER])
		self.assertIn("`tabClient`.`owner` = 'a@x.com'", sql)
		self.assertIn("select `client` from `tabLead`", sql)
		self.assertEqual(self._sql(lp.get_client_query_conditions, [CLIENT]), "1=0")
		self.assertEqual(self._sql(lp.get_client_query_conditions, [COMPANY_ADMIN]), "")

	def test_any_agent_may_create(self):
		doc = frappe._dict({"doctype": "Lead", "name": None})
		with patch.object(frappe, "get_roles", return_value=[AGENT]):
			self.assertTrue(lp.has_permission(doc, "create", "a@x.com"))
			self.assertTrue(lp.has_client_permission(doc, "create", "a@x.com"))
		with patch.object(frappe, "get_roles", return_value=[PLATFORM_ADMIN]):
			self.assertFalse(lp.has_permission(doc, "create", "p@x.com"))
