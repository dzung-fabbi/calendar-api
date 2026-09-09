# System Architecture

Django 3.1 + Django REST Framework service with two independent apps. **`apis/`** serves
Vietnamese almanac data (hiệp kỷ, thần sát, tiết khí, sao, tử vi số học). **`giapha/`**
serves Vietnamese family-tree (gia phả) records. MySQL 5.7 storage; OAuth2 (django-oauth-toolkit,
`grant_type=password`) for authenticated endpoints. The two token endpoints themselves live
outside both apps, in `djangopj/auth_token_views.py` -- a thin DRF shim over
django-oauth-toolkit, kept because DOT's own views accept form-encoded bodies only and
shipped clients send JSON. Password grant is the only login flow.

## Layers

Both apps follow identical layering:

```
apis/ | giapha/
├── models/      ORM only. No behaviour beyond field definitions.
├── selectors/   Bulk read helpers. Everything that batches or prefetches.
├── services/    Calculation. No ORM, no request. Unit-testable in isolation.
├── serializers/ Response shaping.
├── views/       HTTP: validate params -> selectors/services -> serializers.
├── admin/       Django admin, inlines built by factory.
├── management/  Batch jobs (cron entry points). May hold ORM writes services cannot.
└── tests/       Snapshot, value, query-count, service, security suites.
```

The dependency direction is one-way: `views -> serializers/selectors/services -> models`.
`services/` imports nothing from Django's ORM, which is what lets it be tested
with `SimpleTestCase` (no database).

**The rule is "no ORM", not "no I/O".** `giapha/services/fcm.py` performs HTTP and still
belongs there; what it may not do is write a model. See "Push Notification Channel".

**Decoupling rule:** `giapha/` and `apis/` share no imports; code is duplicated if needed.
This is enforced to allow independent evolution.

## Directory structure (giapha/)

```
giapha/
├── models/
│   ├── __init__.py
│   ├── clan.py
│   ├── person.py
│   ├── marriage.py
│   ├── member.py              # ClanMember (person binding for reminders)
│   ├── invite.py              # ClanInvite
│   ├── notification.py        # GioFollow, DeviceToken, GioNotificationLog
│   └── photo.py               # Photo references and CORS config
├── selectors/
│   ├── person.py              # clan_edges, clan_edges_all, clan_kinship_rows
│   ├── gio.py                 # deceased_with_lunar_death (death anniversary queries)
│   ├── kinship.py             # clan_kinship_rows, clan_spouse_pairs
│   └── gio_follow.py          # overrides_for_clan, active_tokens_for
├── services/
│   ├── vn_lunar.py            # VIETNAMESE lunar calendar UTC+7 (deliberate split from apis)
│   ├── gio.py                 # giỗ (death anniversary) date computation
│   ├── can_chi.py             # Heavenly Stems / Earthly Branches (10-line copy from apis)
│   ├── gio_follow.py          # Ancestor resolution for reminders
│   ├── person_rules.py        # Validation: cycle detection, generation propagation
│   ├── kinship_*.py           # Kinship calculation (7 modules, phase 7)
│   ├── fcm.py                 # Firebase Cloud Messaging (HTTP v1, unverified end-to-end)
│   └── storage.py             # S3/R2 presigned URLs (unverified end-to-end)
├── views/
│   ├── clan.py
│   ├── person.py
│   ├── marriage.py
│   ├── gio.py                 # GET /clans/{id}/lich-gio
│   ├── gio_follow.py          # Follow overrides
│   ├── member_binding.py      # /toi-la endpoint
│   ├── device.py              # /devices token management
│   ├── kinship.py             # GET /clans/{id}/xung-ho
│   ├── invite.py
│   ├── photo.py               # /photo-upload-url, /photo, /photo-urls
│   ├── public.py              # Public share endpoint (noindex header)
│   └── params.py              # Common parameter parsing
├── serializers/
│   └── ...
├── admin/
│   └── ...
├── management/
│   └── commands/
│       └── remind_death_anniversary.py   # Nightly cron job
├── migrations/
│   └── ...
└── tests/
    ├── factories.py           # Fixture builders
    ├── snapshots/
    │   └── query_budgets.json # Query count assertions
    ├── test_api_snapshots.py  # Response shape validation
    ├── test_query_counts.py   # Query ceiling enforcement
    ├── test_security.py       # Authorization, PII isolation
    └── test_*.py              # Unit and integration tests
```

