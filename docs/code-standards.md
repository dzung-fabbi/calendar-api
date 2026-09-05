# Code Standards

Both `apis/` and `giapha/` follow these standards. Code is **never** shared between apps.

## Layering

`views -> serializers / selectors / services -> models`. Never the reverse.

- **services/** is pure: no ORM, no `request`. If a function needs the database
  it belongs in `selectors/`. This is what keeps `test_services.py` on
  `SimpleTestCase`.
- **selectors/** owns every `Prefetch` and every bulk fetch. A view should not
  build `Prefetch` objects inline.
- **views/** validate parameters first, via `views/params.py`, then delegate.
- **Decoupling:** `giapha/` and `apis/` imports are forbidden. Duplicate code is
  preferable to cross-app dependency.

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

## Migrations

- Restructuring code must not produce a migration. The gate is:
  `python manage.py makemigrations apis --check --dry-run`.
- A deliberate model change gets its own named migration.

## Serializers

- Never `fields = '__all__'` on a model holding credentials or permission flags.
  Whitelist explicitly.
- Anything scoped to a user filters on `request.user`, never on a client-supplied id.

## Tests

- Value goldens are recorded from known-good code and only re-recorded alongside
  the deliberate change that alters them, so the diff documents the change.
