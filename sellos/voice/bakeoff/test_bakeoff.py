"""SOS-N21A: the Hinglish voice bake-off harness, tested with fake providers and a local server.

The Keychain is never read here: keys.get_secret is replaced. No real provider is called.
"""

import base64
import contextlib
import io
import json
import tempfile
import threading
import traceback
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from unittest import mock

from sellos.provisioning import credentials
from sellos.tests.phones import in_mobile
from sellos.voice.bakeoff import (
	adapters,
	audio,
	cli,
	data,
	keys,
	normalize,
	reports,
	runner,
	scoring,
	transport,
)

FAKE_KEY = "fake-key-for-n21a-test-7c1f9d"
DIGIT_WORDS_HI = ("zero", "ek", "do", "teen", "chaar", "paanch", "chhe", "saat", "aath", "nau")
REPO = Path(__file__).resolve().parents[3]


def spoken_digits(number):
	"""A number's ten national digits as Hindi digit words, as a caller says them."""
	return " ".join(DIGIT_WORDS_HI[int(d)] for d in number[-10:])


def fake_secret(name):
	if name not in keys.ALLOWED_NAMES:
		raise keys.UnknownSecretName("not a bake-off key")
	return FAKE_KEY


def formatted_with_locals(exc):
	return "".join(traceback.TracebackException.from_exception(exc, capture_locals=True).format())


def every_file_text(folder):
	return "\n".join(
		p.read_bytes().decode("utf-8", errors="ignore") for p in Path(folder).rglob("*") if p.is_file()
	)


class TestScoring(unittest.TestCase):
	"""SOS-N21A: word error rate and entity accuracy on hand worked examples."""

	def test_spoken_numbers_match_digits(self):
		self.assertEqual(normalize.normalise("teen crore"), normalize.normalise("3 crore"))
		self.assertEqual(normalize.normalise("do crore pachaas lakh"), ["25000000"])
		self.assertEqual(normalize.normalise("2.5 crore"), ["25000000"])
		self.assertEqual(normalize.normalise("nau aath saat"), ["987"])
		self.assertEqual(normalize.normalise("45 hazaar"), ["45000"])
		self.assertEqual(normalize.normalise("pachaas hazaar"), ["50000"])
		self.assertEqual(normalize.normalise("3,00,00,000"), ["30000000"])

	def test_a_spoken_phone_number_matches_its_digits(self):
		number = in_mobile(8)
		self.assertEqual(normalize.normalise(spoken_digits(number)), [number[-10:]])
		self.assertEqual(
			scoring.word_error_rate(f"number {spoken_digits(number)} hai", f"number {number[-10:]} hai"), 0
		)

	def test_case_and_punctuation_are_ignored(self):
		self.assertEqual(scoring.word_error_rate("Namaste, Bandra West!", "namaste bandra west"), 0)

	def test_word_error_rate_counts_edits(self):
		self.assertEqual(scoring.word_error_rate("a b c d", "a x c"), 0.5)
		self.assertEqual(scoring.word_error_rate("budget teen crore tak hai", "budget 3 crore tak hai"), 0)
		self.assertEqual(scoring.word_error_rate("a b", ""), 1.0)
		self.assertEqual(scoring.word_error_rate("", ""), 0.0)

	def test_entities_are_scored_apart(self):
		entities = {"numbers": ["2"], "prices": ["3 crore"], "localities": ["Bandra West"]}
		scores = scoring.entity_scores(entities, "Bandra West mein 2 BHK, budget teen lakh")
		self.assertEqual(scores, {"numbers": (1, 1), "prices": (0, 1), "localities": (1, 1)})
		scores = scoring.entity_scores(entities, "bandra mein dekhna hai 3 crore")
		self.assertEqual(scores, {"numbers": (0, 1), "prices": (1, 1), "localities": (0, 1)})

	def test_a_price_in_words_matches_the_entity_in_digits(self):
		scores = scoring.entity_scores({"prices": ["2.5 crore"]}, "price do crore pachaas lakh ke andar")
		self.assertEqual(scores["prices"], (1, 1))
		self.assertIsNone(scoring.accuracy(0, 0))
		self.assertEqual(scoring.accuracy(1, 2), 0.5)

	def test_every_reference_line_scores_perfectly_against_itself(self):
		for _file, reference, numbers, prices, localities in data.CALLER_LINES:
			entities = {
				k: [e for e in v.split(";") if e]
				for k, v in zip(scoring.ENTITY_KINDS, (numbers, prices, localities), strict=True)
			}
			self.assertEqual(scoring.word_error_rate(reference, reference), 0)
			for kind, (found, total) in scoring.entity_scores(entities, reference).items():
				self.assertEqual(found, total, f"{_file} {kind}")


