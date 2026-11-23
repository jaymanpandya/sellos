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
