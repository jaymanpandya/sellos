# Market data source adapters (SOS-P3-01)

Market data lives on the control site (SOS-SETUP-34, question 8). A source is wherever registration
records come from. One adapter interface lets SellOS work with whichever source is secured.

## The interface (`sellos/intel/adapters.py`)

* `fetch_batch(cursor=None)` returns a `Batch(records, next_cursor)`. `next_cursor` is None on the last batch.
* `map_fields(raw)` returns the canonical record, or raises `RecordError` (the record is rejected and
  counted, the run goes on). `SourceError` means the source cannot be read at all: the run fails.
* A new adapter subclasses `SourceAdapter`, sets `kind`, is registered with `adapters.register` and is
  added to the Adapter options of Market Source.

## Canonical shape

`source_record_id` and `registration_date` are required; `document_type`, `sro_office`, `district`,
`locality`, `property_description`, `survey_number`, `area_sqft`, `consideration_amount`,
`market_value` and `stamp_duty` are optional. Dates are `YYYY-MM-DD`, `DD-MM-YYYY` or `DD/MM/YYYY`;
rupee amounts may carry commas. No party names or other personal data are carried.

## The file adapter

A CSV (header row of canonical names, extra columns ignored) or a JSON list (or `{"records": [...]}`),
placed in the control site's private files folder and named in the Market Source. Read in batches of 500.

## Runs, schedule and alerts (`sellos/intel/runner.py`)

* A Market Source has an adapter, a file name, Enabled and a Frequency (Hourly, Daily, Weekly).
  `run_scheduled` runs hourly from the scheduler, on the control site only, and runs each enabled
  source whose next run has come.
* Each run is a Market Source Run: batches, records read, accepted and rejected, the first 20 rejected
  records with their reasons, and the error of a failed run.
* A run fails when the source cannot be read or when every record read was rejected. It alerts every
  enabled Platform Admin once, with an App Notification "Market data run failed".
* Accepted records go to the sink, as `(raw, mapped)` pairs: by default the raw transaction table below.
  `runner.set_sink(None)` makes a run count records and store none.

The adapters only read what they are given. They never solve a captcha or go round an access control.
The real source's adapter and its first batch are SOS-P3-01L. `FakeSource` (`sellos/intel/fake_source.py`)
feeds the tests.

## The raw transaction table (SOS-P3-02, `sellos/intel/raw_store.py`)

Every accepted record is stored as received in the Raw Transaction DocType on the control site: the
canonical fields as the source gave them (`raw_record`, JSON), the Market Source, the fetch time and a
SHA-256 hash of the record. Other columns of a file are dropped before hashing. A row is written once and
never changed or deleted, so cleaning (SOS-P3-03) can always be repeated from it.

* **No duplicates.** The duplicate check key is the hash of the source and the record's hash. Running the
  same file again adds nothing. A source's corrected record has a different hash, so it is stored beside
  the original.
* **Reading.** A company site never holds these rows. `sellos.intel.api.list_raw_transactions` (Platform
  Admin, control site only, pages of at most 200) is the one way to read them.

## The normaliser (SOS-P3-03, `sellos/intel/normaliser.py`, `marathi.py`, `normalise_store.py`)

`normaliser.normalise(record)` cleans one raw record, with no database. `normalise_store.normalise_pending`
runs it over the raw table on the control site and writes the results; the raw row is never touched.

* **English, original kept.** Marathi text is translated from a glossary (document types, property words,
  well known Pune and Mumbai places) and any other Devanagari word is transliterated by rule. The original
  text and area are kept in the Normalised Transaction's `original_fields`, and in the raw row.
* **Dates** become YYYY-MM-DD (day first; Devanagari digits and Marathi month names understood). A date out
  of range (before 1980 or more than a year ahead) is unreadable.
* **Money** (consideration, market value, stamp duty) becomes rupees: commas, Rs, the rupee sign, `/-`,
  lakh, crore and the Marathi words are understood. `-`, `NA` and `nil` mean no figure.
* **Area** becomes carpet square feet, with the rule in `area_rule`: sq ft or sq m as given (carpet), built
  up divided by 1.2, super built up divided by 1.4, and land units (guntha, acre, hectare, are) converted
  with no carpet adjustment. The two ratios are constants in the module.
* **Review list.** A record with any unreadable date, amount or area gets no Normalised Transaction and one
  Normaliser Review entry (status Open, the fields and why). A later run that can read it writes the clean
  record and marks the entry Resolved. `normalise_pending(force=True)` repeats the cleaning for every record.
* **Golden file.** `sellos/intel/golden_normaliser.json` has 100 synthetic records (92 readable, 8 not) and
  the gate needs at least 95 percent of fields correct. The check on real data is SOS-P3-13.

## LegiScore (decided by Jayman, 24 November 2026; SOS-P3-14 to SOS-P3-17)