class TestAudio(unittest.TestCase):
	"""SOS-N21A: recordings go out as 8 kHz mono audio."""

	def test_a_44k_stereo_recording_becomes_8k_mono(self):
		import wave

		mono = audio.tone(0.5, 44100)
		path = Path(tempfile.mkdtemp()) / "x.wav"
		with wave.open(str(path), "wb") as w:
			w.setnchannels(2)
			w.setsampwidth(2)
			w.setframerate(44100)
			import array

			pcm = array.array("h", [s for s in mono for _ in (0, 1)])
			w.writeframes(pcm.tobytes())
		samples = audio.to_phone_audio(path)
		self.assertAlmostEqual(len(samples), 4000, delta=2)
		again, rate = audio.read_wav(audio.wav_bytes(samples))
		self.assertEqual(rate, 8000)
		self.assertEqual(again, samples)

	def test_an_8k_recording_is_not_changed(self):
		samples = audio.tone(0.1)
		self.assertEqual(audio.to_phone_audio(audio.wav_bytes(samples)), samples)

	def test_a_bad_file_is_refused(self):
		with self.assertRaises(audio.AudioError):
			audio.read_wav(b"not a wav file")


class TestKeys(unittest.TestCase):
	"""SOS-N21A: get_secret reads only the four Keychain items."""

	def test_an_unknown_name_is_refused_without_reading_the_keychain(self):
		with mock.patch.object(credentials, "read_keychain_item") as read:
			for name in ("sellos_provisioner", "sellos_unknown_key", ""):
				with self.assertRaises(keys.UnknownSecretName):
					keys.get_secret(name)
			read.assert_not_called()

	def test_the_four_names_are_read(self):
		with mock.patch.object(credentials, "read_keychain_item", return_value=(FAKE_KEY, None)) as read:
			for name in keys.ALLOWED_NAMES:
				self.assertEqual(keys.get_secret(name), FAKE_KEY)
		self.assertEqual([c.args[0] for c in read.call_args_list], list(keys.ALLOWED_NAMES))
		self.assertEqual(
			keys.ALLOWED_NAMES,
			("sellos_sarvam_key", "sellos_deepgram_key", "sellos_elevenlabs_key", "sellos_anthropic_key"),
		)

	def test_a_missing_item_says_how_to_store_it_and_shows_no_value(self):
		with mock.patch.object(
			credentials, "read_keychain_item", return_value=(None, "the security command exited 44")
		):
			with self.assertRaises(keys.SecretMissing) as caught:
				keys.get_secret(keys.SARVAM)
		message = str(caught.exception)
		self.assertIn('security add-generic-password -a "$USER" -s sellos_sarvam_key -w', message)
		self.assertNotIn(FAKE_KEY, message)

	def test_the_keychain_helper_never_runs_the_command_off_macos(self):
		with mock.patch.object(credentials.sys, "platform", "linux"):
			self.assertEqual(credentials.read_keychain_item("sellos_sarvam_key")[0], None)

	def test_the_keychain_helper_returns_the_value_and_drops_failures(self):
		done = mock.Mock(returncode=0, stdout=FAKE_KEY + "\n")
		with (
			mock.patch.object(credentials.sys, "platform", "darwin"),
			mock.patch.object(credentials.shutil, "which", return_value="/usr/bin/security"),
			mock.patch.object(credentials.subprocess, "run", return_value=done),
		):
			self.assertEqual(credentials.read_keychain_item("sellos_sarvam_key"), (FAKE_KEY, None))
			failed = mock.Mock(returncode=44, stdout="")
			with mock.patch.object(credentials.subprocess, "run", return_value=failed):
				value, failure = credentials.read_keychain_item("sellos_sarvam_key")
		self.assertIsNone(value)
		self.assertIn("44", failure)


