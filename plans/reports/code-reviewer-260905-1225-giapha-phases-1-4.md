# Code Review — `giapha/` phases 1–4

Date: 2026-09-05 · Reviewer: code-reviewer · Branch: master
Scope: all of `giapha/` (25 modules, ~4.2k LOC incl. tests) + `djangopj/settings.py`, `djangopj/urls.py`. `apis/` excluded.

## Method

Read every module. Then ran an adversarial probe suite (31 temporary tests, two rounds) inside Docker against real MySQL to *prove* rather than infer each finding. Probe file deleted after the run; `git status` clean apart from the untracked `giapha/`. `makemigrations giapha --check --dry-run` → **No changes detected** (no drift).

Every "measured" number below is from an actual run, not an estimate.

## Overall Assessment

Genuinely well-built module. The hard architectural constraints hold:

- `services/` is **100% pure** — `grep '^import\|^from' giapha/services/*.py` returns only `secrets`, `collections.deque`, `datetime`, `decimal`, `json`. No Django, no ORM. This is the constraint most likely to erode and it did not.
- **Cross-clan object access: I could not break it.** Every probe I built (cross-clan `father_id`, cross-clan marriage partner on POST, cross-clan husband swap on PATCH, foreign `person_id` under own `clan_id`) returned 400/404. All object lookups go through `(clan_id, object_id)`-scoped selectors. No endpoint trusts a bare client id.
- **404-vs-403 discipline is correct** at every clan-scoped endpoint, incl. `/tree` and `/marriages`. `clan_role_for` collapses "not a member" and "clan soft-deleted" into `None` → `NotFound`. Anonymous gets 401.
- No `except Exception`, no `fields = '__all__'`, no file over 200 lines outside tests.

The defects are concentrated in three places: **invite lifecycle (security)**, **the write path's denormalised `generation`**, and **unhandled DB-layer errors reaching the client as 500**. Plus one query-budget test that is a false negative and let an N+1 through.

---

## Critical

### C1. Invite codes are permanent, unlimited-use, unrevocable bearer credentials — and can grant `owner`
`giapha/serializers/clan.py:75-86` · `giapha/views/clan_membership.py:80-104` · `giapha/urls.py:28`

Four things compound:

1. `max_uses = IntegerField(default=0)` and `is_exhausted()` treats `0` as **unlimited** (`services/invite_code.py:25-30`).
2. `expires_at = DateTimeField(default=None)` and `is_expired()` treats `None` as **never expires**.
3. `role = ChoiceField(choices=CLAN_ROLE)` — `CLAN_ROLE` includes `'owner'` (`models/choices.py:19-23`). Nothing caps the grantable role.
4. **There is no invite list, revoke or delete endpoint.** `urls.py:28` exposes `POST` only. Once a code leaks there is no API path to kill it.

Measured: an owner posted `{"role": "owner"}` → 201 with `max_uses: 0, expires_at: null`. Two unrelated outsiders each redeemed the same code and each became `owner`. Both now have full control including the ability to remove the original owner.

Failure scenario: owner pastes an invite link into the family Zalo/Facebook group. Group has 60 members, is later archived/leaked/screenshotted. Every reader can join the clan forever. If the invite was `role=owner` (or an editor mis-clicks the role dropdown), every reader can delete the clan and remove the real owner. The owner's only remediation is Django admin.

Aggravating: codes are 8 chars over a 32-symbol alphabet = 40 bits, and `REST_FRAMEWORK` (`settings.py:155-160`) sets **no `DEFAULT_THROTTLE_CLASSES`**, so `POST /join` accepts unbounded guesses. Worse, the response distinguishes cases — unknown code → **404** `Mã mời không hợp lệ`, valid-but-expired/exhausted → **400** `Mã mời đã hết hạn` (`views/clan_membership.py:121,127`). That is an enumeration oracle: an attacker brute-forcing can tell a real code from a miss.

Fix:
- Add `DELETE /clans/{clan_id}/invites/{code}` + `GET` list (owner only). Revocation is the missing primitive.
- Change defaults to bounded: `max_uses` default `1` (or `10`), `expires_at` default `now + 7 days`. Treat `0`/`None` as "not allowed" rather than "unlimited", or gate unlimited behind an explicit `unlimited=true`.
- Restrict grantable roles to `('editor', 'viewer')`; ownership transfer should be its own owner-only endpoint with an explicit confirmation, not an invite code.
- Collapse the two rejection responses into one identical 404 so the oracle disappears.
- Add `ScopedRateThrottle` on `JoinClanAPIView` (e.g. 10/hour/user).

