"""Phone audio for the voice agent (SOS-P5-07): 8 kHz mu-law and 16 bit PCM, with the standard library only."""

import math
import struct

RATE = 8000
FRAME_SECONDS = 0.02
FRAME_SAMPLES = int(RATE * FRAME_SECONDS)  # 160 samples
BYTES_PER_SECOND = RATE * 2  # 16 bit mono

_BIAS = 0x84
_CLIP = 32635


def _decode_one(value: int) -> int:
	value = ~value & 0xFF
	exponent = (value >> 4) & 7
	sample = (((value & 0x0F) << 3) + _BIAS) << exponent
	sample -= _BIAS
	return -sample if value & 0x80 else sample


_DECODE = tuple(_decode_one(i) for i in range(256))


def ulaw_to_pcm(data: bytes) -> bytes:
	"""Mu-law bytes as little endian 16 bit PCM."""
	return struct.pack(f"<{len(data)}h", *(_DECODE[b] for b in data))


def _encode_one(sample: int) -> int:
	sign = 0x80 if sample < 0 else 0
	sample = min(abs(sample), _CLIP) + _BIAS
	exponent, mask = 7, 0x4000
	while exponent > 0 and not sample & mask:
		exponent -= 1
		mask >>= 1
	mantissa = (sample >> (exponent + 3)) & 0x0F
	return ~(sign | (exponent << 4) | mantissa) & 0xFF


def pcm_to_ulaw(pcm: bytes) -> bytes:
	"""Little endian 16 bit PCM as mu-law bytes."""
	count = len(pcm) // 2
	return bytes(_encode_one(s) for s in struct.unpack(f"<{count}h", pcm[: count * 2]))


def samples(pcm: bytes) -> tuple:
	count = len(pcm) // 2
	return struct.unpack(f"<{count}h", pcm[: count * 2])


def from_samples(values) -> bytes:
	values = [max(-32768, min(32767, int(v))) for v in values]
	return struct.pack(f"<{len(values)}h", *values)


def rms(pcm: bytes) -> float:
	"""The root mean square level of a block of PCM, 0 for an empty block."""
	values = samples(pcm)
	if not values:
		return 0.0
	return math.sqrt(sum(v * v for v in values) / len(values))


def seconds(pcm: bytes) -> float:
	return len(pcm) / BYTES_PER_SECOND


def tone(duration_s: float, frequency: int = 440, amplitude: int = 8000) -> bytes:
	"""A sine tone as PCM: stands in for speech in tests and fake voices."""
	count = int(duration_s * RATE)
	return from_samples(amplitude * math.sin(2 * math.pi * frequency * i / RATE) for i in range(count))


def silence(duration_s: float) -> bytes:
	return bytes(int(duration_s * RATE) * 2)


def is_roman(text: str) -> bool:
	"""True when every letter is Latin: transcripts and prompts are in Roman script (SOS-SETUP-30)."""
	return all(not ch.isalpha() or ord(ch) < 0x250 for ch in text or "")
