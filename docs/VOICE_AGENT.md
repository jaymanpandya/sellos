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
