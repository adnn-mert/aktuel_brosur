Recorded once on 2026-11-14 (issue 910 / 5M issue 286, valid 5 - 18 Kasım 2026).

- `migroskop.html`: full viewer page, unchanged (124 pages, 263 product cards).
- `5m-migroskop.html`: trimmed to stay small. The live page has 141 `div.page` elements;
  the first 40 and the last one are kept, the 100 in between were cut out whole. Its
  product cards repeat the Migroskop ones, so nothing new was lost.
- `migroskop-dijital.html`, `5m-migroskop-dijital.html`: the past-issue list had 37
  `data-pageindex` blocks of six links; the first and the last block are kept. The
  current-issue block at the top is unchanged.
