"""The speech to text, language model and text to speech adapters (SOS-P5-07).

Each kind of provider sits behind one small interface, so the provider in use is a setting and the
SOS-N21 choice can change without a rebuild:

* SttAdapter.transcribe(pcm, keyterms) -> Roman script text for one caller utterance (8 kHz, 16 bit
  PCM). The company's keyterms go to the provider on every call.
* LlmAdapter.reply(system, history, context) -> the agent's next line, in Roman Hinglish.
* TtsAdapter.synthesize(text) -> an iterator of 8 kHz, 16 bit PCM chunks, so the first audio can be
  sent before the rest is made.

There is an adapter for every bake-off candidate and a fake of each (no network, no key). An adapter
holds its key only to put it in a request header. It never puts it in an error, a log line or repr.
"""

import base64
import io
import json
import urllib.parse
import uuid
import wave

from sellos.voice.agent import audio, http
from sellos.voice.agent.http import VoiceProviderError

SYSTEM_PROMPT = (
	"You are the voice assistant of a real estate agency in Mumbai, on a phone call. Speak in Roman "
	"Hinglish (Hindi written in English letters, as people speak in Mumbai); never use Devanagari. Reply "
	"in one or two short spoken sentences. Use only the facts in the lead context and never invent a "
	"price, date or availability. Say numbers as words, as a person says them aloud. If asked, say "
	"plainly that you are an AI assistant. Never pressure the caller. Ask one qualifying question at a "
	"time: what they want to buy, where, the budget and when. When the caller wants a person, or you "
	"cannot help, reply only [HANDOVER]. When the call is done, finish your line with [OUTCOME: name] "
	"using one of: {outcomes}."
)


class SttAdapter:
	name = ""

	def transcribe(self, pcm: bytes, keyterms) -> str:
		raise NotImplementedError


class LlmAdapter:
	name = ""

	def reply(self, system: str, history, context: str) -> str:
		"""`history` is a list of (speaker, text), speaker "agent" or "caller"."""
		raise NotImplementedError


class TtsAdapter:
	name = ""

	def synthesize(self, text: str):
		raise NotImplementedError


# Fakes. A fake takes the session's clock and moves it by the delay it stands for, so a latency test
# measures a simulated turn with no sleeping.


class _Delayed:
	def __init__(self, delay_s=0.0, clock=None):
		self.delay_s, self.clock = delay_s, clock

	def _wait(self):
		if self.clock is not None and self.delay_s:
			self.clock.advance(self.delay_s)


class FakeStt(_Delayed, SttAdapter):
	"""Returns the next scripted transcript for each utterance, and records what it was given."""

	name = "fake"

	def __init__(self, transcripts=(), delay_s=0.15, clock=None):
		super().__init__(delay_s, clock)
		self.transcripts, self.calls = list(transcripts), []

	def transcribe(self, pcm, keyterms):
		self.calls.append({"seconds": audio.seconds(pcm), "keyterms": list(keyterms)})
		self._wait()
		return self.transcripts.pop(0) if self.transcripts else ""


class FakeLlm(_Delayed, LlmAdapter):
	name = "fake"

	def __init__(self, replies=(), delay_s=0.25, clock=None):
		super().__init__(delay_s, clock)
		self.replies, self.calls = list(replies), []

	def reply(self, system, history, context):
		self.calls.append({"system": system, "history": list(history), "context": context})
		self._wait()
		return (
			self.replies.pop(0)
			if self.replies
			else "Theek hai, kya main aapko ek aur sawaal pooch sakti hoon?"
		)


class FakeTts(_Delayed, TtsAdapter):
	"""Speaks a tone, 50 ms a word, in 20 ms chunks. The first chunk is what the delay waits for."""

	name = "fake"

	def __init__(self, delay_s=0.1, clock=None):
		super().__init__(delay_s, clock)
		self.spoken = []

	def synthesize(self, text):
		self.spoken.append(text)
		self._wait()
		pcm = audio.tone(max(0.05 * len(text.split()), 0.1))
		step = audio.FRAME_SAMPLES * 2
		for start in range(0, len(pcm), step):
			yield pcm[start : start + step]


# Live adapters. `post` and `stream` default to sellos.voice.agent.http and are replaced in tests.


def _multipart(fields: dict, file_name: str, file_bytes: bytes):
	boundary = uuid.uuid4().hex
	parts = [
		f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
		for key, value in fields.items()
	]
	parts.append(
		(
			f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
			"Content-Type: audio/wav\r\n\r\n"
		).encode()
		+ file_bytes
		+ b"\r\n"
	)
	parts.append(f"--{boundary}--\r\n".encode())
	return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _wav(pcm: bytes) -> bytes:
	buffer = io.BytesIO()
	with wave.open(buffer, "wb") as wav:
		wav.setnchannels(1)
		wav.setsampwidth(2)
		wav.setframerate(audio.RATE)
		wav.writeframes(pcm)
	return buffer.getvalue()


def _json(body: bytes, what: str):
	try:
		return json.loads(body)
	except ValueError:
		raise VoiceProviderError(f"The {what} provider sent an answer that could not be read.") from None