---

## High

### H1. `generation` is never computed on create — the phase-4 feature is inert for API-entered data
`giapha/views/person_list.py:131` · `giapha/serializers/person.py:10-18`

`_create_all` does `Person.objects.create(clan_id=clan_id, **item)` and nothing else. `recompute_descendant_generations` is only wired into `PersonDetailAPIView.patch` behind `parent_changed` (`views/person.py:98-104`).

Measured: `POST /persons {"ho_ten":"Con","father_id":<root>}` → 201, `generation: null`. Bulk create of 20 children of a known root → all 20 `generation: null`.

So the entire `GET /tree` payload returns `generation: null` for every person the API created, until somebody manually runs `manage.py recompute_generations`. Phase-04's success criterion ("`generation` chính xác kể cả cây nhiều gốc", spec line 101) is not met on the primary data-entry path. Existing tests hide this because every fixture passes `generation=` explicitly (`test_tree_api.py:250-256`) or asserts only after `call_command`.

Compounding: `'generation'` is in `_WRITE_FIELDS`, so it is **client-writable**. Measured: `POST {"ho_ten":"Fake","generation":999}` → 201 with `generation: 999`. A computed column accepting arbitrary client input will silently desync from the graph and there is no reconciliation on read.

Fix: after the bulk-insert loop inside the same `transaction.atomic()`, call `compute_generations(edges)` once over the updated edge list and `bulk_update` the created rows (they are all leaves of the batch, so one pass suffices — no per-record cost). Remove `'generation'` from `_WRITE_FIELDS`.

### H2. N+1 in bulk create — and the query-budget test that should catch it is a false negative
`giapha/views/person_list.py:109` · `giapha/serializers/person.py:61-65` · `giapha/tests/test_person_api.py:245-271`

`_create_all` returns freshly-constructed `Person` instances. Their `father`/`mother` relation caches are empty. `PersonReadSerializer.get_father_name` then does `obj.father.ho_ten` → one SELECT per row per non-null parent.

Measured: bulk create of **20 rows with `father_id` set = 66 queries** (vs 46 without). Extrapolated to the documented `MAX_BULK_CREATE = 200` with both parents set: ~4 + 400 writes + 400 parent SELECTs ≈ **800 queries in one request**. A real gia phả import is exactly this shape — every row has a father.

The guard test `test_batch_read_overhead_does_not_scale_with_batch_size` asserts `delta == 2 * delta_rows` and passes — because its fixture rows have **no `father_id`**, so `get_father_name` short-circuits on `if obj.father_id` before touching the relation. The test measures the one case where the bug cannot fire. Same blind spot in `test_bulk_create_of_200_succeeds_in_one_request:232`.

Fix: re-fetch the created rows through the existing selector before serializing — `Person.objects.filter(id__in=[p.id for p in created]).select_related('father','mother')` — or build a `{id: ho_ten}` map from the already-loaded batch. Then change the test fixture to set `father_id` on every row; that single change turns the test into a real contract.

### H3. `POST /restore` bypasses every validation rule, including the cycle rule
`giapha/views/person_revision.py:59-62` · `giapha/services/revision.py:40-49`

`restore()` blind-`setattr`s every key from the snapshot then `person.save()`. No `validate_person_write`, no `validate_no_cycle`, no same-clan check.

Measured, end to end:
1. `A` is father of `B`.
2. PATCH `B` (any field) → revision snapshot recorded with `B.father_id = A`.
3. PATCH `B` `father_id: null`; PATCH `A` `father_id: B` → 200 (legal at this point).
4. `POST /persons/B/restore/<rev>` → **200**. Result: `A.father_id = B` **and** `B.father_id = A`. `CYCLE=True`.

The rule `services/person_rules.py` calls "the most important here" is fully bypassable through a normal editor-role API sequence — no admin access needed. This is the single most likely source of production tree corruption.

Downstream (I checked): the traversals survive — `GET /tree` returned 200, and `compute_generations` on the cyclic graph returned `{A: 1, B: 1}` (Kahn never resolves them, the `setdefault(…, 1)` fallback at `services/tree.py:81-82` catches them). So no hang, but both persons silently collapse to generation 1 and the graph is permanently wrong until someone finds it by eye.

