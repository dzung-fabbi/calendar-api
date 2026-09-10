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
  **The one recorded exception (2026-09-10): the push channel.** `DeviceToken`,
  `POST /devices` and `services/fcm.py` are user-level infrastructure that happens to
  live in `giapha/`, and a device registers its token exactly once — a copy of the model
  would make clients register twice. So `apis/` may import, and only import,
  `giapha.models.DeviceToken`, `giapha.selectors.gio_follow.active_tokens_for` and
  `giapha.services.fcm`. The import sites are `apis/selectors/appointment_remind.py`
  and `apis/management/commands/{remind_appointment_date,_appointment_reminder_log}.py`;
  nothing else crosses (tests of those modules may import giapha fixtures such as
  `DeviceToken`), and `giapha/` still never imports `apis/`.

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

## Data tables and honest answers

Introduced by the xưng hô calculator (phase 7); applies to any lookup that maps facts
to a user-visible claim.

- **A vocabulary/config table is its own module with no logic in it.**
  `services/kinship_terms.py` and `services/kinship_affinal_terms.py` hold data only;
  `services/kinship_lookup.py` holds the rules that read them. Reviewing a word is then
  reading one dict, not tracing a branch.
- **`None` in a table key means "this fact does not change the answer", never "the fact is
  missing".** A row whose answer depends on a fact is stored only under that fact's real
  values, so the answer is *unreachable* without the data and the lookup falls through to
  an explicit hedge. Enforcing it structurally beats a policy comment: no reviewer has to
  notice a guess that the table cannot express.
- **When the data genuinely does not decide, hedge — do not let an id decide.** An
  autoincrement id is data-entry order, not a fact about the world; it is a tie-break for
  stable output only. See `kinship_marriage_rows.ranked_spouses_of`, whose `rank` excludes
  the id precisely so the caller can tell when nothing real separated two candidates.
- **A hedge names only the options the known facts leave open**, or it contradicts the
  confident field printed next to it.

## Migrations

- Restructuring code must not produce a migration. The gate is:
  `python manage.py makemigrations apis --check --dry-run`.
- A deliberate model change gets its own named migration.

## Serializers

- Never `fields = '__all__'` on a model holding credentials or permission flags.
  Whitelist explicitly.
- Anything scoped to a user filters on `request.user`, never on a client-supplied id.
- **A field a client branches on is a machine-readable ASCII slug; human text goes in a
  separate field.** `reason` on the xưng hô response is a slug
  (`thieu_birth_order`), never Vietnamese prose — diacritic strings compared verbatim by a
  mobile client are not a wire format anyone would choose. The user-facing wording is
  mapped once (`kinship_terms.REASON_LABELS`) and reaches the reader through `explain`.
- **"No answer" is not an error.** Where the honest result is "there is no word for this",
  the endpoint answers **200** with a null value plus the reason, not a 4xx. A 4xx would
  make a client treat a correct finding as a failure.
- **A credential is write-only.** An FCM device token is accepted in a request body,
  never echoed in a response, and never written whole into a log line — log a short
  prefix plus a length (`services/fcm._redact`).

## Tests

- Value goldens are recorded from known-good code and only re-recorded alongside
  the deliberate change that alters them, so the diff documents the change.
