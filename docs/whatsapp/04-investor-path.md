# Flow 4: Investor path

* **Document IDs:** B24 (Investor path)
* **Built by:** SOS-P6-16 (group one)
* **Document phase:** none. The document's phase lists do not name B24.
* **Source:** `SOURCE_workflow_design.md`, "Buyer workflows (B)", "Nurture and special paths"

## Purpose

For a person who chose Invest (flow 1) or said so in flow 2, capture the investment brief (ticket size, yield target, horizon, liquidity needs) and propose curated options: a new launch, a resale, a commercial unit, or plots such as Alibaug. The result is an investment shortlist with the assumptions stated.

## Trigger

Flow 1 hands over a person who chose Invest, or flow 2 finds that the purpose is investment.

## Who

Visitors and clients who are buyers. Identity rules of the source apply.

## Steps

1. **Capture the brief.** Ticket size, yield target, horizon, and liquidity needs, plus the property types they would consider (new launch, resale, commercial, plots). Skip what flow 2 already knows.
2. **Propose options.** Look up matching inventory in SellOS (search, never from memory) and offer up to three options with the facts SellOS holds and their "as on" date. The bot never promises appreciation, a guaranteed rental yield or a safe investment, and every example states its assumptions.
3. **Shortlist.** Save the options the person likes as a shortlist and say the assumptions beside each one.
4. **Next step.** Offer a call with an advisor or a site visit (flow 5). A large ticket size alerts a senior advisor with priority.
5. **Questions the bot cannot answer.** Tax on gains, FEMA, valuation and legal opinions go to the advisor, and the bot says why.

## Writes to SellOS

* The investment brief as part of the requirement card or notes on the Lead (purpose Investment).
* A Shortlist with its items, and a note that records the assumptions.
* A task for the advisor.

## Consent

Recorded and shown as a warning, never blocking. After a WhatsApp STOP, flow 1's rule applies: replies only to what the person sends.

## Handoff

Asks for a human, two failed attempts, a large ticket size, negotiation or an offer, or any tax, legal or valuation question: flow 8.

## Guardrails that apply

Compliance check before sending (O15 is in the backlog): banned claims such as guaranteed returns are never sent. Prices come only from SellOS with an "as on" date. Builder name and RERA details are shared only after the person enquires, matching the website; whether outbound project messages must carry the RERA number is an open question for counsel (see `README.md`).

## Test conversations (fake WhatsApp provider)

1. An investor gives a ticket, a yield target and a horizon. Expect up to three options from fixture inventory, each with its assumptions and date, and a saved shortlist.
2. The investor asks "Will this double in five years?" Expect no promise, a statement that the bot gives no such forecast, and an offer of an advisor.
3. The investor asks for a tax opinion on selling. Expect a plain reason and a handoff.

## Gaps

* **Investment fields.** The Lead has a purpose but no ticket size, yield target, horizon or liquidity need field, so the brief goes in notes.
* **Yield and assumptions.** SellOS holds no rental yield figures or investment assumptions for the bot to quote, and the document's rule that every number carries a source and an "as on" date has no store for the date on most figures.
* **Option types.** Property types include Plot, Office and Shop, but nothing marks a unit as a new launch or a resale for an investor search, and there is no pre leased marker.
* **The compliance check** (banned claims) does not exist.
* **The brain, buttons and lists** (see flow 1).
