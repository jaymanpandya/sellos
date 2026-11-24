"""SOS-P5-07: the voice agent service, built and tested against fakes of the Plivo stream, speech to text,
the language model and text to speech. No test calls a real provider or holds a real key."""

import base64
import json
import urllib.error
import urllib.parse
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import ensure_roles
from sellos.crm import call_outcomes, consent
from sellos.crm.test_crm import CrmCase, as_user
from sellos.telephony.settings import save_telephony_settings
from sellos.testing.users import create_test_users
from sellos.tests import phones
from sellos.voice.agent import adapters, audio, config, http, server, service, settings, stream
from sellos.voice.agent.fake_stream import SimClock, recording_pcm, replay, speech_recording
from sellos.voice.agent.http import VoiceProviderError
from sellos.voice.agent.session import (
	CLARIFY_LINE,
	HANDOVER_LINE,
	TARGET_SECONDS,
	AgentSession,
	latency_summary,
	wants_human,
)
from sellos.voice.bakeoff import data

LANDLINE = f"{phones.in_mobile(3500)[:3]}22{phones.in_mobile(3500)[-8:]}"
DISCLOSURE = (
	"Namaste, main ek AI assistant bol rahi hoon, koi insaan nahin. Kya main do minute baat kar sakti hoon?"
)
OUTCOMES = ("Interested", "Call back later", "Not reachable")
DEFAULT_DISCLOSURE = (
	"Namaste, main Nicole baat kar rahi hoon. Main {company} ka AI assistant hoon. Yeh call quality ke "
	"liye record ho rahi hai. Agar aap kisi insaan se baat karna chahein, toh bas bol dijiye."
)
ASK_HUMAN = "mujhe kisi insaan se baat karni hai"
LONG_REPLY = " ".join(["Bilkul ji, main aapko saari jaankari abhi batati hoon"] * 2)


def run_call(script, transcripts=(), replies=(), config=None, stt_delay=0.15, llm_delay=0.25, tts_delay=0.1):
	"""Replay `script` through a session built on fakes and a simulated clock."""
	clock = SimClock()
	stt = adapters.FakeStt(transcripts, stt_delay, clock)
	llm = adapters.FakeLlm(replies, llm_delay, clock)
	tts = adapters.FakeTts(tts_delay, clock)
	sent, handed = [], []
	session = AgentSession(
		stt=stt,
		llm=llm,
		tts=tts,
		send=sent.append,
		clock=clock,
		disclosure=DISCLOSURE,
		keyterms=data.KEYTERMS,
		context="Lead: Asha.",
		outcomes=OUTCOMES,
		config=config,
		on_handover=handed.append,
	)
	for raw in replay(clock, "call-1", script):
		session.handle(raw)
	return session, sent, (stt, llm, tts), handed


def say(seconds=1.0):
	return ("speech", speech_recording(seconds))


def kinds(session):
	return [entry["kind"] for entry in session.log]


class TestAudioAndRules(IntegrationTestCase):
	"""SOS-P5-07: phone audio, Roman script and what counts as a request for a human."""

	def test_mulaw_round_trip_stays_close(self):
		pcm = audio.tone(0.1)
		back = audio.ulaw_to_pcm(audio.pcm_to_ulaw(pcm))
		self.assertEqual(len(back), len(pcm))
		worst = max(abs(a - b) for a, b in zip(audio.samples(pcm), audio.samples(back), strict=True))
		self.assertLess(worst, 600)

	def test_roman_script_check(self):
		self.assertTrue(audio.is_roman("Namaste, mujhe 2 BHK chahiye."))
		self.assertFalse(audio.is_roman("नमस्ते"))

	def test_a_request_for_a_human_is_found_and_a_question_about_the_agent_is_not(self):
		for text in (
			ASK_HUMAN,
			"Please connect me to a human",
			"koi sales executive se baat karao",
			"manager se baat karni hai",
			"I want to speak to a real person",
		):
			self.assertTrue(wants_human(text), text)
		for text in (
			"Kya aap AI ho ya insaan?",
			"Mujhe 2 BHK chahiye Bandra mein",
			"Carpet area kitna hai?",
			"",
		):
			self.assertFalse(wants_human(text), text)

	def test_default_keyterms_start_from_the_bakeoff_and_the_disclosure_line_from_n21c(self):
		state = frappe.get_doc("Voice Agent Settings")
		self.assertEqual(config.parse_keyterms(state.keyterms), list(data.KEYTERMS))
		self.assertEqual(state.disclosure_line, DEFAULT_DISCLOSURE)  # SOS-N21C, Jayman, 24 November 2026
		self.assertTrue(audio.is_roman(state.disclosure_line))


