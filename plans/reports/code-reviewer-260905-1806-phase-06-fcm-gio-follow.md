# Code Review — Phase 6: FCM push + nhắc giỗ (adversarial)

Date: 2026-09-05 | Reviewer: code-reviewer | Scope: phase 6 working tree vs `44b815e`
Spec: `plans/260905-1053-gia-pha-dong-ho/phase-06-fcm-push-va-nhac-gio.md`

## Verification method

Not read-only. Five adversarial probes were written as a throwaway test module, run against
the real MySQL suite, and deleted. Every finding marked **PROVEN** below is backed by an
executed test, not by reading. Baseline re-confirmed after deletion: **450 tests, OK,
4 skipped**; `makemigrations giapha --check --dry-run` → *No changes detected*.

---

## Overall assessment

Craftsmanship is high — layering is clean, the pure/impure split is real, the docstrings
carry actual reasoning, the query budgets are pinned by tests that are not vacuous, and
the timezone trap the spec warned about was genuinely avoided. **But the two things this
phase exists to do — send to the right people, and actually send — are both broken in
ways the 450 green tests do not see.** One proven privacy leak, two proven silent-loss
paths.

Not shippable as-is. Fix C1, H1, H2 (H3 is cheap and should ride along).

---

## Critical

### C1. An ex-member keeps receiving pushes from a clan they were removed from — PROVEN

`giapha/selectors/gio_follow.py:31-42` (`overrides_for_clan`) filters only on
`person__clan_id`; `giapha/services/gio_follow.py:95` then iterates
`set(bindings) | set(overrides_by_user)`. Removing a member
(`giapha/views/clan_membership.py:86` → `member.delete()`) deletes the `ClanMember` row
and therefore the binding, but leaves every `GioFollow` row untouched.

Scenario (executed): `viewer` joins the clan, `PUT /clans/{id}/gio-follows/{cu_id}
{"enabled": true}`, owner then removes `viewer` from the clan. Command run on the target
day →

```
PROBE1 tokens reached = {'tok-ex', 'tok-owner'}
AssertionError: 'tok-ex' unexpectedly found : LEAK: ex-member still notified
```

