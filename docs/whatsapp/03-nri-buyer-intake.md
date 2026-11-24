# Flow 3: NRI buyer intake

* **Document IDs:** N01 (NRI intake), N02 (Time zone aware scheduling)
* **Built by:** SOS-P6-16 (group one)
* **Document phase:** 3 (N01 to N07)
* **Source:** `SOURCE_workflow_design.md`, "NRI and HNI workflows (N)"

## Purpose

Capture what an NRI buyer needs that a local buyer does not (country, time zone, contact hours, budget in rupees and in the home currency, funding route, who in Mumbai can act for them), flag the lead as NRI, and offer call and video slots in the person's own time zone. These clients value time, discretion and certainty.

## Trigger

* A person who tells the bot they live abroad, or whose number or earlier answer shows an overseas country (flow 1 or flow 2).
* A Client record that already has a country of residence other than India.
* The person asks for a call or video at a time they give in another time zone.

## Who

Visitors and clients who are NRIs. The identity rules of the source apply. An NRI who is also flagged HNI or UHNI is routed with priority to a senior advisor (concierge flow N09, in the backlog).

## Steps

1. **Intake (N01).** After consent (flow 1), ask: country, time zone, preferred contact hours, budget in rupees and in the home currency, funding route (NRE, NRO, foreign income), purpose, and who in Mumbai can act for them. Skip what is known. One question at a time, with buttons where the answers are a short list.
2. **Flag.** Mark the lead as NRI and save the requirement card (continue into flow 2's requirement questions for configuration, micro market and timeline).
3. **Scheduling (N02).** Offer call and video slots in the client's local time, show both time zones in the message, and confirm. Reminders go in the client's morning or evening, not in India's night.
4. **Confirm.** The slot is saved with both time zones. If no advisor slot fits, create a task for the advisor to propose one and tell the person when a reply will come.
5. **No legal or tax opinions.** FEMA, repatriation, TDS and power of attorney questions are not answered here; they go to the advisor, who refers to the panel lawyer or chartered accountant (N04, N05, F11 in the backlog). The bot says why.

## Writes to SellOS

* The Client's country of residence and overseas phone (these fields exist, and the overseas number is masked like any phone).
* NRI flag, time zone, contact hours, budget in both currencies, funding route and the Mumbai representative, as the requirement card or notes.
* The scheduled call as a task or visit with both time zones in the note.

## Consent

Recorded and shown as a warning. It never stops a message while Consent enforcement is Off. After a STOP, flow 1's rule applies. Reminders at the client's local morning or evening are messages the person asked for; they are not sent unprompted after a STOP.

## Handoff

Asks for a human, two failed attempts, an HNI or UHNI flag, or any legal, tax or valuation question: flow 8. The handoff summary states the country, the time zone and the contact hours.

## Guardrails that apply

No legal, tax or valuation opinion from the bot. Currency conversions carry a source and an "as on" date (the estimator N06 is in the backlog). Never collect bank or PAN details in chat.

## Test conversations (fake WhatsApp provider)

1. An NRI in a gulf country answers all questions. Expect the NRI flag, the country on the client, and a slot offered in the client's time.
2. A reminder is due while it is night in the client's zone. Expect it held to the client's morning or evening.
3. The NRI asks about tax on sale. Expect no answer, a plain reason, and a handoff.
4. An NRI with a very large ticket. Expect a priority alert to a senior advisor.

## Gaps

* **NRI fields.** The Client has a country of residence and an overseas phone. The Lead and Client have no time zone, no contact hours, no home currency budget, no funding route (NRE, NRO, foreign income), no NRI flag and no Mumbai representative.
* **Time zone scheduling.** There is no advisor calendar or slot availability in SellOS (the Site Visit record is a booked time, not a calendar), so slots cannot be offered from an advisor's calendar, and no time zone conversion exists.
* **Senior advisor and HNI flag.** There is no HNI or UHNI flag and no senior advisor role.
* **The brain, buttons and lists** (see flow 1).
