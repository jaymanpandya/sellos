"""WAV reading, 8 kHz mono conversion and writing, with the standard library only (SOS-N21A)."""

import io
import math
import struct
import wave
from array import array

PHONE_RATE = 8000


class AudioError(ValueError):
	"""A recording that cannot be read."""


def read_wav(source):
	"""(samples, rate): 16-bit samples mixed down to mono. `source` is a path or bytes."""
	handle = io.BytesIO(source) if isinstance(source, bytes | bytearray) else str(source)
	try:
		with wave.open(handle, "rb") as wav:
			width, channels, rate = wav.getsampwidth(), wav.getnchannels(), wav.getframerate()
			frames = wav.readframes(wav.getnframes())
	except (wave.Error, EOFError, OSError) as exc:
		raise AudioError(f"not a readable WAV file ({exc})") from None
	if width != 2:
		raise AudioError("only 16-bit PCM WAV recordings are supported")
	pcm = array("h")
	pcm.frombytes(frames[: len(frames) - len(frames) % (2 * channels)])
	if struct.pack("=h", 1) != struct.pack("<h", 1):
		pcm.byteswap()
	if channels == 1:
		return list(pcm), rate
	return [sum(pcm[i : i + channels]) // channels for i in range(0, len(pcm), channels)], rate


def resample(samples, source_rate, target_rate=PHONE_RATE):
	"""Samples at target_rate: block averages going down (a low pass), linear interpolation going up."""
	if source_rate == target_rate or not samples:
		return list(samples)
	count = int(len(samples) * target_rate / source_rate)
	ratio = source_rate / target_rate
	out = []
	if ratio > 1:
		prefix = [0]
		for sample in samples:
			prefix.append(prefix[-1] + sample)
		for i in range(count):
			start = min(int(i * ratio), len(samples) - 1)
			end = max(min(int((i + 1) * ratio), len(samples)), start + 1)
			out.append((prefix[end] - prefix[start]) // (end - start))
		return out
	for i in range(count):
		position = i * ratio
		left = min(int(position), len(samples) - 1)
		right = min(left + 1, len(samples) - 1)
		fraction = position - left
		out.append(int(samples[left] * (1 - fraction) + samples[right] * fraction))
	return out


def to_phone_audio(source):
	"""A WAV recording as 8 kHz mono samples, converting it first when it is not 8 kHz."""
	samples, rate = read_wav(source)
	return resample(samples, rate, PHONE_RATE)


def wav_bytes(samples, rate=PHONE_RATE):
	buffer = io.BytesIO()
	with wave.open(buffer, "wb") as wav:
		wav.setnchannels(1)
		wav.setsampwidth(2)
		wav.setframerate(rate)
		clipped = [max(-32768, min(32767, int(s))) for s in samples]
		pcm = array("h", clipped)
		if struct.pack("=h", 1) != struct.pack("<h", 1):
			pcm.byteswap()
		wav.writeframes(pcm.tobytes())
	return buffer.getvalue()


def pcm_to_wav(pcm_bytes, rate=PHONE_RATE):
	"""Wrap raw little endian 16-bit mono PCM in a WAV container."""
	pcm = array("h")
	pcm.frombytes(pcm_bytes[: len(pcm_bytes) - len(pcm_bytes) % 2])
	if struct.pack("=h", 1) != struct.pack("<h", 1):
		pcm.byteswap()
	return wav_bytes(list(pcm), rate)


def tone(seconds, rate=PHONE_RATE, frequency=440, amplitude=8000):
	"""A sine tone, used for test recordings and fake speech."""
	return [int(amplitude * math.sin(2 * math.pi * frequency * i / rate)) for i in range(int(seconds * rate))]


def duration(samples, rate=PHONE_RATE):
	return len(samples) / rate