Two smaller restore problems in the same code path:
- `_EXCLUDED_FIELDS` is only `{id, created_at, updated_at}`, so `is_deleted` **and** `clan_id` are restored. Measured: delete a person, then restore its pre-delete revision → `is_deleted=False`. `POST /restore` is therefore an undocumented undelete with no `children_count`-style guard and no explicit intent.
- Restore can reinstate a `father_id` pointing at a person who has since been soft-deleted (see H4), producing a dangling parent link.

Fix: run `validate_person_write` on the restored payload before `save()`, using the same `edges`/`ids_in_clan`/`birth_map` the PATCH path builds, and raise `BadRequestException` on failure. Add `is_deleted` and `clan_id` to `_EXCLUDED_FIELDS` (or restore them only via an explicit `?undelete=true`).

### H4. Soft-delete leaves dangling parent pointers — `children_count` ignores already-deleted children
`giapha/selectors/person.py:88-95` · `giapha/views/person.py:113-117`

`children_count` filters `is_deleted=False`, so a parent whose only children are soft-deleted is considered childless and the delete is allowed.

Measured: parent `P` with one child `C`; soft-delete `C`; `DELETE /persons/P` → **204**, and `C.father_id` still equals `P.id` (`dangling=True`).

Failure scenario: editor tidies a branch by deleting a child, then deletes the parent. Later someone restores `C` (H3 makes this a 200). `C` now points at a soft-deleted father. `clan_edges` excludes the father, so `parent_edges_from_rows` silently drops the edge and `compute_generations` treats `C` as a root → `generation = 1`. A grandchild line detaches from the trunk with no error anywhere. This is precisely the "silently fractures the tree" case.

Fix: either null out `father_id`/`mother_id` on descendants at soft-delete time (inside the existing `transaction.atomic()`), or make `children_count` count *all* children regardless of `is_deleted` so the delete is blocked while any pointer exists.

### H5. Two uncaught DB/stdlib errors reach the client as 500
`giapha/selectors/person.py:80` and `giapha/views/marriage.py:60-63`

**(a) `?death_year=` overflow.** `queryset.filter(death_solar__year=death_year)` — `_int_query_param` validates only that the value parses as `int`. Django's `YearLookup` builds `datetime.date(year, 1, 1)`.
Measured: `GET /persons?death_year=999999999999` → `OverflowError: signed integer is greater than maximum`, `ERROR django.request: Internal Server Error`. Any clan member can 500 the endpoint at will, and a scripted loop is a cheap error-log/alert flood.

**(b) Duplicate marriage.** `Marriage.Meta.unique_together = ('husband','wife')` but the view never checks for an existing pair before `Marriage.objects.create`.
Measured: same husband+wife posted twice → `IntegrityError (1062, "Duplicate entry '24-25' for key 'giapha_marriage_husband_id_wife_id_2e80d978_uniq'")` → 500. Note the DB error text names the exact constraint and both row ids; that reaches the log verbatim.

Both violate `docs/code-standards.md` §Errors ("validate inputs up front and raise `InvalidParam`"). Fix: bound `death_year` to a sane range (`1 <= y <= 9999`) in the param parser; add an existence check for the (husband, wife) pair before create and raise `BadRequestException`, or catch the specific `IntegrityError` (not bare `Exception`) around that one `create`.

### H6. N+1 + unbounded response + inline query in the revisions endpoint
`giapha/views/person_revision.py:38`

```python
revisions = PersonRevision.objects.filter(person=person).order_by('-created_at')
```

Three problems in one line:
1. No `select_related('actor')`; `PersonRevisionSerializer.actor_username` walks `actor.username`. Measured: **12 revisions = 15 queries**.
2. No pagination. Every revision ever recorded is returned. A person edited 5,000 times returns 5,000 full-field JSON snapshots in one body.
3. The query is built **inline in the view** — direct violation of `docs/code-standards.md` §Layering ("selectors/ owns every bulk fetch. A view should not build queries inline"). This is the only place in the module that does it, and it is exactly the place where it caused a bug.

Fix: move to `selectors/revision.py::revisions_of(person)` with `.select_related('actor')`, and apply the existing `LimitOffsetPagination`.

---

## Medium

### M1. `HEAD` and `OPTIONS` are evaluated as write methods
`giapha/views/clan.py:48-50` · `views/person.py:54-56` · `views/person_list.py:71-73` · `views/marriage.py:34-36`

`classes = [IsClanMember] if self.request.method == 'GET' else [IsClanOwner]` — anything that is not literally `'GET'` gets the strict class.

Measured on `/clans/{id}` as a viewer: `GET → 200`, `HEAD → 403`, `OPTIONS → 403`.