class TestScriptedCalls(IntegrationTestCase):
	"""SOS-P5-07: scripted test calls: normal, interruption, silence and handover."""

	def test_a_normal_call_opens_with_the_disclosure_and_answers_each_turn(self):
		replies = [
			"Bilkul, aap kaunsa area dekh rahe hain?",
			"Theek hai, main aapko brochure bhej deti hoon.",
		]
		session, _, (_, llm, tts), _ = run_call(
			[("silence", 2.0), say(1.0), ("silence", 3.0), say(0.8), ("silence", 3.0)],
			["mujhe 2 BHK chahiye", "Bandra West mein"],
			replies,
		)
		self.assertEqual(kinds(session), ["disclosure", "reply", "reply"])
		self.assertEqual(tts.spoken, [DISCLOSURE, *replies])
		self.assertEqual(session.result().transcript.splitlines()[0], f"Agent: {DISCLOSURE}")
		self.assertEqual(session.result().turns, 2)
		self.assertEqual(llm.calls[0]["context"], "Lead: Asha.")
		self.assertEqual(session.end_reason, "the caller hung up")
		self.assertFalse(session.handed_over)
		self.assertTrue(audio.is_roman(session.result().transcript))

	def test_the_disclosure_is_the_first_audio_of_every_call(self):
		for script, transcripts in (
			([("silence", 2.0)], []),
			([say(1.0), ("silence", 2.0)], [ASK_HUMAN]),  # the caller speaks over the disclosure
			([("silence", 2.0), say(1.0), ("silence", 2.0)], ["haan boliye"]),
		):
			session, sent, (_, _, tts), _ = run_call(script, transcripts)
			first = json.loads(sent[0])
			self.assertEqual(first["event"], "playAudio")
			self.assertEqual(tts.spoken[0], DISCLOSURE)
			self.assertEqual(session.log[0], {"kind": "disclosure", "text": DISCLOSURE})
			self.assertEqual(session.result().transcript.splitlines()[0], f"Agent: {DISCLOSURE}")

	def test_the_audio_sent_is_8khz_mulaw(self):
		_, sent, _, _ = run_call([("silence", 0.5)])
		media = json.loads(sent[0])["media"]
		self.assertEqual((media["contentType"], media["sampleRate"]), (stream.MULAW, 8000))
		self.assertEqual(len(base64.b64decode(media["payload"])), audio.FRAME_SAMPLES)

	def test_a_reply_starts_within_a_second_of_the_caller_finishing(self):
		session, _, _, _ = run_call(
			[
				("silence", 2.0),
				say(1.0),
				("silence", 3.0),
				say(0.6),
				("silence", 3.0),
				say(1.4),
				("silence", 3.0),
			],
			["mujhe 2 BHK chahiye", "Bandra", "budget teen crore"],
			["Achha.", "Theek hai.", "Samajh gayi."],
		)
		summary = session.result().summary
		note = (
			f"median {summary['median_ms']} ms, slowest {summary['slowest_ms']} ms, "
			f"target {int(TARGET_SECONDS * 1000)} ms"
		)
		self.assertEqual(summary["turns"], 3, note)
		self.assertLessEqual(summary["slowest_ms"], 1000, note)
		self.assertGreater(summary["median_ms"], 700, note)  # hangover, speech to text, model, voice
		self.assertTrue(summary["within_target"], note)
		self.assertEqual(len(session.result().latencies_ms), 3)

	def test_the_latency_summary_names_the_median_and_the_slowest(self):
		summary = latency_summary([0.5, 0.9, 1.2])
		self.assertEqual(
			(summary["median_ms"], summary["slowest_ms"], summary["within_target"]), (900, 1200, False)
		)
		self.assertEqual(latency_summary([])["turns"], 0)

	def test_the_company_keyterms_reach_the_speech_to_text_on_every_utterance(self):
		terms = ["Bandra West", "RERA", "carpet area"]
		clock = SimClock()
		stt = adapters.FakeStt(["a", "b"], 0.1, clock)
		session = AgentSession(
			stt=stt,
			llm=adapters.FakeLlm((), 0.1, clock),
			tts=adapters.FakeTts(0.1, clock),
			send=lambda m: None,
			clock=clock,
			disclosure=DISCLOSURE,
			keyterms=terms,
		)
		for raw in replay(clock, "c", [("silence", 2.0), say(), ("silence", 2.0), say(), ("silence", 2.0)]):
			session.handle(raw)
		self.assertEqual([call["keyterms"] for call in stt.calls], [terms, terms])

	def test_the_caller_speaking_over_the_agent_stops_the_audio_and_is_heard(self):
		session, sent, (stt, _, _), _ = run_call(
			[
				("silence", 2.0),
				say(1.0),
				("silence", 0.4),
				say(1.0),
				("silence", 3.0),
			],  # the second speech starts as the reply plays
			["mujhe 2 BHK chahiye", "nahin, 3 BHK"],
			[LONG_REPLY, "Theek hai, teen BHK."],
		)
		self.assertEqual(kinds(session), ["disclosure", "reply", "cleared", "reply"])
		self.assertEqual(session.result().interruptions, 1)
		self.assertTrue(any(json.loads(m)["event"] == "clearAudio" for m in sent))
		self.assertEqual(len(stt.calls), 2)

	def test_silence_prompts_twice_then_ends_the_call(self):
		session, _, _, _ = run_call([("silence", 30.0)])
		self.assertEqual(kinds(session), ["disclosure", "prompt", "prompt", "goodbye"])
		self.assertEqual(session.end_reason, "the caller was silent")
		self.assertEqual(session.outcome, "Not reachable")
		self.assertFalse(session.handed_over)

	def test_a_request_for_a_human_during_the_disclosure_hands_over(self):
		session, sent, _, handed = run_call([say(1.0), ("silence", 2.0)], [ASK_HUMAN])
		self.assertEqual(kinds(session), ["disclosure", "cleared", "handover"])
		self.assertTrue(session.handed_over)
		self.assertEqual(handed, ["the caller asked for a human"])
		self.assertEqual(session.log[-1]["text"], HANDOVER_LINE)
		self.assertEqual(session.end_reason, "handed over to a human")
		events = [json.loads(m)["event"] for m in sent]
		self.assertLess(events.index("clearAudio"), len(events) - 1)
		self.assertLess(session.result().latencies_ms[0], 1000)

	def test_a_request_for_a_human_in_the_middle_of_a_reply_hands_over(self):
		session, _, _, handed = run_call(
			[("silence", 2.0), say(1.0), ("silence", 0.4), say(1.0), ("silence", 2.0)],
			["mujhe 2 BHK chahiye", "Human se baat karao please"],
			[LONG_REPLY],
		)
		self.assertEqual(kinds(session), ["disclosure", "reply", "cleared", "handover"])
		self.assertEqual(len(handed), 1)
		self.assertTrue(session.handed_over)

	def test_a_request_for_a_human_after_a_quiet_moment_hands_over(self):
		session, _, _, _ = run_call([("silence", 2.0), say(1.0), ("silence", 2.0)], [ASK_HUMAN])
		self.assertEqual(kinds(session), ["disclosure", "handover"])

	def test_two_turns_in_a_row_not_understood_hand_over(self):
		session, _, _, handed = run_call(
			[("silence", 2.0), say(1.0), ("silence", 2.0), say(1.0), ("silence", 2.0)], ["", ""]
		)
		self.assertEqual(kinds(session), ["disclosure", "clarify", "handover"])
		self.assertEqual(session.log[1]["text"], CLARIFY_LINE)
		self.assertEqual(handed, ["confusion"])

	def test_one_understood_turn_clears_the_confusion(self):
		session, _, _, _ = run_call(
			[
				("silence", 2.0),
				say(1.0),
				("silence", 2.0),
				say(1.0),
				("silence", 2.0),
				say(1.0),
				("silence", 2.0),
			],
			["", "haan bataiye", ""],
			["Zaroor."],
		)
		self.assertEqual(kinds(session), ["disclosure", "clarify", "reply", "clarify"])
		self.assertFalse(session.handed_over)

	def test_text_that_is_not_roman_counts_as_not_understood(self):
		session, _, (_, llm, _), _ = run_call(
			[("silence", 2.0), say(1.0), ("silence", 2.0)], ["मुझे फ्लैट चाहिए"]
		)
		self.assertEqual(kinds(session), ["disclosure", "clarify"])
		self.assertEqual(llm.calls, [])
		self.assertIn("Caller: (not understood)", session.result().transcript)

	def test_a_reply_in_devanagari_is_never_spoken(self):
		_, _, (_, _, tts), _ = run_call(
			[("silence", 2.0), say(1.0), ("silence", 2.0)], ["2 BHK chahiye"], ["नमस्ते"]
		)
		self.assertEqual(tts.spoken, [DISCLOSURE, CLARIFY_LINE])

	def test_the_model_can_hand_over_and_end_with_an_outcome(self):
		session, _, (_, _, tts), _ = run_call(
			[("silence", 2.0), say(1.0), ("silence", 2.0)], ["kuch samajh nahin aaya"], ["[HANDOVER]"]
		)
		self.assertEqual((session.handed_over, session.handover_reason), (True, "the agent could not help"))
		session, _, (_, _, tts), _ = run_call(
			[("silence", 2.0), say(1.0), ("silence", 2.0)],
			["kal subah call kijiye"],
			["Theek hai, kal call karungi. [OUTCOME: call back later]"],
		)
		self.assertEqual(tts.spoken[1], "Theek hai, kal call karungi.")
		self.assertEqual(
			(session.outcome, session.end_reason), ("Call back later", "the agent ended the call")
		)

	def test_a_provider_failure_hands_over_and_leaks_nothing(self):
		class BrokenStt(adapters.SttAdapter):
			name = "broken"

			def transcribe(self, pcm, keyterms):
				raise VoiceProviderError("The provider answered HTTP 500.")

		clock = SimClock()
		session = AgentSession(
			stt=BrokenStt(),
			llm=adapters.FakeLlm(),
			tts=adapters.FakeTts(0.1, clock),
			send=lambda m: None,
			clock=clock,
			disclosure=DISCLOSURE,
		)
		for raw in replay(clock, "c", [("silence", 2.0), say(1.0), ("silence", 2.0)]):
			session.handle(raw)
		self.assertTrue(session.handed_over)
		self.assertIn("HTTP 500", session.handover_reason)

	def test_noise_shorter_than_a_word_is_ignored(self):
		session, _, (stt, _, _), _ = run_call([("silence", 2.0), say(0.1), ("silence", 2.0)], ["x"])
		self.assertEqual((stt.calls, kinds(session)), ([], ["disclosure"]))

	def test_the_replayed_recording_is_8khz_audio(self):
		pcm = recording_pcm(speech_recording(0.5))
		self.assertEqual(audio.seconds(pcm), 0.5)


