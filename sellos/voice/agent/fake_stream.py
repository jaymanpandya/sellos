"""A fake Plivo audio stream that replays recorded 8 kHz audio (SOS-P5-07).

`replay` yields the events Plivo would send for a call: start, then the caller's recordings as 20 ms
`media` events with silence between them, then stop. It moves a simulated clock by 20 ms a frame, so
a test measures the time of each turn with no sleeping. A real call is SOS-P5-07L.
"""

from sellos.voice.agent import audio, stream
from sellos.voice.bakeoff import audio as wav_audio


class SimClock:
	"""A clock the test moves. Calling it returns the time."""

	def __init__(self, start=100.0):
		self.now = start

	def __call__(self):
		return self.now

	def advance(self, seconds):
		self.now += seconds


def speech_recording(seconds: float) -> bytes:
	"""A WAV recording of `seconds` of loud audio at 8 kHz: it stands in for a caller speaking."""
	return wav_audio.wav_bytes(wav_audio.tone(seconds))


def recording_pcm(wav_bytes: bytes) -> bytes:
	"""A WAV recording as 8 kHz PCM, converting it first when it is not 8 kHz."""
	return audio.from_samples(wav_audio.to_phone_audio(wav_bytes))


def _frames(pcm: bytes):
	step = audio.FRAME_SAMPLES * 2
	for start in range(0, len(pcm), step):
		frame = pcm[start : start + step]
		yield frame + bytes(step - len(frame))


def replay(clock, call_id, script, encoding=stream.MULAW):
	"""The stream events for `script`, a list of ("speech", wav_bytes), ("silence", seconds) or ("hangup",)."""
	yield stream.start_message(call_id, encoding)
	for step in script:
		if step[0] == "hangup":
			break
		pcm = recording_pcm(step[1]) if step[0] == "speech" else audio.silence(step[1])
		for frame in _frames(pcm):
			clock.advance(audio.FRAME_SECONDS)
			yield stream.media_message(frame, encoding)
	yield stream.stop_message()
