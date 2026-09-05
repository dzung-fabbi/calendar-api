# Phase 6 — remind_death_anniversary command (steps 8/9/10)

Date: 2026-09-05 | Agent: fullstack-developer

## Status

Full suite **450 tests, OK (4 skipped)**. Baseline 432 → +18 (17 new command
tests + 1 `truncated` test). `makemigrations giapha --check --dry-run` clean.

## Files

**Created**
- `giapha/management/commands/remind_death_anniversary.py` (196 L) — ORM + send half
- `giapha/services/gio_remind.py` (56 L) — pure half: `GioJob`, `message_body`, `due_rows`
- `giapha/tests/test_remind_command.py` (17 tests, FCM fully mocked)
- `docs/deployment-guide.md` (did not exist; created with the cron section)

**Modified**
- `giapha/views/gio_follow.py` — `truncated` surfaced (was discarded)
- `giapha/serializers/gio_follow.py` — `truncated` field (needed for the above; not in
  the stated scope list, but the key is dropped without it)
- `giapha/selectors/gio_follow.py` — appended `notified_pairs()` (dedupe read)
- `giapha/tests/test_gio_follow_api.py` — one test for `truncated`
- `giapha/selectors/__init__.py`, `giapha/services/__init__.py` — flat re-exports, house style

## Design notes

**Split, per the 200-line rule.** Command started at 255 L. Pure arithmetic
(`message_body`, `due_rows`, `GioJob`) → `services/gio_remind.py`; the dedupe
read → `selectors.gio_follow.notified_pairs` (a DB read belongs in `selectors/`
anyway, per Layering). Command now 196 L.

**Two halves.** `collect_due(today)` = all 5 queries/clan + pure resolution,
returns `GioJob`s with `recipients = {user_id: [token]}` already resolved.
`dispatch(jobs)` = the only network caller. Every recipient test asserts on
`collect_due`'s output through the command with `send_multicast` mocked; nothing
reaches the network.

**Query budget.** `deceased_with_lunar_death` → `due_rows` → `return []` before
`clan_edges` / `binding_map` / `overrides_for_clan` / `active_tokens_for`.
Pinned: 3 clans nothing due = 4 queries (1 clan list + 1 per clan).
`dispatch` makes 0 queries when `jobs` is empty.

**Dedupe.** One `notified_pairs()` read up front (skips before sending) AND
`IntegrityError` caught on create inside `transaction.atomic()` (savepoint —
without it the exception poisons the surrounding `TestCase` transaction).
Second run of the day: `send_multicast` call_count 0, log count stays 1.

**Missing credentials.** `send_multicast` returning `{}` is only reachable with a
non-empty token list (`if not tokens: continue` guards it), so `{}` ⇒ no
credentials, unambiguously. Run stops, `dispatch` returns `configured=False`,
command writes a WARNING and exits 0. No log rows written, tokens untouched.
An *exception* escaping `send_multicast` is converted to synthetic per-token
`send_error` results, so it can never be confused with the `{}` signal.

**Timezone.** `services.gio.today_vn()`. `timezone.localdate()` appears nowhere
in the new code. `settings.TIME_ZONE` untouched.

**Dead tokens.** `DEAD_TOKEN_RESULTS` → `DeviceToken.update(is_active=False)` in
the command; `ERROR_NETWORK` left active. `fcm.py` unmodified.

**Resilience.** `except Exception` per clan in `collect_due` (deliberate
divergence from code-standards → Errors, commented: nightly batch, one corrupt
clan must not cost the other 999 theirs) and per recipient in `dispatch`.

**Never logs a full token.** Command logs person/user ids only; `fcm._redact`
handles the token-side logging.

## Success criteria

| Criterion | Result |
|---|---|
| Sends only on target date (±1 day nothing) | ✅ |
| Twice in a day → once | ✅ |
| Missing credentials → exit 0 + warning, no traceback | ✅ |
| One failing token / recipient does not stop the run | ✅ (3 tests) |
| Unbound member receives nothing | ✅ |
| Collateral (uncle) receives nothing | ✅ |
| Override `enabled=False` on ancestor suppresses | ✅ |
| Override `enabled=True` on non-ancestor delivers | ✅ |
| Dead token deactivated, network error not | ✅ |
| 1 query/clan when nothing due | ✅ `assertNumQueries(1+3)` |
| Soft-deleted clan / person skipped | ✅ |
| No test touches the network | ✅ all runs via `run_on()` |
| 100 clans < 30s | ✅ measured **0.12s** (throwaway test, then deleted — not committed, timing asserts are flaky in CI) |
| Real device push | 🔒 blocked, Firebase JSON absent — not attempted |

## Notes / out of scope, flagged

- `docker-compose.yml` `web` service does **not** forward `FIREBASE_CREDENTIALS_PATH`
  / `_JSON` into the container. Real delivery will silently no-op until it does.
  Noted in `docs/deployment-guide.md`; compose file not in scope, not touched.
- `apis/` untouched. Plan step 11 (wiring `remind_appointment_date` into `fcm.py`)
  not done, per instruction.
- `apis/management/commands/remind_appointment_date.py` still uses
  `timezone.localdate()` — same one-day-off bug the plan's risk table calls out.
  Out of scope; owner should be told.
- Phase file `phase-06-fcm-push-va-nhac-gio.md` todo checkboxes NOT ticked —
  file was outside the stated scope. Lead may want to check off the last 3.

## Unresolved questions

1. `gio_remind_before_days = 0` yields "Còn 0 ngày nữa là giỗ …". Awkward but the
   plan fixes the body string verbatim, so no special-casing added. Want a
   "Hôm nay là ngày giỗ …" variant?
2. Failed sends are logged with `status='failed'`, which also blocks a same-day
   retry (documented in the model). Correct for MVP, but if a transient outage
   hits at 07:00 the reminder is simply lost for that day. Retry window wanted?
3. A clan over `MAX_CLAN_PERSONS` logs a WARNING and reminds only the first
   5.000 by id. No test pins it (would need 5.001 rows). Acceptable?
4. Cron example uses `docker compose run --rm web`. If deployment is not
   compose-based, the guide needs the real invocation.

**Status:** DONE
