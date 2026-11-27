"""The markdown files the harness writes (SOS-N21A). None of them can hold a key: only results are passed in."""

import statistics

from sellos.voice.bakeoff import data, runner

NOT_RUN = (
	"# Voice bake-off results\n\n"
	"**Not run yet.** Jayman runs the harness on his own machine with `scripts/bakeoff.sh --live`. "
	"It then replaces this file with one table per provider and a summary table.\n\n"
	"The speech to text, text to speech and language model providers are compared on our own Hinglish "
	"phone audio, so that SOS-N21 chooses from measurements and not from vendor claims.\n"
)


def _cell(value, digits=3):
	return "n/a" if value is None else f"{value:.{digits}f}"


def _percent(value):
	return "n/a" if value is None else f"{value * 100:.0f}%"


def _entity(pair):
	found, total = pair
	return "-" if total == 0 else f"{found}/{total}"


def _median(values):
	return statistics.median(values) if values else None


def _slowest(values):
	return max(values) if values else None


def _row(cells):
	return "| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in cells) + " |"


def _table(header, rows):
	return "\n".join([_row(header), _row("---" for _ in header), *(_row(r) for r in rows)])


def results_md(stt, tts, llm, title="Voice bake-off results", note=""):
	out = [f"# {title}", ""]
	if note:
		out += [note, ""]
	out += [
		(
			"Speech to text calls use each provider's HTTP API and return a whole transcript, so the time to first result is the time to that answer. Text to speech first audio is the first streamed chunk where the provider streams, else the whole call."
		),
		"",
	]
	for provider, items in stt.items():
		out += [f"## Speech to text: {provider}", ""]
		rows = []
		for i in items:
			if i["error"]:
				rows.append([i["file"], f"FAILED: {i['error']}", "", "", "", "", ""])
				continue
			e = i["entities"]
			rows.append(
				[
					i["file"], i["transcript"], _cell(i["wer"]), _entity(e["numbers"]),
					_entity(e["prices"]), _entity(e["localities"]), _cell(i["first_result_s"]),
				]
			)  # fmt: skip
		out += [
			_table(
				["File", "Transcript", "WER", "Numbers", "Prices", "Localities", "First result (s)"], rows
			),
			"",
		]
	for provider, items in tts.items():
		out += [f"## Text to speech: {provider}", ""]
		rows = [
			[i["number"], f"FAILED: {i['error']}", "", ""]
			if i["error"]
			else [i["number"], i["audio"], _cell(i["first_audio_s"]), _cell(i["total_s"])]
			for i in items
		]
		out += [_table(["Reply", "Audio", "First audio (s)", "Total (s)"], rows), ""]
	for model, items in llm.items():
		out += [f"## Language model: {model}", ""]
		rows = [
			[i["number"], f"FAILED: {i['error']}", "", ""]
			if i["error"]
			else [i["number"], i["text"], _cell(i["first_token_s"]), _cell(i["total_s"])]
			for i in items
		]
		out += [_table(["Reply", "Text", "First token (s)", "Total (s)"], rows), ""]
	out += ["## Summary", "", "### Speech to text", ""]
	rows = []
	for provider, items in stt.items():
		s = runner.stt_summary(items)
		rows.append(
			[
				provider, f"{s['files'] - s['failed']}/{s['files']}", _percent(s["wer"]),
				_percent(s["numbers"]), _percent(s["prices"]), _percent(s["localities"]),
				_cell(_median(s["first"])), _cell(_slowest(s["first"])),
			]
		)  # fmt: skip
	out += [
		_table(
			[
				"Provider",
				"Files scored",
				"Mean WER",
				"Numbers",
				"Prices",
				"Localities",
				"Median first result (s)",
				"Slowest (s)",
			],
			rows,
		),
		"",
		"### Text to speech",
		"",
	]
	rows = []
	for provider, items in tts.items():
		ok = [i for i in items if not i["error"]]
		first, total = [i["first_audio_s"] for i in ok], [i["total_s"] for i in ok]
		rows.append(
			[provider, f"{len(ok)}/{len(items)}", _cell(_median(first)), _cell(_slowest(first)),
			_cell(_median(total)), _cell(_slowest(total))]
		)  # fmt: skip
	out += [
		_table(
			[
				"Provider",
				"Replies",
				"Median first audio (s)",
				"Slowest (s)",
				"Median total (s)",
				"Slowest (s)",
			],
			rows,
		),
		"",
		"### Language models",
		"",
	]
	rows = []
	for model, items in llm.items():
		ok = [i for i in items if not i["error"]]
		first, total = [i["first_token_s"] for i in ok], [i["total_s"] for i in ok]
		rows.append(
			[model, f"{len(ok)}/{len(items)}", _cell(_median(first)), _cell(_slowest(first)),
			_cell(_median(total)), _cell(_slowest(total))]
		)  # fmt: skip
	out += [
		_table(
			["Model", "Replies", "Median first token (s)", "Slowest (s)", "Median total (s)", "Slowest (s)"],
			rows,
		),
		"",
	]
	return "\n".join(out)


