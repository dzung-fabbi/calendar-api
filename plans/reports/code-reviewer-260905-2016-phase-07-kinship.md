# Code Review — Phase 07 Máy tính xưng hô (giapha)

- Date: 2026-09-05
- Reviewer: code-reviewer (adversarial pass, review only, no fixes applied)
- Spec: `plans/260905-1053-gia-pha-dong-ho/phase-07-may-tinh-xung-ho.md`
- Implementer report: `plans/reports/fullstack-260905-1918-phase-07-kinship.md`
- Suite re-confirmed after review: **533 passed / 4 skipped**, tree left unmodified.

## Scope

`giapha/services/kinship{,_graph,_lookup,_terms,_explain}.py`,
`giapha/serializers/kinship.py`, `giapha/views/kinship.py`,
`giapha/selectors/person.py::clan_kinship_rows`,
`giapha/selectors/marriage.py::clan_spouse_pairs`, `giapha/urls.py`,
three `__init__.py` re-exports, `giapha/tests/test_kinship{,_api}.py`.
~1512 LOC. All findings below were reproduced with throwaway probes against the
real modules (probes deleted).

## Verdict

**NOT SHIPPABLE — 6/10.**

Architecture, layering, purity, auth, docstrings and the `never guess`
*mechanism* are genuinely good. The vocabulary table — which is the entire
feature — contains two classes of **confidently wrong vai vế**, which is the
one failure mode the plan says must not exist. Fix C1/C2/H1/H2/H3, re-run,
re-review. This is a table + 4-line fix job, not a redesign.

---

## Critical

### C1 — Collateral descending ladder is one rung too deep. Confidently wrong.
`giapha/services/kinship_terms.py:83-92`

The ascending collateral ladder is `+1 bác/chú` `+2 ông` `+3 cụ` `+4 kỵ`.
The descending one is `-1 cháu` `-2 chắt` `-3 chút` `-4 chít`. Those two do not
reciprocate. Standard Vietnamese pairs are ông↔cháu, cụ↔chắt, kỵ↔chút
(con-cháu-chắt-chút-chít is a 5-rung ladder measured from self; the code's own
`TRUC` block gets it right at lines 106-112, so the file contradicts itself).

Reproduced (probe, small clan; `Bac` and `Bo` are brothers, `Con` is `Bo`'s
grandson):

```
Bac -> Con : a_calls_b='chắt'  b_calls_a='ông'   confident True/True
Bac -> Chau: a_calls_b='chút'  b_calls_a='cụ'    confident True/True
Co  -> Con : a_calls_b='chắt'  b_calls_a='bà'    confident True/True
```

`ông ↔ chắt` is not a pair. Your brother's grandson calls you `ông`; you call
him **`cháu`**, not `chắt`. Shipping `chắt` tells a great-uncle he is a
great-*grand*father to that child — exactly the "sai vai vế" the plan bans, and
it comes back `confident: true`.

This also contradicts the plan's own table (`chênh 3 đời → chắt`; the code emits
`chắt` at a 2-generation gap).

Fix — `TERMS`, collateral descending block:
```python
(BANG, -1, None, None, None): 'cháu',
(BANG, -2, None, None, None): 'cháu',   # reciprocal of (BANG, 2) = ông/bà
(BANG, -3, None, None, None): 'chắt',   # reciprocal of (BANG, 3) = cụ
(BANG, -4, None, None, None): 'chút',   # reciprocal of (BANG, 4) = kỵ
(BANG, -5, None, None, None): 'chít',
```
and bump `MAX_TABLE_GAP` handling so `-5` is reached before `hậu duệ`
(`kinship_lookup.py:99`). Then add a **reciprocal-invariant test** (see M6).

### C2 — Your own wife can be returned as `chị`, `confident: true`.
`giapha/services/kinship.py:145-147`