class TestModelList(unittest.TestCase):
	"""SOS-N21A: llm-models.txt holds two or three model names."""

	def _file(self, lines):
		path = Path(tempfile.mkdtemp()) / "llm-models.txt"
		path.write_text("\n".join(lines) + "\n", encoding="utf-8")
		return path

	def test_two_and_three_names_pass(self):
		self.assertEqual(runner.read_models(self._file(["a", "b"])), ["a", "b"])
		self.assertEqual(runner.read_models(self._file(["a", "", "b", "c"])), ["a", "b", "c"])

	def test_one_four_and_none_are_refused(self):
		for lines in (["a"], ["a", "b", "c", "d"], []):
			with self.assertRaises(runner.ModelListError):
				runner.read_models(self._file(lines))
		with self.assertRaises(runner.ModelListError):
			runner.read_models(Path(tempfile.mkdtemp()) / "missing.txt")

	def test_the_comparison_runs_each_model_on_all_twenty_replies(self):
		out = Path(tempfile.mkdtemp())
		models = runner.read_models(self._file(["m-fast", "m-mid", "m-strong"]))
		results = runner.run_llm([adapters.FakeLlm(m) for m in models], out)
		self.assertEqual(list(results), models)
		for items in results.values():
			self.assertEqual(len(items), 20)
			self.assertTrue(all(i["first_token_s"] > 0 and i["total_s"] >= i["first_token_s"] for i in items))
		sheet = reports.llm_rating_sheet_md(tuple(results), results)
		self.assertEqual(len([ln for ln in sheet.splitlines() if ln.startswith("| ") and "m-mid" in ln]), 20)


class TestFakeRun(unittest.TestCase):
	"""SOS-N21A: scripts/bakeoff.sh --fake runs everything and writes every file."""

	def test_a_whole_fake_run_on_two_short_recordings(self):
		work = Path(tempfile.mkdtemp())
		recordings = work / "audio"
		recordings.mkdir()
		for name in ("01.wav", "02.wav"):
			(recordings / name).write_bytes(audio.wav_bytes(audio.tone(0.3)))
		tsv = work / "reference.tsv"
		tsv.write_text(
			"".join(reports_line for reports_line in runner.reference_tsv().splitlines(keepends=True)[:3])
		)
		models = work / "llm-models.txt"
		models.write_text("model-one\nmodel-two\n", encoding="utf-8")
		out = work / "out"
		with contextlib.redirect_stdout(io.StringIO()):
			code = cli.main(
				[
					"--fake",
					"--out",
					str(out),
					"--audio",
					str(recordings),
					"--reference",
					str(tsv),
					"--llm-models",
					str(models),
				]
			)
		self.assertEqual(code, 0)
		for name in ("results.md", "rating-sheet.md", "llm-rating-sheet.md", "results.json"):
			self.assertTrue((out / name).is_file(), name)
		for provider in ("fake-stt-a", "fake-stt-b"):
			self.assertEqual(
				(out / provider / "01.txt").read_text().strip(),
				(" ".join(data.CALLER_LINES[0][1].split()[: -1 if provider == "fake-stt-b" else None])),
			)
		for provider in ("fake-tts-a", "fake-tts-b"):
			self.assertEqual(len(list((out / provider).glob("*.wav"))), 20)
			samples, rate = audio.read_wav(out / provider / "01.wav")
			self.assertEqual(rate, 8000)
			self.assertTrue(samples)
		self.assertEqual(len(list((out / "model-one").glob("*.txt"))), 20)
		results = json.loads((out / "results.json").read_text())
		first = results["stt"]["fake-stt-b"][0]
		self.assertGreater(first["wer"], 0)
		self.assertEqual(first["first_result_s"], 0.25)
		self.assertEqual(results["tts"]["fake-tts-a"][0]["first_audio_s"], 0.12)
		text = (out / "results.md").read_text()
		self.assertIn("## Speech to text: fake-stt-a", text)
		self.assertIn("## Text to speech: fake-tts-b", text)
		self.assertIn("## Language model: model-two", text)
		self.assertIn("Median first result (s)", text)
		self.assertIn("Median first audio (s)", text)
		self.assertIn("Median first token (s)", text)
		rating = (out / "rating-sheet.md").read_text()
		self.assertEqual(
			len([ln for ln in rating.splitlines() if ln.startswith("| ") and "fake-tts" in ln]), 40
		)
		self.assertTrue(all(ln.endswith("|  |") for ln in rating.splitlines() if "fake-tts" in ln))

	def test_a_fake_run_without_inputs_makes_its_own_recordings(self):
		out = Path(tempfile.mkdtemp())
		stt, _tts, llm = cli.run_fake(out)
		self.assertEqual(len(stt["fake-stt-a"]), 20)
		self.assertEqual(len(llm), 2)

	def test_a_failed_file_is_recorded_not_fatal(self):
		work = Path(tempfile.mkdtemp())
		tsv = work / "reference.tsv"
		tsv.write_text(runner.reference_tsv())
		rows = runner.load_reference(tsv)[:2]
		results = runner.run_stt(
			[adapters.FakeStt("f", {r["file"]: r["reference"] for r in rows})], rows, work, work / "o"
		)
		self.assertTrue(all(i["error"] for i in results["f"]))
		self.assertIn("Files scored", reports.results_md(results, {}, {}))


