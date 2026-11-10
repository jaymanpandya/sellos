"""The setup wizard for a new company (P1.03).

Four steps: company profile, logo and colours, pipeline stages, first users. Every step saves at once
into the real records (SellOS Settings, Pipeline Stage, User), and SellOS Settings remembers which
steps are done, so a Company Admin who leaves can come back and carry on where they stopped. Only a
Company Admin may use it. It is safe to run again: a step can be saved any number of times.
"""

import base64
import binascii
import re

import frappe
from frappe import _
from frappe.utils import cint, validate_email_address

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN, ROLES
from sellos.provisioning.tenant_setup import LIMITS_KEY

SETTINGS = "SellOS Settings"
STAGE = "Pipeline Stage"
STEPS = ["profile", "branding", "stages", "users"]
REQUIRED_BEFORE_FINISH = ["profile", "branding", "stages"]

# The roles a Company Admin may give a first user. Never the Platform Admin, and a Client is made
# from a lead, not here.
GRANTABLE_ROLES = [COMPANY_ADMIN, AGENT, CHANNEL_PARTNER]

DEFAULT_STAGES = [
	{"stage_name": "New", "stage_type": "Open"},
	{"stage_name": "Contacted", "stage_type": "Open"},
	{"stage_name": "Site visit scheduled", "stage_type": "Open"},
	{"stage_name": "Site visit done", "stage_type": "Open"},
	{"stage_name": "Negotiation", "stage_type": "Open"},
	{"stage_name": "Booked", "stage_type": "Won"},
	{"stage_name": "Lost", "stage_type": "Lost"},
]
STAGE_TYPES = ["Open", "Won", "Lost"]
MAX_STAGES = 20

DEFAULT_BRAND_COLOR = "#0f4c35"
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_LOGO_BYTES = 1024 * 1024
# The first bytes of each image type allowed as a logo. SVG is left out: it can carry script.
LOGO_TYPES = (
	(b"\x89PNG\r\n\x1a\n", "png"),
	(b"\xff\xd8\xff", "jpg"),
	(b"GIF87a", "gif"),
	(b"GIF89a", "gif"),
)
PROFILE_FIELDS = {"company_name": 140, "contact_phone": 30, "contact_email": 140, "city": 80, "address": 500}


# --- Reading and writing the wizard's state -------------------------------------------------------


def _settings():
	return frappe.get_doc(SETTINGS)


def _steps_done(settings) -> list[str]:
	done = {s for s in (settings.setup_steps_done or "").split(",") if s}
	return [s for s in STEPS if s in done]


def _mark_done(settings, step):
	settings.setup_steps_done = ",".join(s for s in STEPS if s in {*_steps_done(settings), step})


def _next_step(done) -> str:
	return next((s for s in STEPS if s not in done), STEPS[-1])


def is_setup_complete() -> bool:
	"""True once the Company Admin has finished the wizard."""
	return bool(cint(frappe.db.get_single_value(SETTINGS, "setup_complete")))


def _stages() -> list[dict]:
	return frappe.get_all(
		STAGE, fields=["stage_name", "stage_type", "position"], order_by="position asc, stage_name asc"
	)


def _users() -> list[dict]:
	"""Everyone on this site who holds one of the five roles, with the roles they hold."""
	rows = frappe.get_all(
		"Has Role",
		filters={"role": ["in", list(ROLES)], "parenttype": "User"},
		fields=["parent", "role"],
	)
	roles: dict[str, list[str]] = {}
	for row in rows:
		roles.setdefault(row.parent, []).append(row.role)
	users = frappe.get_all(
		"User",
		filters={"name": ["in", list(roles) or [""]], "enabled": 1},
		fields=["name as email", "full_name"],
		order_by="creation asc",
	)
	return [{**u, "roles": sorted(roles[u.email])} for u in users]


def _max_users() -> int:
	return cint((frappe.get_site_config().get(LIMITS_KEY) or {}).get("max_users"))


@sellos_api(COMPANY_ADMIN)
def get_setup_state():
	"""Everything the wizard shows: what is saved, which steps are done and which comes next."""
	settings = _settings()
	done = _steps_done(settings)
	stages = _stages()
	return {
		"complete": bool(cint(settings.setup_complete)),
		"steps": STEPS,
		"steps_done": done,
		"next_step": _next_step(done),
		"profile": {field: settings.get(field) or "" for field in PROFILE_FIELDS},
		"branding": {"logo": settings.logo or "", "brand_color": settings.brand_color or DEFAULT_BRAND_COLOR},
		"stages": [{"stage_name": s.stage_name, "stage_type": s.stage_type} for s in stages]
		or DEFAULT_STAGES,
		"stages_saved": bool(stages),
		"users": _users(),
		"grantable_roles": GRANTABLE_ROLES,
		"max_users": _max_users(),
	}


# --- Step 1: company profile ----------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN)
def save_profile(values):
	"""Company name, phone, email, city and address."""
	values = frappe.parse_json(values) or {}
	settings = _settings()
	clean = {field: str(values.get(field) or "").strip()[:limit] for field, limit in PROFILE_FIELDS.items()}
	if not clean["company_name"]:
		frappe.throw(_("Enter the company name."))
	if clean["contact_email"] and not validate_email_address(clean["contact_email"]):
		frappe.throw(_("Enter a valid company email address."))
	settings.update(clean)
	_mark_done(settings, "profile")
	settings.save(ignore_permissions=True)
	return get_setup_state()


# --- Step 2: logo and colours ---------------------------------------------------------------------


def _logo_type(content: bytes) -> str | None:
	for magic, ext in LOGO_TYPES:
		if content.startswith(magic):
			return ext
	if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
		return "webp"
	return None