`_through_marriage` iterates `sorted(_spouses_of(spouses, b_id))` and only
checks `spouse_id == a_id` *inside* the loop. If B has more than one
non-divorced marriage recorded and the other partner sorts lower by id, the
blood/affinal branch wins before the "this is my own spouse" branch is reached.

Reproduced:
```
rows:  Bo(1); Anh(5, f=1, bo=1); Toi(9, f=1, bo=2); Vo(20, nu)
spouses: [(5,20), (9,20)]        # widowed from Anh (status 'goa', kept by design), now married to Toi
resolve_kinship(rows, 9, 20) -> a_calls_b {'term': 'chị', 'confident': True}
explain: "Vo kết hôn với Anh. Toi gọi Anh là anh, nên xưng hô với Vo theo quan hệ hôn nhân đó."
```
Swap the ids so `a_id` sorts first and the same data returns `vợ`. The answer
depends on autoincrement order.

Not exotic: `clan_spouse_pairs` deliberately keeps `goa`, so any remarriage
after a death — including levirate remarriage, which is what produced this
exact shape historically — lands here. Telling a man his wife is his brother's
wife, with `confident: true`, is the worst possible output of this endpoint.

Fix — hoist the self-check out of the loop:
```python
partners = _spouses_of(spouses, b_id)
if a_id in partners:
    return _married_couple(by_id, a_id, b_id)
for spouse_id in sorted(partners):
    ...
```

---

## High

### H1 — Missing `birth_order` between siblings/cousins loses the hedge entirely and leaks a raw slug.
`giapha/services/kinship_lookup.py:89-91`, dead rows at `kinship_terms.py:120-122`

`resolve_term` looks the hedge up as `AMBIGUOUS_TERMS[(kind, gap, side, gender)]`
using the **real** `side`, but the three `gap == 0` hedge rows are keyed with
`side=None`. For a collateral pair both depths are ≥ 1, so `side` is *always*
`'noi'`/`'ngoai'` at `gap == 0` — those three rows are **unreachable dead code**.

Reproduced:
```
two full brothers, neither with birth_order:
  a_calls_b -> {'term': None, 'confident': False, 'reason': 'ngoai_bang_tu_vung'}
  explain   -> "... Chưa chắc chắn do ngoai_bang_tu_vung."
one brother has birth_order, the other does not: same result.
first cousins, neither branch ranked:            same result.
```
Expected per the table's own intent and the plan: `anh/em`, reason
`thiếu birth_order`. Instead the user gets *no word at all* plus an ASCII
debugging slug rendered inside a Vietnamese sentence. Same path swallows
`anh/chị/em` when `gioi_tinh='khac'`.

Two families with un-ranked siblings — the common case for a freshly imported
gia phả — see the endpoint answer "không xác định được" for the most basic
question it exists to answer.

Fix: fall back on `side` as well as on `gender`, mirroring
`_candidate_keys`:
```python
for one_gender in (gender, None):
    for one_side in (side, None):
        hedge = AMBIGUOUS_TERMS.get((kind, gap, one_side, one_gender))
        if hedge:
            return {'term': hedge[0], 'confident': False, 'reason': hedge[1]}
```
Note the *root cause*: `_candidate_keys` (line 64) already does side-widening
for `TERMS` and the hedge lookup was written by hand instead of reusing it.
DRY violation with a correctness consequence.

### H2 — Mother's ELDER sibling returns `cậu`/`dì`, `confident: true` — and contradicts the module's own documented dialect.
`giapha/services/kinship_terms.py:79-80` vs its docstring at `:6-9`

Docstring: *"the elder sibling of **either parent** is `bác` regardless of that
sibling's gender, `chú`/`cô` are reserved for the father's YOUNGER siblings,
and `cậu`/`dì` for the mother's."* That is the correct Northern rule.

Table: `(BANG, 1, NGOAI, 'nam', None): 'cậu'` — `elder=None` means *seniority
is irrelevant on this side*, so the elder brother of the mother also gets
`cậu`.