The registration data source is LegiScore (https://legiscore.in/docs, base `https://legiscore.in/api/v1`,
Bearer key). It is a per property or per project lookup service, not a bulk feed. SOS-N12 (a request to
the Department) is Not Needed.

* **Panel (SOS-P3-14).** The Platform Admin enters the API key (stored encrypted, shown masked, never in
  code, logs, fixtures or chat), reads the credit balance (`GET /api/v1/search/credits`), sets a monthly
  credit budget and a per run cap, and confirms before any spend.
* **Index II (SOS-P3-15).** `index2_property` for Maharashtra, per building from its CTS numbers, one year
  at a time. District, tahsil and village are resolved by name through the lookups and never enumerated;
  Mumbai uses the Mumbai tab with `area_name`. One raw row per registered document, each result PDF a
  private file. A timed out year is "not searched" and a search at the 25 PDF cap is "truncated", never zero.
* **RERA (SOS-P3-16).** `rera_check` (not `rera_single`, which is replaced) per Project with a RERA number,
  on a schedule Jayman sets. The summary PDF and the latest sold and booked inventory disclosure PDF are
  private files, and each run takes a dated snapshot of the parsed figures.
* **Review (SOS-P3-17).** Extracted figures wait in a review queue. Nothing feeds the Property Matcher or a
  published view before approval. The reader (the normaliser or Sarvam Vision) is chosen after
  SOS-P3-17L's check on real PDFs; SOS-P3-03's normaliser parses text and reads no PDF.
* **Calls.** Every submit sends an `Idempotency-Key`. A search is polled every 5 to 10 seconds for up to
  20 minutes; there is no callback endpoint. No test and no loop run calls LegiScore: tests use saved
  responses in `sellos/intel/fixtures/legiscore/`.
* **Who sees what.** Parties' names stay on the control site (SOS-P3-12). Company sites and the Property
  Matcher get building level and project level figures only.
* **Open questions** (recorded by SOS-P3-01L with LegiScore's written answers): permanent storage, use in
  derived analytics and matching, showing derived figures to several customer companies, and the terms of
  its upstream sources.

* **Limits and cost** (27 November 2026): `docs/LEGISCORE.md` has the rate limits, credit prices, timeouts, the
  balance call and a worked cost for the Bandra to Andheri corridor. There is no bulk or area listing: buildings
  come from reviewed seed lists (SOS-P3-04) and are enriched one at a time.

## The building and micro market master (SOS-P3-04, `sellos/intel/markets.py`, `buildings.py`, `platform_master.py`)

Decided by Jayman, 27 November 2026. Micro markets are data, never code, and SellOS is sold across India, the UAE and
Australia (only India's data adapter is built for 1 January).

* **Two layers.** The control site holds a platform master of buildings (Platform Building, curated by the Platform
  Admin, seeded from the corridor sample with `load_platform_master`). Each company site holds its own Micro Markets
  and Buildings, a building optionally linked to a platform building by its `platform_building` id. A company's micro
  market only groups its own buildings, so it can rename, split, merge and archive without touching another company or the
  platform master. A building that is not on the master has no market data until it is linked.
* **Micro Market.** Name, country, city or region, an optional GeoJSON boundary (`geo.py` checks it), status Active or
  Archived and a history. Two active markets of one country never share a name. A rename, a boundary change, a split,
  a merge, an archive and a restore each add a history line. Nothing is deleted.
* **Split and merge.** A split archives the old market, makes two new ones (each remembers `split_from`) and moves every
  building to one of them. A merge moves a market's buildings into the other and archives it (`merged_into`). Each building
  keeps a list of the micro markets it belonged to, with from and until times and the reason (Added, Moved, Corrected, Split,
  Merged). An archive is refused while buildings remain.
* **From a file.** `load_micro_markets` reads `{"markets": [{name, country, parent, boundary}]}` and updates a market of the
  same name and country instead of doubling it. `sellos/intel/fixtures/corridor_bandra_andheri.json` is a sample for the tests and
  Pandya's first set, with rough boundary boxes and made up buildings. It is not a rule; the real boundaries and buildings are
  SOS-P3-04A. Nothing loads by itself, so the Ahmedabad demo company holds nothing real.
* **Building.** Name, micro market, optional project and country. India: CTS numbers (several), village, tahsil, district and
  RERA number. Optional, stored and shown only: UAE community and DLD number, Australian lot and plan. Which identifiers show
  follows the country (`fixtures/identifier_profiles.json`, data, not code).
* **Seed list.** `load_building_seed_list` takes a CSV with a header (name, RERA, CTS, village, tahsil, district, micro market)
  or one name a line, and makes buildings that Need review. The same list twice adds nothing. It never calls LegiScore.
* **Review.** The Buildings screen lists the buildings with name, CTS, RERA and micro market. A Company Admin or Agent corrects
  a field (a Building Correction keeps the field, old and new value, who and when) or confirms the building. Only Confirmed
  buildings are returned by `buildings.confirmed_buildings`, which is what the Property Matcher and the roll ups use.