def _store_logo(logo_data) -> str:
	"""Save an uploaded logo (base64, with or without a data: prefix) as a public file."""
	payload = str(logo_data).split(",", 1)[-1]
	try:
		content = base64.b64decode(payload, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The logo could not be read. Choose a PNG, JPG, GIF or WebP image."))
	if len(content) > MAX_LOGO_BYTES:
		frappe.throw(_("The logo is larger than 1 MB. Choose a smaller image."))
	ext = _logo_type(content)
	if not ext:
		frappe.throw(_("The logo must be a PNG, JPG, GIF or WebP image."))
	from frappe.utils.file_manager import save_file

	file = save_file(f"company-logo.{ext}", content, SETTINGS, SETTINGS, is_private=0)
	return file.file_url


@sellos_api(COMPANY_ADMIN)
def save_branding(brand_color, logo_data=None, remove_logo=0):
	"""The brand colour, and optionally a new logo or no logo."""
	color = str(brand_color or "").strip()
	if not COLOR.match(color):
		frappe.throw(_("Choose the brand colour as six hex digits, such as #0f4c35."))
	settings = _settings()
	if logo_data:
		settings.logo = _store_logo(logo_data)
	elif cint(remove_logo):
		settings.logo = ""
	settings.brand_color = color.lower()
	_mark_done(settings, "branding")
	settings.save(ignore_permissions=True)
	frappe.clear_document_cache(SETTINGS, SETTINGS)
	return get_setup_state()


# --- Step 3: pipeline stages ----------------------------------------------------------------------


def _clean_stages(stages) -> list[dict]:
	stages = frappe.parse_json(stages) or []
	if not 2 <= len(stages) <= MAX_STAGES:
		frappe.throw(_("A pipeline needs between 2 and {0} stages.").format(MAX_STAGES))
	clean, seen = [], set()
	for stage in stages:
		name = re.sub(r"\s+", " ", str(stage.get("stage_name") or "")).strip()[:60]
		kind = stage.get("stage_type") or "Open"
		if not name:
			frappe.throw(_("Every stage needs a name."))
		if kind not in STAGE_TYPES:
			frappe.throw(_("A stage is Open, Won or Lost."))
		if name.lower() in seen:
			frappe.throw(_("Two stages are named {0}. Each stage needs its own name.").format(name))
		seen.add(name.lower())
		clean.append({"stage_name": name, "stage_type": kind})
	kinds = {s["stage_type"] for s in clean}
	if "Won" not in kinds or "Lost" not in kinds:
		frappe.throw(_("The pipeline needs at least one Won stage and one Lost stage."))
	return clean


@sellos_api(COMPANY_ADMIN)
def save_stages(stages):
	"""Replace the pipeline stages with the list given, in order."""
	clean = _clean_stages(stages)
	existing = {s.stage_name.lower(): s.stage_name for s in _stages()}
	keep = {s["stage_name"].lower() for s in clean}
	for key, name in existing.items():
		if key not in keep:
			frappe.delete_doc(STAGE, name, ignore_permissions=True)
	for position, stage in enumerate(clean, start=1):
		name = existing.get(stage["stage_name"].lower())
		doc = frappe.get_doc(STAGE, name) if name else frappe.new_doc(STAGE)
		doc.update({**stage, "position": position})
		doc.save(ignore_permissions=True)
	settings = _settings()
	_mark_done(settings, "stages")
	settings.save(ignore_permissions=True)
	return get_setup_state()


# --- Step 4: first users and roles ----------------------------------------------------------------


@sellos_api(COMPANY_ADMIN)
def add_user(email, first_name, role, last_name=""):
	"""Make one user with one role. The user gets the welcome email when this site can send email."""
	email = str(email or "").strip().lower()
	first_name = str(first_name or "").strip()[:60]
	if not first_name:
		frappe.throw(_("Enter the person's first name."))
	if not validate_email_address(email):
		frappe.throw(_("Enter a valid email address."))
	if role not in GRANTABLE_ROLES:
		frappe.throw(_("Choose Company Admin, Agent or Channel Partner."))
	if frappe.db.exists("User", email):
		frappe.throw(_("{0} already has an account.").format(email))
	limit = _max_users()
	if limit and len(_users()) >= limit:
		frappe.throw(_("Your plan allows {0} users. Remove one or ask for a bigger plan.").format(limit))

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first_name,
			"last_name": str(last_name or "").strip()[:60],
			"send_welcome_email": 0,
			"roles": [{"role": role}],
		}
	)
	user.flags.ignore_permissions = True
	# Frappe queues a job to make the Contact unless it is installing. Make it inside this save.
	previous = frappe.flags.in_install
	frappe.flags.in_install = "sellos"
	try:
		user.insert()
	finally:
		frappe.flags.in_install = previous

	invited = False
	if frappe.get_all("Email Account", filters={"enable_outgoing": 1}, limit=1):
		try:
			user.send_welcome_mail_to_user()
			invited = True
		except Exception:
			frappe.log_error("Setup wizard welcome email failed")
	return {**get_setup_state(), "invited": invited}


# --- Finishing ------------------------------------------------------------------------------------


@sellos_api(COMPANY_ADMIN)
def finish_setup():
	"""Mark the setup complete. The profile, branding and stages steps must be done first."""
	settings = _settings()
	missing = [s for s in REQUIRED_BEFORE_FINISH if s not in _steps_done(settings)]
	if missing:
		frappe.throw(_("Finish these steps first: {0}.").format(", ".join(missing)))
	_mark_done(settings, "users")
	settings.setup_complete = 1
	settings.save(ignore_permissions=True)
	frappe.clear_document_cache(SETTINGS, SETTINGS)
	return get_setup_state()
