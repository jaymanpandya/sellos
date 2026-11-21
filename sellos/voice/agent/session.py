"""One call between the voice agent and a caller (SOS-P5-07).

The session knows nothing of the database or the network. It reads Plivo stream events (`handle`),
listens for the caller with a simple energy detector, and runs a turn each time the caller stops:
speech to text, a check for a request for a human, the language model, text to speech. It sends audio
through `send`, and keeps the transcript, the time of every turn and how the call ended in `result()`.

* The AI disclosure line is the first thing said, before anything else.
* A caller may speak over the agent at any time, the disclosure line included: the queued audio is
  cleared and what the caller said is heard.
* A request for a human, or two turns in a row that could not be understood, hands the call over.
* The time of a turn runs from the last audio of the caller's speech to the first audio sent.
* Consent is not looked at here: it is recorded before the call (sellos.voice.agent.service) and never
  blocks.
"""

import re
import statistics
from dataclasses import dataclass, field

from sellos.voice.agent import audio, stream
from sellos.voice.agent.adapters import SYSTEM_PROMPT
from sellos.voice.agent.http import VoiceProviderError

TARGET_SECONDS = 1.0

CLARIFY_LINE = "Maaf kijiye, awaaz saaf nahin aayi. Kya aap dobara bata sakte hain?"
HANDOVER_LINE = (
	"Theek hai, main aapko abhi apne sales executive se jod rahi hoon. Kripya line par bane rahiye."
)
SILENCE_LINE = "Hello, kya aap line par hain?"
GOODBYE_LINE = "Lagta hai awaaz nahin aa rahi. Main baad mein dobara call karungi. Dhanyavaad."

# A request for a person needs someone to ask for and a way of asking: "Kya aap AI ho ya insaan?" is a
# question about the agent, not a request, and is answered by the language model.
_TARGET = re.compile(
	r"\b(human|insaan|insan|aadmi|admi|banda|bande|person|manager|representative|executive|operator|"
	r"officer|agent|owner)\b"
)
_ASK = re.compile(
	r"\b(baat|bat|talk|speak|connect|jod|jodo|jodiye|transfer|chahiye|chahta|chahti|karao|karwao|karvao|"
	r"dijiye|please|pls|milna|bulao|bulaiye|forward)\b"
)
_NOT_AN_ASK = re.compile(r"\b(ai ho ya|ai hain ya|bot ho ya|robot ho ya)\b")
_TAG = re.compile(r"\[\s*(HANDOVER|OUTCOME\s*:\s*([^\]]*?)|END)\s*\]", re.IGNORECASE)


def wants_human(text: str) -> bool:
	"""True when the caller asks for a person. `text` is Roman script."""
	words = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
	if _NOT_AN_ASK.search(words):
		return False
	return bool(_TARGET.search(words) and _ASK.search(words))


def latency_summary(latencies_s) -> dict:
	"""The median and the slowest turn, in milliseconds, and whether both meet the one second target."""
	if not latencies_s:
		return {"turns": 0, "median_ms": 0, "slowest_ms": 0, "within_target": True}
	median, slowest = statistics.median(latencies_s), max(latencies_s)
	return {
		"turns": len(latencies_s),
		"median_ms": round(median * 1000),
		"slowest_ms": round(slowest * 1000),
		"within_target": slowest <= TARGET_SECONDS,
	}


@dataclass
class Config:
	voice_rms: float = 500.0  # frame level above which the caller is speaking
	hangover_s: float = 0.3  # silence after speech that ends the caller's turn
	min_speech_s: float = 0.2  # shorter than this is a click, not speech
	silence_timeout_s: float = 6.0
	max_silence_prompts: int = 2
	max_confusions: int = 2
	max_turns: int = 30


@dataclass
class Result:
	transcript: str = ""
	latencies_ms: list = field(default_factory=list)
	handed_over: bool = False
	handover_reason: str = ""
	end_reason: str = ""
	outcome: str = ""
	turns: int = 0
	interruptions: int = 0
	summary: dict = field(default_factory=dict)


