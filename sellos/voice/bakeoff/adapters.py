"""One adapter interface for each kind of provider, and the fakes (SOS-N21A).

A provider is added by writing one adapter: a class with a `name` and one method (`transcribe`,
`synthesize` or `generate`) that returns the matching result with its latencies in seconds.
"""

import base64
import json
import os
import time
import urllib.parse
import uuid

from sellos.voice.bakeoff import audio, data, keys, transport


class SttResult:
	"""A transcript and the time to the first result. `first_result_s` None means: the whole call."""

	def __init__(self, transcript, first_result_s=None):
		self.transcript, self.first_result_s = transcript, first_result_s


class TtsResult:
	def __init__(self, wav, first_audio_s, total_s):
		self.wav, self.first_audio_s, self.total_s = wav, first_audio_s, total_s


class LlmResult:
	def __init__(self, text, first_token_s, total_s):
		self.text, self.first_token_s, self.total_s = text, first_token_s, total_s


class SttAdapter:
	name = ""

	def transcribe(self, file_name, wav_8k):
		"""A transcript of `wav_8k` (WAV bytes, 8 kHz mono) as an SttResult."""
		raise NotImplementedError


class TtsAdapter:
	name = ""

	def synthesize(self, text):
		"""`text` spoken at 8 kHz as a TtsResult."""
		raise NotImplementedError


class LlmAdapter:
	name = ""

	def generate(self, system, scenario):
		"""The model's reply to `scenario` as an LlmResult."""
		raise NotImplementedError


# Fakes: no network, no key. Used by --fake and by the tests.


class FakeStt(SttAdapter):
	"""Says what the reference says, dropping the last `drop` words; reports a fixed first result time."""

	def __init__(self, name, references, drop=0, first_result_s=0.25):
		self.name, self.references, self.drop, self.first_result_s = name, references, drop, first_result_s

	def transcribe(self, file_name, wav_8k):
		words = self.references[file_name].split()
		kept = words[: len(words) - self.drop] if self.drop else words
		return SttResult(" ".join(kept), self.first_result_s)


class FakeTts(TtsAdapter):
	def __init__(self, name, first_audio_s=0.12, total_s=0.4):
		self.name, self.first_audio_s, self.total_s = name, first_audio_s, total_s

	def synthesize(self, text):
		samples = audio.tone(min(0.05 * len(text.split()), 2.0))
		return TtsResult(audio.wav_bytes(samples), self.first_audio_s, self.total_s)


class FakeLlm(LlmAdapter):
	def __init__(self, name, first_token_s=0.2, total_s=0.9):
		self.name, self.first_token_s, self.total_s = name, first_token_s, total_s

	def generate(self, system, scenario):
		return LlmResult(f"({self.name}) {scenario['reply']}", self.first_token_s, self.total_s)


# Live adapters. Each sends the request through transport.post, which holds the key.


def _multipart(fields, file_field, file_name, file_bytes):
	boundary = uuid.uuid4().hex
	parts = []
	for key, value in fields.items():
		parts.append(
			f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
		)
	parts.append(
		(
			f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'
			"Content-Type: audio/wav\r\n\r\n"
		).encode()
		+ file_bytes
		+ b"\r\n"
	)
	parts.append(f"--{boundary}--\r\n".encode())
	return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class SarvamStt(SttAdapter):
	"""Sarvam Saaras V3 over its HTTP API. The call returns the whole transcript, so the time to first
	result is the time to the answer. `mode` and `language` are settings to confirm on the first live run."""

	name = "sarvam-saaras-v3"

	def __init__(self, base_url="https://api.sarvam.ai", mode="translit", language="unknown"):
		self.base_url, self.mode, self.language = base_url, mode, language

	def transcribe(self, file_name, wav_8k):
		body, content_type = _multipart(
			{"model": "saaras:v3", "mode": self.mode, "language_code": self.language},
			"file",
			file_name,
			wav_8k,
		)
		reply = transport.post(
			f"{self.base_url}/speech-to-text",
			body,
			("api-subscription-key", "", keys.SARVAM),
			{"Content-Type": content_type},
		)
		return SttResult(json.loads(reply.body).get("transcript", ""), reply.total_s)


