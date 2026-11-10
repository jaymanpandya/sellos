"""SOS-SETUP-25: the user fixture survives a Contact that another connection changed mid transaction.

SOS-P1-06A was Blocked by MariaDB error 1020 ("Record has changed since last read in table
tabcontact") from ensure_test_users() -> create_contact() -> contact.save(). Saving a User queues a
create_contact job, the shared bench worker runs it at any moment, and MariaDB 11.8's snapshot
isolation refuses a write to a row changed since the transaction's read view. A timing race, so
these tests make it happen on purpose: a second connection changes the Contact row after the first
connection's read view has started, then the fixture runs on the first connection.
"""

from contextlib import contextmanager

import frappe
from frappe.core.doctype.user.user import create_contact
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from sellos.testing import users
from sellos.testing.users import TEST_USERS, ensure_test_users
from sellos.tests import ui_fixtures

RUNS = 20


@contextmanager
def _as_bench_execute():
	"""Run as bench execute does: outside the test runner, so Frappe would queue the Contact job."""
	in_test, frappe.in_test = frappe.in_test, False
	try:
		yield
	finally:
		frappe.in_test = in_test


def _other_connection():
	"""A second, independent connection to this site's database."""
	from frappe.database import get_db

	conf = frappe.conf
	return get_db(
		socket=conf.db_socket,
		host=conf.db_host,
		port=conf.db_port,
		user=conf.db_user,
		password=conf.db_password,
		cur_db_name=conf.db_name,
	)


def _jobs_queued_after_commit():
	"""The methods frappe.enqueue(..., enqueue_after_commit=True) is holding for the commit."""
	methods = []
	for func in frappe.db.after_commit._functions:
		for cell in getattr(func, "__closure__", None) or ():
			value = cell.cell_contents
			if isinstance(value, dict) and "method" in value:
				methods.append(value["method"])
	return methods


class TestContactRace(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# The users and their Contacts committed, as prepare_clean_site leaves them on every gate run.
		with _as_bench_execute():
			ensure_test_users()
		cls.email = TEST_USERS["agent"]["email"]
		cls.contact = users._contact_for(cls.email)

	def tearDown(self):
		frappe.db.rollback()

	def _modified(self):
		return frappe.db.sql("select modified from `tabContact` where name=%s", self.contact)[0][0]

	def _start_read_view_then_change_the_row_elsewhere(self, run):
		"""Open a read view on this connection, then change the Contact row on another one."""
		frappe.db.rollback()  # a new transaction
		before = self._modified()  # the first consistent read starts the read view
		other = _other_connection()
		try:
			other.sql(
				"update `tabContact` set modified=%s where name=%s",
				(add_to_date(now_datetime(), seconds=run + 1), self.contact),
			)
			other.commit()
		finally:
			other.close()
		# The row really changed after the read view: this connection still sees the old value.
		self.assertEqual(self._modified(), before)
		return before

	def test_the_old_write_is_refused_by_the_same_race(self):
		"""The control: the race these tests make is the one that Blocked SOS-P1-06A."""
		self.assertTrue(self.contact, "the agent has no Contact, so there is nothing to race on")
		self._start_read_view_then_change_the_row_elsewhere(0)
		with self.assertRaises(frappe.QueryDeadlockError) as caught:
			create_contact(frappe.get_doc("User", self.email), ignore_mandatory=True)
		self.assertIn("1020", str(caught.exception))

	def test_ensure_test_users_does_not_raise_when_the_contact_changed_20_times_in_a_row(self):
		self.assertTrue(self.contact)
		for run in range(RUNS):
			with self.subTest(run=run):
				before = self._start_read_view_then_change_the_row_elsewhere(run)
				with _as_bench_execute():
					self.assertEqual(ensure_test_users(), [s["email"] for s in TEST_USERS.values()])
				# Nothing was written and nothing committed: the read view is still the old one.
				self.assertEqual(self._modified(), before)

	def test_the_seed_fixtures_use_create_test_users_inside_the_test_runner(self):
		self.assertTrue(frappe.in_test)
		self._start_read_view_then_change_the_row_elsewhere(RUNS)
		calls = []
		original = ui_fixtures.ensure_test_users
		ui_fixtures.ensure_test_users = lambda: calls.append("ensure")
		try:
			ui_fixtures.seed_agent_leads()
			ui_fixtures.seed_client_with_phone(seed=22)
		finally:
			ui_fixtures.ensure_test_users = original
		self.assertEqual(calls, [])
		with _as_bench_execute():
			self.assertEqual(ui_fixtures._test_users(), [s["email"] for s in TEST_USERS.values()])
		ui_fixtures.remove_seeded_leads()

	def test_a_user_it_creates_gets_its_contact_now_and_no_job_is_queued(self):
		spec = {
			"email": "sos_setup25_race@example.com",
			"first_name": "Race Check",
			"roles": [],
			"desk": False,
		}
		self.assertFalse(frappe.db.exists("User", spec["email"]))
		flag = frappe.flags.in_install
		frappe.db.after_commit.reset()
		with _as_bench_execute():
			users._ensure_user(spec, synchronous_contact=True)
		self.assertEqual(frappe.flags.in_install, flag, "the flag was not restored")
		self.assertTrue(users._contact_for(spec["email"]), "the Contact was not made in this transaction")
		self.assertNotIn("frappe.core.doctype.user.user.create_contact", _jobs_queued_after_commit())
		frappe.db.rollback()  # the user and its Contact were never committed
		self.assertFalse(frappe.db.exists("User", spec["email"]))