class AgentSession:
	def __init__(
		self,
		*,
		stt,
		llm,
		tts,
		send,
		clock,
		disclosure,
		keyterms=(),
		context="",
		outcomes=(),
		config=None,
		on_handover=None,
	):
		self.stt, self.llm, self.tts, self.send, self.clock = stt, llm, tts, send, clock
		self.disclosure, self.keyterms, self.context = disclosure, list(keyterms), context
		self.outcomes, self.config, self.on_handover = tuple(outcomes), config or Config(), on_handover
		self.system = SYSTEM_PROMPT.format(outcomes=", ".join(self.outcomes) or "none")
		self.encoding, self.stream_id = stream.MULAW, ""
		self.lines, self.latencies = [], []  # lines: (speaker, text); latencies in seconds
		self.log = []  # what was sent, in order: {"kind", "text"}
		self.started = self.ended = False
		self.handed_over, self.handover_reason, self.end_reason, self.outcome = False, "", "", ""
		self.interruptions = self.turns = self.confusions = self.prompts = 0
		self._playing_until = 0.0
		self._speaking, self._frames = False, []
		self._speech_start = self._last_voiced = 0.0
		self._idle_since = 0.0
		self._caller_spoke = False

	# Stream events

	def handle(self, raw):
		"""Handle one Plivo stream message (a JSON string or a dict)."""
		if self.ended:
			return
		event = stream.parse(raw)
		if event.kind == "start":
			self.stream_id, self.encoding = event.stream_id, event.encoding
			self.start()
		elif event.kind == "media" and self.started:
			self.feed(stream.to_pcm(event.pcm, self.encoding))
		elif event.kind == "stop":
			self._end("the caller hung up")

	def start(self):
		"""The call is connected: the AI disclosure line comes before anything else."""
		self.started = True
		self._idle_since = self.clock()
		self._say(self.disclosure, "disclosure")

	# Listening

	def feed(self, pcm: bytes):
		"""One frame of the caller's audio, at the time `clock()` says it arrived."""
		if self.ended:
			return
		now = self.clock()
		if audio.rms(pcm) >= self.config.voice_rms:
			if not self._speaking:
				self._speaking, self._frames, self._speech_start = True, [], now
				if now < self._playing_until:
					self._interrupt(now)
			self._last_voiced = now
			self._frames.append(pcm)
			return
		if self._speaking:
			self._frames.append(pcm)
			if now - self._last_voiced >= self.config.hangover_s:
				self._speaking = False
				if self._last_voiced - self._speech_start >= self.config.min_speech_s:
					self._turn(b"".join(self._frames), self._last_voiced)
				self._frames = []
			return
		if now >= self._playing_until and now - max(self._idle_since, self._playing_until) >= (
			self.config.silence_timeout_s
		):
			self._silence()

	def _interrupt(self, now):
		"""The caller spoke over the agent: stop the queued audio and listen."""
		self.interruptions += 1
		self._playing_until = now
		self.log.append({"kind": "cleared", "text": ""})
		self.send(stream.clear_audio(self.stream_id))

	# Speaking

	def _say(self, text, kind):
		"""Speak `text`. Returns the time its first audio was sent, or None when nothing was."""
		first = None
		total = 0
		for chunk in self.tts.synthesize(text):
			if first is None:
				first = self.clock()
			total += len(chunk)
			self.send(stream.play_audio(chunk, self.encoding))
		if first is None:
			raise VoiceProviderError("The voice provider made no audio.")
		self._playing_until = max(self._playing_until, first) + total / audio.BYTES_PER_SECOND
		self._idle_since = self._playing_until
		self.lines.append(("agent", text))
		self.log.append({"kind": kind, "text": text})
		return first

	# A turn

	def _turn(self, pcm, speech_end):
		self._caller_spoke = True
		self.turns += 1
		try:
			text = self.stt.transcribe(pcm, self.keyterms).strip()
			if not text or not audio.is_roman(text):
				self.lines.append(("caller", "(not understood)"))
				return self._confused(speech_end)
			self.lines.append(("caller", text))
			if wants_human(text):
				return self._handover("the caller asked for a human", speech_end)
			if self.turns >= self.config.max_turns:
				return self._handover("the call ran long", speech_end)
			reply = self.llm.reply(self.system, list(self.lines), self.context)
			self._answer(reply, speech_end)
		except VoiceProviderError as error:
			self._handover(f"a provider failed: {error}", None)

	def _answer(self, reply, speech_end):
		tags = _TAG.findall(reply)
		spoken = _TAG.sub("", reply).strip()
		wants_handover = any(t[0].upper() == "HANDOVER" for t in tags)
		if wants_handover and not spoken:
			return self._handover("the agent could not help", speech_end)
		if not spoken or not audio.is_roman(spoken):
			return self._confused(speech_end)
		self.confusions = 0
		self._timed_say(spoken, "reply", speech_end)
		for tag in tags:
			name = (tag[1] or "").strip()
			if name and name.lower() in {o.lower() for o in self.outcomes}:
				self.outcome = next(o for o in self.outcomes if o.lower() == name.lower())
		if wants_handover:
			self._handover("the agent could not help", None)
		elif tags:
			self._end("the agent ended the call")

	def _confused(self, speech_end):
		self.confusions += 1
		if self.confusions >= self.config.max_confusions:
			return self._handover("confusion", speech_end)
		self._timed_say(CLARIFY_LINE, "clarify", speech_end)

	def _timed_say(self, text, kind, speech_end):
		first = self._say(text, kind)
		if speech_end is not None:
			self.latencies.append(max(first - speech_end, 0.0))

	def _handover(self, reason, speech_end):
		"""Say the handover line, then give the call to a human."""
		self.handed_over, self.handover_reason = True, reason
		try:
			self._timed_say(HANDOVER_LINE, "handover", speech_end)
		except VoiceProviderError:
			pass  # no voice to say it with: the handover still happens
		self._end("handed over to a human")
		if self.on_handover:
			self.on_handover(reason)

	def _silence(self):
		self.prompts += 1
		if self.prompts > self.config.max_silence_prompts:
			self._say(GOODBYE_LINE, "goodbye")
			if not self._caller_spoke and not self.outcome:
				self.outcome = next((o for o in self.outcomes if o.lower() == "not reachable"), "")
			return self._end("the caller was silent")
		self._say(SILENCE_LINE, "prompt")

	def _end(self, reason):
		self.close(reason)

	def close(self, reason):
		"""The call is over, for the reason given. The first reason stays."""
		if not self.ended:
			self.ended, self.end_reason = True, reason

	def result(self) -> Result:
		return Result(
			transcript="\n".join(f"{'Agent' if s == 'agent' else 'Caller'}: {t}" for s, t in self.lines),
			latencies_ms=[round(v * 1000) for v in self.latencies],
			handed_over=self.handed_over,
			handover_reason=self.handover_reason,
			end_reason=self.end_reason or "the call is still open",
			outcome=self.outcome,
			turns=self.turns,
			interruptions=self.interruptions,
			summary=latency_summary(self.latencies),
		)