The push carries the deceased person's full name plus `{"clan_id": …, "person_id": …}`
to someone who now gets a 404 from every endpoint of that clan. This is exactly the leak
the design document claims `ClanMember.person` was chosen to prevent (spec §A, row
"Rời họ thì đứt liên kết" — *"vẫn nhận push của một clan mình không còn quyền đọc.
Đây là lỗi rò rỉ thật, không phải khẩu vị"*). The binding half was solved; the override
half was not.

Note the existing test `test_leaving_the_clan_drops_the_binding_not_the_person`
(`test_gio_follow_api.py:160`) asserts the docstring *"a departed member must stop being
resolvable"* — but only checks `ClanMember.person`, so it passes while the leak is open.

**Fix** — constrain the override read to current members. Still one query:

```python
GioFollow.objects.filter(
    person__clan_id=clan_id,
    user__clanmember__clan=clan_id,   # ClanMember.user has no related_name
).values_list('user_id', 'person_id', 'enabled')
```

Plus, for hygiene, delete that user's `GioFollow` rows for the clan in
`ClanMemberDetailAPIView.delete`. Add a regression test at the command level, not the
selector level.

---

## High

### H1. A reminder that fails to send is lost for a year, never retried — PROVEN

`_log` (`remind_death_anniversary.py:116-137`) writes a row with `status='failed'`;
`notified_pairs` (`selectors/gio_follow.py:108-124`) does not filter on `status`, so the
next run treats the failed pair as already handled.

Both `giapha/models/notification.py:6-8` and
`remind_death_anniversary.py:120-121` justify this with *"the next day's run covers the
person again if the giỗ is still ahead"*. **That claim is false.** `target = today +
gio_remind_before_days` advances one day for every day `today` advances, and `due_rows`
matches on a single day (`gio_occurrences_in_range(..., target, target)`), so a person is
due on **exactly one calendar day per year**. There is no "next day's run" for them.

Executed: force one `ERROR_NETWORK` on the target day, then run the command on each of
the following five days →

```
PROBE2 retry attempts over the following 5 days = 0
AssertionError: NO RETRY: reminder lost for the year
```

One DNS blip, one 5xx, one expired service account (`_classify` returns
`HTTP 401 UNAUTHENTICATED`, which is not in `DEAD_TOKEN_RESULTS` and not a `{}`), and that
ancestor's giỗ reminder is silently gone until next year — with a `status='failed'` row
nobody reads.

**Fix** — pick one:
1. `notified_pairs` filters `status='sent'`, and `_log` uses `update_or_create` keyed on
   `(person, user, solar_date)` so the retry overwrites the failed row. Smallest change,
   keeps the unique constraint as the dedupe guarantee.
2. Widen `due_rows` to the window `[target, target + N]` so a person is due on more than
   one day and a failure has somewhere to be retried.

Option 1 is the KISS answer.

### H2. A transient OAuth failure aborts the entire run and is reported as "not configured" — PROVEN

`services/fcm.py:104-115,186-188`: `_access_token` returns `None` when
`credentials.refresh(Request())` raises `GoogleAuthError` / `requests.RequestException`
(`:98`) — i.e. a transient network or Google-side failure — and `send_multicast` then
returns `{}`. That is the *same* value used for "no service account at all"
(`:180`, `:184`). `dispatch` (`remind_death_anniversary.py:169-170`) reads `{}` as
`configured=False` and `return`s, abandoning every remaining job in the run.

Executed: first recipient succeeds, second hits a mint blip →

```
PROBE5 attempts = 2 | logs = [(1, 'sent')]
        | stdout = Chưa cấu hình Firebase (FIREBASE_CREDENTIALS_PATH/JSON); không gửi được gì.
                 | 2026-03-20: 1 lượt nhắc giỗ, đã gửi 1, bỏ qua 0
PROBE5 retries next day = 0
```

Three problems in one line of output: the operator is told Firebase is unconfigured while
one push demonstrably went out; the abandoned recipients are never logged; and per H1 they
are never retried. On a busy day this loses most of the run.

`test_missing_credentials_exits_cleanly` passes because its stub returns `{}`
unconditionally from the first call — it cannot distinguish the two meanings either.

**Fix** — reserve `{}` strictly for `_credentials_info() is None` / missing `project_id`.
Have the transient auth path return `{token: ERROR_NETWORK for token in tokens}` (which
already flows correctly through `_deactivate_dead` — `ERROR_NETWORK` is not a dead-token
result) or raise a dedicated exception the command catches per job.

### H3. `except IntegrityError` without a savepoint in two views — PROVEN

`views/member_binding.py:96-101` and `views/device.py:42-61` catch `IntegrityError` around
a bare `save()` / `update_or_create()` with no `transaction.atomic()` around it. The
command's `_log` got this right (`:128`); the two views did not.

Executed (forcing the pre-check to miss so the race branch runs):

```
PROBE4 status = 400
django.db.transaction.TransactionManagementError: An error occurred in the current
transaction. You can't execute queries until the end of the 'atomic' block.
```

The 400 is produced, but the connection is left in a broken-transaction state. Harmless in
production *today* only because `djangopj/settings.py` sets no `ATOMIC_REQUESTS` — turning
it on, or ever calling these from inside an `atomic` block, converts the documented
"keeps it a 400, not a 500" into a guaranteed 500. Neither branch has a test; the existing
`test_already_claimed_person_is_400_not_500` exercises the pre-check path
(`person_claimed_by_other`), never the `IntegrityError` path it is named after.

**Fix** — `with transaction.atomic():` around the write in both views.

---

## Medium

### M1. Soft-deleting one person silently severs the whole line above them — PROVEN

`clan_edges` filters `is_deleted=False` (`selectors/person.py:20-23`), so `ancestors()`
hits a hole and stops. Soft-delete a mistakenly-duplicated `ông` and every descendant
below him silently loses `cụ`, `kỵ`, and everything above — from reminders *and* from
`GET /gio-follows`.

```
PROBE3 send.call_count for cu after soft-deleting ong = 0   (expected 1)
```

Existing `test_soft_deleted_person_is_skipped` only asserts the deleted person gets no
reminder — not the severed-chain side effect. Nothing documents this.
**Fix** — either walk over an unfiltered edge list (soft-deleted persons are excluded from
`person_ids` by `deceased_with_lunar_death` anyway, so they still receive nothing), or
state the behaviour explicitly in the service docstring and add a test that pins it.

### M2. `dispatch` has no per-job isolation

`collect_due` wraps each clan in `try/except Exception` (`:95-102`) so one bad clan does
not sink the others. `dispatch` guards only `send_multicast` (`:162-168`). A
`DatabaseError` out of `_log` or `_deactivate_dead` (deadlock, connection drop mid-batch)
kills every remaining job in the run — which, per H1, means those reminders are gone.
The spec's "một clan lỗi không chặn các clan khác" holds only for the collection half.

### M3. `_log` counts a lost race as a send

`:134-137` — the `IntegrityError` branch falls through to `return delivered`, so a
concurrent double-run reports `đã gửi N` including pushes it did not send. Cosmetic, but
it is the same value the operator reads to decide whether the job worked.

### M4. An override can become invisible *and* undeletable

`_items` (`views/gio_follow.py:93-114`) iterates only rows from
`deceased_with_lunar_death`, and `_gio_person_or_reject` (`:146-159`) 400s when
`death_lunar_day`/`month` is `None`. If an editor later clears a person's lunar death date,
the user's existing `GioFollow` row disappears from `GET` and both `PUT` and `DELETE`
reject it — the user cannot remove their own row. Removing an override is always
meaningful; `DELETE` should not require the person to still have a giỗ.

### M5. `services/fcm.py` bypasses `settings`, and its token cache is unkeyed

`:58,66` read `os.environ` directly. Everything else in the project routes config through
`django.conf.settings`, so `override_settings` cannot reach this module and a deploy that
sets the variable in `settings.py` rather than the process env silently gets no FCM.
Separately, `_token_cache` (`:44`) is a module-level global keyed on nothing: if the
credentials ever change (rotation, two projects), it serves a bearer token for the wrong
project for up to 3000 seconds. Both are cheap to fix and neither bites today.

---

## Low

- **L1. `ancestors`' safety counter is unreachable.** `visited` already guarantees each
  node is enqueued at most once, so the loop pops at most `len(edges)+1` times while
  `max_iterations = 2*len(edges)+10`. It can never fire with the default.
  `test_fails_open_with_a_partial_set_when_the_counter_is_exhausted`
  (`test_gio_follow_service.py:68`) only reaches it by passing `max_iterations=2`
  explicitly — it pins a path production never takes, and the elaborate "fail OPEN vs
  `person_rules.descendants`' fail CLOSED" docstring is therefore moot. Harmless; just
  don't believe the docstring. The *real* cycle protection (`visited` +
  `visited.discard(person_id)`) is correct and genuinely covered.
- **L2. `docs/deployment-guide.md`** closes by warning that `docker-compose.yml` "does not
  yet forward `FIREBASE_CREDENTIALS_*`". It does, added in this same change set
  (`docker-compose.yml:30-33`). Stale on arrival.
- **L3. Dead re-exports.** `giapha/services/__init__.py` newly re-exports
  `DEAD_TOKEN_RESULTS`, `GioJob`, `ancestors`, `due_rows`, `followers_by_person`,
  `message_body`, `send_multicast` — no caller imports any of them flat (the command
  imports by module path). It also pulls `requests` into the import graph of every
  `from giapha.services import …`. And it is inconsistent: `RESULT_OK` / `ERROR_NETWORK`
  *are* used by callers and are not re-exported.
- **L4.** `selectors/__init__.py` `__all__` is no longer alphabetical
  (`deceased_with_lunar_death` before `clans_for_user`).
- **L5. Device-token takeover is a design trade-off, name it as one.**
  `views/device.py:48` keys the upsert on `token`, so anyone who learns another user's FCM
  token can `POST /devices` and steal the row: the victim's handset stops receiving their
  own reminders and starts receiving the attacker's clan's. The read direction is safe and
  the spec asked for exactly this (spec line 230), so it is not a defect — but it should be
  a recorded decision, not an accident.
- **L6.** `GioNotificationLog.status` / `.error` are written and never read — no admin, no
  query, no test on the 255-char truncation. Fine as an audit trail; note it is currently
  write-only.

---

## Verified fine (briefly — not padding, these were the priority items)

- **Timezone: clean.** `today_vn()` used; grep across `giapha/` finds zero
  `localdate` / `date.today()` / `datetime.now()` / `utcnow` outside comments.
  `run_on` patches `today_vn` *in the command module*, so tests exercise the real path
  rather than a parallel one. `deployment-guide.md`'s "on a UTC host that means
  `0 0 * * *`" is arithmetically right.
- **Query budgets are real, not fitted.** `test_one_query_per_clan_when_nothing_is_due`
  pins `1 + N`; moving the early exit turns 4 into 16, so it fails loudly. `notified_pairs`
  correctly short-circuits with no query on an empty job list, so `dispatch` costs nothing
  on a quiet day. `GET /gio-follows` is genuinely constant in follower count —
  `test_budget_does_not_grow_with_the_follow_count` builds a 30-deep line plus 20 overrides,
  asserts 52 items, and still asserts 5 queries.
- **Same-day idempotency works.** `test_running_twice_in_one_day_sends_once` passes for the
  right reason. `_log`'s savepoint reasoning is correct: `transaction.atomic()` is a
  savepoint when nested and a real transaction when not, so the `IntegrityError` is
  contained either way. (The *failed*-row consequence of that design is H1, not a savepoint
  bug.)
- **Authorization is right.** All four clan-scoped routes carry
  `IsAuthenticated + IsClanMember`; outsiders get 404 on GET/PUT/DELETE of both `toi-la`
  and `gio-follows` (covered). `request.user` everywhere, no client-supplied user id
  anywhere — `MemberBindingWriteSerializer` accepts only `person_id`. Cross-clan binding →
  400, cross-clan override → 404. `/devices` correctly `IsAuthenticated`-only, with the
  `_role_for` / `view.kwargs['clan_id']` reasoning verified against `permissions.py:29`.
- **Device tokens do not leak.** Never echoed (`test_response_never_echoes_the_token`);
  every `fcm.py` log line goes through `_redact`; `DeviceToken.__str__` omits the token;
  no serializer outside `serializers/device.py` reads the field. Grep-confirmed.
- **No test touches the network.** `test_fcm_service` patches `requests.post` *and*
  `_mint_token` on every path (including the credential-error paths, verified by
  `post.assert_not_called()`); `test_remind_command` patches `send_multicast` in the command
  module. Full-suite run emits only fake-token warnings.
- **`send_multicast` raising is handled.** `dispatch:163-168` catches it and synthesises
  `{token: SEND_ERROR}` per token — the implementer's claim checks out, and
  `test_an_exception_from_the_sender_does_not_abort_the_run` proves the run continues.
  Per-token isolation inside `fcm.py` (`_send_one`) is also real.
- **Layering holds.** `services/gio_follow.py` and `services/gio_remind.py` are ORM-free
  and `SimpleTestCase`-tested; `services/fcm.py` does network but imports no model;
  `_deactivate_dead` correctly keeps the `is_active=False` write in the command.
- **Migrations.** `makemigrations giapha --check --dry-run` → *No changes detected*.
  0004 is additive-nullable + unique index, 0005 is three `CreateModel` + one `AddField`
  with `default=3`; dependency order (0005 → 0004 → `AUTH_USER_MODEL`) is correct and both
  are auto-reversible. MySQL 5.7-safe (int unique index; `token` `varchar(255)` unique =
  1020 bytes, under the 3072-byte DYNAMIC limit) — empirically confirmed, the suite runs
  on MySQL.
- **Django 3.1 / Python 3.9.** No walrus, no `match`, no `dict |`, no `zoneinfo`, no
  3.2+ model APIs. `namedtuple` / `deque` / `.format()` throughout. Compiles under 3.9 in
  the test image.
- **Style.** Every new file under 200 lines (`fcm.py` exactly 200), snake_case throughout.
- **Recipient resolution, the parts that are right.** Two users bound to the same node is
  impossible (global OneToOne) and the collision is a 400. A user bound to a node in
  another clan resolves to an empty ancestor set (edges are per-clan) — no cross-clan
  bleed. `enabled=True` overrides are correctly intersected with `person_ids`
  (`services/gio_follow.py:106`), so a manual follow cannot pull in a person outside the
  run. Cycles and self-parent rows terminate and are excluded. A person is never their own
  follower.

---

## Test-quality verdict

Better than most. The service layer is tested on `SimpleTestCase` with real inputs, the
API tests assert behaviour rather than mocks, the `assertNumQueries` numbers are derived
and would actually catch the regressions they claim to, and the FCM mocking is at the right
seam (`_mint_token` / `requests.post`) rather than mocking the function under test.

The gaps are all *missing negative cases*, and they map one-to-one onto the findings:
no test for an ex-member with a surviving override (C1), none that a failed send is ever
retried (H1), none that distinguishes "no credentials" from "transient auth failure" (H2),
none reaching either `IntegrityError` branch despite one test being named after it (H3),
none for a soft-deleted intermediate ancestor (M1). "450 green" is, as suspected, not
evidence about any of these.

---

## Metrics

| | |
|---|---|
| Tests | 450 passed, 4 skipped (re-run after probe removal) |
| New files | 15 code + 4 test |
| Largest new file | `services/fcm.py`, 200 lines (at the limit) |
| Stray migrations | none (`--check --dry-run` clean) |
| Linting | not measured — no flake8/ruff/setup.cfg in the repo |
| Type coverage | n/a — project uses no annotations |

## Score

**6 / 10. Not shippable.**

The scaffolding is 9/10 work. The two behaviours the phase was built to deliver are not:
a removed member still receives that clan's pushes, and any transient failure loses a
reminder for a full year with no retry and a misleading log line. C1 is a privacy defect
the design document explicitly claimed to have solved. H1 and H2 turn the feature into one
that works in the demo and rots quietly in production — the exact failure mode nobody
notices until a family complains that grandfather's giỗ was never announced.

C1, H1, H2 are blocking. H3 is a two-line fix that should ride along. M1 needs a decision
(fix or document) before the next tree-editing phase inherits the assumption.

---

## Unresolved questions

1. **C1 fix shape** — filter `overrides_for_clan` by current membership (cheap, self-healing,
   rows survive a rejoin), or hard-delete `GioFollow` rows on member removal (destructive,
   but leaves no dormant rows)? Recommend the filter, plus deletion only if the product
   wants "rejoining resets preferences".
2. **H1 fix shape** — filter `notified_pairs` on `status='sent'` (retry within the same day
   only, which is one cron run) or widen `due_rows` to a `[target, target+N]` window (real
   multi-day retry, but changes the "3 days before" message wording)? The former is KISS;
   the latter is what actually survives a whole-day outage.
3. **M1** — is a soft-deleted person severing the ancestor line intended? This is phase 4's
   `clan_edges` contract, so changing it affects the generation walk and phase 7's kinship
   calculator too. Needs an owner decision, not a local patch.
4. `gio_remind_before_days` is per-clan and mutable. Changing it mid-year moves every
   person's single due day — anyone whose day was skipped over never gets reminded that
   year. Worth a note in the admin, or a wider `due_rows` window (see #2).
5. `apis/management/commands/remind_appointment_date.py` has the same `localdate()`
   timezone bug the spec flags at line 299. Out of phase-6 scope, still open.
6. The blocked criterion — real push to a real handset — remains blocked on the Firebase
   service account. Nothing found in this review depends on unblocking it; all five proven
   findings reproduce with FCM mocked.

---

**Status:** DONE_WITH_CONCERNS
**Summary:** Phase 6 is well-engineered scaffolding around three proven production defects —
an ex-member privacy leak in recipient resolution, and two paths that silently drop a
reminder for a full year. All five findings were reproduced with executed tests, not
inferred.
**Critical:** 1 · **High:** 3