class Recorder:
	"""A recorded transport for the live adapters: it keeps the request and returns a fixed answer."""

	def __init__(self, reply=b"", chunks=()):
		self.reply, self.chunks, self.calls = reply, list(chunks), []

	def post(self, url, body, headers):
		self.calls.append((url, body, headers))
		return self.reply

	def stream(self, url, body, headers):
		self.calls.append((url, body, headers))
		yield from self.chunks


KEY = "key-for-the-fake-provider-1"


class TestLiveAdapters(IntegrationTestCase):
	"""SOS-P5-07: an adapter for every bake-off candidate, tested against a recorded transport."""

	def test_deepgram_gets_every_keyterm_and_the_language_multi_model(self):
		net = Recorder(
			json.dumps({"results": {"channels": [{"alternatives": [{"transcript": "2 BHK"}]}]}}).encode()
		)
		terms = ["carpet area", "Bandra West", "RERA"]
		text = adapters.DeepgramStt(KEY, post=net.post).transcribe(audio.tone(0.2), terms)
		url, body, headers = net.calls[0]
		query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
		self.assertEqual(text, "2 BHK")
		self.assertEqual(query["keyterm"], terms)
		self.assertEqual((query["model"], query["language"]), (["nova-3"], ["multi"]))
		self.assertEqual(headers["Authorization"], f"Token {KEY}")
		self.assertEqual(body, audio.tone(0.2))

	def test_sarvam_speech_to_text_asks_for_roman_script_and_sends_the_keyterms(self):
		net = Recorder(json.dumps({"transcript": " mujhe flat chahiye "}).encode())
		text = adapters.SarvamStt(KEY, post=net.post).transcribe(audio.tone(0.2), ["RERA", "BHK"])
		_, body, headers = net.calls[0]
		self.assertEqual(text, "mujhe flat chahiye")
		self.assertIn(b"saaras:v3", body)
		self.assertIn(b"translit", body)
		self.assertIn(b"RERA, BHK", body)
		self.assertEqual(headers["api-subscription-key"], KEY)

	def test_sarvam_text_to_speech_returns_8khz_audio(self):
		wav = base64.b64encode(adapters._wav(audio.tone(0.1))).decode()
		net = Recorder(json.dumps({"audios": [wav]}).encode())
		chunks = list(adapters.SarvamTts(KEY, "anushka", post=net.post).synthesize("Namaste"))
		payload = json.loads(net.calls[0][1])
		self.assertEqual(chunks, [audio.tone(0.1)])
		self.assertEqual(
			(payload["model"], payload["speech_sample_rate"], payload["speaker"]),
			("bulbul:v3", 8000, "anushka"),
		)

	def test_elevenlabs_streams_whole_samples(self):
		pcm = audio.tone(0.1)
		net = Recorder(chunks=[pcm[:101], pcm[101:]])
		chunks = list(adapters.ElevenLabsTts(KEY, "voice-1", stream=net.stream).synthesize("Namaste"))
		self.assertTrue(all(len(c) % 2 == 0 for c in chunks))
		self.assertEqual(b"".join(chunks), pcm)
		url, _, headers = net.calls[0]
		self.assertIn("/voice-1/stream?output_format=pcm_8000", url)
		self.assertEqual(headers["xi-api-key"], KEY)

	def test_anthropic_uses_the_voice_agent_model_and_alternating_messages(self):
		net = Recorder(json.dumps({"content": [{"type": "text", "text": " Namaste ji "}]}).encode())
		llm = adapters.AnthropicLlm(KEY, "a-fast-model-for-the-test", post=net.post)
		text = llm.reply(
			"system", [("agent", "Namaste"), ("caller", "haan"), ("caller", "boliye")], "Lead: Asha."
		)
		body = json.loads(net.calls[0][1])
		self.assertEqual(text, "Namaste ji")
		self.assertEqual(body["model"], "a-fast-model-for-the-test")
		self.assertIn("Lead: Asha.", body["system"])
		self.assertEqual([m["role"] for m in body["messages"]], ["user", "assistant", "user"])
		self.assertEqual(net.calls[0][2]["x-api-key"], KEY)

	def test_no_adapter_shows_its_key_in_its_repr_and_a_failure_names_no_key(self):
		for adapter in (adapters.DeepgramStt(KEY), adapters.SarvamTts(KEY), adapters.AnthropicLlm(KEY, "m")):
			self.assertNotIn(KEY, repr(adapter))
		error = urllib.error.URLError(f"cannot reach https://x/?key={KEY}")
		with mock.patch("urllib.request.urlopen", side_effect=error):
			with self.assertRaises(VoiceProviderError) as raised:
				http.post("https://x.example/", b"", {"x-api-key": KEY})
		self.assertNotIn(KEY, str(raised.exception))
		with mock.patch("urllib.request.urlopen", side_effect=OSError(KEY)):
			with self.assertRaises(VoiceProviderError) as raised:
				list(http.stream("https://x.example/", b"", {}))
		self.assertNotIn(KEY, str(raised.exception))