class TestLiveRefusal(unittest.TestCase):
	"""SOS-N21A: --live refuses to start without a terminal."""

	def test_main_refuses_when_standard_input_is_not_a_terminal(self):
		stdin = io.StringIO()
		err = io.StringIO()
		with mock.patch.object(keys, "get_secret") as get_secret, contextlib.redirect_stderr(err):
			code = cli.main(["--live"], stdin=stdin)
		self.assertEqual(code, 2)
		self.assertIn("terminal", err.getvalue())
		get_secret.assert_not_called()

	def test_the_script_refuses_without_a_terminal(self):
		import subprocess

		done = subprocess.run(
			[str(REPO / "scripts" / "bakeoff.sh"), "--live"],
			stdin=subprocess.DEVNULL,
			capture_output=True,
			text=True,
			timeout=60,
		)
		self.assertEqual(done.returncode, 2)
		self.assertIn("terminal", done.stderr)

	def test_a_live_run_with_a_terminal_still_checks_the_model_list_first(self):
		tty = mock.Mock()
		tty.isatty.return_value = True
		base = Path(tempfile.mkdtemp())
		(base / "llm-models.txt").write_text("only-one\n")
		err = io.StringIO()
		with mock.patch.object(keys, "get_secret") as get_secret, contextlib.redirect_stderr(err):
			code = cli.run_live(base, base, stdin=tty)
		self.assertEqual(code, 2)
		self.assertIn("two or three", err.getvalue())
		get_secret.assert_not_called()


class Handler(BaseHTTPRequestHandler):
	seen: ClassVar[list] = []

	def log_message(self, *args):
		pass

	def do_POST(self):
		body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
		type(self).seen.append((self.path, dict(self.headers), body))
		if self.server.fail:
			self.send_response(500)
			self.end_headers()
			self.wfile.write(b"upstream said " + FAKE_KEY.encode())
			return
		path = self.path.split("?")[0]
		wav = audio.wav_bytes(audio.tone(0.1))
		if path.endswith("/speech-to-text"):
			payload = json.dumps({"transcript": "teen crore ka budget hai"}).encode()
		elif path.endswith("/v1/listen"):
			payload = json.dumps(
				{"results": {"channels": [{"alternatives": [{"transcript": "3 crore"}]}]}}
			).encode()
		elif path.endswith("/text-to-speech"):
			payload = json.dumps({"audios": [base64.b64encode(wav).decode()]}).encode()
		elif "/v1/text-to-speech/" in path:
			payload = wav[44:]
		else:
			events = [
				{"type": "message_start"},
				{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Namaste "}},
				{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "ji"}},
			]
			payload = "".join(f"event: x\ndata: {json.dumps(e)}\n\n" for e in events).encode()
		self.send_response(200)
		self.send_header("Content-Length", str(len(payload)))
		self.end_headers()
		self.wfile.write(payload)


