# OCR step

`python -m scraper ocr --state-dir state --out out` runs in `scrape.yml` between "Scrape" and
"Publish". It reads the page images of new brochures whose chain prints prices only in the
images, with Gemini (`gemini-3.8-flash`, `thinkingLevel: LOW`, the page prompt in
`gemini._pages_prompt`), and adds the products to `out/`. Code: `pipeline.py` (the step),
`state.py` (what it remembers between runs).

## What it publishes

- `products_ocr/<brochure_id>.json`: the usual product file (`schema/products.schema.json`);
  every product has `"source": "ocr"` and a 0-based `page_index` into the brochure's `pages`.
- `ocr_products_url` on the brochure in `catalog.json`, pointing at that file. `kind`,
  `products_url` and `product_count` are never changed, so app versions that do not know the
  field (v1.0.0, v1.1.x) never show OCR prices without their "broşürden okundu" label.
- `ocr_state.json` (`schema/ocr_state.schema.json`, not read by the app): per brochure the
  page fingerprint that was read, model, thinking level, prompt version and read time, or the
  failed attempts; plus the requests spent on the current quota day.

A reading is dropped (and counts as a failed attempt) when fewer than `max(5, pages)`
products are usable or more products are unusable than usable. A product is unusable without
a name, a price that `prices.parse_ocr_price` understands, or a page. After every change the
whole output is checked with `scraper.core.pipeline.verify_output`; a reading that fails the
check is rolled back, the rest of `out/` is published as the scrape step wrote it.

## Each brochure is read once

The fingerprint is the ordered page list (URL, `w`, `h`) plus the SHA-256 of each page file we
render ourselves (Şok WebP). If it matches the record in the previous output (`state/`, restored
from the `data` branch), the earlier `products_ocr` file is copied over and no request is sent.
New pages mean a new reading. Records of brochures that left the catalog are deleted.

## Budget (free tier: about 20 requests a day, retries included)

Constants at the top of `pipeline.py`:

| constant | value | meaning |
|---|---|---|
| `DAILY_REQUEST_LIMIT` | 15 | requests per quota day (America/Los_Angeles calendar day, when Google resets the quota: 10:00 or 11:00 in Turkey) |
| `RUN_REQUEST_LIMIT` | 5 | requests per run (three scheduled runs a day) |
| `MAX_FAILED_ATTEMPTS` | 3 | failed readings of the same pages before a brochure is given up |
| `SERVER_ERROR_RETRIES` | 1 | retries after HTTP 5xx; HTTP 429 stops OCR for the run |
| `MAX_PAGES_PER_REQUEST` | 10 | more pages are split into even requests; `page_index` is mapped back |
| `TIME_BUDGET` | 50 min | a brochure is started only if all its requests fit, even at their timeout |

Every request is counted (and saved to `ocr_state.json`) before it is sent. Order: brochures
valid today before upcoming ones, newest start first; expired brochures are never read.

## Running it locally

The key is read only from `GEMINI_API_KEY` (never from a file in this step). Keep the previous
output in its own folder: `scraper run` replaces `--out` and would drop the OCR state.

```bash
python -m scraper run --only sok --state-dir <previous> --out <new>
python -m scraper ocr --state-dir <previous> --out <new> --dry-run
GEMINI_API_KEY="$(cat secrets/gemini_api_key.txt)" python -m scraper ocr --state-dir <previous> --out <new> --max-requests 1
python -m scraper validate <new>/ocr_state.json --type ocr_state
```

`--dry-run` sends nothing, downloads nothing and writes nothing; it lists which brochures are
cached, which would be read and with how many requests.

## Adding a chain

1. Check that its prices really are only in the images (a written list is better: BİM and
   Migros are never on the list) and that its pages are images (`kind` `pages`, no webview).
2. Add the chain id to `OCR_CHAINS` in `pipeline.py` and its printed name to
   `gemini.BROCHURE_STORES` (the prompt says "pages of ONE Turkish supermarket (<name>) brochure").
3. Measure it first with `python -m scraper.ocr.evaluate` if it has any written list to score
   against; otherwise compare a few prices with the pages by hand.
4. Mind the budget: a chain with many or long brochures uses up the 15 daily requests.