Reproduced:
```
mother birth_order=2, her brother birth_order=1 -> 'cậu'  confident True
mother birth_order=1, her brother birth_order=2 -> 'cậu'  confident True
mother birth_order=2, her sister birth_order=1  -> 'dì'   confident True
```

This is also the direct answer to the "never guess" audit: **this is the one
place a seniority-relevant term comes back `confident: true` with no
`birth_order` backing it.** The structural guarantee holds everywhere else
(verified: `None` really is a literal key, `_candidate_keys` never widens
`elder` into a match that does not exist) — but here the author opted the
maternal side out of seniority on purpose, and the opt-out is wrong for the
dialect the file claims to encode.

Implementer report decision #6 defends this as "per the plan's table and
ordinary Northern usage". The plan's table is a two-line sketch; the file's own
docstring is the more considered statement, and they disagree. One of them must
change; I'd change the table.

Fix:
```python
(BANG, 1, NGOAI, 'nam', True): 'bác',
(BANG, 1, NGOAI, 'nu', True): 'bác',
(BANG, 1, NGOAI, 'nam', False): 'cậu',
(BANG, 1, NGOAI, 'nu', False): 'dì',
```
plus hedge rows `(BANG, 1, NGOAI, 'nam'): ('bác/cậu', REASON_MISSING_BIRTH_ORDER)`
and `(BANG, 1, NGOAI, 'nu'): ('bác/dì', ...)`, and update
`AFFINAL_TERMS` accordingly. Consequence, and it is the right one: the maternal
side stops being silently `confident: true` and starts asking for
`birth_order` like the paternal side.

If the team decides `cậu` for all maternal uncles is what Northern gia phả
users actually expect, then **the docstring must be corrected** — right now the
file documents behaviour it does not have, which is how this kind of bug
survives review.

### H3 — "No blood relation", `confident: true`, returned for people who ARE in-laws.
`giapha/services/kinship.py:156-158` (silent `continue`) → `kinship.py:60-67` (`_unrelated`)

Whenever `AFFINAL_TERMS` has no row for `(blood_term, spouse_gender)`, the loop
`continue`s and the request falls through to `_unrelated(REASON_NO_BLOOD)` —
which sets **`confident: True`**. The docstring calls this "silence chosen over
invention", but the wire format does not say "I don't know", it asserts
"khong_cung_huyet_thong" with full confidence about a person the caller is
demonstrably related to by marriage.

Reproduced — all `{'term': None, 'confident': True, 'reason': 'khong_cung_huyet_thong'}`:
```
B is the wife of A's `cụ`            (no ('cụ', 'nu') row)
B is A's stepmother, married to A's father   (no ('bố', 'nu') row)
B is A's grandfather's second wife   (no ('ông nội','nu') row)
B is the husband of a gender-unknown maternal uncle -> blood term 'cậu/dì' hedged, no ('cậu/dì','nam') row
```
The last one also falsifies the report's claim #10 ("hedges propagate as
hedges"): gender hedges do not propagate at all, they vanish into
"no relation".

Fix (two parts, both small):
1. Add the missing affinal rows, at minimum `('cậu/dì','nam')`,
   `('bác/chú/cô','nu')`, `('cụ',·)`, `('kỵ',·)`, `('chắt',·)`, `('chút',·)`.
2. When a marriage edge WAS found but no word exists, return
   `{'term': None, 'confident': False, 'reason': <'không có từ xưng hô thông dụng'>}`
   with the spouse named in `explain` — not `REASON_NO_BLOOD`. "There is a
   link, I have no word for it" and "there is no link" are different findings
   and the client cannot currently tell them apart.

