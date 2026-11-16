OCR measurement fixtures.

- `gemini_response.json`, `gemini_brochure_response.json`: hand-made Gemini answers (BİM).
- `gemini_bim_real.json`: a trimmed real answer for one BİM poster (2026-11-15).
- `tkkoop_firsat-dolu-haftasonu.html`: https://www.tkkoop.com.tr/haftalik-kampanyalar/firsat-dolu-haftasonu
  as fetched once on 2026-11-16 (campaign valid 14-16 Kasım). Only the `<title>` and the two
  `.ss_urun_area` blocks (all 15 product cards) are kept; menus, scripts and footer are dropped.
  The matching home page is `../tkkoop/anasayfa.html` (2026-11-14; same campaign and PDF link).
- `gemini_tkkoop_brochure_response.json`: hand-made answer for that campaign's one PDF page,
  written from the page as printed (16 products). It is not a recorded Gemini answer. The page
  prints the eggs at 105,00 while the card says 108,00; the tests keep that disagreement on purpose.