The failure direction is safe (writes never get the weaker check), so this is not a hole — but `HEAD` breaks conditional-GET/cache-validation clients, and `OPTIONS` breaks DRF's metadata/browsable-API for non-owners. Fix: `if self.request.method in SAFE_METHODS`.

### M2. Last-owner guard is check-then-act with no lock
`giapha/views/clan_membership.py:61,73`

`owner_count(clan_id) <= 1` is read, then `member.save()`/`member.delete()` runs — no `transaction.atomic()`, no `select_for_update`. The sequential path works (measured: second delete → 400, one owner remains), but two concurrent requests removing/demoting two different owners of a 2-owner clan both read `count == 2`, both pass, and the clan ends with **zero owners**. There is no API path to appoint a new owner from a zero-owner state (`ClanMemberDetailAPIView` is `IsClanOwner`) — the clan is permanently frozen except via Django admin.

Contrast: the invite path *does* get this right (`select_for_update` inside `atomic`). Apply the same pattern: wrap both handlers in `transaction.atomic()` and take `select_for_update()` on the clan's owner rows before counting.

### M3. Soft-deleted clan is unrecoverable — and its persons are left live
`giapha/views/clan.py:71-77`

Measured: owner `DELETE /clans/{id}` → 204; owner `GET /clans/{id}` → **404**. `clan_role_for` filters `clan__is_deleted=False`, so the owner's own permission check fails and every clan-scoped endpoint 404s for them. There is no restore endpoint and no `?include_deleted` on the list.

Also: `delete` sets only `Clan.is_deleted`. `Person.is_deleted` is untouched, so the clan's persons remain "live" rows — any future query that filters persons without joining `clan__is_deleted` will resurrect them. `Clan.public_slug`'s unique constraint also stays held by a deleted clan.

Fix: allow an owner to read/restore their soft-deleted clan (resolve role against `Clan.objects.all()` and gate write endpoints on `is_deleted`), add `POST /clans/{id}/restore`, and decide explicitly whether the cascade to `Person.is_deleted` should happen.

### M4. `marriages_of` does not filter soft-deleted partners
`giapha/selectors/marriage.py:14-19`

Every other selector in `selectors/person.py` filters `is_deleted=False`; this one does not.

Measured: soft-delete a wife → `GET /marriages` still returns the row with `wife_name: 'VoX'`. So a "deleted" person's name is still served to viewers through a different endpoint. `/tree` is unaffected (`marriage_edges_from_rows` filters by `included_ids`), which is why this slipped through.

Fix: `.filter(husband__is_deleted=False, wife__is_deleted=False)` in both `marriages_of` and `get_marriage_or_none`.

### M5. `tree_payload` loads the whole clan into memory before truncating
`giapha/selectors/tree.py:39-43`

```python
rows = list(Person.objects.filter(clan_id=clan_id, is_deleted=False).order_by('id').values(...))
```
No `LIMIT`. `max_persons` is applied in Python at line 64-66, after the full result set is materialised. `MAX_CLAN_PERSONS = 5000` is enforced only by the API write path — Django admin, `loaddata` and any future import bypass it. A 200k-person clan means 200k dicts + 200k serializer passes before the truncation flag is set.

Same for `clan_edges` (`selectors/person.py:20-23`), which `recompute_descendant_generations` calls on every parent-changing PATCH.

Fix: `[:max_persons + 1]` on the queryset — one extra row is all that's needed to set `truncated`. (Note the `?root=` path needs the full edge set to compute the subtree; that one genuinely needs the whole graph, so bound it separately.)

### M6. Concurrent generation recomputes can persist a stale graph
`giapha/selectors/tree.py:97-113` · `giapha/views/person.py:92-104`

`recompute_descendant_generations` reads `clan_edges(clan_id)` then `bulk_update`s. Two editors PATCHing different persons in the same clan concurrently: T1 reads edges, T2 commits its parent change, T1 computes from its now-stale snapshot and writes. Both transactions succeed; the persisted `generation` column no longer matches the graph.

Lower severity than it looks — `generation` is denormalised with a documented fixup command — but silent divergence in the field the tree renders from. Fix: `select_for_update` on the target rows, or accept it and document that `recompute_generations` is the reconciliation mechanism.

### M7. `?force=true` waives the age check for the entire batch
`giapha/views/person_list.py:106,123-127` (known gap — confirmed and quantified)

Measured: a 2-record batch where record 2 violates the 12-year rule → 400 with rollback. Same batch with `?force=true` → **201, both records created**, the sound record's own validation silently relaxed along with it.

