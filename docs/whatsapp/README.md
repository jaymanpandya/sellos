# WhatsApp flows

The WhatsApp flow designs for SellOS (SOS-N23). `SOURCE_workflow_design.md` is Jayman's design document of 24 November 2026: 175 workflows in eleven families, one bot brain behind three doors (the website, the direct WhatsApp number and the SellOS panel). It is the source and is kept exactly as written. **No workflow from it is in `TASKS.md`.**

SOS-P6-16 and SOS-P6-17 build the ten launch flows below from these files, against the fake WhatsApp provider of SOS-P6-11. The real number is SOS-P6-11L.

## The ten launch flows

| # | Flow | Document IDs | Built by |
| --- | --- | --- | --- |
| 1 | [Welcome and consent](01-welcome-and-consent.md) | B01, X01, X02 | SOS-P6-16 |
| 2 | [Lead qualification and routing](02-lead-qualification-and-routing.md) | B02, B03, B04 | SOS-P6-16 |
| 3 | [NRI buyer intake](03-nri-buyer-intake.md) | N01, N02 | SOS-P6-16 |
| 4 | [Investor path](04-investor-path.md) | B24 | SOS-P6-16 |
| 5 | [Site visit booking, reminders and no show](05-site-visit-booking-reminders-and-no-show.md) | B13, B14, B15 | SOS-P6-16 |
| 6 | [Post visit feedback](06-post-visit-feedback.md) | B17 | SOS-P6-17 |
| 7 | [Cold lead nurture and reactivation](07-cold-lead-nurture-and-reactivation.md) | B22, B23 | SOS-P6-17 |
| 8 | [Human handoff](08-human-handoff.md) | the handoff rules, O19 | SOS-P6-17 |
| 9 | [Seller intake](09-seller-intake.md) | S01 | SOS-P6-17 |
| 10 | [Partner and referrer registration and status](10-partner-and-referrer-registration-and-status.md) | P10, P11, P15 | SOS-P6-17 |

Group one (SOS-P6-16) is flows 1 to 5. Group two (SOS-P6-17) is flows 6 to 10. SOS-N23 does not fix a different split. The descriptions of SOS-P6-16 and SOS-P6-17 in `TASKS.md` do not match it exactly: SOS-P6-17's description names site visit booking, which is flow 5 here, in group one. This README follows the split Jayman gave on 24 November 2026, and the note on each task says so.

The ten flows cover 20 workflow IDs (the handoff rules are not an ID). The other 155 are listed in [BACKLOG.md](BACKLOG.md) with the document's build phase.

## What every flow file holds

Document IDs and group; the purpose; the trigger; who it is for; the steps; what it writes to SellOS; consent; handoff; the messages and templates; the guardrails that apply; scripted test conversations for the fake provider; and **Gaps**. A gap is something the flow needs that SellOS does not have today: a role, a tool, a setting, a field. A gap is only listed. It is not built, and it is not a task.

## Decisions (Jayman, 24 November 2026)

1. **STOP.** A WhatsApp STOP always suppresses everything the bot, campaigns and partner digests send unprompted. The flow sends one confirmation reply, creates a task for the assigned advisor, and records the opt out in the consent log. The person can still write to us and get replies; nothing is sent unprompted until they opt in again. Calls and SMS are still never blocked by consent. `CLAUDE.md` decision 7 was restated to say so on 24 November 2026, and SOS-P6-11, SOS-P6-11L and SOS-P6-17 follow it.
2. **The brain.** The WhatsApp brain is Claude. The voice agent stays Sarvam (SOS-N21).
3. **Identity rules, handoff rules and guardrails** are used as the document writes them (`SOURCE_workflow_design.md`, "Surfaces, identity and roles", "Handoff rules", "Guardrails, compliance and escalation"), except where they conflict with a decision here.

## Open questions (not decided)

1. **Connection route.** Meta's Cloud API directly, or a solution provider. (The notes of SOS-P6-11L, SOS-P6-16 and SOS-P6-17 record Meta's Cloud API directly, from 13 November 2026, and the code has a Meta adapter behind a provider interface. The source document lists the route as a decision still needed, and nothing here changes the earlier note.)
2. **Launch languages.** English and Hindi first, then Marathi and Gujarati, or another order.
3. **Business hours and reply times.** The business hours, and the reply time promised for each type of handoff.
4. **Advisor replies.** From SellOS only, or also from the WhatsApp Business app on the same number.
5. **The RERA number on outbound project messages.** Whether a message about a specific project must carry the RERA registration number (counsel to confirm).

## Conflicts to settle

These are not decided here and no code or task was changed for them.

* **Protection at registration.** Flow 10: the document confirms protection in writing at registration; SOS-P7-02 protects from approval.

## Notes on how these files were made

* The source document was read from `~/Documents/SellOS/` because it was not in `~/Downloads`. Its 175 rows were counted.
* SOS-N23 names no per flow file format, so the format above is the one used.
* The brain, interactive messages, the scheduler, business hours and most requirement fields are gaps in every flow. They are listed in each file where the flow needs them.