def sentences_md():
	lines = [f"{i}. `{f}`: {text}" for i, (f, text, *_rest) in enumerate(data.CALLER_LINES, start=1)]
	return (
		"# Bake-off sentences\n\n"
		"Record each line as its own WAV file, named as shown, in `~/iespl-baseline/bakeoff/audio/`. "
		"Speak as a caller on a phone would. Any sample rate and channel count is fine: the harness converts "
		"each file to 8 kHz mono before it sends it.\n\n" + "\n".join(lines) + "\n"
	)


def rating_sheet_md(providers=data.TTS_PROVIDERS, results=None):
	rows = []
	for number, (_c, _x, reply) in enumerate(data.REPLIES, start=1):
		for provider in providers:
			info = next((i for i in (results or {}).get(provider, []) if i["number"] == number), None)
			audio = info["audio"] if info and not info["error"] else f"{provider}/{number:02d}.wav"
			rows.append([number, provider, reply, audio, ""])
	return (
		"# Text to speech rating sheet\n\n"
		"Listen to each file and write a rating from 1 (poor) to 5 (natural, clear Hinglish) in the last "
		"column. Reply 1 is a draft of the AI disclosure line (SOS-N21 sets the final one).\n\n"
		+ _table(["Reply", "Provider", "Text", "Audio", "Rating (1-5)"], rows)
		+ "\n"
	)


def llm_rating_sheet_md(
	models=("(model 1 from llm-models.txt)", "(model 2 from llm-models.txt)"), results=None
):
	rows = []
	for number, (caller, _context, reference) in enumerate(data.REPLIES, start=1):
		for model in models:
			info = next((i for i in (results or {}).get(model, []) if i["number"] == number), None)
			text = info["text"] if info and not info["error"] else ""
			rows.append([number, caller, model, text, reference, "", ""])
	return (
		"# Language model rating sheet\n\n"
		"For each reply, rate the model's own reply against the reference reply beside it, from 1 (poor) "
		"to 5 (very good): Hinglish naturalness (does it sound like a Mumbai agent speaking) and "
		"correctness (does it use only the facts in the lead context, and answer the line).\n\n"
		+ _table(
			[
				"Reply",
				"Caller line",
				"Model",
				"Model's reply",
				"Reference reply",
				"Hinglish naturalness (1-5)",
				"Correctness (1-5)",
			],
			rows,
		)
		+ "\n"
	)


SARVAM_PLACEHOLDER = "(Sarvam model from sarvam-llm-model.txt)"


def voice_llm_results_md(results, title="Voice language model comparison", note=""):
	"""The replies, the time to first token and the total time per case and model (SOS-N21B)."""
	out = [f"# {title}", ""]
	if note:
		out += [note, ""]
	for model, items in results.items():
		out += [f"## {model}", ""]
		rows = []
		for item, (label, _caller, _context, reference) in zip(items, data.voice_cases(), strict=True):
			if item["error"]:
				rows.append([label, f"FAILED: {item['error']}", "", "", ""])
				continue
			expected = "n/a"
			if reference == data.HANDOVER_TAG:
				expected = "yes" if runner.handed_over(item["text"]) else "NO"
			rows.append([label, item["text"], expected, _cell(item["first_token_s"]), _cell(item["total_s"])])
		out += [_table(["Case", "Reply", "Handed over", "First token (s)", "Total (s)"], rows), ""]
	return "\n".join(out)


def voice_llm_rating_sheet_md(models=(SARVAM_PLACEHOLDER, data.HAIKU_MODEL), results=None):
	"""One row per case and model, with empty 1 to 5 columns for Hinglish naturalness and correctness."""
	rows = []
	for number, (label, caller, _context, reference) in enumerate(data.voice_cases(), start=1):
		for model in models:
			info = next((i for i in (results or {}).get(model, []) if i["number"] == number), None)
			text = info["text"] if info and not info["error"] else ""
			first = _cell(info["first_token_s"]) if info and not info["error"] else ""
			total = _cell(info["total_s"]) if info and not info["error"] else ""
			rows.append([number, label, caller, model, text, reference, first, total, "", ""])
	return (
		"# Voice language model rating sheet\n\n"
		"Sarvam and Claude Haiku 5.5 on the AI disclosure line (the default of SOS-N21C, with a test company "
		"name) and the handover cases. Rate each reply from 1 (poor) to 5 (very good): Hinglish naturalness "
		"(does it sound like a Mumbai agent speaking) and correctness (a handover case must hand over: the "
		"reply is the handover tag alone; the disclosure line must be spoken as written).\n\n"
		+ _table(
			[
				"Case",
				"Label",
				"Caller line",
				"Model",
				"Model's reply",
				"Expected reply",
				"First token (s)",
				"Total (s)",
				"Hinglish naturalness (1-5)",
				"Correctness (1-5)",
			],
			rows,
		)
		+ "\n"
	)
