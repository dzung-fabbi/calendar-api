# Fix verification — Phase 6 (FCM push + nhắc giỗ)

Date: 2026-09-05 | Reviewer: code-reviewer | Narrow pass
Verifies: `plans/reports/fullstack-260905-1817-phase-06-review-fixes.md`
against `plans/reports/code-reviewer-260905-1806-phase-06-fcm-gio-follow.md`

## Method

Six throwaway probe classes (`giapha/tests/test_zz_review_probe.py`, 12 cases) written,
run on the real MySQL suite, deleted. Every **PROVEN** line below is executed output.
Tree left as found: probe deleted, backup deleted, `git status` matches the pre-review
snapshot, **469 passed / 4 skipped**, `makemigrations giapha --check --dry-run` →
*No changes detected*.

---

## Per-finding verdicts

### C1 — ex-member push leak · **VERIFIED FIXED**

`selectors/gio_follow.py:51` filters `person__clan_id=clan_id, user__clanmember__clan_id=clan_id`.

- Ex-member receives nothing — PROVEN. Harder case than their test: viewer removed from
  clan A but *still a member of clan B*, override intact → `P1c overrides = {}`,
  `P1c tokens = {'tok-owner'}`. The reverse path cannot be satisfied by membership of a
  *different* clan.
- Rejoin restores preferences — their `test_rejoining_restores_the_kept_preferences`
  is real (row survives the delete, re-added membership re-admits it).
- **No row duplication**: `ClanMember` has `unique_together ('clan','user')`, so the join
  is 1:1. PROVEN `P1b raw joined rows = [(3, 2, True)]` — one row, no `distinct()` needed.
- **No legitimate override dropped**: a current member of another clan keeps theirs.
  PROVEN `P1a tokens = {'tok-owner', 'tok-viewer'}`.
- `GET /gio-follows` still 5 queries — PROVEN, my own `assertNumQueries(5)` probe passed,
  plus their two budget tests. The endpoint does not use `overrides_for_clan` at all.
- **Revert sanity-check (the one I picked as highest-risk).** Reverted the join
  out-of-tree, ran `MembershipTests` + my probe:
  ```
  FAIL: test_a_removed_member_stops_receiving_pushes — 'tok-viewer' in first set
  FAIL: test_ex_member_of_this_clan_but_member_elsewhere_is_excluded
  FAILED (failures=2)
  ```
  Red as claimed. File restored byte-identical (`diff` → IDENTICAL). The fixer's
  "reverted and observed red" claim holds where I checked it.

Note, not a defect: `follow_rows_for_user` (the GET path) has **no** membership join. It is
safe only because `IsClanMember` gates the view. If that selector is ever reused off a
clan-scoped route the leak reopens; the docstring does not say so.

### H1 — failed reminders never retried · **VERIFIED FIXED**, one new Low regression

`notified_pairs` filters `status='sent'`; `log_attempt` upserts. Retry works, success never
repeats (their `RetryTests` ×3 are non-vacuous — they assert the row is *updated in place*,
not duplicated, and that a success for one recipient is not re-attempted).

**The "no double-send window" claim is not strictly true — PROVEN.** `update_or_create`
lets a later *failed* attempt overwrite an existing `sent` row; `create()` could not
(the `IntegrityError` branch left the sent row intact). Simulating two overlapping runs
whose `notified_pairs` reads both predate the first commit:

```
P4 status after concurrent failed run = failed
P4 resend attempts on an already-delivered pair = 1
```

i.e. a pair that was genuinely delivered is downgraded to `failed` and re-pushed by the
next run. Requires overlapping runs (cron overlap, or an operator re-running during the
nightly job — which the deployment guide now *instructs* them to do after an outage), and
the command takes no lock. Cost is a duplicate push and a lying audit row, not a leak.
See NEW-1.

Also inherent, worth stating somewhere: the retry moves the job from at-most-once to
at-least-once. A response lost after FCM accepted the message (`ERROR_NETWORK` on a
delivered push) now produces a duplicate notification on re-run. Acceptable for this
feature; currently undocumented.