class TestLiveAdaptersAgainstALocalServer(unittest.TestCase):
	"""SOS-N21A: the live adapters, the key handling and the output files, with a local server standing in."""

	def setUp(self):
		Handler.seen = []
		self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
		self.server.fail = False
		self.base = f"http://127.0.0.1:{self.server.server_port}"
		thread = threading.Thread(target=self.server.serve_forever, daemon=True)
		thread.start()
		self.addCleanup(thread.join, 10)
		self.addCleanup(self.server.server_close)
		self.addCleanup(self.server.shutdown)
		patcher = mock.patch.object(keys, "get_secret", side_effect=fake_secret)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_each_key_goes_only_into_its_providers_request_header(self):
		wav = audio.wav_bytes(audio.tone(0.1))
		self.assertEqual(
			adapters.SarvamStt(self.base).transcribe("01.wav", wav).transcript, "teen crore ka budget hai"
		)
		self.assertEqual(adapters.DeepgramStt(self.base).transcribe("01.wav", wav).transcript, "3 crore")
		self.assertTrue(audio.read_wav(adapters.SarvamTts(self.base).synthesize("namaste").wav)[0])
		self.assertTrue(audio.read_wav(adapters.ElevenLabsTts(self.base).synthesize("namaste").wav)[0])
		llm = adapters.AnthropicLlm("model-x", self.base).generate("system", runner.scenarios()[0])
		self.assertEqual(llm.text, "Namaste ji")
		self.assertLessEqual(llm.first_token_s, llm.total_s)
		headers = [{k.lower(): v for k, v in h.items()} for _p, h, _b in Handler.seen]
		self.assertEqual(headers[0]["api-subscription-key"], FAKE_KEY)
		self.assertEqual(headers[1]["authorization"], f"Token {FAKE_KEY}")
		self.assertEqual(headers[2]["api-subscription-key"], FAKE_KEY)
		self.assertEqual(headers[3]["xi-api-key"], FAKE_KEY)
		self.assertEqual(headers[4]["x-api-key"], FAKE_KEY)
		for _path, _headers, body in Handler.seen:
			self.assertNotIn(FAKE_KEY.encode(), body)

	def test_deepgram_is_asked_for_multi_language_with_keyterms_on_8k_audio(self):
		wav = audio.wav_bytes(audio.tone(0.1))
		adapters.DeepgramStt(self.base).transcribe("01.wav", wav)
		path, _headers, body = Handler.seen[0]
		self.assertIn("model=nova-3", path)
		self.assertIn("language=multi", path)
		self.assertIn("keyterm=carpet+area", path)
		self.assertIn("keyterm=RERA", path)
		self.assertEqual(audio.read_wav(body)[1], 8000)

	def test_a_provider_error_holds_no_key_in_message_or_traceback_with_locals(self):
		self.server.fail = True
		for call in (
			lambda: adapters.SarvamStt(self.base).transcribe("01.wav", b"x"),
			lambda: adapters.AnthropicLlm("model-x", self.base).generate("s", runner.scenarios()[0]),
			lambda: adapters.ElevenLabsTts(self.base).synthesize("namaste"),
		):
			with self.assertRaises(transport.ProviderError) as caught:
				call()
			self.assertNotIn(FAKE_KEY, str(caught.exception))
			self.assertNotIn(FAKE_KEY, formatted_with_locals(caught.exception))
			self.assertIn("500", str(caught.exception))

	def test_a_whole_run_with_the_live_adapters_leaves_no_key_in_output_or_files(self):
		work = Path(tempfile.mkdtemp())
		recordings = work / "audio"
		recordings.mkdir()
		tsv = work / "reference.tsv"
		tsv.write_text(runner.reference_tsv())
		rows = runner.load_reference(tsv)[:3]
		for row in rows:
			(recordings / row["file"]).write_bytes(audio.wav_bytes(audio.tone(0.2, 16000), 16000))
		out, err = io.StringIO(), io.StringIO()
		with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
			stt, tts, llm = cli.run_all(
				[adapters.SarvamStt(self.base), adapters.DeepgramStt(self.base)],
				[adapters.SarvamTts(self.base), adapters.ElevenLabsTts(self.base)],
				[adapters.AnthropicLlm("model-a", self.base), adapters.AnthropicLlm("model-b", self.base)],
				rows, recordings, work / "out", work / "docs", "t", "n",
			)  # fmt: skip
		self.assertEqual(len(stt["sarvam-saaras-v3"]), 3)
		self.assertTrue(
			all(not i["error"] for items in (*stt.values(), *tts.values(), *llm.values()) for i in items)
		)
		self.assertEqual(stt["sarvam-saaras-v3"][0]["entities"]["prices"], (1, 1))
		self.assertNotIn(FAKE_KEY, out.getvalue() + err.getvalue() + every_file_text(work))
		self.server.fail = True
		with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
			stt, tts, llm = cli.run_all(
				[adapters.SarvamStt(self.base)], [adapters.ElevenLabsTts(self.base)],
				[adapters.AnthropicLlm("model-a", self.base)], rows, recordings, work / "out2", work / "docs2", "t", "n",
			)  # fmt: skip
		self.assertTrue(all(i["error"] for i in llm["model-a"]))
		self.assertIn("HTTP 500", (work / "docs2" / "results.md").read_text())
		self.assertNotIn(FAKE_KEY, out.getvalue() + err.getvalue() + every_file_text(work))