## The lunar calendar split: Vietnamese vs. Chinese

**`apis/` uses `lunarcalendar` (Chinese, UTC+8). `giapha/` uses `vn_lunar.py` (Vietnamese, UTC+7).
This split is DELIBERATE and VERIFIED. Do not unify them.**

The two calendars diverge whenever a new moon falls near the UTC day boundary:

| Year | Vietnamese | Chinese | Divergence |
|---|---|---|---|
| 1968 | 29/01 | 30/01 | 1 day |
| 1969 | 17/02 | 18/02 | 1 day |
| 1985 | **21/01** | **20/02** | **Full month** (leap month placement differs) |
| 2007 | 17/02 | 18/02 | 1 day |

A giỗ (death anniversary) calculated against the wrong calendar puts the ceremony on the
wrong day, defeating the entire purpose of a genealogy app. `vn_lunar.py` implements Hồ Ngọc
Đức's algorithm (the Vietnamese standard reference) and has been verified against the original
`amlich.js` across all 146,097 days from 1800–2199 with zero discrepancies.

`apis/` keeps `lunarcalendar` because its almanac snapshots depend on it; `giapha/` must not
import it. If pressure arises to "fix" the 1985 date to Feb, that is the signal that this doc
failed — the date **is correct**: Vietnamese families held giỗ on 21/01/1985, not 20/02. The
calendar belongs to the cultural context, not to the astronomical one.

### Known limitations (documented, not bugs)

**Lunar calendar timezone before 1968.** `vn_lunar.py` hard-codes `TIMEZONE = 7` (UTC+7).
Vietnam actually used UTC+8 in 1943–45, 1947–55, and 1960–67. Dates before 1968 are off by
~8 hours, enough to flip the lunar month near a new moon. Does not affect `GET /lich-gio`
(only scans forward). **Will** affect any future "enter ancestor's solar death date" feature
for pre-1968 ancestors — exactly this app's subject matter. Flagged as a deferred enhancement
(needs a timezone lookup table). See `docs/deployment-guide.md` and
`plans/260905-1053-gia-pha-dong-ho/plan.md` (open question 10).

**Clan size limit: 5,000 persons.** Python tree walk uses no SQL recursion (MySQL 5.7 has
none). Setting `MAX_CLAN_PERSONS = 5000` in `djangopj/settings.py` is the architectural
limit; going beyond requires materialized path or closure table (out of scope). Hit this
limit only when a user reports a clan larger than 5,000 members and demonstrates the need.

**End-to-end delivery unverified: FCM push and S3/R2 upload.** Every test mocks the Firebase
and boto3 layers. Recipient resolution, de-duplication, failure classification are proven;
that a real handset receives a push or that a real bucket accepts an upload is not. See
`docs/deployment-guide.md` for smoke-test procedures when connecting to live services for
the first time.

## Data model shape (apis/)

The schema is unusually wide: the twelve hours of a day and the twelve months
of a thần sát year each get their own through-table (`SaoHour1..12`,
`SaoMonth1..12`) rather than one table with an `hour` / `month` column. That is
the single largest remaining performance constraint -- see
`docs/codebase-summary.md`.

Column definitions for the twelve monthly tables live on one abstract base
(`SaoMonthBase`); Django names each concrete table after its own class, so this
is a source-level change with no schema effect.

## Account management (apis/)

Login and logout are OAuth2 (`/auth/token`, `/auth/revoke-token`, served by the shim at
`djangopj/auth_token_views.py`). Everything else about an account lives in `apis/` under
`/api/auth/*` and `/api/me`. Nothing here imports `giapha/`.

**Email is the identity.** Registration writes the address to both `auth_user.username`
and `auth_user.email`, lower-cased, so a new account works with the existing password
grant unchanged. `username` is the unique column and is therefore what every lookup keys
on; `auth_user.email` has no unique constraint in stock Django and cannot be trusted to
identify a row.

**Password reset is a stateful 6-digit OTP**, not `django.contrib.auth.tokens`. That
generator is stateless and cannot express the three controls a short numeric code needs:
a per-code attempt counter, single use, and a short absolute lifetime. With a keyspace of
only 10**6, those controls *are* the security — the code's own entropy is not. Hence
`apis/models/password_reset.py`.