### H4 — A-side affinity missing makes the endpoint useless for exactly the users who need it.
`giapha/services/kinship.py:174-197` (unresolved question #2 in the report)

`_through_marriage` only walks B's spouses. A person who married *into* the
clan has no blood link to anyone, so every query they make returns
"khong_cung_huyet_thong":
```
A = con dâu mới về; B = her husband's uncle  -> None / khong_cung_huyet_thong
A = con dâu;        B = her husband's father -> None / khong_cung_huyet_thong
```
`a` defaults to `ClanMember.person`, i.e. the caller themselves. A newly
married-in member is the single most likely user of a "what do I call this
person?" feature, and for them the feature returns nothing, ever.

The plan's step 5 does only specify the B-side direction, so this is a scope
gap rather than a spec violation — but it is not a footnote. Minimum for
shipping: mirror the loop over A's spouses (the symmetric case: A calls B by
A's spouse's term). ~8 lines, one extra `ancestor_index` per A-spouse. If it
is deferred, the `khong_cung_huyet_thong` reason must be distinguishable so the
UI can say "chưa hỗ trợ bên dâu/rể" instead of "không có quan hệ".

---

## Medium

### M1 — `common_ancestor` and `path` describe the wrong person on the affinal path.
`giapha/services/kinship.py:165`

For an in-law answer the response carries `blood['common_ancestor']` and
`blood['path']` — the walk between **A and B's spouse**, not A and B:
```
A=Toi, B=Thim (wife of Chu):
  a_calls_b 'thím'; common_ancestor {'id': 1, 'Ong'}; path {'a_up': 2, 'b_up': 1, 'side': 'noi'}
```
`b_up: 1` says Thím is one generation below Ông, which is false — she is not
descended from him at all. `serializers/kinship.py:43-47` documents `path` as
"Generations up from each person to the common ancestor" and explicitly invites
clients to *draw the path*. A client that does will draw a line to a person who
is not on it. Either null the two fields on the affinal path (consistent with
`_married_couple`, which already nulls them) or add a `via` field naming the
spouse the numbers actually refer to.

### M2 — `explain` never mentions the missing field on the affinal path.
`giapha/services/kinship_explain.py:58-67`

`kinship_explain`'s module docstring: *"When `confident` is False the sentence
says which field is missing instead."* `explain_affinal` never calls `_doubts`:
```
a_calls_b {'term': 'bác/thím', 'confident': False, 'reason': 'thiếu birth_order'}
explain   "Vo kết hôn với ?. Toi gọi ? là bác/chú, nên xưng hô với Vo theo quan hệ hôn nhân đó."
```
The user is shown a hedged term with no explanation of what to fill in — the
"nudge the user to enter birth_order" mechanism the plan built the hedge for.
Fix: append `_doubts(a_calls_b, b_calls_a)` in `explain_affinal` as
`explain_blood` does.

### M3 — Query-budget tests assert nothing about the answer; can pass vacuously.
`giapha/tests/test_kinship_api.py:75-95`

None of the three `assertNumQueries` tests assert a status code or a term.
`test_defaulting_a_costs_one_more_for_the_binding` expects 3 — a 400 raised at
`views/kinship.py:84` (binding points at a foreign/deleted person) also costs
exactly 3 and the test stays green. Add `self.assertEqual(200, r.status_code)`
and one term assertion to each.

Separately: the worst case is **4** (default `a` + no blood link:
role + binding + rows + marriages), which is neither pinned nor stated. The
view docstring says "two paths cost one more each" and leaves the reader to
multiply. Spec said ≤ 2. Judgment: the two +1s are individually well reasoned
and I would accept both — the lazy marriage load is the right call, the binding
lookup is unavoidable — but 4 unstated is budget creep. Document the 4 and pin
it.

### M4 — `clan_kinship_rows` is the only bulk clan read that ignores `MAX_CLAN_PERSONS`.
`giapha/selectors/person.py:53-78`

`settings.MAX_CLAN_PERSONS = 5000` caps `/tree`, the gio list, gio_follow, the
person list and the reminder command. This selector loads the whole clan
unbounded, and `resolve_kinship` then builds `parents_of` up to ~6 times per
request on the no-blood path (two `resolve_kinship` calls at
`views/kinship.py:91-94`, each rebuilding both indexes, plus one per spouse
candidate). One query, so the budget claim holds — but memory and CPU are
uncapped where the house convention says they should not be.