class TestShippedDocs(unittest.TestCase):
	"""SOS-N21A: the files in docs/bakeoff are the ones the harness writes."""

	def test_the_shipped_files_match_the_harness(self):
		docs = REPO / "docs" / "bakeoff"
		self.assertEqual((docs / "reference.tsv").read_text(), runner.reference_tsv())
		self.assertEqual((docs / "sentences.md").read_text(), reports.sentences_md())
		self.assertEqual((docs / "rating-sheet.md").read_text(), reports.rating_sheet_md())
		self.assertEqual((docs / "llm-rating-sheet.md").read_text(), reports.llm_rating_sheet_md())
		self.assertIn("Not run yet", (docs / "results.md").read_text())

	def test_the_reference_has_twenty_rows_with_entities(self):
		rows = runner.load_reference(REPO / "docs" / "bakeoff" / "reference.tsv")
		self.assertEqual(len(rows), 20)
		self.assertEqual(rows[7]["entities"]["numbers"], [normalize.normalise(rows[7]["reference"])[-2]])
		self.assertEqual(rows[15]["entities"]["localities"], ["Powai", "Goregaon"])
		self.assertEqual(rows[3]["entities"]["prices"], ["2.5 crore"])
		sentences = (REPO / "docs" / "bakeoff" / "sentences.md").read_text()
		for _file, reference, *_ in data.CALLER_LINES:
			self.assertIn(reference, sentences)

	def test_the_first_reply_is_the_disclosure_draft_and_the_sheets_have_empty_rating_columns(self):
		self.assertIn("AI assistant", data.REPLIES[0][2])
		sheet = (REPO / "docs" / "bakeoff" / "rating-sheet.md").read_text()
		self.assertEqual(
			len([ln for ln in sheet.splitlines() if ln.startswith("| ") and "elevenlabs" in ln]), 20
		)
		self.assertIn("Rating (1-5)", sheet)
		self.assertIn("Correctness (1-5)", (REPO / "docs" / "bakeoff" / "llm-rating-sheet.md").read_text())

	def test_the_adapters_share_one_interface_per_kind(self):
		self.assertTrue(issubclass(adapters.SarvamStt, adapters.SttAdapter))
		self.assertTrue(issubclass(adapters.DeepgramStt, adapters.SttAdapter))
		self.assertTrue(issubclass(adapters.SarvamTts, adapters.TtsAdapter))
		self.assertTrue(issubclass(adapters.ElevenLabsTts, adapters.TtsAdapter))
		self.assertTrue(issubclass(adapters.AnthropicLlm, adapters.LlmAdapter))
