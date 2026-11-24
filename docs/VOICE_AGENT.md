# Voice agent service (SOS-P5-07)

Code: `sellos/voice/agent/`. Built and tested against fakes; the first real call is SOS-P5-07L.

* `stream.py`: Plivo's audio streaming events (`start`, `media`, `stop`, `playAudio`, `clearAudio`), 8 kHz mu-law.
* `session.py`: one call. The AI disclosure line is the first audio. The caller may speak over the agent at any time
  (the queued audio is cleared). A request for a human, or two turns in a row not understood, hands the call over.
  Each turn's time (end of the caller's speech to first audio sent) is kept; the target is one second.
* `adapters.py`: speech to text (Sarvam Saaras V3, Deepgram Nova-3), text to speech (Sarvam Bulbul V3, ElevenLabs),
  language model (Anthropic, model = the setting "Voice agent model"), and a fake of each.
* `config.py`, `settings.py`: Voice Agent Settings. Providers, model, disclosure line and keyterms are company
  settings, edited by a Company Admin; the keys are encrypted and never returned.
* `service.py`: `start_agent_call` places an AI call through the one call function (consent check and purpose
  recorded on the Call Log); `run_stream` and `handle_stream` run a call and write transcript, outcome, turn times
  and handover to the Call Log. Consent never blocks.
* `server.py`: the WebSocket end (needs the `websockets` package; not installed on the shared bench). The Call Log
  write is queued for a worker, which commits it.
* `fake_stream.py`: replays recorded 8 kHz WAV audio as Plivo events on a simulated clock.

To confirm in SOS-P5-07L: the exact Plivo field names, Sarvam's keyterm field, the live handover transfer, and the
real turn times.

## Provider choices (SOS-N21, decided by Jayman, 24 November 2026)

* Speech to text: Sarvam Saaras, the current recommended version (`saaras:v4`; `saaras:v3` stays available).
* Text to speech: Sarvam Bulbul. `bulbul:v4-flash` is available and is the one Sarvam documents for new
  integrations; `bulbul:v3` is the older one. Both are selectable, and the model is a setting.
* The voice agent's language model: a Sarvam chat model, named in a setting by Jayman.
* The agent assistant: Claude, default Sonnet 5.5 (`claude-sonnet-5-5`), a changeable setting, on the
  Anthropic account Jayman holds.
* Jayman holds the Sarvam account and enters all keys. No key is in the repository or in chat.
* The voice agent's language model is Sarvam 105B, to be confirmed against docs.sarvam.ai.
* Before the voice agent goes live, the Sarvam model is compared with Claude Haiku 5.5 on the fixed
  disclosure line and the handover. SOS-N21A's harness compares Anthropic models only, so SOS-N21B (Claude Code:
  the Sarvam adapter and the comparison, with fakes) and SOS-N21BL (Jayman: the live run with his Sarvam key)
  do it.

## The AI disclosure line (SOS-N21C, decided by Jayman, 24 November 2026)

The default of the company setting "AI disclosure line" (Voice Agent Settings), spoken first on every call:

> Namaste, main Nicole baat kar rahi hoon. Main {company} ka AI assistant hoon. Yeh call quality ke liye record ho rahi hai. Agar aap kisi insaan se baat karna chahein, toh bas bol dijiye.

A Company Admin can edit it. `{company}` is replaced with the company's display name (the setting "Company name",
or "the company" while it is empty) when the line is spoken, and the settings screen shows the raw text. The persona
name Nicole is part of the text. Counsel reviews it before launch. The voice agent refuses to place a live call, and
creates no Call Log, while the setting is empty.