I would *not* simply apply the cap: a truncated row set silently produces wrong
"no relation" answers. Correct resolution is an explicit documented exemption
plus a guard (e.g. count first, 400/`truncated: true` above the cap), and
passing `rows` through once instead of re-resolving.

### M5 — Test quality: table-restating tests, and the missing negatives that hid C1/H1/H2.
`giapha/tests/test_kinship.py`

63 tests, 46 of them table-driven — but the ones covering the defects above
assert the table rather than the culture:
- `:193-197` `test_two_collateral_generations_down_is_chat` /
  `test_three_collateral_generations_down_is_chut` **enshrine C1**. Together
  with `:187-191` (`..._up_is_ong` / `..._is_cu`) they *prove* the
  inconsistency; nobody cross-read them.
- No reciprocal-invariant test anywhere. The whole class of C1 is caught by one
  loop asserting `RECIPROCAL[a_calls_b] == b_calls_a` over a generated tree.
- `MissingDataTests` covers `gap == 1` only (`:203-231`). **No case at all for
  a sibling or cousin with a missing `birth_order`** — the exact hole H1 lives
  in, and precisely the "defect hiding in a missing negative case" pattern the
  previous phase's review flagged.
- `test_truncated_walk_never_invents_a_nearer_ancestor` (`:295-301`) asserts
  `index[TOI][0] == 0` and `ONG_NOI not in index`. That is a restatement of the
  loop bound; it pins none of the safety property its name claims (see L1).
- Maternal tests (`:117-130`) never vary `birth_order`, so H2 is invisible.

API-side gaps: no test for a caller **bound in a different clan** (behaviour is
correct — `member_binding` filters on `clan_id` — but unpinned), no
`BINDING_GONE` stale-binding test despite the view having a dedicated message
for it (`views/kinship.py:44-47`), no `a`-from-another-clan test (only `b`).

---

## Low

### L1 — The fail-open safety argument is wrong as stated (though unreachable).
`giapha/services/kinship_graph.py:7-23`, report decision #5

"BFS discovers ancestors in non-decreasing depth order, so a truncated walk can
only MISS a common ancestor, never invent a nearer one — worst case is
`term: null`". The first half is true. The conclusion is not: if truncation
drops the nearest common ancestor, `best_common_ancestor` will happily pick a
**farther** surviving one and return a confident wrong term, not `null`.
Truncation drops whole pops, and two frontier nodes at the same depth are
popped separately — so a same-depth split is possible and the surviving
ancestor can have a different `depth_b`, hence a different `gap`.

In practice the counter cannot fire (`index` admits each id once → at most
`len(rows)+1` pops vs `2*len(rows)+10` budget), so this is a false claim in two
docstrings and a report, not a live bug. Either correct the claim to "cannot
fire; the counter exists only as a backstop for hand-entered cycles", or make
it fail closed. Note the actual cycle protection is `parent_id in index`
(line 68), which is sound — verified with a 3-cycle and a self-parent row.

### L2 — ASCII reason slugs rendered inside Vietnamese sentences.
`kinship_terms.py:52-54` + `kinship_explain.py:42`. `REASON_NO_BLOOD` /
`REASON_OUT_OF_TABLE` are documented as machine-readable slugs, then
interpolated into `"Chưa chắc chắn do ngoai_bang_tu_vung."`. Split the
user-facing text from the client-facing code.

### L3 — `member_binding` joins `person` but only `person_id` is read.
`views/kinship.py:100-102`. Needless `select_related` JOIN on every defaulting
request. Same query count, wider row.

### L4 — Service contract treats an unknown id as a confident stranger.
`resolve_kinship(rows, a, b)` with an id absent from `rows` returns
`{'term': None, 'confident': True, 'reason': 'khong_cung_huyet_thong'}` — the
same answer as a genuine stranger. The view guards it (`views/kinship.py:82-89`),
so no user-visible bug, but `test_unknown_id_does_not_raise` (`:275-276`)
enshrines "unknown == unrelated" and a future caller will trip on it.