class VoiceCase(CrmCase):
	def setUp(self):
		ensure_roles()
		create_test_users()
		_, self.lead = self.make_lead()
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		frappe.db.set_single_value("Telephony Settings", "provider", "fake")
		save_telephony_settings("FAKEOK1", "token-for-the-fake", LANDLINE)
		call_outcomes.ensure_default_outcomes()
		settings.save_voice_agent_settings(stt_provider="fake", tts_provider="fake", llm_provider="fake")

	def stream_for(self, log_name, script, clock):
		call_id = frappe.db.get_value("Call Log", log_name, "call_id")
		return replay(clock, call_id, script)  # lazy: the clock moves as the session reads each frame


class TestSettings(VoiceCase):
	"""SOS-P5-07: the providers, the model, the disclosure line and the keyterms are company settings."""

	def test_switching_the_provider_setting_changes_the_adapter_with_no_code_change(self):
		self.assertEqual([a.name for a in config.build_adapters()], ["fake", "fake", "fake"])
		settings.save_voice_agent_settings(
			stt_provider="deepgram-nova-3",
			tts_provider="elevenlabs",
			llm_provider="anthropic",
			voice_agent_model="a-fast-model-for-the-test",
			deepgram_key=KEY,
			elevenlabs_key=KEY,
			anthropic_key=KEY,
		)
		stt, llm, tts = config.build_adapters()
		self.assertEqual((stt.name, tts.name, llm.name), ("deepgram-nova-3", "elevenlabs", "anthropic"))
		self.assertEqual(llm.model, "a-fast-model-for-the-test")
		settings.save_voice_agent_settings(
			stt_provider="sarvam-saaras-v3", tts_provider="sarvam-bulbul-v3", sarvam_key=KEY
		)
		stt, _, tts = config.build_adapters()
		self.assertEqual((stt.name, tts.name), ("sarvam-saaras-v3", "sarvam-bulbul-v3"))
		settings.save_voice_agent_settings(stt_provider="fake")
		self.assertEqual(config.build_adapters()[0].name, "fake")

	def test_every_bake_off_candidate_has_an_adapter(self):
		self.assertEqual(set(config.STT) - {"fake"}, {"sarvam-saaras-v3", "deepgram-nova-3"})
		self.assertEqual(set(config.TTS) - {"fake"}, {"sarvam-bulbul-v3", "elevenlabs"})
		self.assertEqual(set(config.LLM) - {"fake"}, {"anthropic"})

	def test_a_missing_provider_key_or_model_is_a_clear_error(self):
		settings.save_voice_agent_settings(stt_provider="deepgram-nova-3")
		with self.assertRaises(VoiceProviderError) as raised:
			config.build_adapters()
		self.assertIn("speech to text", str(raised.exception))
		settings.save_voice_agent_settings(stt_provider="fake", llm_provider="anthropic", anthropic_key=KEY)
		with self.assertRaises(VoiceProviderError) as raised:
			config.build_adapters()
		self.assertIn("Voice agent model", str(raised.exception))
		settings.save_voice_agent_settings(stt_provider="", tts_provider="")
		with self.assertRaises(VoiceProviderError):
			config.build_adapters()

	def test_the_keys_are_stored_encrypted_and_never_returned(self):
		state = settings.save_voice_agent_settings(deepgram_key=KEY)
		self.assertTrue(state["keys_set"]["deepgram_key"])
		self.assertFalse(state["keys_set"]["sarvam_key"])
		self.assertNotIn(KEY, json.dumps(state))
		self.assertNotIn(KEY, json.dumps(settings.get_voice_agent_settings()))
		self.assertNotEqual(
			frappe.db.sql(
				"select value from tabSingles where doctype='Voice Agent Settings' and field='deepgram_key'"
			)[0][0],
			KEY,
		)
		self.assertTrue(settings.save_voice_agent_settings(deepgram_key="")["keys_set"]["deepgram_key"])

	def test_a_company_admin_edits_the_keyterms_and_the_disclosure_line(self):
		state = settings.save_voice_agent_settings(
			keyterms="Powai\n  Powai \n\nBandra  West\nstamp duty",
			disclosure_line="Namaste, main ek AI hoon.",
		)
		self.assertEqual(state["keyterms"], ["Powai", "Bandra West", "stamp duty"])
		self.assertEqual(config.load().keyterms, ["Powai", "Bandra West", "stamp duty"])
		self.assertEqual(config.load().disclosure, "Namaste, main ek AI hoon.")

	def test_the_disclosure_line_replaces_company_when_spoken_and_stays_raw_on_the_screen(self):
		old_name = frappe.db.get_single_value("SellOS Settings", "company_name")
		self.addCleanup(frappe.db.set_single_value, "SellOS Settings", "company_name", old_name)
		frappe.db.set_single_value("SellOS Settings", "company_name", "N21C Realty")
		frappe.clear_document_cache("SellOS Settings", "SellOS Settings")
		self.addCleanup(frappe.clear_document_cache, "SellOS Settings", "SellOS Settings")
		self.assertEqual(config.load().disclosure, DEFAULT_DISCLOSURE.replace("{company}", "N21C Realty"))
		self.assertIn("main Nicole baat kar rahi hoon", config.load().disclosure)
		self.assertEqual(settings.get_voice_agent_settings()["disclosure_line"], DEFAULT_DISCLOSURE)
		frappe.db.set_single_value("SellOS Settings", "company_name", "")
		frappe.clear_document_cache("SellOS Settings", "SellOS Settings")
		self.assertIn("Main the company ka AI assistant hoon", config.load().disclosure)
		self.assertNotIn("{company}", config.load().disclosure)

	def test_bad_settings_are_refused(self):
		for values in (
			{"disclosure_line": "  "},
			{"disclosure_line": "नमस्ते, मैं एक एआई हूँ"},
			{"stt_provider": "not-a-provider"},
			{"keyterms": ["x" * 81]},
			{"keyterms": [f"term {i}" for i in range(201)]},
		):
			with self.assertRaises(frappe.ValidationError, msg=str(values)):
				settings.save_voice_agent_settings(**values)

	def test_only_a_company_admin_may_call_the_settings_methods(self):
		for key in ("agent", "channel_partner", "platform_admin"):
			as_user(key)
			with self.assertRaises(frappe.PermissionError, msg=key):
				settings.get_voice_agent_settings()
			with self.assertRaises(frappe.PermissionError, msg=key):
				settings.save_voice_agent_settings(keyterms="x")
		as_user("company_admin")
		self.assertIn("fake", settings.get_voice_agent_settings()["choices"]["stt"])

	def test_the_fake_is_refused_on_a_site_that_does_not_allow_tests(self):
		with mock.patch.dict(frappe.local.conf, {"allow_tests": 0}):
			self.assertNotIn("fake", config.allowed_providers("stt"))
			with self.assertRaises(VoiceProviderError):
				config.build_adapters()
			with self.assertRaises(frappe.ValidationError):
				settings.save_voice_agent_settings(stt_provider="fake")