The code is stored as an HMAC-SHA256 keyed on `SECRET_KEY` and bound to the user id, not
as a password hash: a slow hash buys nothing over a million values, while a key held
outside the database means a table dump alone yields nothing. See `apis/services/otp.py`.

**Defence in depth, weakest layer first.** The per-IP throttle scopes are the weakest —
`NUM_PROXIES` is 0 and there is no shared `CACHES` backend, so buckets are per-process and
keyed on `REMOTE_ADDR`. What actually holds is per-code and per-user state: one live code
at a time, dead after 5 wrong guesses, expired after 10 minutes, and at most 3 requests per
hour per account. Lockout is per *code*, never per account — an account-level lock would
let anyone who knows an address deny service to its owner.

**Both password-changing paths revoke every token.** `apis/selectors/auth_tokens.py`
deletes rather than calling `revoke()`, because `RefreshToken.revoke()` in
django-oauth-toolkit 2.2.0 is a *soft* revoke that the refresh grant still honours inside
`REFRESH_TOKEN_GRACE_PERIOD_SECONDS`. Refresh tokens are deleted first: the FK between the
two models is `SET_NULL`, not a cascade, so the other order leaves live refresh tokens
behind.

**No account enumeration on reset.** `forgot-password` returns one identical 200 for an
unknown address, an inactive account, a rate-limited user and a failed send. The failed-send
case is the subtle one — a send is only attempted for accounts that exist, so surfacing its
failure would leak exactly the fact being protected.

## Giapha Design Decisions

**Python tree traversal, not SQL recursion.** MySQL 5.7 has no `WITH RECURSIVE`.
The entire clan (up to 5000 persons) loads in one `selectors/` query and is
walked in Python. Closure table / materialized path were rejected as over-engineering
at this scale; the limit lives in `settings.MAX_CLAN_PERSONS` and would need to
change first before SQL recursion became cost-justified.

**`GET /tree` is a hard 3-query contract**, asserted per-test by `assertNumQueries`.
One query checks permission; one fetches all `Person` rows; one fetches all `Marriage`
rows. Parent edges are derived from already-fetched rows. Nodes are intentionally lean
(no `tieu_su`, `que_quan`, details) -- depth comes from `GET /persons/{pid}`.
Layout coordinates are computed client-side.

**`generation` is derived state**, computed by topological walk, persisted on write,
and never client-writable. Subtree recompute on parent change uses `bulk_update`;
whole-clan recompute is a management command, kept out of request paths.

**Cycle safety is defence-in-depth.** Parent-child cycles are rejected at API write time,
but Django admin bypasses serializer validation entirely, so every graph walk must also
survive corrupt data -- bounds fail CLOSED (raise) rather than returning partial results,
because a partial descendant set would let a real cycle pass the API validation gate.
The one deliberate exception is `services.gio_follow.ancestors`, which fails OPEN because
it feeds a background job rather than a write gate -- see "Push Notification Channel".

**Three edge shapes exist on purpose; do not unify them.** Each answers a different
question, and the docstrings say `DO NOT UNIFY` for a reason.

| Selector | Shape | Soft-deleted rows | Used by |
|---|---|---|---|
| `person.clan_edges` | `(id, father_id, mother_id)` | **excluded** — the *visible tree* | tree payload, generation walk, `person_rules`, `recompute_generations` |
| `person.clan_edges_all` | `(id, father_id, mother_id)` | **included** — *connectivity* | giỗ-follow resolution only (`views/gio_follow.py`, `remind_death_anniversary`) |
| `person.clan_kinship_rows` | `{id, father_id, mother_id, birth_order, gioi_tinh, ho_ten}` | excluded | the xưng-hô calculator only |

- `clan_edges_all` exists because a soft-deleted person is still `father_id`/`mother_id`
  on their children: walking the filtered list stops dead at them, which once cut `cụ`,
  `kỵ` and everything above out of every descendant's giỗ reminders. It is safe only
  where the *answer set* is separately restricted to live people.
- `clan_kinship_rows` exists because the calculator needs three more columns
  (`birth_order` decides bác vs chú, `gioi_tinh` decides chú vs cô, `ho_ten` names the
  common ancestor) and widening `clan_edges` was not an option: its consumers unpack rows
  as exactly three positional values. It returns **dicts** precisely so it can grow a
  column later without touching a consumer.

