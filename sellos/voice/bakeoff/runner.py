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


def run_llm(adapters, out_dir, system=data.SYSTEM_PROMPT):
	"""{model: [per reply result]}. Every model gets the same system prompt and the same 20 scenarios."""
	results = {}
	for adapter in adapters:
		folder = Path(out_dir) / _slug(adapter.name)
		folder.mkdir(parents=True, exist_ok=True)
		items = []
		for scenario in scenarios():
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
