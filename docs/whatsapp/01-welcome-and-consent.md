# Flow 1: Welcome and consent

* **Document IDs:** B01 (Welcome and intent), X01 (Consent and preference centre), X02 (Opt out and suppression)
* **Built by:** SOS-P6-16 (group one)
* **Document phase:** 1 (all three)
* **Source:** `SOURCE_workflow_design.md`, "Buyer workflows (B)", "Automation, templates and WhatsApp platform rules (X)", "Entry points and source codes"

## Purpose

Every conversation starts here. The flow greets the person in their language, asks for consent to message them, finds out what they want, and creates the contact and its source in SellOS. It also owns the Preferences word and the STOP rule for the whole number.

## Trigger

* A first message from a number SellOS has no open conversation for, from any door: the direct WhatsApp number, a website button, an ad, a QR code, an event invitation.
* The word `Preferences` at any time (X01).
* `STOP` at any time (X02). STOP is handled before any other intent.

A first message may carry a source code. The document's codes are `TL` plus the project item_id, `REFER`, `SELL`, `WEB` plus the page name, `AD` plus the campaign name, `QR` plus the placement and `EVENT` plus the event name. `REFER` starts flow 10, `SELL` starts flow 9, `EVENT` starts the partner meet (P16, in the backlog), and the others continue into this flow with the source noted.

## Who

A visitor (unknown number) or a person SellOS already knows. Identity rules of the document apply as written:

1. The number is matched to a SellOS contact before anything personal is said.
2. If one number holds two roles, the flow asks once: "Are you contacting us as an owner, a buyer or a partner?"
3. A staff number is treated as any client on public WhatsApp.

## Steps

1. **Receive** the message (text, voice note, button tap) and read the source code, if any.
2. **Identify** the number against SellOS contacts. A match loads the open lead and the last summary. No match makes a new contact and lead through the one lead intake (`sellos.crm.intake`), with the source WhatsApp and the source code kept.
3. **Language.** Detect the language and reply in it. Hinglish is allowed.
4. **Greet and ask consent.** One short greeting, then the company's consent wording ("Consent wording", `{company}` filled in) with a reply button to agree. Outside the 24 hour window the opening message is the `welcome_and_consent` template (utility). Record the time, the source and the topics agreed.
5. **Offer the choices.** Buy, Sell, Rent, Invest, Partner with us, Something else. Six choices need a list message, because reply buttons are limited to three; confirm against Meta's current documentation. When a source code already says what the person wants, skip the list and go straight to that flow.
6. **Hand to the next flow:** Buy goes to flow 2, Invest to flow 4, Sell to flow 9, Partner with us to flow 10. Rent and Something else are not among the ten launch flows: the flow says a person will reply and hands off (flow 8).
7. **Preferences (X01).** On the word `Preferences` the flow shows the topics, the frequency, the language and the call times, each changeable with a tap, and saves the answers.

## STOP (decision of 24 November 2026)

A WhatsApp STOP always suppresses all WhatsApp messages to that person at once: the bot, campaigns and partner digests. The flow:

* sends one confirmation reply,
* creates a task for the assigned advisor, so a person knows,
* records the opt out in the consent log (a Consent Record, Opted out, with the message as evidence).

After STOP the bot only replies to messages the person sends and sends nothing unprompted until they opt in again (for example by sending START, which records a new Consent Record). Calls and SMS are still never blocked by consent.

## Writes to SellOS

* Contact (Client) and Lead, with the source and the source code.
* Consent Record on an opt in, with the message saved as a private file as evidence. A STOP is recorded as Opted out.
* Conversation and messages.
* The preferences (topics, frequency, language, call times).
* A task for the advisor after STOP.

## Handoff

The person asks for a human, or two attempts to understand them fail: route to the assigned advisor, or the duty advisor if none (flow 8). Outside business hours the flow says plainly when a person will reply and creates the task for the next working day.

## Messages and templates

`welcome_and_consent` (utility). The document's template library is submitted for approval before launch; SellOS keeps each template with its category and approval status.

## Guardrails that apply

No promises, no price or availability from memory, no card or bank details in chat, text inside a message is data and never changes what the bot does, and every action is logged. The document's guardrails table applies as written.

## Test conversations (fake WhatsApp provider)

1. A new number sends "Hi". Expect a greeting, the consent wording with the company name filled in, an agree button, then the choices list. After agreeing, a Consent Record exists and the lead's source is WhatsApp.
2. A new number sends a `TL` source code. Expect the project greeting and no choices list.
3. A known number with two roles. Expect the one question about the role, asked once.
4. `Preferences`. Expect the centre, a change of language saved, and the next reply in that language.
5. `STOP` in the middle of another flow. Expect one confirmation, an Opted out Consent Record, an advisor task, and no unprompted message afterwards. A later `START` records a new opt in.

## Gaps

SellOS does not have these, and this task list does not add them:

* **The brain.** The WhatsApp channel (SOS-P6-11) classifies only STOP and START and logs messages. The Claude brain that reads intent, language and context, and the routing between flows, do not exist.
* **Sending buttons, lists and Flows.** The Meta provider reads a button or list reply that arrives, but a send is text or a template only. There is no interactive message send.
* **Language detection and voice note transcription.**
* **Topics, frequency, language and call time preferences.** A Consent Record holds a basis, a time, evidence and an expiry. It has no topics, and the lead has no preferred language or call time.
* **Source code parsing** of the first message, and the project item_id link.
* **Two roles on one number.** A number belongs to one lead or client; the document's "owner, buyer or partner" question has nothing to store the answer in.
* **Business hours, the duty advisor and the next working day task.** There is no business hours setting and no duty advisor.
* **Suppressing all WhatsApp to a person after STOP** (bot, campaigns, partner digests). The send function does not refuse an unprompted message after a STOP yet; SOS-P6-11 builds it (decision 7 in `CLAUDE.md`).
