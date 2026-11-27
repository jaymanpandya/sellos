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
		elif path.endswith("/v1/chat/completions"):
			events = [
				{"choices": [{"delta": {"content": "Namaste "}}]},
				{"choices": [{"delta": {"content": "Sarvam"}}]},
			]
			payload = ("".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n").encode()
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

	def test_n21b_sarvam_llm_and_haiku_run_with_the_key_in_the_header_only(self):
		work = Path(tempfile.mkdtemp())
		out, err = io.StringIO(), io.StringIO()
		with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
			results = cli.run_voice_comparison(
				adapters.SarvamLlm("sarvam-model-x", self.base),
				adapters.AnthropicLlm(data.HAIKU_MODEL, self.base),
				work / "out", work / "docs", "t", "n",
			)  # fmt: skip
		self.assertTrue(all(not i["error"] for items in results.values() for i in items))
		sarvam_calls = [c for c in Handler.seen if c[0] == "/v1/chat/completions"]
		self.assertEqual(len(sarvam_calls), 4)
		self.assertEqual(sarvam_calls[0][1]["Api-Subscription-Key"], FAKE_KEY)
		self.assertNotIn(FAKE_KEY.encode(), sarvam_calls[0][2])
		self.assertEqual(json.loads(sarvam_calls[0][2])["model"], "sarvam-model-x")
		self.assertEqual(results["sarvam-model-x"][0]["text"], "Namaste Sarvam")
		self.assertNotIn(FAKE_KEY, out.getvalue() + err.getvalue() + every_file_text(work))
		self.server.fail = True
		with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
			failed = cli.run_voice_comparison(
				adapters.SarvamLlm("sarvam-model-x", self.base),
				adapters.AnthropicLlm(data.HAIKU_MODEL, self.base),
				work / "out2", work / "docs2", "t", "n",
			)  # fmt: skip
		self.assertTrue(all(i["error"] for items in failed.values() for i in items))
		self.assertIn("HTTP 500", (work / "docs2" / "voice-llm-results.md").read_text())
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


class TestVoiceComparison(unittest.TestCase):
	"""SOS-N21B: the Sarvam model and Claude Haiku 5.5 on the disclosure line and the handover cases."""

	def _name_file(self, text):
		path = Path(tempfile.mkdtemp()) / data.SARVAM_MODEL_FILE
		path.write_text(text, encoding="utf-8")
		return path

	def test_the_cases_are_the_disclosure_line_and_three_handovers(self):
		cases = data.voice_cases()
		self.assertEqual(len(cases), 4)
		line = data.default_disclosure()
		self.assertIn(data.TEST_COMPANY, line)
		self.assertNotIn("{company}", line)
		self.assertTrue(line.startswith("Namaste, main Nicole baat kar rahi hoon."))
		self.assertEqual(cases[0][3], line)
		self.assertEqual([c[3] for c in cases[1:]], [data.HANDOVER_TAG] * 3)
		labels = " ".join(c[0] for c in cases)
		for part in ("during the disclosure", "middle of a reply", "Confused"):
			self.assertIn(part, labels)

	def test_both_models_answer_every_case_with_times(self):
		out = Path(tempfile.mkdtemp())
		sarvam, haiku = adapters.FakeSarvamLlm("sarvam-model-x"), adapters.FakeLlm(data.HAIKU_MODEL)
		results = runner.run_voice_llm([sarvam, haiku], out)
		self.assertEqual(list(results), ["sarvam-model-x", "claude-haiku-5-5"])
		for items in results.values():
			self.assertEqual(len(items), 4)
			self.assertTrue(all(not i["error"] and i["first_token_s"] > 0 for i in items))
			self.assertTrue(all(i["total_s"] >= i["first_token_s"] for i in items))
		self.assertTrue((out / "voice-llm" / "sarvam-model-x" / "01.txt").is_file())

	def test_both_models_get_the_same_prompt_and_the_handover_rule(self):
		seen = []

		class Spy(adapters.FakeLlm):
			def generate(self, system, scenario):
				seen.append((system, scenario["context"]))
				return super().generate(system, scenario)

		runner.run_voice_llm([Spy("a"), Spy("b")], tempfile.mkdtemp())
		self.assertEqual(seen[:4], seen[4:])
		self.assertIn(data.HANDOVER_TAG, seen[0][0])
		self.assertIn(data.default_disclosure(), seen[0][1])

	def test_a_fake_run_writes_replies_times_and_the_rating_sheet(self):
		out = Path(tempfile.mkdtemp())
		cli.run_fake(out)
		sheet = (out / "voice-llm-rating-sheet.md").read_text()
		rows = [
			ln for ln in sheet.splitlines() if ln.startswith("| ") and ("fake-sarvam" in ln or "haiku" in ln)
		]
		self.assertEqual(len(rows), 8)
		self.assertIn("Hinglish naturalness (1-5)", sheet)
		self.assertIn("Correctness (1-5)", sheet)
		self.assertTrue(all(ln.endswith("|  |  |") for ln in rows))
		results = (out / "voice-llm-results.md").read_text()
		self.assertIn("First token (s)", results)
		self.assertIn("claude-haiku-5-5", results)
		self.assertNotIn("NO |", results)
		saved = json.loads((out / "voice-llm.json").read_text())
		self.assertEqual(len(saved["fake-sarvam"]), 4)

	def test_a_reply_that_does_not_hand_over_is_marked(self):
		class Chatty(adapters.FakeLlm):
			def generate(self, system, scenario):
				return adapters.LlmResult("Zaroor, bataiye.", 0.1, 0.2)

		results = runner.run_voice_llm([Chatty("chatty")], tempfile.mkdtemp())
		self.assertEqual(reports.voice_llm_results_md(results).count("| NO |"), 3)

	def test_the_model_name_file_is_read(self):
		self.assertEqual(runner.read_sarvam_model(self._name_file("sarvam-the-name\n")), "sarvam-the-name")
		out = Path(tempfile.mkdtemp())
		cli.run_fake(out, sarvam_model_file=self._name_file("sarvam-the-name\n"))
		self.assertIn("sarvam-the-name", (out / "voice-llm-rating-sheet.md").read_text())

	def test_a_missing_empty_or_many_line_model_name_file_is_refused(self):
		for text in ("", "\n  \n", "one\ntwo\n", "has space\n"):
			with self.assertRaises(runner.SarvamModelError):
				runner.read_sarvam_model(self._name_file(text))
		with self.assertRaises(runner.SarvamModelError):
			runner.read_sarvam_model(Path(tempfile.mkdtemp()) / "missing.txt")

	def test_live_refuses_without_a_terminal_and_with_a_bad_model_name_file(self):
		err = io.StringIO()
		with mock.patch.object(keys, "get_secret") as get_secret, contextlib.redirect_stderr(err):
			self.assertEqual(cli.main(["--live"], stdin=io.StringIO()), 2)
		self.assertIn("terminal", err.getvalue())
		tty = mock.Mock()
		tty.isatty.return_value = True
		base = Path(tempfile.mkdtemp())
		(base / "llm-models.txt").write_text("a\nb\n")
		err = io.StringIO()
		with mock.patch.object(keys, "get_secret") as get_secret, contextlib.redirect_stderr(err):
			self.assertEqual(cli.run_live(base, base, stdin=tty), 2)
		self.assertIn(data.SARVAM_MODEL_FILE, err.getvalue())
		get_secret.assert_not_called()

	def test_sarvam_is_behind_the_same_interface_and_reads_only_the_sarvam_key(self):
		self.assertTrue(issubclass(adapters.SarvamLlm, adapters.LlmAdapter))
		self.assertTrue(issubclass(adapters.FakeSarvamLlm, adapters.LlmAdapter))
		self.assertEqual(keys.SARVAM, "sellos_sarvam_key")

	def test_the_shipped_sheet_matches_and_results_stay_not_run(self):
		docs = REPO / "docs" / "bakeoff"
		self.assertEqual(
			(docs / "voice-llm-rating-sheet.md").read_text(), reports.voice_llm_rating_sheet_md()
		)
		self.assertIn("Not run yet", (docs / "results.md").read_text())
