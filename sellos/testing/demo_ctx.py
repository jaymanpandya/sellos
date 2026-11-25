"""The context every demo builder receives, and the minimum volumes of a demo company.

No Frappe import at module level: the pure content generators of each builder module are unit tested without a bench.

A company seed runs its builders in this order, each reading what the earlier ones left on the context:
inventory (developers, projects, units, properties, listings), crm (clients, leads, consent, activities, calls,
site visits, follow ups), sales (sellers, mandates, partners and firms, deals, commission payouts), whatsapp
(conversations). Every builder looks a record up before it creates it, so a second run creates nothing, and counts
what it created, renamed and removed in `ctx.summary`.
"""

import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

# What each company site holds at least (the demo brief of 25 November 2026). The unit tests assert them on the
# generated content, and the seed asserts them on the site when it finishes.
MINIMUMS = {
	"developers": 6,
	"projects": 12,
	"units_per_project": 60,  # on average
	"properties": 40,
	"localities": 10,
	"leads": 180,
	"leads_per_stage": 8,  # every one of the 11 pipeline stages
	"leads_per_consent_state": 15,  # Consented, Unknown, Opted out, Registered DND
	"activities": 400,
	"call_logs": 120,
	"site_visits": 50,
	"sellers": 25,
	"mandates": 25,
	"deals": 30,
	"payouts": 24,
	"partners": 12,
	"whatsapp_conversations": 40,
}

SEED_OF = {"bom": 20261125, "amd": 20261126}


@dataclass
class Ctx:
	"""One company's seed run."""

	word: str  # "bom" or "amd": the region key of demo_names.REGIONS
	company_name: str
	users: dict  # admin, manager, agents (4 emails), partner, client: emails
	staff_names: dict  # the same keys, the people's names (demo_names.STAFF)
	today: date = field(default_factory=date.today)
	rng: random.Random = None
	used_names: set = field(default_factory=set)  # every person name drawn so far, so none repeats
	summary: Counter = field(
		default_factory=Counter
	)  # "<action> <doctype>": a count, action = created, renamed, removed
	# Left here by the builders, in order:
	developers: list = field(default_factory=list)  # [{name, ...}]
	projects: list = field(default_factory=list)  # [{name, developer, rera, locality, units: [unit names]}]
	units: list = field(default_factory=list)  # [{name, project, number, configuration, status, price}]
	properties: list = field(default_factory=list)  # [{name, title, locality, asking_price}]
	listings: list = field(default_factory=list)
	leads: list = field(
		default_factory=list
	)  # [{name, client, client_name, stage, agent, source, created_on, consent}]
	sellers: list = field(default_factory=list)  # seller leads
	mandates: list = field(default_factory=list)
	partners: list = field(default_factory=list)  # [{firm, email, user, status}]
	deals: list = field(default_factory=list)
	payouts: list = field(default_factory=list)

	def __post_init__(self):
		if self.rng is None:
			self.rng = random.Random(SEED_OF.get(self.word, 20261125))

	def count(self, action, doctype, n=1):
		"""Record that `n` records of a doctype were created, renamed or removed."""
		self.summary[f"{action} {doctype}"] += n

	@property
	def region(self):
		from sellos.testing import demo_names

		return demo_names.REGIONS[self.word]
