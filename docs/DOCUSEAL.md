# DocuSeal signing of a mandate

SellOS sends a mandate for signing through [DocuSeal](https://www.docuseal.com) (their cloud, or a copy you host
yourself). DocuSeal emails each signer a link, collects the signature and keeps an audit trail. SellOS builds the
document, records where signing stands, and keeps the signed copy.

## This is an electronic signature, not Aadhaar eSign

DocuSeal produces an **electronic signature** under the Information Technology Act, 2000: the signer opens an emailed
link, draws or types a signature, and DocuSeal records the signer's name, email, time, address and device in an audit
trail. It is **not** an Aadhaar eSign, which is a signature made with the signer's Aadhaar and certified through a
licensed eSign service. Whether an electronic signature of this kind is enough for a mandate, and whether any
registration or stamping a mandate needs is satisfied by it, is a question for counsel. **Counsel decides**, and also
decides the wording of the clauses: the text in `sellos/inventory/mandate_document.py` is a plain starting wording
and is not legal advice. Until counsel has said yes, the manual route (upload a signed document) remains in the
mandate page and works as before.

## Setup

1. Have a DocuSeal account, or a self hosted DocuSeal. Create an API key (Console, API) and copy it.
2. In SellOS, sign in as a Company Admin and open **Company settings** (Company, Company settings), the DocuSeal card.
3. Enter:
   * **DocuSeal address**: `https://api.docuseal.com` for DocuSeal's cloud (use `https://api.docuseal.eu` for the EU
     cloud), or the address of your own installation such as `https://sign.example.com`. It must start with `https://`.
   * **API key**: the key from step 1. It is stored encrypted and is never shown again; leave the box empty later to keep
     the saved key.
   * **Webhook secret**: any long random text you make up. Enter the same text in DocuSeal (step 4).
   * **Company signer name and email**: the person who signs for the company. DocuSeal emails them too.
4. In DocuSeal, open Webhooks, add a webhook and set:
   * the URL shown on the card (it ends `/api/method/sellos.inventory.docuseal_webhook.docuseal_event` on your company's
     address);
   * a custom header named `X-Webhook-Secret` whose value is the webhook secret from step 3;
   * the events: form viewed, form started, form completed, form declined, submission completed and submission expired.
5. Press **Test the connection** on the card. It asks DocuSeal for one template and says whether the address and key
   work. (It does not test the webhook: that is checked by sending a real mandate to yourself.)
6. The seller needs an email address on their client record, because DocuSeal emails them the document.

With the address or key missing, the mandate page says **Connect DocuSeal** and links to the settings.

## Using it

1. Open a Draft mandate and press **Send for signing**. SellOS builds the document from the mandate template with the
   company's branding (Company profile: logo, colours, name, RERA number, address, footer), the seller, the property,
   the fee, the term, the exclusivity and the two signers, and puts a signature box for each signer on the last page.
2. SellOS uploads it to DocuSeal as a template, creates a submission for the seller and the company's signer, and
   records the submission id, each signer's status and the times.
3. While it is out, the mandate's terms are locked (the document they signed holds them). If a signer declines or the
   submission expires, the terms unlock and the mandate can be corrected and sent again.
4. DocuSeal reports each step to the webhook: **Sent, Viewed, Signed, Declined, Expired**. When everyone has signed,
   SellOS downloads the signed PDF and the audit trail, stores them as private files of the mandate, and moves the
   mandate to **Signed**, which releases its Private Sale Dossier. The mandate page and the list show the status, and
   **Download signed copy** and **Audit trail** links.

## What is stored

Settings (SellOS Settings, one row per company site): the DocuSeal address, the company signer's name and email, the API
key and the webhook secret (the last two as encrypted password fields; they are never returned by any method, written to
a log, an error or a test).

On the mandate:

| Field | Meaning |
| --- | --- |
| Signing status | Not sent, Sent, Viewed, Signed, Declined or Expired |
| Signing provider, DocuSeal submission | Where it was sent and the submission's id |
| Sent for signing on, first viewed on, signed by all on, declined on | The times |
| Signers (a table) | Role (Seller or Company), name, email, DocuSeal signer id, status, and when each was sent, viewed and signed |
| Mandate document | The PDF that went out (a private file) |
| Signed document | DocuSeal's signed PDF (a private file; the same field the manual upload uses) |
| Audit trail | DocuSeal's audit trail PDF (a private file) |

Every file is private and is opened only by who may read the mandate. The Webhook Event table keeps a hash of each event
for replay protection. Nothing is deleted.

## The webhook

* `POST /api/method/sellos.inventory.docuseal_webhook.docuseal_event`, with no SellOS user, on the company's own site
  (the site the request arrives on is the company; nothing in the request chooses it).
* The shared webhook rules apply: the secret header is checked first and a failure writes nothing and answers `refused`;
  a replayed event (same type, timestamp and id) changes nothing; the body is capped at 512 KB; requests are limited to
  120 a minute per company.
* A status only moves forward, so a late "viewed" after "signed" is ignored.
* DocuSeal's document links are fetched only over https, only from the company's own DocuSeal or a public host (never a
  private address), without following redirects, and only if they are PDFs of up to 25 MB. The API key is sent only to
  the company's own DocuSeal.
* If a document can not be fetched the request fails, so DocuSeal retries it later and nothing is half recorded.

## What was tested, and what was not

Tested against a **fake DocuSeal server** on the same machine (`sellos/tests/fake_docuseal.py`): the settings, sending,
the signature fields on the document, every webhook event, replays, out of order events, bad and missing secrets,
oversized and rate limited requests, the fetch rules, and who may do what. **Not tested against real DocuSeal:** the
fake was written from DocuSeal's public API description (`POST /api/templates/pdf`, `POST /api/submissions`, the
`X-Auth-Token` header, the webhook events `form.*` and `submission.*`). If the real service differs in a field name or
in how the webhook header is configured, `sellos/inventory/docuseal.py` and `docuseal_webhook.py` are the only places
to change. Do one real test mandate to yourself before using it on a client.

Characters outside the Windows Latin 1 set (for example Devanagari) are written as `?` in the generated PDF, because the
PDF writer uses the standard Helvetica font. A seller's name in another script should be entered in Latin letters.
