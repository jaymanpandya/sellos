# The WhatsApp flow engine and the visual builder

Decided by Jayman, 27 November 2026. The ten flows in this folder (SOS-N23) and the flow tasks SOS-P6-16 and SOS-P6-17 are approved and are MUST for 1 January 2027. SellOS also gets a visual workflow builder, so each company builds its own custom WhatsApp workflows. Nothing is hard coded to Pandya. Jayman has a Meta verified number; its keys go in SOS-INT-1.

This file is the scope. The tasks are in `TASKS.md` (SOS-WA-1 to SOS-WA-8, and SOS-P6-16 and SOS-P6-17 changed). Nothing here is built yet.

## Design

1. **One engine.** A flow is stored data: a graph of steps, per company, versioned (Draft and Published). The ten bots are authored as flows in the same engine, so the builder edits the data they run on. There is no bot code outside the engine.
2. **Step types.** Trigger (inbound keyword or intent, button or list reply, new lead from a form or portal, schedule, stage change, mandate expiry); send message (text, image, document, location); send approved template; ask a question (free text, buttons, list) and save the answer to a field; branch on a condition; AI step (answers or classifies using the company's instruction and data only); wait; create or update a lead, task, site visit or follow up; assign to an agent or team; hand off to a human with context; end.
3. **Rules enforced in the engine, for every flow:** the WhatsApp STOP rule (nothing unprompted after STOP, one confirmation reply, an advisor task, the opt out logged); Meta's 24 hour window (free text inside it, approved templates only outside it); calling hours and do not call flags; consent rules (decision 7: consent never blocks a call or an SMS); rate limits per number and loop protection; a kill switch per flow and per company; the AI step never invents prices, availability or legal advice.
4. **The builder.** A canvas (Vue Flow or similar) with draggable steps and connections, a side panel to edit a step, template and field pickers, validation (dead ends, missing branches, the 24 hour rule), a test panel that runs a flow against a simulated conversation and sends nothing, versions with publish and roll back, a run log per conversation, and the ten bots as starter workflows. It follows `docs/UI_STYLE.md`.
5. **AI model.** Configurable per company on the Integrations screen (an AI model card added by SOS-WA-3). The default follows the SOS-N21B result; until Jayman runs it, the default is Claude Haiku 5.5.
6. **Permissions.** A Company Admin builds and publishes. A Sales Manager can view and test. Agents cannot edit. The Platform Admin, Clients and Channel Partners have no access. All are in the permission test matrix.
7. **Tests.** Engine unit tests with saved provider payloads (no live Meta call), the STOP and 24 hour rules, branching, versions, permissions, and a Cypress spec of building and publishing a simple flow (SOS-WA-7). The live test is SOS-P6-11L, Jayman's, once SOS-INT-1's WhatsApp card holds the keys.

## Tasks, points and order

| Task | What | Points | Depends on |
| --- | --- | --- | --- |
| SOS-WA-1 | (a) Engine: data model, step types, runner, triggers, roles | 8 | SOS-P6-11, SOS-P1-25, SOS-P2-04, SOS-INT-1 |
| SOS-WA-2 | (a) Rules in the engine: STOP, 24 hour window, calling hours, rate limits, loops, kill switches | 8 | SOS-WA-1 |
| SOS-WA-3 | (a) AI step and the per company AI model | 5 | SOS-WA-1, SOS-WA-2 |
| SOS-P6-16 | (b) Bots 1 to 5 as flows (was 8, unchanged) | 8 | adds SOS-WA-1 to 3 |
| SOS-P6-17 | (b) Bots 6 to 10 as flows (was 8, unchanged) | 8 | adds SOS-WA-1 to 3, SOS-P6-16 |
| SOS-WA-4 | (c) Builder canvas, side panel, pickers | 8 | SOS-WA-1, SOS-WA-2, SOS-P3-05 to SOS-P3-11 |
| SOS-WA-5 | (c) Validation in the builder | 5 | SOS-WA-4 |
| SOS-WA-6 | (d) Test panel | 5 | SOS-WA-4, SOS-WA-2 |
| SOS-WA-7 | (d) Versions, publish, roll back, run log, the Cypress spec | 5 | SOS-WA-4, SOS-WA-5, SOS-WA-6 |
| SOS-WA-8 | (e) Starter workflows | 3 | SOS-P6-16, SOS-P6-17, SOS-WA-7 |

New points: 47 (the eight SOS-WA tasks), plus 16 for SOS-P6-16 and SOS-P6-17, which become MUST.

Order in the loop:

* (a) and (b) come right after SOS-P3-04: SOS-WA-1, 2, 3, then SOS-P6-16 and SOS-P6-17, ahead of the other Jan 1 tasks. Dec 20 tasks still go first.
* (c), (d) and (e) come after the valuation chain (SOS-P3-05 to SOS-P3-11, listed as dependencies of SOS-WA-4) and before the scraper: SOS-P6-08 now depends on SOS-WA-8.
* **SOS-P6-16 and SOS-P6-17 depend on SOS-N23, which is Waiting on Jayman.** Until Jayman marks it Complete (`scripts/set-task-status.sh SOS-N23 Complete TASKS.md`, after reading these files), neither runs, and neither does SOS-WA-8 or the scraper behind it.

## What changes in the existing tasks

* SOS-P6-16 and SOS-P6-17 are authored as flows in the engine. Their acceptance and tests now say so. The STOP rule moves to the engine (SOS-WA-2); they no longer implement it.
* SOS-P6-08 (the scraper) depends on SOS-WA-8, so the builder comes first.
* SOS-INT-1 is already Complete and is not reopened. The AI model card is added by SOS-WA-3.
