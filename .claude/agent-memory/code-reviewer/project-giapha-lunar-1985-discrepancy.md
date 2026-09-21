---
name: giapha-lunar-1985-discrepancy
description: plan.md and researcher-260905-1610 wrongly claim VN Tết 1985 = 20/02; the giapha/services/vn_lunar.py implementation (21/01) is correct — do not "fix" code to match those docs
metadata:
  type: project
---

`plans/260905-1053-gia-pha-dong-ho/plan.md:98` and
`plans/reports/researcher-260905-1610-vn-lunar-ho-ngoc-duc-algorithm.md:385`
both state Vietnamese Tết 1985 = 20/02/1985 and that 1985 is NOT a VN/CN
divergence year. Both are wrong. Verified externally: VN Tết Ất Sửu 1985 =
**21/01/1985**, China = 20/02/1985 (VN put the leap month in month 2 of 1985,
China in month 10 of 1984). Documented VN/CN Tết divergences since 1967:
1968, 1969, 1985, 2007 — exactly what `giapha/services/vn_lunar.py` produces
at tz=7 vs tz=8.

Root cause of the bad doc: the researcher's "computed from reference
implementation" vectors were produced at tz=8 (Chinese), not tz=7.

**Why:** an artifact that claims to be verified against a reference is the
kind of thing a future engineer trusts over the code, and "correcting" the
code to match it would silently shift every giỗ in 1985 by a month.

**How to apply:** if anyone proposes changing `vn_lunar` or its Tết vectors to
match the plan/researcher docs, refuse and point at the reference JS
differential instead. Related: [[giapha-lunar-verification-method]].