**Authorization:** three permission classes keyed off `clan_id` in URL; role is cached
on request (≤1 query per check). Non-members receive **404, never 403** -- a 403 would
confirm the clan exists.

**Soft delete** on `Clan.is_deleted` and `Person.is_deleted`; every selector filters
`is_deleted=False` consistently or the tree silently fractures.

**Invites** grant editor/viewer only (never owner -- ownership transfers via member PATCH).
Default 30-day expiry, revocable, and redeemable only once. Redemption locks the row
with `select_for_update` inside `transaction.atomic` and re-checks role, because admin
can write invite rows that bypass the serializer. `/join` is the only throttled endpoint
in the project (`giapha-join` scope: 10/hour).

## Push Notification Channel (Phase 6)

The first outbound channel in this codebase: everything before it was request/response
only. One nightly management command, no Celery — one job a day does not justify a broker.

> **Status: real-device delivery is UNVERIFIED.** No Firebase project has been created,
> and every test mocks the FCM layer (`requests.post`, `_mint_token`, `send_multicast`).
> What is proven is recipient resolution, de-duplication, and failure classification.
> What is not proven is that a handset ever receives a notification.

### Follow resolution: computed, never stored

The set of people a user is reminded about is **resolved at send time**, not materialised.

```
ClanMember.person   "I am this node"        (one row per member, nullable)
        |
        v
services.gio_follow.ancestors(edges, self_person_id)
        |                       ^
        |                       |  selectors.person.clan_edges_all
        |                          (INCLUDES soft-deleted rows)
        v
   default set = direct-line ancestors (father AND mother, no gender filter,
                 no descendants, no collaterals)
        |
        +-- GioFollow(enabled=True)  -> add     (source: thu-cong)
        +-- GioFollow(enabled=False) -> remove  (source: da-bo)
        |
        v
   followers_by_person -> {person_id: {user_id, ...}}
```

Consequences that follow directly from this design:

- Editing `father` / `mother` in the tree changes every affected follow set immediately.
  **There is no re-sync job and none is needed.**
- Three states, not two — hence both `PUT` and `DELETE` on an override. Without `DELETE`
  a user who switched an ancestor off could only get back to a manual "on" that no longer
  tracks the tree.
- **A member with no binding receives nothing by default.** Guessing which node a user is
  would push another family's giỗ at them; silence is the honest answer.
- Traversal uses `clan_edges_all`, so a soft-deleted ancestor does not sever the line
  above them. Nobody is ever notified *about* a soft-deleted person — the candidate set
  comes from `deceased_with_lunar_death`, which filters `is_deleted=False`.
- `overrides_for_clan` joins `ClanMember` as a **privacy guard**: removing a member drops
  their membership row but leaves their `GioFollow` rows standing, and without the join
  an ex-member would keep receiving a deceased person's name from a clan that now answers
  404 to them on every endpoint. The rows survive so rejoining restores preferences.

**Cycle policy inverts here.** `services.gio_follow.ancestors` fails **OPEN** (returns the
partial set) where `services.person_rules.descendants` fails **CLOSED** (raises). Both are
correct: `descendants` gates a write, so a partial answer would let a real cycle through
the validation gate; `ancestors` feeds a nightly batch, where missing a few recipients
beats killing the run.

### Send path

```
cron (Vietnam morning)
  -> manage.py remind_death_anniversary
     -> collect_due(today_vn())        reads + arithmetic only
        per clan: deceased_with_lunar_death  <-- EARLY EXIT if nothing due
                  clan_edges_all / binding_map / overrides_for_clan
                  followers_by_person -> active_tokens_for
        -> [GioJob(..., recipients={user_id: [token]})]
     -> dispatch(jobs)                 the only half that touches the network
        notified_pairs()               one query, status='sent' only
        services.fcm.send_multicast()  HTTP v1, one POST per token, shared bearer
        _gio_reminder_log.deactivate_dead() / log_attempt()   the only ORM writes
```

**Query budget: 1 per clan on a quiet day.** `deceased_with_lunar_death` runs first and
the clan is abandoned before the other four queries whenever nothing is due — which is
almost every clan on almost every day. Reordering that early exit multiplies a nightly
job's cost by five per clan.

