"""Plivo's audio streaming protocol, in SellOS's words (SOS-P5-07).

Plivo opens a WebSocket to the service and sends JSON events: `start` (with the call and stream ids
and the audio format), `media` (base64 audio, 20 ms at a time), `dtmf` and `stop`. The service sends
`playAudio` to speak and `clearAudio` to stop what is still queued. The audio is 8 kHz, mu-law
(audio/x-mulaw) or 16 bit linear (audio/x-l16). The first call against the real service is SOS-P5-07L,
which confirms the field names below against Plivo's own events.
"""

import base64
import json
from dataclasses import dataclass

from sellos.voice.agent import audio

MULAW = "audio/x-mulaw"
LINEAR16 = "audio/x-l16"
ENCODINGS = (MULAW, LINEAR16)


class StreamError(ValueError):
	"""A message that is not a Plivo stream event."""


@dataclass
class Event:
	kind: str  # start, media, dtmf, stop or other
	call_id: str = ""
	stream_id: str = ""
	encoding: str = MULAW
	pcm: bytes = b""
	digit: str = ""


def parse(raw) -> Event:
	"""One incoming message as an Event. Raises StreamError for anything unreadable."""
	try:
		message = json.loads(raw) if isinstance(raw, str | bytes | bytearray) else dict(raw)
	except (ValueError, TypeError):
		raise StreamError("The stream message could not be read.") from None
	if not isinstance(message, dict):
		raise StreamError("The stream message could not be read.")
	kind = message.get("event")
	if kind == "start":
		start = message.get("start") or {}
		encoding = (start.get("mediaFormat") or {}).get("encoding") or MULAW
		if encoding not in ENCODINGS:
			raise StreamError("The stream audio format is not supported.")
		return Event(
			"start",
			call_id=str(start.get("callId") or ""),
			stream_id=str(start.get("streamId") or message.get("streamId") or ""),
			encoding=encoding,
		)
	if kind == "media":
		return Event("media", stream_id=str(message.get("streamId") or ""), pcm=_payload(message))
	if kind == "dtmf":
		return Event("dtmf", digit=str((message.get("dtmf") or {}).get("digit") or ""))
	if kind == "stop":
		return Event("stop")
	return Event("other")


def _payload(message) -> bytes:
	try:
		return base64.b64decode((message.get("media") or {}).get("payload") or "", validate=True)
	except ValueError:
		raise StreamError("The stream audio could not be read.") from None


def to_pcm(payload: bytes, encoding: str) -> bytes:
	"""A media payload as 16 bit PCM."""
	return audio.ulaw_to_pcm(payload) if encoding == MULAW else payload


def play_audio(pcm: bytes, encoding: str = MULAW) -> str:
	"""The message that speaks `pcm` to the caller."""
	payload = audio.pcm_to_ulaw(pcm) if encoding == MULAW else pcm
	return json.dumps(
		{
			"event": "playAudio",
			"media": {
				"contentType": encoding,
				"sampleRate": audio.RATE,
				"payload": base64.b64encode(payload).decode(),
			},
		}
	)


def clear_audio(stream_id: str = "") -> str:
	"""The message that stops the audio still queued: the caller spoke over the agent."""
	return json.dumps({"event": "clearAudio", "streamId": stream_id})


def media_message(pcm: bytes, encoding: str = MULAW, stream_id: str = "stream") -> str:
	"""A `media` event as Plivo sends it. The fake stream uses it to replay recorded audio."""
	payload = audio.pcm_to_ulaw(pcm) if encoding == MULAW else pcm
	return json.dumps(
		{
			"event": "media",
			"streamId": stream_id,
			"media": {"track": "inbound", "payload": base64.b64encode(payload).decode()},
		}
	)


def start_message(call_id: str, encoding: str = MULAW, stream_id: str = "stream") -> str:
	return json.dumps(
		{
			"event": "start",
			"start": {
				"callId": call_id,
				"streamId": stream_id,
				"mediaFormat": {"encoding": encoding, "sampleRate": audio.RATE},
			},
		}
	)


def stop_message() -> str:
	return json.dumps({"event": "stop"})


def answer_xml(stream_url: str) -> str:
	"""The answer document that connects a call's audio to the service. `stream_url` is wss://."""
	if not stream_url.startswith("wss://"):
		raise StreamError("The stream address must start with wss://.")
	return (
		'<Response><Stream bidirectional="true" keepCallAlive="true" '
		f'contentType="{MULAW};rate={audio.RATE}">{_escape(stream_url)}</Stream></Response>'
	)


def _escape(text: str) -> str:
	return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