Unchanged and correct: `delivered = len(errors) < len(results)` is per *pair*, not per
device, so a user with two handsets where one fails is logged `sent` and that handset is
never retried (`P4b status ... = sent | error = ''`, `P4b retry attempts = 0`). Pre-existing,
and the docstring's wording ("retries exactly the pairs that failed") is honest about it.

### H2 — transient OAuth aborting the run · **PARTIALLY FIXED** (mint path yes, credentials-read path no)

Fixed and genuinely exercised: `fcm_auth.FcmTransientError` vs `None`, `send_multicast`
converting the former to `{token: ERROR_NETWORK}`, `dispatch` no longer returning
`configured=False`. Their `TransientAuthFailureTests` run the **real** `send_multicast`
with only `_mint_token` and `requests.post` faked — the right seam. Genuine misconfiguration
still exits 0 with the warning and records nothing (verified; `handle` returns `None`).

**The sibling transient path was missed.** `fcm_auth.credentials_info()` treats
`IOError`/`OSError` reading `FIREBASE_CREDENTIALS_PATH` as CONFIGURATION
(`fcm_auth.py:83-88` → `return None`), and `send_multicast` calls it **once per recipient**.
A credentials file that is rotated (or momentarily unreadable) mid-run therefore still
collapses to `{}` and abandons the rest of the run — exactly H2's failure mode, in the
other half of the same module. PROVEN, with a real file and no patching of the
classification (`requests.post` deletes the file after the first push):

```
P6 posts = 1 | logs = [(1, 'sent')]
P6 out = Chưa cấu hình Firebase (FIREBASE_CREDENTIALS_PATH/JSON); không gửi được gì.
         2026-03-20: 1 lượt nhắc giỗ, đã gửi 1, bỏ qua 0
```