**Timezone is load-bearing.** The command computes today with `services.gio.today_vn()`,
never `timezone.localdate()`. `settings.TIME_ZONE` is `'UTC'` with `USE_TZ=True`, so a
cron firing before 07:00 Vietnam time would otherwise compute the *previous* day and send
every reminder one day off.

**Layering holds even with a network.** `services/fcm.py` performs HTTP but touches no
ORM: it *reports* a dead token, and the command deactivates it. That is why
`_gio_reminder_log.py` sits under `management/commands/` rather than in `services/`.

### Failure taxonomy — three outcomes, deliberately distinct

| Condition | Signal | Effect |
|---|---|---|
| No / malformed credentials | `send_multicast` → `{}` | Command warns, exits **0**, no stacktrace. Cron stays quiet. |
| Credentials file unreadable *right now* (rotation, flaky mount) | `FcmTransientError` → `{token: network_error}` | **Retriable**, not "unconfigured". The rest of the batch continues. |
| `UNREGISTERED` / `INVALID_ARGUMENT` from FCM | matched against `DEAD_TOKEN_RESULTS` | `DeviceToken.is_active = False`. |
| 5xx, timeout, DNS | `network_error` | Token stays **active**; `failed` log row; retried on the next run. |

Collapsing "unconfigured" into "transient" once abandoned every remaining recipient of a
run *and* printed "Firebase is not configured" in a run where a push had already gone out.
`{}` from `send_multicast` means "nothing to attempt with" and nothing else.

### De-duplication and retry

`GioNotificationLog`'s `unique_together ('person','user','solar_date')` is the guarantee;
`notified_pairs()` reads it up front so a second run of the same day sends nothing rather
than sending and only then failing to record it.

**Only `sent` rows block.** A `failed` row must not, because a person is due on exactly
one calendar day a year (`target = today + gio_remind_before_days` advances with `today`)
— a pair blocked by a failed attempt would never be retried at all, and a 07:00 DNS blip
would cost that ancestor their giỗ notice for a year.

### Security posture

- Device tokens are credentials: accepted in a body, **never** returned in a response,
  redacted to a 6-char prefix plus length in every log line.
- **Accepted risk, recorded not overlooked:** the `POST /devices` upsert is keyed on
  `token` alone, so whoever presents a token owns it from that moment. Required for the
  shared-handset / re-login case; it also means anyone who learns another user's FCM token
  can redirect that handset's reminders. The read direction stays safe and the write is
  authenticated. Revisit the spec before "fixing" it.
- The service account JSON must never be committed.

## Kinship Calculator (Phase 7)

`GET /clans/{id}/xung-ho?a=&b=` answers "what do these two people call each other?".
Everything below `views/kinship.py` is **pure**: two selectors load scalars, and the whole
resolution runs in memory over those rows. No model, no migration, no new setting.

### Pipeline — one module per concern

```
views/kinship.py       a defaults to ClanMember.person; validates both ids against the rows
   |  clan_kinship_rows(clan_id)                       <-- 1 query, dict rows
   v
services.kinship.resolve_kinship(rows, a, b, spouses=None)
   |
   +-- a == b                       -> unrelated(cung_mot_nguoi)
   |
   +-- kinship_graph.ancestor_index(rows, a) / (rows, b)   BFS up: {id: (depth, side, via)}
   |   kinship_graph.best_common_ancestor(...)             nearest = min(depth_a + depth_b)
   |        found -> kinship_blood.blood_result
   |                     kinship_lookup.resolve_term(kind, gap, side, gender, elder)
   |                        -> TERMS / AMBIGUOUS_TERMS      (kinship_terms.py, data only)
   |
   +-- not found, and only then:  clan_spouse_pairs(clan_id)   <-- 1 more query, lazily
            married to each other  -> vo / chong
            kinship_affinal.affinal -> through B's spouse, else through A's (mirrored)
                 kinship_marriage_rows.ranked_spouses_of     which marriage wins
                 AFFINAL_TERMS[(blood term, spouse gender)]  (kinship_affinal_terms.py)
            still nothing           -> unrelated(khong_cung_huyet_thong)   HTTP 200
   |
   v  kinship_explain.*  the Vietnamese sentence, restating only facts it was handed
```

