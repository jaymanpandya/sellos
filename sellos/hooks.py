app_name = "sellos"
app_title = "SellOS"
app_publisher = "Interactive eCollective Softwares Pvt. Ltd."
app_description = "Real estate sales CRM — intelligently managed."
app_email = "jayman@theamplabs.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "sellos",
# 		"logo": "/assets/sellos/logo.png",
# 		"title": "SellOS",
# 		"route": "/sellos",
# 		"has_permission": "sellos.api.permission.has_app_permission",
# 	}
# ]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `sellos/dock/sellos/sellos.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/sellos/css/sellos.css"
# app_include_js = "/assets/sellos/js/sellos.js"

# include js, css files in header of web template
# web_include_css = "/assets/sellos/css/sellos.css"
# web_include_js = "/assets/sellos/js/sellos.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "sellos/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "sellos/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# P0.10 every SellOS role lands in the web app after sign in
role_home_page = {
	"SellOS Platform Admin": "sellos",
	"SellOS Company Admin": "sellos",
	"SellOS Agent": "sellos",
	"SellOS Client": "sellos",
	"SellOS Channel Partner": "sellos",
	"SellOS Sales Manager": "sellos",
}

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "sellos.utils.jinja_methods",
# 	"filters": "sellos.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "sellos.install.before_install"
after_install = "sellos.access.roles.after_install"
after_migrate = ["sellos.access.roles.after_migrate"]

# Uninstallation
# ------------

# before_uninstall = "sellos.uninstall.before_uninstall"
# after_uninstall = "sellos.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "sellos.utils.before_app_install"
# after_app_install = "sellos.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "sellos.utils.before_app_uninstall"
# after_app_uninstall = "sellos.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "sellos.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "sellos.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "sellos.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["sellos.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# P1.04 and P1.06: agents and partners see their own leads, and the records that follow a lead.
_LEAD_PERMS = "sellos.access.lead_permissions"
permission_query_conditions = {
	"Lead": f"{_LEAD_PERMS}.get_permission_query_conditions",
	"Client": f"{_LEAD_PERMS}.get_client_query_conditions",
	"Lead Activity": f"{_LEAD_PERMS}.get_child_query_conditions",
	"Lead Task": f"{_LEAD_PERMS}.get_child_query_conditions",
	"Site Visit": f"{_LEAD_PERMS}.get_child_query_conditions",
	"Consent Record": f"{_LEAD_PERMS}.get_child_query_conditions",
}
has_permission = {
	"Lead": f"{_LEAD_PERMS}.has_permission",
	"Client": f"{_LEAD_PERMS}.has_client_permission",
	"Lead Activity": f"{_LEAD_PERMS}.has_child_permission",
	"Lead Task": f"{_LEAD_PERMS}.has_child_permission",
	"Site Visit": f"{_LEAD_PERMS}.has_child_permission",
	"Consent Record": f"{_LEAD_PERMS}.has_child_permission",
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# P1.13 mark ended support grants as Expired. Access ends at expiry without it.
scheduler_events = {
	"all": ["sellos.access.support.expire_due_grants"],
	"hourly": ["sellos.crm.consent.expire_due_records"],
}
# scheduler_events = {
# 	"all": [
# 		"sellos.tasks.all"
# 	],
# 	"daily": [
# 		"sellos.tasks.daily"
# 	],
# 	"hourly": [
# 		"sellos.tasks.hourly"
# 	],
# 	"weekly": [
# 		"sellos.tasks.weekly"
# 	],
# 	"monthly": [
# 		"sellos.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "sellos.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "sellos.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# P1.06B: the record loader leaves out the history of fields the reader may not read.
override_whitelisted_methods = {
	"frappe.desk.form.load.getdoc": "sellos.access.field_history.getdoc",
	"frappe.desk.form.load.get_docinfo": "sellos.access.field_history.get_docinfo",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "sellos.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# P0.10 customer roles never see the desk
# P1.13 a Platform Admin with a support grant has every request logged
# P1.01 the control site opens for a Platform Admin only
before_request = [
	"sellos.provisioning.control.guard_control_site",
	"sellos.access.desk_guard.block_desk",
	"sellos.access.registry.guard_api",
	"sellos.access.support.log_support_request",
]
# after_request = ["sellos.utils.after_request"]

# Job Events
# ----------
# before_job = ["sellos.utils.before_job"]
# after_job = ["sellos.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"sellos.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

website_route_rules = [
	{"from_route": "/sellos/<path:app_path>", "to_route": "sellos"},
]

page_renderer = ["sellos.spa.SellOSPage"]