class _Keyed:
	def __init__(self, key, post=None, stream=None):
		self._key, self._post, self._stream = key, post or http.post, stream or http.stream

	def __repr__(self):
		return f"<{type(self).__name__} {self.name}>"


class SarvamStt(_Keyed, SttAdapter):
	"""Sarvam Saaras V3. mode "translit" returns Roman script. The keyterms go in the prompt field; the
	field names are confirmed on the first live call (SOS-P5-07L)."""

	name = "sarvam-saaras-v3"
	url = "https://api.sarvam.ai/speech-to-text"

	def transcribe(self, pcm, keyterms):
		fields = {"model": "saaras:v3", "mode": "translit", "language_code": "unknown"}
		if keyterms:
			fields["prompt"] = ", ".join(keyterms)
		body, content_type = _multipart(fields, "utterance.wav", _wav(pcm))
		reply = self._post(self.url, body, {"api-subscription-key": self._key, "Content-Type": content_type})
		return (_json(reply, "speech to text").get("transcript") or "").strip()


class DeepgramStt(_Keyed, SttAdapter):
	"""Deepgram Nova-3, language=multi, with the company's keyterms."""

	name = "deepgram-nova-3"
	url = "https://api.deepgram.com/v1/listen"

	def transcribe(self, pcm, keyterms):
		query = [
			("model", "nova-3"),
			("language", "multi"),
			("punctuate", "true"),
			("encoding", "linear16"),
			("sample_rate", str(audio.RATE)),
			("channels", "1"),
		]
		query += [("keyterm", term) for term in keyterms]
		reply = self._post(
			f"{self.url}?{urllib.parse.urlencode(query)}",
			pcm,
			{"Authorization": f"Token {self._key}", "Content-Type": "application/octet-stream"},
		)
		channels = _json(reply, "speech to text").get("results", {}).get("channels") or [{}]
		alternatives = channels[0].get("alternatives") or [{}]
		return (alternatives[0].get("transcript") or "").strip()


class SarvamTts(_Keyed, TtsAdapter):
	"""Sarvam Bulbul V3. It answers with whole audio, so there is one chunk."""

	name = "sarvam-bulbul-v3"
	url = "https://api.sarvam.ai/text-to-speech"

	def __init__(self, key, voice="", post=None, stream=None):
		super().__init__(key, post, stream)
		self.voice = voice

	def synthesize(self, text):
		payload = {
			"text": text,
			"target_language_code": "hi-IN",
			"model": "bulbul:v3",
			"speech_sample_rate": audio.RATE,
		}
		if self.voice:
			payload["speaker"] = self.voice
		reply = self._post(
			self.url,
			json.dumps(payload).encode(),
			{"api-subscription-key": self._key, "Content-Type": "application/json"},
		)
		try:
			wav_bytes = base64.b64decode(_json(reply, "text to speech")["audios"][0])
			with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
				pcm = wav.readframes(wav.getnframes())
		except (KeyError, IndexError, ValueError, wave.Error, EOFError):
			raise VoiceProviderError(
				"The text to speech provider sent audio that could not be read."
			) from None
		yield pcm


class ElevenLabsTts(_Keyed, TtsAdapter):
	"""ElevenLabs, streamed as 8 kHz PCM."""

	name = "elevenlabs"
	url = "https://api.elevenlabs.io/v1/text-to-speech"
	default_voice = "21m00Tcm4TlvDq8ikWAM"
	model_id = "eleven_multilingual_v2"

	def __init__(self, key, voice="", post=None, stream=None):
		super().__init__(key, post, stream)
		self.voice = voice or self.default_voice

	def synthesize(self, text):
		carry = b""
		chunks = self._stream(
			f"{self.url}/{urllib.parse.quote(self.voice, safe='')}/stream?output_format=pcm_8000",
			json.dumps({"text": text, "model_id": self.model_id}).encode(),
			{"xi-api-key": self._key, "Content-Type": "application/json"},
		)
		for chunk in chunks:
			buffered = carry + chunk
			usable = buffered[: len(buffered) - len(buffered) % 2]
			carry = buffered[len(usable) :]
			if usable:
				yield usable


class AnthropicLlm(_Keyed, LlmAdapter):
	"""A model on Anthropic's Messages API. The model is the setting "Voice agent model"."""

	url = "https://api.anthropic.com/v1/messages"

	def __init__(self, key, model, post=None, stream=None):
		super().__init__(key, post, stream)
		self.model, self.name = model, "anthropic"

	@staticmethod
	def messages(history):
		"""The history as alternating user and assistant messages, starting with the user."""
		out = [{"role": "user", "content": "(The call has connected.)"}]
		for speaker, text in history:
			role = "assistant" if speaker == "agent" else "user"
			if out[-1]["role"] == role:
				out[-1]["content"] += " " + text
			else:
				out.append({"role": role, "content": text})
		if out[-1]["role"] == "assistant":
			out.append({"role": "user", "content": "(The caller is silent.)"})
		return out

	def reply(self, system, history, context):
		body = {
			"model": self.model,
			"max_tokens": 200,
			"system": f"{system}\n\nLead context: {context}",
			"messages": self.messages(history),
		}
		reply = self._post(
			self.url,
			json.dumps(body).encode(),
			{"x-api-key": self._key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
		)
		blocks = _json(reply, "language model").get("content") or []
		return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