class TestCallLogWriteBack(VoiceCase):
	"""SOS-P5-07: consent before the call, the outcome and the transcript on the Call Log."""

	def run_stream(self, log, script, transcripts, replies=()):
		clock = SimClock()
		fakes = (
			adapters.FakeStt(transcripts, 0.15, clock),
			adapters.FakeLlm(replies, 0.25, clock),
			adapters.FakeTts(0.1, clock),
		)
		sent = []
		result = service.handle_stream(
			self.stream_for(log, script, clock), sent.append, clock=clock, adapters=fakes
		)
		return result, sent, fakes

	def test_the_outcome_transcript_and_turn_times_are_written_to_the_call_log(self):
		placed = service.start_agent_call(self.lead, "Service")
		result, sent, _ = self.run_stream(
			placed["log"],
			[("silence", 2.0), say(1.0), ("silence", 3.0), say(1.0), ("silence", 3.0)],
			["mujhe 2 BHK chahiye", "kal subah call kijiye"],
			["Kaunsa area dekh rahe hain?", "Theek hai, kal call karungi. [OUTCOME: Call back later]"],
		)
		log = frappe.get_doc("Call Log", placed["log"])
		self.assertEqual(log.mode, "AI")
		self.assertEqual(log.outcome, "Call back later")
		self.assertTrue(log.transcript.startswith(f"Agent: {config.load().disclosure}"))
		self.assertIn("Caller: kal subah call kijiye", log.transcript)
		latencies = json.loads(log.turn_latencies)
		self.assertEqual(len(latencies), 2)
		self.assertEqual(log.turn_count, 2)
		self.assertEqual(log.slowest_latency_ms, max(latencies))
		self.assertLessEqual(log.slowest_latency_ms, 1000)
		self.assertEqual(log.median_latency_ms, round(sum(latencies) / 2))
		self.assertEqual((log.handed_over, log.ai_end_reason), (0, "the agent ended the call"))
		self.assertEqual(log.ai_providers, "fake, fake, fake")
		self.assertEqual(result.outcome, "Call back later")
		self.assertEqual(json.loads(sent[0])["event"], "playAudio")

	def test_a_handover_is_written_to_the_call_log(self):
		placed = service.start_agent_call(self.lead, "Service")
		self.run_stream(placed["log"], [say(1.0), ("silence", 2.0)], [ASK_HUMAN])
		log = frappe.get_doc("Call Log", placed["log"])
		self.assertEqual((log.handed_over, log.handover_reason), (1, "the caller asked for a human"))
		self.assertIn(f"Agent: {HANDOVER_LINE}", log.transcript)

	def test_the_stream_runs_on_the_fakes_the_settings_name_with_no_adapters_given(self):
		placed = service.start_agent_call(self.lead, "Service")
		clock = SimClock()
		script = [("silence", 2.0), say(1.0), ("silence", 2.0), say(1.0), ("silence", 2.0)]
		service.handle_stream(self.stream_for(placed["log"], script, clock), lambda m: None, clock=clock)
		log = frappe.get_doc("Call Log", placed["log"])
		self.assertEqual((log.handed_over, log.handover_reason), (1, "confusion"))  # the fake hears nothing
		self.assertEqual(log.ai_providers, "fake, fake, fake")

	def test_the_company_keyterms_reach_the_speech_to_text_through_the_settings(self):
		settings.save_voice_agent_settings(keyterms="Powai\nRERA")
		placed = service.start_agent_call(self.lead, "Service")
		_, _, (stt, _, _) = self.run_stream(
			placed["log"], [("silence", 2.0), say(1.0), ("silence", 2.0)], ["haan boliye"]
		)
		self.assertEqual(stt.calls[0]["keyterms"], ["Powai", "RERA"])

	def test_the_consent_status_and_warning_are_recorded_and_never_block(self):
		consent.set_enforcement(False)
		placed = service.start_agent_call(self.lead, "Service")
		self.assertIsNotNone(placed["log"])
		self.assertEqual(placed["consent_status"], "Unknown")
		self.assertTrue(placed["warning"])
		log = frappe.get_doc("Call Log", placed["log"])
		self.assertEqual(frappe.db.get_value("Consent Check", log.consent_check, "consent_status"), "Unknown")
		self.assertEqual(frappe.db.get_value("Consent Check", log.consent_check, "refused"), 0)
		consent.record_opt_out(self.lead, "Phone call")
		again = service.start_agent_call(self.lead, "Service")
		self.assertEqual(again["consent_status"], "Opted out")
		self.assertIsNotNone(again["log"])  # an explicit stop is a red warning and never blocks

	def test_enforcement_on_is_the_one_function_that_can_refuse(self):
		consent.set_enforcement(True)
		placed = service.start_agent_call(self.lead, "Service")
		self.assertTrue(placed["check"].refused)
		self.assertIsNone(placed["log"])

	def test_each_call_records_its_purpose_and_a_promotional_one_is_a_warning(self):
		service_call = service.start_agent_call(self.lead, "Service")
		promo = service.start_agent_call(self.lead, "Promotional")
		self.assertEqual(frappe.db.get_value("Call Log", service_call["log"], "purpose"), "Service")
		self.assertEqual(frappe.db.get_value("Call Log", promo["log"], "purpose"), "Promotional")
		self.assertIn("022 number is for service and transactional", promo["warning"])
		self.assertNotIn("022 number", service_call["warning"])
		self.assertIsNotNone(promo["log"])  # a warning, never a refusal

	def test_an_agent_that_is_not_set_up_places_no_call(self):
		settings.save_voice_agent_settings(stt_provider="")
		with self.assertRaises(VoiceProviderError):
			service.start_agent_call(self.lead, "Service")
		self.assertEqual(frappe.db.count("Call Log", {"lead": self.lead}), 0)

	def test_an_empty_disclosure_line_places_no_live_call(self):
		"""SOS-N21C: the agent never places a live call while the AI disclosure line is empty."""
		frappe.db.set_single_value("Voice Agent Settings", "disclosure_line", "")
		frappe.clear_document_cache("Voice Agent Settings", "Voice Agent Settings")
		self.assertEqual(config.load().disclosure, "")
		with self.assertRaises(VoiceProviderError) as raised:
			service.start_agent_call(self.lead, "Service")
		self.assertIn("disclosure line is empty", str(raised.exception))
		self.assertEqual(frappe.db.count("Call Log", {"lead": self.lead}), 0)

	def test_a_stream_for_an_unknown_or_manual_call_is_refused(self):
		manual = service.call_log.place_logged_call(self.lead, "Service", mode="Manual")["log"]
		clock = SimClock()
		for call_id in ("no-such-call", frappe.db.get_value("Call Log", manual, "call_id"), ""):
			with self.assertRaises(VoiceProviderError):
				service.handle_stream(replay(clock, call_id, [("silence", 0.1)]), lambda m: None, clock=clock)
		self.assertIsNone(frappe.db.get_value("Call Log", manual, "transcript"))

	def test_the_lead_context_holds_no_phone_number(self):
		frappe.db.set_value(
			"Lead", self.lead, {"configuration": "2 BHK", "preferred_localities": "Bandra West"}
		)
		context = service.lead_context(self.lead)
		self.assertIn("Asha", context)
		self.assertIn("2 BHK", context)
		self.assertNotIn("+91", context)
		self.assertFalse(
			any(len(run) >= 10 for run in "".join(c if c.isdigit() else " " for c in context).split())
		)

	def test_the_socket_end_runs_a_call_over_any_socket(self):
		placed = service.start_agent_call(self.lead, "Service")
		clock = SimClock()

		class FakeSocket:
			def __init__(self, messages):
				self.messages, self.sent = messages, []

			def __iter__(self):
				return iter(self.messages)

			def send(self, message):
				self.sent.append(message)

		socket = FakeSocket(self.stream_for(placed["log"], [("silence", 2.0)], clock))
		fakes = (adapters.FakeStt((), 0, clock), adapters.FakeLlm((), 0, clock), adapters.FakeTts(0.1, clock))
		with mock.patch("frappe.enqueue") as queued:
			result = server.serve_connection(socket, clock=clock, adapters=fakes)
		self.assertEqual(json.loads(socket.sent[0])["event"], "playAudio")
		self.assertEqual(result.end_reason, "the caller hung up")
		# The write is queued for a worker, which commits it; running the job here saves it.
		call = queued.call_args
		self.assertEqual(call.args, ("sellos.voice.agent.service.save_values",))
		service.save_values(call.kwargs["log"], call.kwargs["values"])
		self.assertEqual(
			frappe.db.get_value("Call Log", placed["log"], "ai_end_reason"), "the caller hung up"
		)
		with mock.patch("frappe.enqueue") as queued:
			self.assertIsNone(server.serve_connection(FakeSocket([stream.stop_message()])))
		queued.assert_not_called()