Severity is contained: `_wants_force` correctly restricts the flag to `owner` (measured: editor → 403), and the check it waives is a heuristic, not an invariant. But at `MAX_BULK_CREATE = 200` one flag disables the check for 200 records, and there is no record of which rows were force-created. Fix: accept `force` as a per-record key in the payload; if a request-level flag is kept, tag force-created rows in their `PersonRevision`.

### M8. Member roster exposes every member's email to every member
`giapha/serializers/clan.py:45-53`

`ClanMemberSerializer.fields` includes `email`, and `ClanMembersAPIView` is `IsClanMember` — any role.

Measured: a `viewer` who joined via invite code received the full roster with `clan_owner@example.com`, `clan_editor@example.com`, … Combined with C1 (a leaked, never-expiring, unlimited-use invite), anyone who obtains a code harvests the email addresses of the whole family. Fix: return `email` only to `owner`, or drop it in favour of `username` (the PATCH/DELETE endpoints key on `user_id`, so `email` is not needed for any client flow).

---

## Low

- **L1. `views/params.py` does not exist.** `docs/code-standards.md` §Layering names it explicitly ("views/ validate parameters first, via `views/params.py`"), and `apis/views/params.py` is the precedent. Instead, `_parse_positive_int` (`views/tree.py:25-38`) and `_int_query_param` (`views/person_list.py:35-45`) are near-duplicates in two modules. Consolidate — H5(a)'s range bound then lands in one place.
- **L2. `_wants_force` is duplicated verbatim**, 13 lines, in `views/person.py:34-46` and `views/person_list.py:48-60`. DRY. Both also read the private `request._giapha_role_cache` without a default — currently unreachable (the permission class always populates it first) but a fragile coupling; a `permissions.role_for(request, clan_id)` helper would make it safe and shared.
- **L3. `/tree` query-budget contract is stated more strongly than it is tested.** `views/tree.py:1-9` says "exactly 3 for any clan size". Measured: 3 for populated clans (asserted at `test_tree_api.py:60,69,75`), but **4 for an empty clan** — the `get_clan_or_none` fallback at `selectors/tree.py:56`. `test_empty_clan_still_returns_clan_name:100` exercises that path but is not wrapped in `assertNumQueries`. Also note all three assertions use `force_authenticate`, which skips the real `OAuth2Authentication` token lookup; production adds 1–2 queries on top. Reword the docstring or add the assertion.
- **L4. Query budgets exist for `/tree` only.** `docs/code-standards.md` §Queries: "Adding an endpoint means adding it to `test_query_counts.py`. The ceiling is the contract." Thirteen endpoints, one budgeted. I measured the rest: `GET /clans` = 2, `GET /persons` = 3, `GET /marriages` = 2 (all fine), `GET /revisions` = 15 for 12 rows (H6), bulk `POST /persons` = 66 for 20 rows (H2). The two that were never budgeted are the two that are broken.
- **L5. Traversal safety counters are correct but dead, and fail-open if they ever fire.** I verified termination on cyclic input for all three walks. `descendants` (`services/person_rules.py:50-61`) and `subtree_ids` (`services/tree.py:94-109`) terminate because of the `visited` set, not the counter — each node is enqueued at most once, so pops ≤ N+1, and the cap is `2N+10`. `compute_generations` terminates by Kahn construction (each id enqueued at most once when `pending` hits 0), with cycle members falling through to the `setdefault(…, 1)` at line 81-82. Measured on a real cycle: `{A: 1, B: 1}`, no hang. **So the bounds are genuinely correct.** The residual concern: if `max_iterations` ever *did* fire, `descendants()` returns a *partial* set and `validate_no_cycle` would then pass a real cycle — the safety net fails open. Consider raising `PersonValidationError` on cap-exhaustion instead of returning silently.
- **L6. Marriage integrity gaps.** No gender check (a `gioi_tinh='nu'` person can be `husband`); no check that partners are not parent/child; `validate_marriage_order_unique` is check-then-act with no DB unique constraint on `(husband, order)`, so concurrent creates can produce duplicate orders. All cosmetic relative to the above.
- **L7. `MarriageDetailAPIView.patch` silently discards `husband_id`/`wife_id`.** Verified immutable (measured `CHANGED=False`, and a cross-clan husband swap did not escape — good). But the serializer accepts and validates the field, then the view ignores it and returns 200. A client changing a partner gets a success response and no change. Return 400 when those keys are present.
- **L8. `test_requires_clan_id_or_all` / `test_rejects_unknown_clan_id`** (`test_tree_api.py:322-328`) use `assertRaises(Exception)` — blanket catch, same smell the standards ban in application code. Use `CommandError`.
- **L9. `services/revision.py::snapshot` is only nominally pure** — it takes no Django import but requires `person._meta.fields`, so it cannot actually run without a model instance. Not a violation as written; worth noting the purity guarantee is weaker here than in `person_rules.py`/`tree.py`.

