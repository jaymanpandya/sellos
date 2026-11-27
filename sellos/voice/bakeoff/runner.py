"""Runs the three comparisons and collects their numbers (SOS-N21A)."""

import re
import statistics
from pathlib import Path

from sellos.voice.bakeoff import audio, data, keys, scoring, transport

LLM_MODELS_FILE = "llm-models.txt"
KNOWN_FAILURES = (transport.ProviderError, keys.SecretMissing, keys.UnknownSecretName)


class ModelListError(ValueError):
	"""llm-models.txt does not hold two or three model names."""


def read_models(path):
	"""The candidate model names: one per line, two or three of them. Anything else is refused."""
	path = Path(path)
	if not path.is_file():
		raise ModelListError(
			f"{path} does not exist. Write two or three Anthropic model names in it, one per line."
		)
	names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
	if not 2 <= len(names) <= 3:
		raise ModelListError(
			f"{path} must hold two or three model names, one per line. It holds {len(names)}."
		)
	return names


class SarvamModelError(ValueError):
	"""sarvam-llm-model.txt is missing, empty or does not hold one model name."""


def read_sarvam_model(path):
	"""The Sarvam chat model name (SOS-N21B): one line, written by Jayman. The agent never picks one."""
	path = Path(path)
	if not path.is_file():
		raise SarvamModelError(f"{path} does not exist. Write the Sarvam chat model name in it, on one line.")
	names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
	if len(names) != 1:
		raise SarvamModelError(
			f"{path} must hold one Sarvam model name on one line. It holds {len(names)} non-empty lines."
		)
	if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", names[0]):
		raise SarvamModelError(f"{path} does not hold a model name (letters, digits and . _ : / - only).")
	return names[0]


def load_reference(path):
	"""Rows of reference.tsv as dicts: file, reference, and the entity lists."""
	lines = Path(path).read_text(encoding="utf-8").splitlines()
	header = lines[0].split("\t")
	rows = []
	for line in lines[1:]:
		if not line.strip():
			continue
		cells = dict(zip(header, line.split("\t") + [""] * len(header), strict=False))
		rows.append(
			{
				"file": cells["file"],
				"reference": cells["reference"],
				"entities": {
					kind: [e.strip() for e in cells.get(kind, "").split(";") if e.strip()]
					for kind in scoring.ENTITY_KINDS
				},
			}
		)
	return rows


def reference_tsv():
	header = "file\treference\tnumbers\tprices\tlocalities"
	return header + "\n" + "\n".join("\t".join(row) for row in data.CALLER_LINES) + "\n"


def _failure(exc):
	"""What to record for a failed call: a known failure's sentence, else only the exception's type."""
	return str(exc) if isinstance(exc, KNOWN_FAILURES) else f"the call failed ({type(exc).__name__})"


def _slug(name):
	return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "model"


def run_stt(adapters, rows, audio_dir, out_dir):
	"""{provider: [per file result]}. Each recording goes out as 8 kHz mono audio."""
	results = {}
	for adapter in adapters:
		folder = Path(out_dir) / _slug(adapter.name)
		folder.mkdir(parents=True, exist_ok=True)
		items = []
		for row in rows:
			item = {"file": row["file"], "reference": row["reference"], "error": None}
			try:
				wav = audio.wav_bytes(audio.to_phone_audio(Path(audio_dir) / row["file"]))
				result, elapsed = _timed(adapter.transcribe, row["file"], wav)
				first = result.first_result_s if result.first_result_s is not None else elapsed
			except (*KNOWN_FAILURES, audio.AudioError, OSError, ValueError, KeyError, TypeError) as exc:
				item["error"] = _failure(exc)
				items.append(item)
				continue
			(folder / (Path(row["file"]).stem + ".txt")).write_text(
				result.transcript + "\n", encoding="utf-8"
			)
			item.update(
				transcript=result.transcript,
				wer=scoring.word_error_rate(row["reference"], result.transcript),
				entities=scoring.entity_scores(row["entities"], result.transcript),
				first_result_s=first,
			)
			items.append(item)
		results[adapter.name] = items
	return results


def _timed(function, *args):
	import time

	started = time.perf_counter()
	result = function(*args)
	return result, time.perf_counter() - started


def run_tts(adapters, out_dir):
	"""{provider: [per reply result]}; the audio is saved as <out>/<provider>/NN.wav."""
	results = {}
	for adapter in adapters:
		folder = Path(out_dir) / _slug(adapter.name)
		folder.mkdir(parents=True, exist_ok=True)
		items = []
		for number, (_caller, _context, reply) in enumerate(data.REPLIES, start=1):
			item = {"number": number, "text": reply, "error": None}
			try:
				result = adapter.synthesize(reply)
			except (*KNOWN_FAILURES, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
				item["error"] = _failure(exc)
				items.append(item)
				continue
			path = folder / f"{number:02d}.wav"
			path.write_bytes(result.wav)
			item.update(
				audio=f"{_slug(adapter.name)}/{path.name}",
				first_audio_s=result.first_audio_s,
				total_s=result.total_s,
			)
			items.append(item)
		results[adapter.name] = items
	return results


def scenarios():
	return [
		{"number": n, "caller": caller, "context": context, "reply": reply}
		for n, (caller, context, reply) in enumerate(data.REPLIES, start=1)
	]


def voice_scenarios():
	"""The disclosure line and the handover cases of SOS-N21B, in the shape the adapters take."""
	return [
		{"number": n, "label": label, "caller": caller, "context": context, "reply": reply}
		for n, (label, caller, context, reply) in enumerate(data.voice_cases(), start=1)
	]


def run_llm(adapters, out_dir, system=data.SYSTEM_PROMPT, cases=None):
	"""{model: [per reply result]}. Every model gets the same system prompt and the same 20 scenarios,
	or the same `cases`."""
	results = {}
	for adapter in adapters:
		folder = Path(out_dir) / _slug(adapter.name)
		folder.mkdir(parents=True, exist_ok=True)
		items = []
		for scenario in cases or scenarios():
			item = {"number": scenario["number"], "error": None}
			try:
				result = adapter.generate(system, scenario)
			except (*KNOWN_FAILURES, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
				item["error"] = _failure(exc)
				items.append(item)
				continue
			(folder / f"{scenario['number']:02d}.txt").write_text(result.text + "\n", encoding="utf-8")
			item.update(text=result.text, first_token_s=result.first_token_s, total_s=result.total_s)
			items.append(item)
		results[adapter.name] = items
	return results


def run_voice_llm(adapters, out_dir):
	"""{model: [per case result]} for the voice comparison (SOS-N21B), saved under <out>/voice-llm/."""
	return run_llm(adapters, Path(out_dir) / "voice-llm", data.VOICE_SYSTEM_PROMPT, voice_scenarios())


def handed_over(text):
	"""True when a reply is the handover tag alone: what a handover case must produce."""
	return (text or "").strip() == data.HANDOVER_TAG


def stt_summary(items):
	"""Mean WER, entity accuracy per kind, and first result times over the files that ran."""
	done = [i for i in items if not i["error"]]
	summary = {"files": len(items), "failed": len(items) - len(done), "wer": None, "first": []}
	if done:
		summary["wer"] = statistics.mean(i["wer"] for i in done)
		summary["first"] = [i["first_result_s"] for i in done]
	for kind in scoring.ENTITY_KINDS:
		found = sum(i["entities"][kind][0] for i in done)
		total = sum(i["entities"][kind][1] for i in done)
		summary[kind] = scoring.accuracy(found, total)
	return summary
