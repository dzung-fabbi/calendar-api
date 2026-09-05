# Code Standards

Both `apis/` and `giapha/` follow these standards. Code is **never** shared between apps.

## Layering

`views -> serializers / selectors / services -> models`. Never the reverse.

- **services/** is pure: no ORM, no `request`. If a function needs the database
  it belongs in `selectors/`. This is what keeps `test_services.py` on
  `SimpleTestCase`.
  **The rule is "no ORM", not "no I/O".** `giapha/services/fcm.py` speaks HTTP and
  still belongs in `services/`; what it may not do is write a model. It *reports*
  that a device token is dead, and the caller flips `is_active`. An ORM write that
  only a batch job needs goes next to that job — hence
  `management/commands/_gio_reminder_log.py`, leading underscore so Django's
  command discovery ignores it.
- **selectors/** owns every `Prefetch` and every bulk fetch. A view should not
  build `Prefetch` objects inline.
- **views/** validate parameters first, via `views/params.py`, then delegate.
- **Decoupling:** `giapha/` and `apis/` imports are forbidden. Duplicate code is
  preferable to cross-app dependency. Example: `giapha/services/can_chi.py` is a
  10-line copy of `apis/services/can_chi.py`, not an import. This boundary allows
  each app to evolve independently (especially critical for the lunar calendars — see
  `docs/system-architecture.md` → "Dual Lunar Calendar Implementation").

## Files

- Under 200 lines. Split by concern, not by arbitrary line count.
- `snake_case` module names (Python cannot import `kebab-case`), descriptive
  enough to be found by grep.
- Packages re-export a flat namespace from `__init__.py` so call sites stay short.

## Queries

- Any serializer that reads `obj.<relation>` must be given a matching
  `Prefetch` by its caller, with `select_related` for the far side.
  `star_payload()` reads `row.sao`; handing it an unprefetched queryset is an N+1.
- Adding an endpoint means adding it to `test_query_counts.py`. The ceiling is
  the contract.

## Errors

- No blanket `except Exception`. Validate inputs up front and raise
  `InvalidParam`, which produces a 400 naming the parameter. Let genuine faults
  reach the logger as 500s.
- **Exception, batch jobs only:** a per-item loop in a management command *does*
  catch broadly, around each item, with `logger.exception`. One clan holding a
  corrupt row must cost that clan its reminders, not the other 999 theirs — and
  there is no user watching to retry. `remind_death_anniversary.collect_due` and
  `.dispatch` are the two instances; both name the rule they are breaking and why.
  This licence does not extend to request paths.
- **Catching `IntegrityError` requires a savepoint.** A failed statement poisons
  its transaction, so `except IntegrityError` without an enclosing
  `with transaction.atomic():` leaves the connection unusable and turns the
  intended 400 into a 500 under `ATOMIC_REQUESTS` (or inside a `TestCase`). See
  `views/device.py`, `views/member_binding.py`, `_gio_reminder_log.log_attempt`.
- **Distinguish configuration faults from transient ones.** "Not configured" and
  "the network was down for a second" must not share a return value: the first
  should stop cleanly, the second must be retried and must not abandon the rest
  of a batch. `services/fcm_auth.py` uses `None` for the first and
  `FcmTransientError` for the second.

## Migrations

- Restructuring code must not produce a migration. The gate is:
  `python manage.py makemigrations apis --check --dry-run`.
- A deliberate model change gets its own named migration.

## Serializers

- Never `fields = '__all__'` on a model holding credentials or permission flags.
  Whitelist explicitly.
- Anything scoped to a user filters on `request.user`, never on a client-supplied id.
- **A credential is write-only.** An FCM device token is accepted in a request body,
  never echoed in a response, and never written whole into a log line — log a short
  prefix plus a length (`services/fcm._redact`).

## Tests

- Value goldens are recorded from known-good code and only re-recorded alongside
  the deliberate change that alters them, so the diff documents the change.
