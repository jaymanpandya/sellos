# Flow 8: Human handoff

* **Document IDs:** the handoff rules (section "Core engine: entry, routing, handoff, memory", "Handoff rules") and O19 (Handoff inbox)
* **Built by:** SOS-P6-17 (group two)
* **Document phase:** O19 is in phase 1 (the handoff rules are part of the core engine)
* **Source:** `SOURCE_workflow_design.md`, "Core engine", "Handoff rules", "Staff workflows inside SellOS (O)"

## Purpose

Every flow can hand a conversation to a person, and this flow is how: who gets it, what they are given, when the bot goes quiet and when it comes back. The advisor works the queue in the SellOS app.

## Trigger

The document's handoff table, as written:

| Trigger | What happens |
| --- | --- |
| The person asks for a human | Routed at once to the assigned advisor, or the duty advisor if none |
| HNI or UHNI flag, or a large ticket size | Senior advisor alerted with priority (concierge workflow N09, in the backlog) |
| Negotiation, discount, token or any offer | Advisor takes over. The bot keeps logging. |
| Anger, complaint or a threat of escalation | Manager alerted, bot stops selling and only acknowledges |
| A legal, tax or valuation opinion is asked for | Routed to the panel professional or advisor. The bot explains why. |
| Two failed attempts to understand the person | Bot offers a human instead of a third try |
| Payment, refund or dispute | Staff only |
| Low confidence in an answer | Bot says it will check, creates a task, and does not guess |

## Who

Any person on any flow. The staff side is the assigned advisor, the duty advisor, a senior advisor or a manager, in the SellOS app.

## Steps

1. **Detect** one of the triggers above, in any flow.
2. **Tell the person** plainly what happens next and when a human will reply. Outside business hours the bot still answers information questions and takes bookings, says when a human will reply, and creates the task for the start of the next working day.
3. **Hand over.** Create the handoff with a three line summary, the requirement card, the last messages and a suggested first reply. The conversation moves to "With a human" and the advisor is told.
4. **Go quiet.** When a human replies, the bot stays quiet on that thread.
5. **Return.** The bot resumes after a set period of human silence, or when the advisor taps Return to bot.
6. **Inbox (O19).** A queue of conversations waiting for a human, with their ages. The advisor claims one, replies, and returns it to the bot.

## STOP (decision of 24 November 2026)

STOP is handled before any trigger. The flow sends one confirmation reply, creates a task for the assigned advisor and records Opted out in the consent log, and all WhatsApp to the person is suppressed from then on: bot, campaigns and partner digests. After STOP the bot only replies to messages the person sends and sends nothing unprompted until they opt in again. The advisor's reply to a message the person sends is a reply, not an unprompted message. Calls and SMS are never blocked by consent.

## Writes to SellOS

* The conversation state (Open, With a human, Closed), who it is handed to, when, and the handoff note.
* A task for the advisor (or the manager, for anger), with the summary.
* A log of every trigger and every handoff.

## Consent

The lead's consent status and warning are shown to the advisor with the handoff. Nothing here stops a human reply on consent.

## Messages and templates

None of its own. Replies by the advisor inside the 24 hour window are free text; outside it, a template.

## Guardrails that apply

The bot never decides a payment, a refund or a dispute. It never gives a legal, tax or valuation opinion. When it is unsure it says it will check and does not guess. The document's guardrails table applies as written.

## Test conversations (fake WhatsApp provider)

1. "I want to talk to a person". Expect the conversation With a human, the advisor told, a handoff note of three lines, and no further bot reply on the thread.
2. The advisor taps Return to bot. Expect the bot to resume.
3. A buyer asks for a discount. Expect the advisor to take over and the bot to keep logging.
4. An angry message. Expect a manager task, an acknowledgement only, and no selling.
5. Two failed attempts to understand. Expect the offer of a human, not a third try.
6. A question outside business hours. Expect a plain message about when a person replies and a task for the next working day.
7. A tax question. Expect a plain reason and a routed task.

## Gaps

* **Duty advisor, senior advisor and manager alerts.** There is no duty advisor, no senior advisor role and no HNI flag. SellOS has the Sales Manager role and sales teams, but no escalation target for anger.
* **Business hours and the next working day.** No business hours setting exists.
* **Return to bot** and the period of human silence after which the bot resumes. A conversation can be handed to a human and closed (SOS-P6-11), but there is no return.
* **The handoff summary**, with a suggested first reply, needs the brain (see flow 1).
* **The inbox (O19).** A conversation holds who it was handed to, when and a note, and conversations can be listed by state. Claiming a conversation, and a queue ordered by waiting time, are not actions.
* **Sentiment and low confidence detection** for anger and for "I will check".
* **Panel professionals** (lawyer, chartered accountant, valuer) are not a role or a list in SellOS. The document leaves who to connect first as an open decision.
