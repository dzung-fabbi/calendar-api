---
name: giapha-lunar-verification-method
description: How to independently verify giapha/services/vn_lunar.py — differential vs Hồ Ngọc Đức's JS via node, not vs the project's own tests
metadata:
  type: reference
---

`giapha/services/vn_lunar.py` is a port of Hồ Ngọc Đức's `amlich`. The project's
own tz=7-vs-tz=8 tests are self-referential and cannot prove the port is right.

Authoritative reference source (fetchable, includes the full algorithm):
`gh api repos/trongthanh/amlich.app/contents/src/lib/amlich.js --jq .content | base64 -d`
(first ~235 lines are the algorithm; `INT()` is `Math.floor`).

Method that worked: run the JS under `node` over all 146,097 days of 1800–2199
plus ~38k lunar→solar vectors, dump to a file, diff against the Python. Result
as of 2026-09-05: **0 mismatches** in both directions. Python's only deliberate
divergence is raising `ValueError` where JS returns `[0,0,0]` or silently falls
back to the regular month for a bad `is_leap` flag.

**How to apply:** re-run this differential before accepting any edit to
`vn_lunar.py`. Do not accept "the tests pass" as evidence for this module.
