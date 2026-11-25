"""Words the demo content must never contain. Pure data, no Frappe import.

The demo's content itself is made by the builder modules (demo_inventory, demo_crm, demo_sales, demo_whatsapp) from the
names in demo_names; their unit tests check every generated text against this list.
"""

FORBIDDEN_WORDS = ("regression", "gate ", "test ", "lorem")
