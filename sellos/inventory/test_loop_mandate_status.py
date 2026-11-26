"""SOS-LOOP: the Sales Manager's mandate status method. It returns the id and the status of the mandates of the
seller leads of its own team and nothing else; any other role is refused."""

import frappe

from sellos.access.roles import SALES_MANAGER
from sellos.access.test_p1_18_sales_teams import SalesTeamCase
from sellos.crm import api
from sellos.inventory import mandates
from sellos.tests import phones

TERMS = {"mandate_type": "Exclusive", "term_months": 6, "fee_percent": 1.5}


class TestMandateStatusForSalesManager(SalesTeamCase):
	def seller(self, label, assigned_to):
		client = api.save_client(
			values={"client_name": label, "client_type": "Seller", "phone": phones.in_mobile(119)}
		)
		return api.save_lead(
			values={
				"client": client["name"],
				"source": "Website",
				"pipeline": "Seller",
				"assigned_to": assigned_to,
			}
		)["lead"]["name"]

	def mandate(self, lead):
		return frappe.get_doc({"doctype": "Mandate", "lead": lead, **TERMS, "status": "Draft"}).insert().name

	def test_a_manager_reads_only_id_and_status_of_its_own_teams_mandates(self):
		frappe.set_user(self.admin)
		own, other = self.seller("LOOP Seller A", self.agent_a), self.seller("LOOP Seller B", self.agent_b)
		own_mandate, other_mandate = self.mandate(own), self.mandate(other)
		frappe.set_user(self.manager_a)
		result = mandates.mandate_status([own, other])
		self.assertEqual(result, {"mandates": [{"name": own_mandate, "lead": own, "status": "Draft"}]})
		self.assertNotIn(other_mandate, str(result))

	def test_an_archived_mandate_and_an_unknown_lead_show_nothing(self):
		frappe.set_user(self.admin)
		lead = self.seller("LOOP Seller C", self.agent_a)
		name = self.mandate(lead)
		doc = frappe.get_doc("Mandate", name)
		doc.archived = 1
		doc.save()
		frappe.set_user(self.manager_a)
		self.assertEqual(mandates.mandate_status([lead, "NO-SUCH-LEAD"]), {"mandates": []})
		self.assertEqual(mandates.mandate_status([]), {"mandates": []})

	def test_only_the_sales_manager_is_declared(self):
		from sellos.access.matrix import MATRIX

		self.assertEqual(MATRIX["sellos.inventory.mandates.mandate_status"], frozenset({SALES_MANAGER}))
		frappe.set_user(self.agent_a)
		with self.assertRaises(frappe.PermissionError):
			mandates.mandate_status([self.lead_a])