### L5 — `path.side` on a full-sibling pair.
Tie-break picks the lower id → the father → `side: 'noi'` for a full sibling,
where nội/ngoại is meaningless. Deterministic, harmless, but the client will
render "bên nội" for a brother.

---

## Confirmed clean

- **Layering.** All five service modules import only from `giapha.services.*`
  and `collections`. Zero ORM, zero `request`. `docs/code-standards.md:7-12`
  satisfied; `test_kinship.py` genuinely runs on `SimpleTestCase`.
- **`clan_edges` / `clan_edges_all` untouched.** `git diff giapha/selectors/person.py`
  is a pure insertion at line 53. The 3-tuple consumers in phases 4 and 6 are
  unaffected. The decision to add a third shape rather than widen is correct
  and the docstring explains why — good.
- **`clan_kinship_rows` is one query.** Single `.filter().values()`, no
  `select_related` needed, no N+1 anywhere in the walk.
- **`clan_spouse_pairs` placement in `selectors/marriage.py` is right.** It
  queries `Marriage`; putting it in `person.py` would cross the module
  boundary for no gain. The stated file list was wrong, the implementer was
  right to deviate. Excluding `ly_hon` and keeping `goa` is the correct call
  (though `goa` is what makes C2 reachable — that is C2's bug, not this one's).
- **Auth / data exposure.** `IsAuthenticated + IsClanMember`, outsiders 404 via
  the shared `_role_for`. `a` and `b` are both validated against the clan's own
  non-deleted row set before any resolution, so a cross-clan or soft-deleted id
  is a 400 that reveals nothing. The `a` default reads
  `member_binding(clan_id, request.user.id)` — clan-scoped and taken from
  `request.user`, never from a client parameter, so no cross-clan binding leak.
  Unbound caller gets a 400 naming `/toi-la`; stale binding gets its own
  message. Nothing in the response (`ho_ten` of A, B, ancestor) is unavailable
  via `/tree` to the same caller. No PII or stack-trace leakage.
- **No model or migration changes.** `makemigrations giapha --check --dry-run`
  → *No changes detected in app 'giapha'*. No files under `*/migrations/*` in
  `git status`.
- **Constraints.** Python 3.9-compatible (no walrus/match/PEP 604), Django 3.1
  APIs only, snake_case throughout, every production file under 200 lines
  (largest: `kinship.py` 197). Five modules instead of two is justified by the
  200-line rule and each is one concern — good split, not over-engineering.
- **Cycle termination.** 3-cycle and self-parent rows both terminate and return
  a sane answer. Endogamous double-linkage (B reachable via both paternal and
  maternal lines) correctly picks the nearer link. Half-siblings on a shared
  father resolve correctly. A == B, no-common-ancestor and unknown-id all
  return 200.
- **The "never guess" mechanism itself is sound.** `None` is a literal key;
  `_candidate_keys` widens `gender`/`side`/`elder` only into slots that were
  written on purpose. I could not find a way to make a paternal `bác`/`chú`/`cô`
  or an `anh`/`chị`/`em` come back `confident: true` without a real
  `birth_order`. The only hole is H2, which is a deliberate table decision, not
  a leak in the mechanism.
- **Over-hedging check.** No case found where a confident answer is needlessly
  hedged. Equal `birth_order` → `None` (`kinship_lookup.py:59`) is the right
  call, not over-caution.

---

## My view on the implementer's five open questions