**What decides the word:** `gap = depth_a - depth_b` (generations B is above A), plus
`kind` (`truc` when one of the pair *is* the common ancestor, `bang` when both hang off
it), `side` (nội/ngoại, from the first step up on that person's own walk), the gender of
the person being named, and the seniority of the two **branches** at the common ancestor.
The raw depth pair is reduced to `(kind, gap)` before lookup, because an uncle (`2,1`) and
a father's cousin (`3,2`) share one word — keying on the pair would need an unbounded
table.

Each direction is resolved independently: B may be bên nội to A while A is bên ngoại to B.

### Never guess — enforced by the table, not by policy

`TERMS` stores an entry under a `None` slot **only where that fact genuinely does not
change the word**. Every seniority-bearing row (`gap == 0` and `gap == 1`) is stored under
`elder=True`/`False` only, so a missing `birth_order` cannot find one: the lookup falls
through to `AMBIGUOUS_TERMS` and returns a hedge (`bác/chú`) with `confident: false` and a
`reason` slug naming the field to fill in. Getting vai vế wrong is a real insult, so the
code is built to be *unable* to produce it.

- The hedge lists only options the known facts leave open (`anh/chị`, not `anh/chị/em`,
  when B's branch is known to be the elder) — both tables are widened by one generator
  over the same five slots, so a hedge can never contradict the confident word printed
  beside it.
- A hedge propagates through the in-law table as a hedge (`bác/chú` → `bác gái/thím`).
- Where one word covers both genders (`bác` for an elder sibling of either parent), a
  missing `gioi_tinh` still answers confidently — hedging there would throw away
  certainty and buy no honesty.
- `common_ancestor` is `null` and all three `path` fields are `null` on every in-law
  answer: the only walk that exists there runs between A and B's *spouse*, so `b_up`
  would count generations for someone not descended from that ancestor at all.

### Which marriage the answer routes through

`clan_spouse_pairs` keeps `goa` rows (a widow stays her late husband's family's thím) and
drops `ly_hon`, so one person can have several live marriage rows.
`kinship_marriage_rows.ranked_spouses_of` states the order once:

1. a marriage that is **not** `goa` outranks one that is;
2. among equals, the lower `Marriage.order` (vợ cả before vợ lẽ; `None` reads as 1);
3. the id, purely to make the list stable.

**The id is the tie-break, never the decision.** `rank` is steps 1–2 only, so when two
equal-rank candidates disagree, `kinship_affinal` hedges with
`nhieu_hon_nhan_ngang_hang` instead of letting autoincrement — i.e. data-entry order —
decide. Not hypothetical: ranking by id once routed the wife of a younger brother through
her dead elder husband and told her to call his elder brother `em`.

Affinity is walked from **both** sides but only **one hop**: B married in (the ordinary
"what do I call my uncle's wife?") *and* A married in (the con dâu asking about her
husband's family — the likeliest caller, since `a` defaults to her own binding). A person
who married in borrows their spouse's own word, with one substitution:
`MARRIED_IN_SUBSTITUTES` strips `nội`/`ngoại`, because those assert descent the speaker
does not have (`ông nội` → `ông`).

### A link without a word is not "no link"

`khong_cung_huyet_thong` (`confident: true`) asserts there is no relation at all and is
reached only after both marriage walks came back empty. A marriage that *was* found but
has no everyday Vietnamese word answers `term: null, confident: false,
khong_co_tu_xung_ho_thong_dung`, naming the spouse it went through. Merging the two would
tell a user their own stepmother is unrelated to them.

### `reason` is a wire contract

Every `reason` is an **ASCII slug** — it is the field a client branches on. Vietnamese
prose reaches a user only through `explain`; `REASON_LABELS` in `kinship_terms.py` is the
single place the two meet. Half these values used to be diacritic Vietnamese that a mobile
client would have had to compare verbatim.

### Traversal safety

`ancestor_index` fails **OPEN** (returns what it has) — this is a read, and a 500 helps
nobody; contrast `person_rules.descendants`, which fails closed because it gates writes.
Its safety counter cannot actually fire: `parent_id in index` admits each person once, so
the loop pops at most `len(rows) + 1` times against a budget of `2 * len(rows) + 10`. The
counter is retained because that same `parent_id in index` check is the cycle guard, and
Django admin writes bypass `person_rules.validate_no_cycle`. A *truncated* walk would not
be harmless — it can surface a farther common ancestor and hence a confidently wrong
`gap`, not a null.

**`clan_kinship_rows` is exempt from `settings.MAX_CLAN_PERSONS`**, alone among the bulk
clan reads. The cap truncates, and a truncated row set here does not degrade the answer,
it falsifies it: a dropped ancestor turns a real relative into `khong_cung_huyet_thong`
with `confident: true`. Cost is bounded anyway — one query, six columns, O(clan size).

### Known gaps (deliberate, not oversights)

| Gap | Behaviour |
|---|---|
| `parent_kind` (`ruot`/`nuoi`/`ke`) is ignored | an adopted child is addressed exactly like a natural one — distinguishing would be the surprising behaviour |
| stepmother absent from `AFFINAL_TERMS` (`('bố','nu')`) | falls to the hedge; real usage varies (mẹ / dì / mẹ kế) and picking one is the insult this module exists to avoid |
| both parties married in | `khong_cung_huyet_thong` — naming it (chị dâu = wife of my husband's brother) needs two marriage hops plus a routing rule; out of scope for this phase |
| Northern dialect only | Southern/Central usage differs; a regional variant means a second table keyed by region, not edits to this one |

## Dual Lunar Calendar Implementation

**Two independent lunar calendar implementations exist and must NOT be unified.**

- **`apis/`** uses `lunarcalendar` (PyPI) — Chinese lunar calendar at UTC+8 timezone.
  Used for almanac endpoints (`home`, `than-sat`, etc.). Golden-snapshot tests depend on it.
- **`giapha/`** uses `services/vn_lunar.py` — Vietnamese lunar calendar at UTC+7 timezone.
  Used for giỗ (death anniversary) calculations.

**Reason:** Vietnam and China use different lunar calendars. Historical Tết divergences:
1968, 1969, 1985, 2007. Most critical: 1985, where the intercalary month placed Vietnam's
Tết on 21/01 and China's on 20/02 (full month apart). Using the Chinese calendar for a giỗ
would place the anniversary on the wrong day — the core reason the `giapha` module exists.

**Package isolation:** `giapha/` shares no imports from `apis/`. Code duplication is
deliberate (e.g., `giapha/services/can_chi.py` copies `apis/services/can_chi.py`).
This boundary is enforced to allow independent evolution.

**`vn_lunar.py` verification:** Differential against Hồ Ngọc Đức's own `amlich.js` over
1800–2199 (both directions): 0 mismatches. Cross-check against `lunarcalendar` at tz=8
over 1950–2050: 0 mismatches. Supported range: 1800–2199. No external dependency.

**Known limitation:** `vn_lunar.TIMEZONE` is fixed to 7. Vietnam used UTC+8 during
1943-01-01..1945-09-14, 1947-04-01..1955-06-30, 1960-01-01..1967-12-31. Converting a
solar date inside those windows disagrees with the calendar in force at the time on ~230
dates. The `lich-gio` endpoint never hits this (sweeps forward from modern windows), so
current code is correct. Any future "enter ancestor's solar death date" feature requires
a `tz_for_date()` lookup table first.

## Request path, `/api/home` as the example

1. `views/params.py` validates and coerces the query string; a bad parameter is
   a 400 that names the parameter.
2. `selectors/stars.py` supplies `Prefetch` objects that join each through-table
   to `sao` (and `sao.category` where the serializer renders it).
3. `serializers/` walk only prefetched relations -- `star_payload()` reads
   `row.sao` and must never be handed an unprefetched queryset.

## Collation dependency

The app relies on MySQL's case-insensitive `utf8_unicode_ci`: `HomeAPIView`
matches one `lunar_day` parameter against `HiepKy.lunar_day` (stored upper-case)
and `QuyNhan.can_ngay` (stored capitalised). The test suite therefore runs
against real MySQL, not SQLite -- see `djangopj/settings_test.py`.

`CalendarAPIView` indexes days in memory with an upper-cased key and falls back
to a database lookup when that misses, so the looser SQL matching is preserved.

## Configuration

All secrets and environment-specific values come from environment variables;
see `.env.example`. `djangopj/settings_test.py` supplies test defaults.
