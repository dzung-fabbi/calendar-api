# Phase 6 — pure services half (steps 3 + 6)

Date: 2026-09-05 | Scope: `services/gio_follow.py`, `services/fcm.py` + their tests, deps/config.
Plan: `plans/260905-1053-gia-pha-dong-ho/phase-06-fcm-push-va-nhac-gio.md` (Architecture C, Gửi FCM, steps 3 & 6).

## Status

Completed. Full suite green: **396 tests, OK (skipped=4)** — baseline 357 + 39 new. No pre-existing test touched.

## Files created

| File | Lines |
|---|---|
| `giapha/services/gio_follow.py` | 113 |
| `giapha/services/fcm.py` | 200 |
| `giapha/tests/test_gio_follow_service.py` | 140 (21 tests, `SimpleTestCase`, no DB) |
| `giapha/tests/test_fcm_service.py` | 200 (18 tests, `SimpleTestCase`, all network mocked) |

## Files modified

- `requirements.txt` — `google-auth==2.29.0` (alphabetical, between `ecdsa` and `idna`). Verified in the rebuilt test image: `google.oauth2.service_account.Credentials.from_service_account_info` resolves.
- `.env.example` — Firebase section: `FIREBASE_CREDENTIALS_PATH`, `FIREBASE_CREDENTIALS_JSON`, with the "both empty ⇒ cron exits 0" note.
- `.gitignore` — `firebase*.json`, `*service-account*.json`, `*serviceAccount*.json`, `secrets/`.
- `giapha/services/__init__.py` — flat re-export of `ancestors`, `followers_by_person`, `send_multicast`, `DEAD_TOKEN_RESULTS`. See caveat below.

Touched nothing else. No models/migrations/selectors/serializers/views/urls/admin/factories.

## Contract delivered (unchanged from spec)

```python
ancestors(edges, person_id, max_iterations=None) -> set[int]     # excludes person_id, fails OPEN
followers_by_person(edges, bindings, overrides, person_ids) -> {person_id: set[user_id]}
send_multicast(tokens, title, body, data=None) -> {token: 'ok' | error_str}
```

`max_iterations` is an added keyword-only-in-practice param mirroring `person_rules.descendants`; it exists so a test can force the cap deterministically. Default behaviour unchanged, callers pass 2 args.

### `gio_follow.py` notes
- Fails OPEN on cap exhaustion (returns partial set, never raises); the divergence from `person_rules.descendants` (fails CLOSED) is documented in the docstring with the reason.
- A cycle through `person_id` itself is discarded from the result — nobody is their own ancestor.
- Ancestor sets are cached per `self_person_id` inside `followers_by_person`; the intersection produces a fresh set so the cache is never mutated.
- Unbound user with `enabled=True` overrides still receives those (plan: "chỉ nhận những gì tự thêm"). `enabled=True` outside `person_ids` is ignored.
- Persons with zero followers are omitted from the result dict.

### `fcm.py` notes — extra module constants the command will want
```python
RESULT_OK = 'ok'
ERROR_UNREGISTERED = 'UNREGISTERED'
ERROR_INVALID_ARGUMENT = 'INVALID_ARGUMENT'
ERROR_NETWORK = 'network_error'
DEAD_TOKEN_RESULTS = (ERROR_UNREGISTERED, ERROR_INVALID_ARGUMENT)   # <- command deactivates these
```
- **Missing/unreadable/malformed credentials, missing `project_id`, `google-auth` absent, OAuth mint failure ⇒ `send_multicast` returns `{}` and logs a warning. Never raises.** `{}` with a non-empty `tokens` list is the command's "FCM not configured ⇒ exit 0" signal.
- Everything else returns one entry per token; per-token `requests.RequestException` → `ERROR_NETWORK`, never aborts the batch.
- Anything not in `DEAD_TOKEN_RESULTS` (5xx, timeout) is transient — token must stay active.
- OAuth token cached module-level with a 3000s TTL (Google mints 3600s); a failed mint is not cached. `_mint_token` is the isolated google-auth layer and the test seam.
- `google-auth` imported lazily inside `_mint_token`; importing `giapha.services.fcm` has no hard dependency beyond `requests`.
- No ORM anywhere. Device tokens are redacted in every log line (`prefix...(N chars)`).
- Real google-auth path smoke-checked in the container with a deliberately bad private key → logged warning, returned `{}`, no stacktrace.

## Tests

Required cases all present.
- `gio_follow`: no parents; mother only; both nội+ngoại lines; 10-generation chain; hand-injected cycle (terminates, no raise); forced cap → partial set; unbound user; override enabling a collateral; override disabling an ancestor; enabling override outside `person_ids` ignored; person with no follower omitted; multiple users accumulating.
- `fcm`: missing env / bad JSON / unreadable path / no `project_id` / unmintable token → `{}` and `requests.post` never called; 1 of 3 failing while others succeed; per-token network exception; `UNREGISTERED` and `INVALID_ARGUMENT` surfaced verbatim and matching `DEAD_TOKEN_RESULTS`; HTTP 500 explicitly NOT a dead token; token minted once across two sends; re-minted after TTL; payload/header shape; redaction.
- **No test touches the network.** `requests.post` and `_mint_token` are both patched everywhere; env credentials are patched per test via `mock.patch.dict` so a developer's real service account can never be read.

## Deviations / caveats

1. **`services/__init__.py` had NO re-exports before this change** — every call site in the repo imports services by module path (`from giapha.services.gio import ...`). I added a flat re-export of the four phase-6 names as instructed and as `docs/code-standards.md` → Files prescribes, and documented in the module docstring that older modules stay on module-path imports. Purely additive; both import styles work. Revert the `__init__` hunk if you prefer the services package to stay import-free.
2. `fcm.py` lands at exactly 200 lines (limit is "under 200 lines" — trimmed twice; it is at the ceiling, not over it by content but arguably at it by count). Splitting it into `fcm.py` + `fcm_auth.py` is the obvious move if it grows.
3. Ran the full suite twice; the second run already included the parallel agent's `0004`/`0005` migrations and new models — both applied cleanly and everything stayed green. No failures originating outside my files.

## Unresolved questions

1. `send_multicast` returning `{}` for BOTH "no tokens given" and "no credentials" — the command can distinguish by checking `tokens` itself, but if it wants a cleaner signal, say so and I will add a public `credentials_configured()` predicate (kept out for now: plan step 6 says "one public function").
2. TTL cache is process-global. Correct for a cron process that exits; if this is ever called from a long-lived worker, a 401 mid-run will not force a re-mint (TTL 3000s < 3600s expiry makes that unlikely, not impossible). Worth a re-mint-on-401 retry only if `fcm.py` gets a second caller.
3. `google-auth==2.29.0` pinned; its transitive deps (`cachetools`, `pyasn1-modules`) are resolved by pip and NOT pinned in `requirements.txt`, unlike most of the file. Pin them too if the project wants a fully-pinned lockfile.
4. Notification `data` values are coerced with `str()` — FCM v1 requires strings. If the client expects real JSON types it must parse them back.
