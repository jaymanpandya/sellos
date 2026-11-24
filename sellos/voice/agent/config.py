"""The voice agent's settings and the adapter each setting names (SOS-P5-07).

The providers, the model, the disclosure line, the keyterms and the keys are company settings
(Voice Agent Settings). The keys are encrypted Password fields and no method returns one. Switching a
provider is a change of setting: `build_adapters` looks the name up here, so a new choice from SOS-N21
needs no rebuild. The fake adapters are for a site that allows tests and nothing else.
"""

from dataclasses import dataclass

import frappe
from frappe import _

from sellos.voice.agent import adapters
from sellos.voice.agent.http import VoiceProviderError

DOCTYPE = "Voice Agent Settings"
FAKE = "fake"

# provider name -> (adapter class, the settings field that holds its key)
STT = {
	"sarvam-saaras-v3": (adapters.SarvamStt, "sarvam_key"),
	"deepgram-nova-3": (adapters.DeepgramStt, "deepgram_key"),
	FAKE: (adapters.FakeStt, None),
}
TTS = {
	"sarvam-bulbul-v3": (adapters.SarvamTts, "sarvam_key"),
	"elevenlabs": (adapters.ElevenLabsTts, "elevenlabs_key"),
	FAKE: (adapters.FakeTts, None),
}
LLM = {
	"anthropic": (adapters.AnthropicLlm, "anthropic_key"),
	FAKE: (adapters.FakeLlm, None),
}
KINDS = {"stt": STT, "tts": TTS, "llm": LLM}
KEY_FIELDS = ("sarvam_key", "deepgram_key", "elevenlabs_key", "anthropic_key")
MAX_KEYTERMS = 200
MAX_KEYTERM_LENGTH = 80


@dataclass
class VoiceSettings:
	stt_provider: str
	tts_provider: str
	llm_provider: str
	model: str
	voice: str
	disclosure: str  # as spoken: {company} replaced with the company's display name (SOS-N21C)
	keyterms: list
	disclosure_raw: str = ""  # as saved, {company} still in it: what the settings screen edits


def allowed_providers(kind: str) -> list[str]:
	"""The provider names a Company Admin may choose. The fake only on a site that allows tests."""
	allow_tests = bool(frappe.conf.get("allow_tests"))
	return [name for name in KINDS[kind] if name != FAKE or allow_tests]


def parse_keyterms(value) -> list[str]:
	"""A list, or text with one term per line, as a clean list with no empty line and no repeat."""
	lines = value.splitlines() if isinstance(value, str) else [str(v) for v in value or []]
	terms, seen = [], set()
	for line in lines:
		term = " ".join(line.split())
		if term and term.lower() not in seen:
			seen.add(term.lower())
			terms.append(term)
	return terms


def load() -> VoiceSettings:
	from sellos.access.partner_registrations import render_wording  # SOS-N21C: the shared {company} rule

	doc = frappe.get_doc(DOCTYPE)
	raw = (doc.disclosure_line or "").strip()
	return VoiceSettings(
		stt_provider=doc.stt_provider or "",
		tts_provider=doc.tts_provider or "",
		llm_provider=doc.llm_provider or "",
		model=doc.voice_agent_model or "",
		voice=doc.tts_voice or "",
		disclosure=render_wording(raw),
		keyterms=parse_keyterms(doc.keyterms or ""),
		disclosure_raw=raw,
	)


def _key(field: str) -> str:
	return frappe.get_doc(DOCTYPE).get_password(field, raise_exception=False) or ""


def _choose(kind: str, name: str, label: str):
	if not name:
		raise VoiceProviderError(_("Choose the {0} provider in the voice agent settings.").format(label))
	if name not in allowed_providers(kind):
		raise VoiceProviderError(_("The {0} provider is not available on this site.").format(label))
	return KINDS[kind][name]


def build_adapters(settings: VoiceSettings | None = None, clock=None):
	"""(stt, llm, tts) for the providers the settings name. Raises VoiceProviderError, with a message that
	is safe to show, when a provider is missing, unknown or has no key. A fake gets the clock."""
	settings = settings or load()
	built = []
	for kind, name, label in (
		("stt", settings.stt_provider, _("speech to text")),
		("llm", settings.llm_provider, _("language model")),
		("tts", settings.tts_provider, _("text to speech")),
	):
		cls, key_field = _choose(kind, name, label)
		if key_field is None:
			built.append(cls(clock=clock))
			continue
		key = _key(key_field)
		if not key:
			raise VoiceProviderError(
				_("The key for the {0} provider is not saved in the voice agent settings.").format(label)
			)
		if kind == "llm":
			if not settings.model:
				raise VoiceProviderError(_("Set the Voice agent model in the voice agent settings."))
			built.append(cls(key, settings.model))
		elif kind == "tts":
			built.append(cls(key, settings.voice))
		else:
			built.append(cls(key))
	return tuple(built)
