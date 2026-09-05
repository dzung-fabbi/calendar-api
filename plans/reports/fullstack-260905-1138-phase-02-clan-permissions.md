# Phase 2 report: Clan/ClanMember/Invite API + permission layer

Plan: `plans/260905-1053-gia-pha-dong-ho/phase-02-clan-membership-va-phan-quyen.md`

## Status: DONE. Full suite green (84 tests: 50 apis + 34 giapha), 0 regressions.

## Files created
- `giapha/exceptions.py` (14 loc) -- `BadRequestException`, mirrors `apis/exceptions.py`.
- `giapha/services/invite_code.py` (30 loc) -- `generate_code`, `is_expired`, `is_exhausted`. Pure, no ORM.
- `giapha/selectors/clan.py` (76 loc) -- `get_clan_or_none`, `clans_for_user`, `clan_role_for`, `roles_for_clans`, `members_of`, `member_by_user_id`, `owner_count`, `get_invite_for_update`. All filter `is_deleted=False`.
- `giapha/permissions.py` (73 loc) -- `IsClanMember`/`IsClanEditor`/`IsClanOwner`, shared `_role_for()` caches on `request._giapha_role_cache`.
- `giapha/serializers/clan.py` (98 loc) -- `ClanSerializer` (strips `public_slug` for non-owners via `to_representation`), `ClanMemberSerializer`, `ClanMemberRoleUpdateSerializer`, `ClanInviteSerializer`/`ClanInviteCreateSerializer`, `JoinClanSerializer`.
- `giapha/views/clan.py` (77 loc) -- list/create + detail/patch/soft-delete.
- `giapha/views/clan_membership.py` (134 loc) -- members list, member role/removal, invite create, join. Split out from `clan.py` to stay under the 200-loc cap (spec named one `views/clan.py`; splitting by concern is the repo's documented rule when a single-file plan would exceed the cap).
- `giapha/tests/factories.py` (38 loc) -- `build_clan_fixture(ten_ho=, suffix=)` returns clan + owner/editor/viewer/outsider users, viewer/editor/owner already `ClanMember`s. `suffix` lets one test build 2+ fixtures without username collisions.
- `giapha/tests/test_permissions.py` (153 loc) -- full matrix, outsider-404-not-403, public_slug visibility, role-cache query-count test.
- `giapha/tests/test_invites_and_join.py` (114 loc) -- expiry/exhaustion rejection, join idempotency, last-owner guard.
- `giapha/tests/test_services.py` (65 loc) -- `SimpleTestCase`, no DB, for `invite_code.py`.

## Files modified
- `giapha/models/clan.py` -- added `is_deleted = BooleanField(default=False)`.
- `giapha/migrations/0002_clan_is_deleted.py` -- generated via `manage.py makemigrations giapha --name clan_is_deleted` in the test container; applied clean, `makemigrations --check --dry-run` reports no drift.
- `giapha/urls.py` -- 6 routes: `clans` (GET/POST), `clans/<id>` (GET/PATCH/DELETE), `clans/<id>/members` (GET), `clans/<id>/members/<user_id>` (PATCH/DELETE), `clans/<id>/invites` (POST), `join` (POST).
- `giapha/views/__init__.py`, `giapha/selectors/__init__.py`, `giapha/serializers/__init__.py`, `giapha/services/__init__.py` -- flat re-exports (services kept docstring-only per `apis/services/__init__.py` precedent, no re-export since callers import submodule directly).

## Key design decisions
1. **404 vs 403**: `clan_role_for` returns `None` for both "never joined" and "clan soft-deleted" -- `permissions.py`'s `_role_for()` raises `NotFound` on `None`, called by all three permission classes before any role-sufficiency check. Insufficient-role members hit `return False` (403) instead.
2. **Role cache**: dict on `request._giapha_role_cache` keyed by `clan_id`; first permission class populates it, subsequent classes/serializer reads reuse it. Verified with `assertNumQueries(1)` across 3 stacked permission checks on the same request/clan_id.
3. **public_slug**: `ClanSerializer.to_representation` pops the key (not just nulls it) for non-owners, so viewers/editors never see the field exists. List endpoint (`GET /clans`) passes a `{clan_id: role}` dict via serializer context (`roles_for_clans`, 1 query) instead of doing a per-row role lookup, avoiding N+1 on the "my clans" list.
4. **Join concurrency**: `select_for_update()` on the invite row inside `transaction.atomic()`; membership-existence check happens first (idempotent 200, no new row) *before* the expiry/exhaustion check, so a member who already joined can still "rejoin" via a code that's since expired/maxed-out -- only genuinely new redemptions are checked against those limits.
5. **Last-owner guard**: lives in the member PATCH/DELETE view only, not clan-level DELETE. Rationale: soft-deleting the whole clan is a deliberate act by its (any) owner and doesn't strand a *surviving* clan without an owner -- the whole clan is gone. Guard triggers on `member.role == 'owner' and (new_role != 'owner' or being removed) and owner_count(clan_id) <= 1`.
6. **Soft-delete semantics**: `clan_role_for` filters `clan__is_deleted=False`, so a deleted clan 404s for *everyone*, owner included -- treated as fully gone, not "read-only archived." Not explicitly specified in the phase file; flagged as an assumption below.
7. **Invite code collision**: retry loop (`MAX_CODE_ATTEMPTS=5`) wraps each `ClanInvite.objects.create()` in its own `transaction.atomic()` and catches `IntegrityError` -- correct under MySQL where a failed statement poisons the enclosing transaction if not isolated per-attempt.

## Tests
- Type/model check: `manage.py check` -- clean.
- Migration drift: `makemigrations giapha --check --dry-run` -- clean.
- `./scripts/run-tests.sh giapha -v 2` -- 34/34 pass.
- `./scripts/run-tests.sh` (full) -- 84/84 pass (50 apis unchanged + 34 giapha new).
- Acceptance criteria: every matrix cell tested; outsider 404 (not 403) asserted explicitly for 7 endpoint/method combos in one test; expired + over-max-uses invites both asserted 400; double-join asserted single `ClanMember` row + `used_count==1`; last-owner PATCH/DELETE asserted 400 (and the non-last-owner case asserted 200, to prove the guard isn't just always-on); role-cache query count asserted `assertNumQueries(1)` for 3 stacked permission checks; `invite_code.py` tests use `SimpleTestCase`; `grep -rn "from apis\|import apis" giapha/` empty; all files <200 loc.

## Unresolved questions
1. Soft-deleted clan is fully inaccessible (404) to its former owner too, not just to outsiders/other roles -- confirm this matches product intent, or whether an owner should retain read/restore access to their own soft-deleted clan (would need a distinct permission path, out of scope for phase 2 as specced).
2. `ClanInviteSerializer` exposes `used_count`/`created_at` beyond the spec's literal `{code, expires_at}` -- kept since owner-only endpoint, no leak risk, but flagging in case a stricter contract was intended.
3. Phase file didn't specify whether removing/demoting a *non-owner* last-editor-or-such needs any guard -- none implemented, matches spec (guard is owner-specific only).

**Status:** DONE
**Summary:** Clan/ClanMember/ClanInvite CRUD + join implemented with a request-cached, non-leaking (404-vs-403) permission layer; full suite (84 tests) green, no regressions, migration clean.
**Concerns/Blockers:** none blocking; see unresolved questions above (mainly the soft-delete-owner-access assumption).
