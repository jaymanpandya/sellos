"""The bake-off command line (SOS-N21A): --fake, --live and --templates. scripts/bakeoff.sh runs it."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from sellos.voice.bakeoff import adapters, audio, data, keys, reports, runner

LIVE_NEEDS_TERMINAL = (
	"--live talks to the real providers and uses your Keychain keys, so it runs only from a terminal "
	"you are sitting at. Standard input is not a terminal here, so nothing was started."
)


def baseline_dir():
	import os

	return Path(os.environ.get("SELLOS_BASELINE_DIR") or data.BASELINE_DIR) / "bakeoff"


def write_templates(docs):
	"""The files Jayman starts from. results.md is only reset while it still says Not run yet."""
	docs = Path(docs)
	docs.mkdir(parents=True, exist_ok=True)
	(docs / "reference.tsv").write_text(runner.reference_tsv(), encoding="utf-8")
	(docs / "sentences.md").write_text(reports.sentences_md(), encoding="utf-8")
	(docs / "rating-sheet.md").write_text(reports.rating_sheet_md(), encoding="utf-8")
	(docs / "llm-rating-sheet.md").write_text(reports.llm_rating_sheet_md(), encoding="utf-8")
	results = docs / "results.md"
	if not results.exists() or "Not run yet" in results.read_text(encoding="utf-8"):
		results.write_text(reports.NOT_RUN, encoding="utf-8")


def _write_outputs(docs, out, stt, tts, llm, title, note):
	docs, out = Path(docs), Path(out)
	docs.mkdir(parents=True, exist_ok=True)
	(docs / "results.md").write_text(reports.results_md(stt, tts, llm, title, note), encoding="utf-8")
	(docs / "rating-sheet.md").write_text(reports.rating_sheet_md(tuple(tts), tts), encoding="utf-8")
	(docs / "llm-rating-sheet.md").write_text(reports.llm_rating_sheet_md(tuple(llm), llm), encoding="utf-8")
	(out / "results.json").write_text(
		json.dumps({"stt": stt, "tts": tts, "llm": llm}, indent=1, ensure_ascii=False), encoding="utf-8"
	)


def run_all(stt_adapters, tts_adapters, llm_adapters, rows, audio_dir, out, docs, title, note):
	out = Path(out)
	out.mkdir(parents=True, exist_ok=True)
	stt = runner.run_stt(stt_adapters, rows, audio_dir, out)
	tts = runner.run_tts(tts_adapters, out)
	llm = runner.run_llm(llm_adapters, out)
	_write_outputs(docs, out, stt, tts, llm, title, note)
	return stt, tts, llm


def run_fake(out, audio_dir=None, reference=None, models_file=None):
	"""The whole harness with fake providers. Without recordings it makes tone recordings of its own."""
	out = Path(out)
	out.mkdir(parents=True, exist_ok=True)
	if reference is None:
		reference = out / "reference.tsv"
		reference.write_text(runner.reference_tsv(), encoding="utf-8")
	rows = runner.load_reference(reference)
	if audio_dir is None:
		audio_dir = out / "recordings"
		audio_dir.mkdir(exist_ok=True)
		for row in rows:
			(audio_dir / row["file"]).write_bytes(audio.wav_bytes(audio.tone(0.5, 16000), 16000))
	models = runner.read_models(models_file) if models_file else ["fake-fast", "fake-strong"]
	references = {row["file"]: row["reference"] for row in rows}
	return run_all(
		[adapters.FakeStt("fake-stt-a", references), adapters.FakeStt("fake-stt-b", references, drop=1)],
		[adapters.FakeTts("fake-tts-a"), adapters.FakeTts("fake-tts-b", 0.2, 0.6)],
		[adapters.FakeLlm(m) for m in models],
		rows,
		audio_dir,
		out,
		out,
		"Voice bake-off results (FAKE run)",
		"**This is a fake run.** The providers are fakes and the numbers say nothing about real ones.",
	)


def run_live(base, docs, stdin=None):
	"""The real providers. Refuses without a terminal, before it reads a model list or a key."""
	stdin = stdin or sys.stdin
	if not stdin.isatty():
		print(LIVE_NEEDS_TERMINAL, file=sys.stderr)
		return 2
	base = Path(base)
	try:
		models = runner.read_models(base / runner.LLM_MODELS_FILE)
	except runner.ModelListError as exc:
		print(str(exc), file=sys.stderr)
		return 2
	audio_dir, reference = base / "audio", base / "reference.tsv"
	if not reference.is_file() or not audio_dir.is_dir():
		print(f"Put the recordings in {audio_dir} and reference.tsv in {base}.", file=sys.stderr)
		return 2
	missing = keys.missing_keys(keys.ALLOWED_NAMES)
	if missing:
		for name in missing:
			print(
				f"The Keychain item {name} is missing. Store it with: {keys.store_command(name)}",
				file=sys.stderr,
			)
		return 2
	rows = runner.load_reference(reference)
	absent = [r["file"] for r in rows if not (audio_dir / r["file"]).is_file()]
	if absent:
		print("Missing recordings: " + ", ".join(absent), file=sys.stderr)
		return 2
	run_all(
		[adapters.SarvamStt(), adapters.DeepgramStt()],
		[adapters.SarvamTts(), adapters.ElevenLabsTts()],
		[adapters.AnthropicLlm(m) for m in models],
		rows,
		audio_dir,
		base / "out",
		docs,
		"Voice bake-off results",
		"Live run. Audio and transcripts are in " + str(base / "out") + ".",
	)
	print(f"Done. Results: {Path(docs) / 'results.md'}")
	return 0


def main(argv=None, stdin=None):
	parser = argparse.ArgumentParser(prog="bakeoff.sh", description=__doc__)
	mode = parser.add_mutually_exclusive_group(required=True)
	mode.add_argument("--fake", action="store_true", help="fake providers, written to --out")
	mode.add_argument(
		"--live", action="store_true", help="real providers; needs a terminal and the Keychain keys"
	)
	mode.add_argument("--templates", action="store_true", help="write the shipped docs/bakeoff files")
	parser.add_argument("--out", help="folder for a --fake run")
	parser.add_argument("--audio", help="recordings for a --fake run")
	parser.add_argument("--reference", help="reference.tsv for a --fake run")
	parser.add_argument("--llm-models", help="llm-models.txt for a --fake run")
	parser.add_argument("--docs", default=str(data.APP_DOCS), help="folder for the docs files")
	args = parser.parse_args(argv)
	if args.live:
		return run_live(baseline_dir(), args.docs, stdin)
	if args.templates:
		write_templates(args.docs)
		return 0
	out = args.out or tempfile.mkdtemp(prefix="bakeoff-fake-")
	run_fake(out, args.audio and Path(args.audio), args.reference and Path(args.reference), args.llm_models)
	print(f"Fake run written to {out}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