## Informational (not defects)

- `Clan.hide_living_details` (default `True`) is stored and ignored — a living person's `birth_year` and full name are returned in `/tree`. Confirmed against `phase-09-chia-se-cong-khai.md:39`: this flag is phase-9 scope. Correctly out of scope here; flagging only so it is not forgotten, since the default is `True` and the field already reads as a privacy promise.
- `PersonRevision.payload_json` is a full field dump including `clan_id` and `is_deleted`. Correctly gated to `IsClanEditor` (`views/person_revision.py:29`), which the tests cover.
- `giapha` has zero imports from `apis` — the package boundary asserted in `exceptions.py:1-5` holds.

---

## Recommended Actions (priority order)

1. **C1** — invite lifecycle: add revoke + list, bound `max_uses`/`expires_at` defaults, drop `owner` from grantable roles, unify the 404/400 rejection, throttle `/join`.
2. **H3** — run `validate_person_write` in the restore path; exclude `is_deleted`/`clan_id` from restore.
3. **H1** — compute `generation` on create; remove `generation` from `_WRITE_FIELDS`.
4. **H5** — bound `death_year`; pre-check the duplicate marriage pair.
5. **H2 + H6** — kill both N+1s; fix the false-negative test by adding `father_id` to its fixture; add `select_related` + pagination to revisions.
6. **H4** — decide the soft-delete cascade rule and make `children_count` match it.
7. **M2** — wrap the last-owner guard in `atomic` + `select_for_update`.
8. **M1, M3, M4, M5, M8** — safe-methods check, clan restore path, marriage soft-delete filter, queryset `LIMIT`, roster email gating.
9. **L1/L2/L4** — extract `views/params.py`, dedupe `_wants_force`, backfill query budgets for the remaining 12 endpoints.

## Metrics

| | |
|---|---|
| Modules reviewed | 25 (+2 touched project files) |
| Suite | 219/219 green (per handoff); probe suite 31/31 ran clean |
| Migration drift | none (`makemigrations giapha --check` → No changes detected) |
| Files > 200 lines | 0 outside `tests/` (max non-test: `services/person_rules.py`, 189) |
| `services/` purity | verified clean — no Django/ORM imports |
| Blanket `except Exception` | 0 in app code (1 in a test) |
| `fields = '__all__'` | 0 |
| Endpoints with query budgets | 1 / 13 |
| Confirmed 500-producing inputs | 2 |
| Confirmed authorization bypasses | **0** |

## Score

**7 / 10**

Architecture, layering and authorization are strong — I attacked the clan-scoping from five angles and it held, and the purity/404-discipline constraints are genuinely enforced rather than aspirational. Points come off for one Critical security gap in the invite lifecycle, a core phase-4 feature (`generation`) that does not fire on the main write path, a validation bypass that can corrupt the tree through ordinary API calls, and two 500s reachable from valid client input. All are contained fixes; none require rework of the design.

---

## Unresolved Questions

1. **Invite role `owner` — intended?** If ownership transfer via invite is a deliberate product decision, C1 narrows to "bound the defaults + add revocation". If not, drop `owner` from the choices entirely.
2. **Is `POST /restore` meant to undelete?** It currently does, silently. Deliberate, or should `is_deleted` be excluded from the snapshot?
3. **Soft-deleted clan:** should soft-deleting a clan cascade to `Person.is_deleted`? Current behaviour leaves persons live but unreachable, which will matter when the phase-9 public page queries persons.
4. **`?force=true` granularity** — per-record flag, or keep request-level and just audit it? Affects the payload contract, so worth deciding before clients ship.
5. **`MAX_CLAN_PERSONS = 5000` is API-only.** Should the management command and admin enforce it too, or is `tree_payload`'s `truncated` flag considered sufficient protection against oversized clans?
6. **Throttling** is absent project-wide (`REST_FRAMEWORK` has no throttle classes at all). Is that an existing `apis/` decision that giapha should inherit, or should giapha set its own scoped throttles?
