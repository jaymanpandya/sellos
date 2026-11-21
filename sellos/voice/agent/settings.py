"""Voice agent settings API (SOS-P5-07): a Company Admin chooses the providers and edits the keyterms.

Only a Company Admin may call these methods. The keys are encrypted and no method returns one, not
even masked: a response says only whether each is set. A blank key keeps the saved one.
"""

import frappe
from frappe import _

from sellos.access.registry import sellos_api
from sellos.access.roles import COMPANY_ADMIN
from sellos.voice.agent import audio, config

_PROVIDER_FIELDS = (
	("stt_provider", "stt", "speech to text"),
	("tts_provider", "tts", "text to speech"),
	("llm_provider", "llm", "language model"),
)


def _state() -> dict:
	doc = frappe.get_doc(config.DOCTYPE)
	settings = config.load()
	return {
		"stt_provider": settings.stt_provider,
		"tts_provider": settings.tts_provider,
		"llm_provider": settings.llm_provider,
		"voice_agent_model": settings.model,
		"tts_voice": settings.voice,
		"disclosure_line": settings.disclosure,
		"keyterms": settings.keyterms,
		"keys_set": {
			field: bool(doc.get_password(field, raise_exception=False)) for field in config.KEY_FIELDS
		},
		"choices": {kind: config.allowed_providers(kind) for kind in config.KINDS},
	}


@sellos_api(COMPANY_ADMIN)
def get_voice_agent_settings():
	"""What is set, never a key."""
	return _state()


@sellos_api(COMPANY_ADMIN)
def save_voice_agent_settings(
	stt_provider=None,
	tts_provider=None,
	llm_provider=None,
	voice_agent_model=None,
	tts_voice=None,
	disclosure_line=None,
	keyterms=None,
	sarvam_key=None,
	deepgram_key=None,
	elevenlabs_key=None,
	anthropic_key=None,
):
	"""Save what is given; what is left out (or a blank key) stays as it was."""
	doc = frappe.get_doc(config.DOCTYPE)
	given = {"stt_provider": stt_provider, "tts_provider": tts_provider, "llm_provider": llm_provider}
	for field, kind, label in _PROVIDER_FIELDS:
		name = (given[field] or "").strip() if given[field] is not None else None
		if name is None:
			continue
		if name and name not in config.allowed_providers(kind):
			frappe.throw(
				_("The {0} provider is not one of the choices.").format(label), frappe.ValidationError
			)
		doc.set(field, name)
	if voice_agent_model is not None:
		doc.voice_agent_model = str(voice_agent_model).strip()
	if tts_voice is not None:
		doc.tts_voice = str(tts_voice).strip()
	if disclosure_line is not None:
		line = " ".join(str(disclosure_line).split())
		if not line:
			frappe.throw(_("The AI disclosure line cannot be empty."), frappe.ValidationError)
		if not audio.is_roman(line):
			frappe.throw(_("Write the AI disclosure line in Roman script."), frappe.ValidationError)
		doc.disclosure_line = line
	if keyterms is not None:
		terms = config.parse_keyterms(keyterms)
		if len(terms) > config.MAX_KEYTERMS or any(len(t) > config.MAX_KEYTERM_LENGTH for t in terms):
			frappe.throw(
				_("Use at most {0} keyterms of {1} characters each.").format(
					config.MAX_KEYTERMS, config.MAX_KEYTERM_LENGTH
				),
				frappe.ValidationError,
			)
		doc.keyterms = "\n".join(terms)
	for field, value in (
		("sarvam_key", sarvam_key),
		("deepgram_key", deepgram_key),
		("elevenlabs_key", elevenlabs_key),
		("anthropic_key", anthropic_key),
	):
		if value and str(value).strip():
			doc.set(field, str(value).strip())
	doc.flags.ignore_permissions = True
	doc.save()
	return _state()
