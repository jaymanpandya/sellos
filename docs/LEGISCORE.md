# LegiScore API limits and the corridor loading cost (SOS-P3-14 to SOS-P3-17)

Read from https://legiscore.in/docs and its full text file on 27 November 2026 (Jayman's request, same day).
Nothing here comes from a real call: no key was used. "Not stated" means the docs do not say; the first
real run (SOS-P3-01L) records the answer. Base `https://legiscore.in/api/v1`.

## What the docs state

| Topic | Finding |
|---|---|
| Auth | `Authorization: Bearer lsk_...` (or `X-API-Key`). Keys belong to one workspace and spend that workspace's search wallet. Use an unrestricted key server to server. |
| Key and balance | There is no key check call. `GET /search/credits` returns `data.scope`, `balance`, `spendable` (includes postpaid headroom), `postpaid.enabled`, `postpaid.limit` and a `ledger` (`type` charge, refund, topup or adjust; `balance_after`, `cost_key`, `note`, `at`; `limit` up to 100). A bad key is 401 `unauthorized`. The balance call is not stated to cost anything. |
| Rate limits | Submit 120 searches a minute per key (a batch of 25 spends 25). Reads ten times that. Lookups 120 a minute per key. At most 100 searches queued or running per workspace. 429 codes: `rate_limited`, `too_many_open_searches`, `upstream_busy`, with `Retry-After`. |
| Credit prices | Charged at submit; failed or cancelled searches are refunded in full; refused requests (402, 422, 429) cost nothing. **Only one price is stated: Maharashtra Index II by property, 20 credits per year searched.** `rera_check`, AI Assist and AI Recovery have no stated price. |
| Documents | A result lists `filename`, `content_type`, `bytes`, `withheld`. A document is fetched with a 302 to a signed URL valid one hour; a failed integrity check is 410 (withheld). |
| 25 | The docs state 25 only as the **batch size** (up to 25 searches in one submit). A cap of 25 documents a search is **not stated** in the general pages; it appears only in a per state summary I could not verify. The "truncated" handling in SOS-P3-15 stays, and SOS-P3-01L confirms the real cap. |
| Timeouts | Poll every 5 to 10 seconds. A search not finished after 3 hours is failed and refunded by LegiScore. Idempotency window 24 hours. Webhooks (not used by us): answer in 30 seconds. HTTP timeouts and the OTP wait are not stated. Per search run times are only in unverified summaries (about 2 minutes for RERA, about 20 minutes for Index II by property), so our 20 minute poll limit is a guess to confirm. |
| Lookups | Resolve district, tahsil, village and office names. At most 10 matches. "Lists are not available. Never try to enumerate a lookup." |
| Rupees | Not stated. Credits are added by LegiScore on request (info@legiscore.in). A sample balance in the docs is 1,180 credits. We need the rupee price per credit from LegiScore before any budget is real. |

## Is there a bulk or area listing? No.

No endpoint lists the buildings or projects of an area, locality, pincode or village. Every search takes one
property or one project (Index II by property takes village plus survey, gat or CTS number plus year; RERA
searches take a project name or number). The only lists are your own searches and your credit ledger. LegiScore
is a per property and per project lookup, as TASKS.md already says.

So the loader cannot ask LegiScore "what is in Bandra". It is built as:

1. **Seed list** of buildings and projects, from a RERA project search, a CSV, or an agent's list. The seed
   gives a name, a micro market and, where known, village, CTS numbers and RERA number.
2. **Enrich** each seed through LegiScore, one lookup per building, inside the budget and per run cap
   (SOS-P3-14). Enrichment fills missing CTS, RERA and registered documents.
3. **Review screen** (SOS-P3-04): a person confirms or corrects each system built building before it counts.
   Nothing unconfirmed reaches the matcher or a published view.

## Worked example: loading the Bandra to Andheri corridor

Assumptions, all mine and to be replaced with the real seed file: **300 buildings**, an average of **1.5 CTS
numbers** each, so **450 CTS numbers**, and **5 years** of Index II history.

* Index II: 450 CTS x 5 years = **2,250 searches x 20 credits = 45,000 credits**. A building with a CTS missing
  is not searched until the review supplies it.
* RERA check: 150 projects among the 300 buildings, one check each. Price not stated, so not counted
  (if it were 20 credits, 3,000 more). It repeats each time the schedule runs.
* Re-runs are free only for the same search inside 24 hours (idempotency); a re-run next week is charged again,
  so the loader must skip years already stored (SOS-P3-15 already requires a re-run to change nothing).
* Time: 2,250 submits is about 19 minutes at 120 a minute, but only 100 searches may be open at once. If an
  Index II search takes about 20 minutes (unverified), the throughput is about 5 a minute, so about 7.5 hours.
  Run it overnight in batches, never by hand.
* Rupees: 45,000 credits times the price per credit, which is not stated. **Ask LegiScore for the price before
  Jayman approves a run.** The per run cap in the panel should be set to one batch (for example 5,000 credits),
  so a bad assumption costs one batch, not the whole corridor.
* The twenty buildings of SOS-P3-04A cost at most 20 x 1.5 x 5 x 20 = **3,000 credits**, a sensible first run.

## Rules this page does not change

No test and no loop run calls LegiScore. A real run needs the key from the Integrations screen (the Market
data source panel) and stays inside the monthly budget and the per run cap. Parties' names stay on the control
site (SOS-P3-12).
