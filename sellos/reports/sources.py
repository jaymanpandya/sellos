"""What a report may be built on (SOS-P5-01).

A Report Definition names a source here, one field of it to group by, and optionally one field to add up.
Anything that is not listed is refused when the definition is saved, so a definition can never reach a
phone number, a note or a field the screens do not show. A new source or field is added here on purpose.

* `date_field` and `date_type`: the field a report's dates are about, and whether it holds a date or a
  date and time.
* `scope_field`: the user the record belongs to. The Company Admin's filter by agent uses it.
* `groups`: the fields a report may group by. `users` are the groups that are people.
* `sums`: the fields a report may add up, with the unit the screen shows them in.
* `base_filters`: always applied (an archived record is not counted, as everywhere else).
* `columns`: what the drill down lists, in order. `lead_field` names the field that holds the lead the
  record opens on. No column holds a phone number.
"""

SOURCES = {
	"Lead": {
		"date_field": "creation",
		"date_type": "Datetime",
		"date_label": "Created",
		"scope_field": "assigned_to",
		"base_filters": {"archived": 0},
		"groups": {
			"stage": "Stage",
			"source": "Source",
			"assigned_to": "Agent",
			"consent_status": "Consent",
			"purpose": "Purpose",
			"property_type": "Property type",
		},
		"users": ("assigned_to",),
		"sums": {"budget_to": ("Budget up to", "rupees")},
		"lead_field": "name",
		"columns": (
			("lead_title", "Lead"),
			("stage", "Stage"),
			("source", "Source"),
			("assigned_to", "Agent"),
			("creation", "Created"),
		),
	},
	"Call Log": {
		"date_field": "started_on",
		"date_type": "Datetime",
		"date_label": "Started",
		"scope_field": "agent",
		"base_filters": {},
		"groups": {
			"purpose": "Purpose",
			"state": "State",
			"mode": "Mode",
			"agent": "Agent",
			"outcome": "Outcome",
		},
		"users": ("agent",),
		"sums": {"cost_rupees": ("Cost", "rupees"), "duration": ("Talk time", "seconds")},
		"lead_field": "lead",
		"columns": (
			("started_on", "Started"),
			("lead", "Lead"),
			("agent", "Agent"),
			("purpose", "Purpose"),
			("state", "State"),
			("duration", "Seconds"),
			("cost_rupees", "Cost"),
		),
	},
	"Site Visit": {
		"date_field": "visit_datetime",
		"date_type": "Datetime",
		"date_label": "Visit",
		"scope_field": "agent",
		"base_filters": {"archived": 0},
		"groups": {
			"status": "Status",
			"agent": "Agent",
			"confirmation_status": "Confirmation",
			"visit_outcome": "Outcome",
		},
		"users": ("agent",),
		"sums": {},
		"lead_field": "lead",
		"columns": (
			("visit_datetime", "Visit"),
			("lead", "Lead"),
			("project_name", "Project"),
			("agent", "Agent"),
			("status", "Status"),
			("visit_outcome", "Outcome"),
		),
	},
	"Lead Task": {
		"date_field": "due_date",
		"date_type": "Date",
		"date_label": "Due",
		"scope_field": "assigned_to",
		"base_filters": {"archived": 0},
		"groups": {"status": "Status", "assigned_to": "Agent"},
		"users": ("assigned_to",),
		"sums": {},
		"lead_field": "lead",
		"columns": (
			("due_date", "Due"),
			("lead", "Lead"),
			("title", "Task"),
			("assigned_to", "Agent"),
			("status", "Status"),
		),
	},
}
