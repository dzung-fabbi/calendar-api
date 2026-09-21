---
name: project-throttles-are-xff-bypassable
description: XFF throttle bypass was FIXED (NUM_PROXIES now env-driven, default 0); per-IP throttles still only raise single-source cost
metadata:
  type: project
---

History: until ~2026-09, every anonymous `ScopedRateThrottle` (`giapha-join`, `giapha-public`)
was bypassable with a rotating `X-Forwarded-For` header because `NUM_PROXIES` was unset
(verified 2026-09-05: 70 requests, 0x 429).

**Current state (checked 2026-09-19):** `djangopj/settings.py` sets
`'NUM_PROXIES': int(os.environ.get('DJANGO_NUM_PROXIES', '0'))`, so XFF is ignored by default.
Authenticated throttles (`giapha-invite-create`, `giapha-family-import`) bucket per user anyway.

**How to apply:** do not re-report the XFF bypass. Only flag it again if a deploy sets
`DJANGO_NUM_PROXIES` higher than the real proxy count, or if a throttle is cited as the
*only* defence (per-IP still just raises single-source cost). Related:
[[feedback-verify-claims-with-throwaway-probes]].