class DeepgramStt(SttAdapter):
	"""Deepgram Nova-3, language=multi, with the real estate keyterms, over its HTTP API."""

	name = "deepgram-nova-3"

	def __init__(self, base_url="https://api.deepgram.com", keyterms=data.KEYTERMS):
		self.base_url, self.keyterms = base_url, keyterms

	def transcribe(self, file_name, wav_8k):
		query = [("model", "nova-3"), ("language", "multi"), ("punctuate", "true")]
		query += [("keyterm", term) for term in self.keyterms]
		reply = transport.post(
			f"{self.base_url}/v1/listen?{urllib.parse.urlencode(query)}",
			wav_8k,
			("Authorization", "Token ", keys.DEEPGRAM),
			{"Content-Type": "audio/wav"},
		)
		channels = json.loads(reply.body).get("results", {}).get("channels") or [{}]
		alternatives = channels[0].get("alternatives") or [{}]
		return SttResult(alternatives[0].get("transcript", ""), reply.total_s)


class SarvamTts(TtsAdapter):
	"""Sarvam Bulbul V3. The call returns whole audio, so the first audio time equals the total."""

	name = "sarvam-bulbul-v3"

	def __init__(self, base_url="https://api.sarvam.ai", speaker=None):
		self.base_url, self.speaker = base_url, speaker or os.environ.get("SELLOS_BAKEOFF_SARVAM_SPEAKER")

	def synthesize(self, text):
		payload = {
			"text": text,
			"target_language_code": "hi-IN",
			"model": "bulbul:v3",
			"speech_sample_rate": audio.PHONE_RATE,
		}
		if self.speaker:
			payload["speaker"] = self.speaker
		reply = transport.post(
			f"{self.base_url}/text-to-speech",
			json.dumps(payload).encode(),
			("api-subscription-key", "", keys.SARVAM),
			{"Content-Type": "application/json"},
		)
		wav = base64.b64decode(json.loads(reply.body)["audios"][0])
		return TtsResult(wav, reply.total_s, reply.total_s)


class ElevenLabsTts(TtsAdapter):
	"""ElevenLabs, streamed as 8 kHz PCM. The voice comes from SELLOS_BAKEOFF_ELEVENLABS_VOICE."""

	name = "elevenlabs"

	def __init__(
		self, base_url="https://api.elevenlabs.io", voice_id=None, model_id="eleven_multilingual_v2"
	):
		self.base_url, self.model_id = base_url, model_id
		self.voice_id = voice_id or os.environ.get("SELLOS_BAKEOFF_ELEVENLABS_VOICE", "21m00Tcm4TlvDq8ikWAM")

	def synthesize(self, text):
		reply = transport.post(
			f"{self.base_url}/v1/text-to-speech/{self.voice_id}/stream?output_format=pcm_8000",
			json.dumps({"text": text, "model_id": self.model_id}).encode(),
			("xi-api-key", "", keys.ELEVENLABS),
			{"Content-Type": "application/json"},
		)
		return TtsResult(audio.pcm_to_wav(reply.body), reply.first_byte_s, reply.total_s)


class _SseText:
	"""Collects the text deltas of an Anthropic stream and the time of the first one."""

	def __init__(self):
		self.buffer, self.text, self.first_token_s = b"", [], None

	def feed(self, chunk, elapsed):
		self.buffer += chunk
		while b"\n" in self.buffer:
			line, self.buffer = self.buffer.split(b"\n", 1)
			line = line.strip()
			if not line.startswith(b"data:"):
				continue
			try:
				event = json.loads(line[5:])
			except ValueError:
				continue
			delta = event.get("delta") or {}
			if event.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
				if self.first_token_s is None:
					self.first_token_s = elapsed
				self.text.append(delta.get("text", ""))


class AnthropicLlm(LlmAdapter):
	"""A model on Anthropic's Messages API, streamed over HTTPS with the standard library."""

	def __init__(self, model, base_url="https://api.anthropic.com"):
		self.name, self.model, self.base_url = model, model, base_url

	def generate(self, system, scenario):
		prompt = f"Lead context: {scenario['context']}\nCaller's line: {scenario['caller']}\nYour reply:"
		body = {
			"model": self.model,
			"max_tokens": 300,
			"stream": True,
			"system": system,
			"messages": [{"role": "user", "content": prompt}],
		}
		sse = _SseText()
		reply = transport.post(
			f"{self.base_url}/v1/messages",
			json.dumps(body).encode(),
			("x-api-key", "", keys.ANTHROPIC),
			{"Content-Type": "application/json", "anthropic-version": "2023-06-01"},
			on_chunk=sse.feed,
			keep_body=False,
		)
		first = sse.first_token_s if sse.first_token_s is not None else reply.total_s
		return LlmResult("".join(sse.text).strip(), first, reply.total_s)


def timed(function, *args):
	"""(result, seconds) for one call."""
	started = time.perf_counter()
	result = function(*args)
	return result, time.perf_counter() - started