| # | Question | Verdict |
|---|---|---|
| 1 | Northern `bác` for father's elder sister, no region option | **Acceptable MVP** — documented in the module docstring and the plan. But fix H2 first: the file currently documents a Northern rule it does not implement on the maternal side. |
| 2 | A-side affinity not implemented | **Real defect (H4)**, not a note. `a` defaults to the caller, and married-in members are the primary audience. Implement the mirror loop or at least give the case its own `reason`. |
| 3 | `parent_kind` (`ruot`/`nuoi`/`ke`) ignored | **Acceptable, correct as-is.** An adopted child is addressed identically in Vietnamese; distinguishing would be the surprising behaviour. Worth one line in the docstring stating it is deliberate. |
| 4 | `AFFINAL_TERMS` gap above ông/bà | **Real defect (H3)**, and larger than described — it also swallows `bố`/`mẹ`/`ông nội` (step-parents, a grandfather's second wife) and every gender hedge. The bug is not the missing word, it is answering `confident: true, khong_cung_huyet_thong` for someone who is plainly an in-law. |
| 5 | Tie-break picks lower id → father for full siblings | **Taste, acceptable.** Deterministic and documented. Cosmetic follow-on at L5. |

---

## Recommended actions, in order

1. **C1** — fix the collateral descending ladder (`kinship_terms.py:89-92`), add `-5`, and delete/rewrite the two tests that enshrine it.
2. **C2** — hoist the `a_id in partners` check out of the loop (`kinship.py:145`).
3. **H1** — widen the hedge lookup on `side` (`kinship_lookup.py:89-91`); reuse `_candidate_keys` rather than a second hand-rolled fallback.
4. **H2** — decide table-vs-docstring on the maternal side and make them agree. If the table changes, add the two `bác/cậu` `bác/dì` hedges.
5. **H3** — add the missing `AFFINAL_TERMS` rows and give "married in, no word for it" its own non-confident reason.
6. **H4** — mirror the marriage walk on the A side, or give the unsupported case a distinct `reason` so the UI can say so.
7. **M5** — add: a reciprocal-invariant sweep over a generated tree; a sibling-with-missing-`birth_order` case; a maternal case with `birth_order` varied; cross-clan binding and stale-binding API tests.
8. **M1/M2/M3** — null or relabel the affinal `path`; append `_doubts` in `explain_affinal`; assert status + term in the `assertNumQueries` tests and pin the 4-query worst case.
9. **M4/L1/L2** — document the `MAX_CLAN_PERSONS` exemption; correct the fail-open claim in two docstrings and the report; separate user-facing reason text from client slugs.
10. `docs/system-architecture.md` still needs the endpoint and the Northern-dialect decision (correctly flagged as out of scope by the implementer).

## Metrics

- New tests: 63 (46 service + 17 API) — count as claimed.
- Suite: 533 passed / 4 skipped, unchanged before and after review.
- Migrations pending: 0.
- Production files > 200 lines: 0.
- Findings: **2 Critical, 4 High, 5 Medium, 5 Low.**

## Unresolved questions

1. Is `cậu` for *all* maternal uncles what your users expect, or is `bác` for the elder one? This decides H2 and it is a product call, not an engineering one — ask a Northern gia phả holder before changing the table.
2. For the collateral ladder, is `cháu` at a 2-generation gap (C1's fix) right for gia phả documents specifically, or do some clans write `chắt` collaterally? The reciprocal argument (ông↔cháu) says `cháu`; confirm against a real gia phả text before merging.
3. Should the affinal `path`/`common_ancestor` be nulled or extended with a `via_spouse` field? Depends on what the client intends to draw.
4. Is a 4-query worst case acceptable given the spec said ≤ 2, or should the binding be folded into the permission query (it already touches `ClanMember`)?

**Status:** DONE_WITH_CONCERNS
**Summary:** Architecture, layering, auth and query discipline are solid, but the kinship vocabulary table — the entire feature — emits confidently wrong terms in two places (collateral descending ladder off by one; own spouse reported as sibling-in-law) and drops the hedge entirely for un-ranked siblings. Not shippable until C1/C2/H1-H3 are fixed.
**Concerns/Blockers:** 2 Critical, 4 High. All reproduced with probes against the real modules; probes deleted, working tree left exactly as found, suite re-confirmed at 533 passed / 4 skipped.