class TestPlivoStream(IntegrationTestCase):
	"""SOS-P5-07: Plivo's audio streaming protocol."""

	def test_events_are_read_in_sellos_words(self):
		start = stream.parse(stream.start_message("call-9", stream.LINEAR16, "s1"))
		self.assertEqual(
			(start.kind, start.call_id, start.stream_id, start.encoding),
			("start", "call-9", "s1", stream.LINEAR16),
		)
		pcm = audio.tone(0.02)
		media = stream.parse(stream.media_message(pcm, stream.LINEAR16))
		self.assertEqual(stream.to_pcm(media.pcm, stream.LINEAR16), pcm)
		self.assertEqual(stream.parse(stream.stop_message()).kind, "stop")
		self.assertEqual(stream.parse(json.dumps({"event": "dtmf", "dtmf": {"digit": "5"}})).digit, "5")
		self.assertEqual(stream.parse(json.dumps({"event": "ping"})).kind, "other")

	def test_unreadable_events_are_refused(self):
		for raw in ("not json", "[]", json.dumps({"event": "media", "media": {"payload": "!!"}})):
			with self.assertRaises(stream.StreamError):
				stream.parse(raw)
		bad = json.dumps({"event": "start", "start": {"mediaFormat": {"encoding": "audio/ogg"}}})
		with self.assertRaises(stream.StreamError):
			stream.parse(bad)

	def test_the_answer_document_connects_the_call_to_a_secure_stream(self):
		xml = stream.answer_xml("wss://voice.example.test/stream?a=1&b=2")
		self.assertIn('bidirectional="true"', xml)
		self.assertIn("audio/x-mulaw;rate=8000", xml)
		self.assertIn("a=1&amp;b=2", xml)
		with self.assertRaises(stream.StreamError):
			stream.answer_xml("ws://insecure.example.test/")

	def test_clear_audio_names_the_stream(self):
		self.assertEqual(json.loads(stream.clear_audio("s1")), {"event": "clearAudio", "streamId": "s1"})
