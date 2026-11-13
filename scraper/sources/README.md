# Adding a chain

A source turns one chain's web pages into `Brochure` objects. The pipeline
(`scraper/core/pipeline.py`) does everything else: merging with the previous run,
`first_seen` / `updated_at`, archive and pruning, `stale` handling, validation and the
atomic write. A source never writes JSON itself.

1. **Record fixtures once.** Download each page the source needs a single time (one
   request per second, honest User-Agent: use `scraper.core.http.HttpClient`) and save it
   under `scraper/tests/fixtures/<chain>/`. Keep fixtures under 1 MB; build PDFs in the
   test with `conftest.make_pdf` instead of committing real ones.
2. **Write `scraper/sources/<chain>.py`.** Two layers:
   - pure parsers, e.g. `parse_cards(html: str) -> list[...]` and a builder that returns
     `Brochure`s (and `ProductFile`s). Raise `SourceError("... page layout may have
     changed")` when the expected markup is missing; never return an empty list silently.
     Reuse `parse_date_label`, `brochure_id`, `parse_price_minor`, `products_path`.
   - a class with `chain_id = "<chain>"` and `collect(ctx: SourceContext) -> SourceResult`
     that only downloads (`fetch(ctx.http, url)`) and calls the parsers.
   - Images hosted by the chain: put their https URLs in `pages`. PDFs: render with
     `render_pdf_pages` and store via `ctx.media.write_pages`; derive the brochure id from
     the PDF address and call `ctx.media.reuse(old)` for ids found in `ctx.previous`, so an
     unchanged PDF is not downloaded again.
3. **Test it** in `scraper/tests/test_<chain>.py` without network: parser results checked
   against concrete values from the fixture, unrelated HTML raising `SourceError`, and
   `collect` with `conftest.mock_http`.
4. **Register it:** add a `ChainInfo` (kind `SCRAPED`) to `scraper/chains.py` and the
   source instance to `SOURCES` in `scraper/sources/__init__.py`.
5. **Try it live once:** `python -m scraper run --only <chain> --dry-run`.