All three symptoms the original H2 named survive here: "not configured" printed in a run
where a push demonstrably went out, the remaining recipient neither sent nor logged, and
(per H1's arithmetic) no next day to catch them. See NEW-2.

Same call site, Low: `credentials_info()` re-reads and re-parses the service account file
**per recipient** — a 500-recipient run does 500 file opens for a value that could not have
changed legitimately.

### H3 — `IntegrityError` without a savepoint · **VERIFIED FIXED**

`transaction.atomic()` present in both `views/member_binding.py:104` and
`views/device.py:59`. Both new tests genuinely reach the `IntegrityError` branch, not the
pre-check:

- `test_losing_the_race_…` patches `person_claimed_by_other` → `False`, so the OneToOne
  raises at the DB; the detector is the `ClanMember.objects.get(...)` **after** the response,
  which is what raised `TransactionManagementError` before the fix.
- `test_a_racing_insert_…` replaces `update_or_create` with a genuine duplicate `INSERT`
  (not a mock raising) — correct, since Django's own `update_or_create` savepoints
  internally and a mock would not have reproduced it.
- Rename of `test_already_claimed_person_is_400_via_the_pre_check` is accurate.

### M1 — soft-deleted ancestor severing the line · **VERIFIED FIXED**

`clan_edges` is **behaviourally byte-for-byte unchanged** — `git diff selectors/person.py`
shows a docstring addition only; the query body is untouched. Callers still on `clan_edges`:
`selectors/tree.py`, `views/person.py`, `views/person_list.py`, `views/person_revision.py`,
`management/commands/recompute_generations.py` (phase 4 / phase 7 contract intact,
grep-confirmed). `clan_edges_all` has exactly two callers.

Traversal through a soft-deleted middle ancestor works, and a soft-deleted person still
generates nothing (their two tests, plus my P2 probes).

### Scope widening: `GET /gio-follows` on `clan_edges_all` · **RIGHT CALL, no leak** — PROVEN

The judgement is correct: the screen and the push must resolve the same ancestor set, or
the endpoint tells a member they follow someone the command will never notify them about.

No soft-deleted person can reach the response. `_items` iterates only `rows` from
`deceased_with_lunar_death` (`is_deleted=False`); `line` is used solely as a membership test.
PROVEN, both directions:

```
P2a items = [(6, 'Cu', 'truc-he')]      # ong soft-deleted: absent, cu restored to the line
P2b ids = {6, 7}  bac = 8               # soft-deleted person WITH an enabled override: absent
```

`source` cannot leak one either — it is computed per listed row, and no soft-deleted row is
listed. Query budget still 5.

One undocumented behaviour change fell out of it (Low, NEW-3): a member whose **own bound
node** is soft-deleted now resolves a full ancestor line again and resumes receiving pushes
(`P2c items = [cu, ong]`, `P2c push tokens = {'tok-owner'}`); before, the walk started at a
node absent from the edge list and returned nothing. Not a leak — they are still a member of
the clan — but nothing tests or documents it, and `toi-la` refuses to *create* such a
binding (`test_soft_deleted_person_is_400`), so the two rules now disagree.

### The two file splits · **CLEAN**

- Import graph is a DAG: `services/fcm.py` → `services/fcm_auth.py` (leaf: `requests`,
  `settings`, stdlib). `management/commands/_gio_reminder_log.py` → `services.fcm`
  constants + `giapha.models`. Nothing in `services/` imports a command. No cycle.
- **No ORM in `services/`** — `grep 'giapha.models\|from django.db' giapha/services/*.py`
  returns nothing. The two ORM writes are correctly in the command package, not in
  `services/`; the reasoning in the module docstring is right.
- **Underscore module genuinely excluded from discovery** — PROVEN
  `P3 giapha commands = ['recompute_generations', 'remind_death_anniversary']`
  (Django's `find_commands` skips `_`-prefixed modules).
- Behaviour preserved in the move: `SEND_ERROR`, `deactivate_dead`, `log_attempt` moved
  verbatim plus the M3 `return False`; test patch targets updated (`REMIND_BEFORE`/`REMINDER_LOG`
  constants); `run_on` still patches `today_vn` in the command module, so the real path is
  still what runs.
- Line counts after the split: `fcm.py` 149, `fcm_auth.py` 151, command 176,
  `_gio_reminder_log.py` 63, `views/gio_follow.py` 175. All under 200.

### Remaining Medium/Low — spot-check

| # | Verdict | Evidence |
|---|---|---|
| M2 | FIXED | per-recipient `try/except` around `deactivate_dead`/`log_attempt`; `LogFailureIsolationTests` asserts both recipients attempted after the first log raises |
| M3 | FIXED | `IntegrityError` branch returns `False`; test asserts `đã gửi 0` |
| M4 | PARTIALLY FIXED, reasonably declined | `DELETE` no longer requires a giỗ (undeletable trap gone); the row is still invisible in `GET`. Residue is cosmetic and the decline is argued |
| M5 | FIXED | `_setting()` prefers `settings`, falls back to env; `FIREBASE_CREDENTIALS_*` declared in `djangopj/settings.py`; cache keyed on `(project_id, client_email, private_key_id)` — never secret material — with a real two-account test |
| L1 | FIXED (doc) | docstring now says `visited` is the real guard and the counter is unreachable; counter kept — declining removal is right, it is a public signature |
| L2 | FIXED | `deployment-guide.md:47` now says compose *does* forward both vars |
| L3 | FIXED | `services/__init__.py` re-exports nothing; no caller broke (only submodule imports remain) |
| L4 | FIXED | `__all__` re-alphabetised, `clan_edges_all` exported |
| L5 | FIXED (recorded) | takeover risk written up as an accepted decision in `views/device.py` module docstring |
| L6 | FIXED | `status` is now read by `notified_pairs`; model docstring states `error` is write-only |

---

## New defects introduced by the fixes

**NEW-1 (Low) — `update_or_create` can downgrade a `sent` log row to `failed`, causing a
duplicate push.** `_gio_reminder_log.log_attempt`. PROVEN (P4 above). Only under
overlapping runs, which the updated deployment guide makes more likely by telling operators
to re-run after an outage. Cheap mitigations: exclude `status='sent'` from the update
(`update_or_create` on a filtered queryset, or an explicit `create`-then-`update`-if-failed),
or take a DB lock / `flock` for the command. Not blocking.

**NEW-2 (Medium) — H2's classification stops at the mint call; a transient *read* of the
credentials file is still "not configured" and still abandons the run.**
`services/fcm_auth.py:83-88`. PROVEN (P6 above). Fix shape matching the one already chosen:
let `credentials_info()` raise `FcmTransientError` on `IOError`/`OSError` (keep `None` for
"unset" and for `ValueError`/malformed JSON), and cache the parsed info for the run so the
file is read once rather than per recipient.

**NEW-3 (Low) — a member bound to a soft-deleted node silently resumes receiving reminders.**
Side effect of the `clan_edges_all` widening in `views/gio_follow.py` + the command.
PROVEN (P2c). Decide and pin it with a test; today `toi-la` forbids creating that binding
while the resolver honours it.

No new Critical or High.

---

## Metrics

| | |
|---|---|
| Tests | 469 passed, 4 skipped (re-confirmed after probe deletion) |
| Migrations | `--check --dry-run` clean |
| Probes | 12 cases, 6 classes, deleted; 3 new defects found, 0 Critical/High |
| Revert spot-check | C1 — red as claimed, restored byte-identical |
| Files > 200 lines | none |
| Linting / type coverage | not measured (no flake8/ruff config; project has no annotations) |

## Score

**8.5 / 10. Shippable.**

The four blocking findings (C1, H1, H2, H3) are genuinely closed, not papered over: the
regression tests reach the branches they name, the query budgets held, and the one revert
I re-ran went red on cue. The scope widening was the right judgement and provably does not
expose a soft-deleted person. What is left is one Medium of the fixer's own making
(NEW-2 — the same bug class as H2, one function to the left) and two Lows; none of them
loses a reminder on a normal day, and all three are small, well-understood follow-ups.
Ship phase 6; put NEW-2 at the top of phase 7's list, since a credentials rotation is a
routine operation and it currently costs a whole run.

## Unresolved questions

1. NEW-1: is a duplicate push worse than a lying `sent` row? Choosing "never downgrade
   `sent`" trades the audit truth for the user's inbox — I would take that trade, but it is
   the product's call.
2. Concurrency: `remind_death_anniversary` takes no lock at all. Two cron hosts, or a
   manual re-run over the nightly one, is the precondition for NEW-1 and for plain
   double-sends. Is a single-runner guarantee an assumption we can state, or does the
   command need a lock?
3. NEW-3: should soft-deleting a person also stop the member bound to them, or is a
   soft-deleted node with a live member simply a data error the tree UI should refuse?
4. Carried over unfixed from the previous review and still open: `gio_remind_before_days`
   being mutable mid-year (a person's single due day can be skipped over entirely — H1's
   retry cannot help, they were never due), and `apis/management/commands/remind_appointment_date.py`'s
   `localdate()` timezone bug (out of scope by instruction, still a real bug).
5. Real-handset delivery still blocked on the Firebase service account; nothing in this
   verification depended on it.

---

**Status:** DONE_WITH_CONCERNS
**Summary:** All five named findings (C1, H1, H2, H3, M1) plus M2–M5 and L1–L6 are really
fixed — verified by executed probes, not by reading — and the two risky moves (the
`clan_edges_all` widening and the two file splits) are clean, with no soft-deleted person
reachable from any API response. Three new defects fell out of the fixes: one Medium
(H2's classification missed the credentials-file read, so a rotation mid-run still abandons
the run and prints "not configured") and two Low.
**New Critical:** 0 · **New High:** 0 (1 new Medium, 2 new Low)
