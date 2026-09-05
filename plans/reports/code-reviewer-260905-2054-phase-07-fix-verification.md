# Fix Verification — Phase 07 Máy tính xưng hô (narrow pass)

- Date: 2026-09-05
- Reviewer: code-reviewer (verification only, no fixes applied)
- Verifying: `plans/reports/fullstack-260905-2029-phase-07-review-fixes.md`
- Against: `plans/reports/code-reviewer-260905-2016-phase-07-kinship.md`
- Suite re-confirmed after review: **560 passed / 4 skipped**. `makemigrations giapha --check --dry-run` → *No changes detected*. Tree left exactly as found (probes deleted; two temporary reverts restored and byte-diffed).

## Verdict

**SHIPPABLE — 8/10**, with one High I would close first (N1: ~10 lines, one
selector + a sort key). All 2 Critical and 4 High from the previous pass are
really fixed, reproduced by probe in both directions. The reciprocity property
test is genuine, not tautological — mutation-tested. The residual High is the
*unfixed half* of C2: C2 fixed "B is my own spouse"; it did not fix "which of
B's several spouses do we route through", and H4 extended that same ambiguity
to the A side.

---

## Per-finding verdicts

### C1 — collateral descending ladder — **VERIFIED FIXED**

Probe, `Bac` and `Bo` brothers, descending chain under `Bo`:

```
Bac->ConBo   a='cháu' b='bác'      Bac->ChauBo  a='cháu' b='ông'
Bac->ChatBo  a='chắt' b='cụ'       Bac->ChutBo  a='chút' b='kỵ'
Bac->ChitBo  a='chít' b='tổ tiên'
```

ông↔cháu, cụ↔chắt, kỵ↔chút all reciprocate. The `MAX_TABLE_GAP` claim is true:
`-5` is found in `TERMS` before the `gap < -MAX_TABLE_GAP` bound; `-6` →
`hậu duệ`. The two previously-wrong tests were rewritten, not deleted, and now
assert BOTH directions via `both(...)`:
`test_two_collateral_generations_down_is_chau_the_reciprocal_of_ong` asserts
`('ông','cháu')`, `..._chat_the_reciprocal_of_cu` asserts `('cụ','chắt')`, plus
new `..._chut_the_reciprocal_of_ky` and `..._is_chit`.

My view on the previous pass's open question: `cháu` at collateral gap 2 is
right. Collateral `cháu` covers both the sibling's child and the sibling's
grandchild; `chắt` collaterally begins at gap 3, matching `cụ`. Reciprocity is
decisive.

### C2 — own wife returned as `chị` — **VERIFIED FIXED**

Self-check hoisted to `kinship.py:67`, above `affinal(...)`, so it cannot be
reached from inside the spouse loop. Probe with the exact reproducer (`Vo`
widowed from `Anh(5)`, remarried to `Toi(9)`, `goa` kept):

```
Toi(9)->Vo(20)             vợ / chồng   confident True
Vo(20)->Toi(9)             chồng / vợ   confident True
ids swapped (Toi=5,Anh=9)  vợ / chồng   -- id order no longer decides
```

Autoincrement order no longer decides *this* answer. See **N1**: it still
decides the derived (in-law) answer.

### H1 — unreachable hedge / leaked slug — **VERIFIED FIXED**

`_widenings(side, gender)` (`kinship_lookup.py:64`) is one generator used by
both `_candidate_keys` and the hedge lookup; the hand-rolled second fallback is
gone. Probe:

```
two unranked brothers      anh/em      False  'thiếu birth_order'
one ranked, one not        anh/em      False  'thiếu birth_order'
two unranked sisters       chị/em      False  'thiếu birth_order'
gioi_tinh='khac'           anh/chị/em  False  'thiếu giới tính'
unranked first cousins     anh/em      False  'thiếu birth_order'
```

No `AMBIGUOUS_TERMS` row is dead: `test_every_hedge_row_is_reachable` walks
every row and, for `side=None` rows, tries both `noi` and `ngoai`. Checked it is
not circular — it derives the *input* from the table but asserts a property (the
lookup reaches it) independent of table content, which is exactly the H1 bug.
Blind spot: it pins `elder=None`, so it cannot catch a hedge row shadowing a
confident `TERMS` row. Not reachable today (`resolve_term` exhausts `TERMS`
first), so a note, not a finding.

### H2 — strict Northern rule — **VERIFIED FIXED**

Table and docstring agree, and the docstring records that they used to disagree
— good practice. Probe:

```
elder brother of mẹ  bác True    younger brother of mẹ  cậu True
elder sister  of mẹ  bác True    younger sister  of mẹ  dì  True
maternal uncle, no birth_order   bác/cậu     False 'thiếu birth_order'
maternal aunt,  no birth_order   bác/dì      False 'thiếu birth_order'
maternal, gender unknown         bác/cậu/dì  False 'thiếu giới tính'
```

`mợ` follows automatically from `('cậu','nu')`, so `mợ` can no longer appear for
an elder maternal uncle's wife; `('bác','nu') → bác gái` and the hedge
`('bác/cậu','nu') → bác gái/mợ` are consistent. No seniority-bearing word comes
back `confident: true` without a `birth_order` behind it any more — I could not
construct one.

### H3 — in-laws reported as confident "no blood relation" — **VERIFIED FIXED**

`REASON_AFFINAL_NO_TERM` with `confident: False` and the spouse named in
`explain`. All four previous reproducers now behave:

```
stepmother              term None, confident False, 'không có từ xưng hô thông dụng'
                        explain: "MeKe kết hôn với Bo. Toi gọi Bo là bố, ..."
wife of a cụ            'cụ' True
grandfather's 2nd wife  'bà' True     (not 'bà nội' -- correct, no blood)
husband of gender-unknown maternal sibling  'bác/dượng' False 'thiếu giới tính'
```

Gender hedges propagate instead of vanishing. `khong_cung_huyet_thong` is
emitted only from `kinship.py:72`, reached only when `affinal(...)` returned
`None`, which requires BOTH `_through_marriage` calls to return `None` — i.e.
neither party has a spouse with a blood link. Verified by probe on a genuine
stranger and on a stranger carrying an irrelevant marriage row.

### H4 — A-side affinity — **VERIFIED FIXED; the argument swap is correct**

Scrutinised specifically. `_through_marriage(rows, by_id, index_b, b_id, a_id,
spouses)` computes *B's* term for A through A's spouses, so its `a_calls_b` is
B→A and its `b_calls_a` is A→B; `_swapped` transposes exactly those two and
leaves `common_ancestor`/`path` alone. Both are `None` / `EMPTY_PATH` on every
affinal branch, so there is nothing to mirror wrongly — **the M1 nulling is what
makes the swap safe, and that is a real dependency between the two fixes**.
Probe, con dâu married to `Chong`:

```
ConDau->Bo(bố chồng)         bố      / con    both True
ConDau->Bac(bác chồng)       bác     / cháu   both True
ConDau->AnhHo(anh họ chồng)  anh     / em     both True
AnhHo ->ConDau               em      / anh            (transpose is right)
ConDau->Ong                  ông nội / cháu           (see N5)
```

Not transposed, not silently mirrored. Both-married-in behaves as documented
(`khong_cung_huyet_thong`), pinned by
`test_two_people_who_both_married_in_get_no_derived_term`. Preference order is
sane and deterministic: B-side named word → A-side named word → B-side hedge →
A-side hedge → `None`.

### Mediums / Lows — spot check

| Item | Verdict |
|---|---|
| M1 affinal `path`/`common_ancestor` | **VERIFIED FIXED** — `None` + `EMPTY_PATH` on every affinal branch; serializer docstring corrected. Also the precondition making H4's swap safe. |
| M2 `explain_affinal` never hedges | **VERIFIED FIXED** — `_doubts(*entries)` on both branches; probe shows "… Chưa chắc chắn do thiếu birth_order." on a hedged in-law. |
| M3 vacuous query tests | **VERIFIED FIXED** — all three assert `200` + the term; a fourth pins the 4-query ceiling; view docstring states it. |
| M4 `MAX_CLAN_PERSONS` | **FIXED AS DECLINED-WITH-REASON** — explicit exemption docstring in `clan_kinship_rows`. Reasoning (truncation falsifies rather than degrades) is correct. Accept. |
| M5 test gaps | **PARTIALLY FIXED** — reciprocity sweep, unranked sibling/cousin, maternal `birth_order` added. Cross-clan-binding and `BINDING_GONE` API tests still absent; `views/kinship.py:47` still has a dedicated message no test exercises. |
| L1 fail-open claim | **VERIFIED FIXED** — `kinship_graph` docstring now says truncation CAN select a farther ancestor and emit a confident wrong term; test renamed `..._stops_early_instead_of_raising`. |
| L2 / L3 / L4 / L5 | **DECLINED, reasonably** — cosmetic or contract-scope. L2 partly self-resolved (H1 removed the common path that surfaced `ngoai_bang_tu_vung`), but H3 reintroduced the same smell in the other direction — see N4. |

---

## The reciprocity property test — is it real?

**Real, and stronger than expected. Not tautological.** Evidence by mutation
(each applied, run, reverted, files byte-diffed back):

1. Reverted C1 in `TERMS` (`-2 → chắt` …) → `test_every_pair_addresses_each_other_consistently` FAILS: `132 gọi 107 là "ông" nhưng 107 gọi lại là "chắt"`, plus `test_collateral_and_direct_ladders_agree_below_the_ancestor`. It genuinely catches the class of bug it was written for.
2. Added an unreachable row `(BANG, 9, …): 'MUTANT'` → `test_every_word_in_the_table_is_reached` FAILS. The "sweep touches the whole table" invariant is a real invariant, not a coincidence of the fixture: a new table row nobody in the tree reaches fails the suite.

`RECIPROCAL` is a hand-written, independent counterpart map — not derived from
`TERMS`, so it is not restating the thing under test.

**Its honest boundaries, which should be written down before it is trusted as
"the guarantee for the whole vocabulary":**

- It constrains *ladder depth*, not *word choice at gap 0/1*. All of
  `bác/chú/cô/cậu/dì/ông/bà` map to the same reciprocal `cháu`. Verified:
  mutating `(BANG, 1, NGOAI, 'nam', True)` from `bác` back to `cậu` —
  re-introducing H2 exactly — leaves `test_kinship_reciprocity.py` **entirely
  green**. Only `test_kinship.py` catches H2.
- The sweep drops any pair where either term is `None`, and `RECIPROCAL.get`
  skips hedged words, so **hedges are not covered by the sweep at all** — and
  the fixture assigns `birth_order` almost everywhere, so hedges barely occur in
  it. H1's bug class would not have been caught here.
- `RECIPROCAL['tổ tiên'] = ('chít', 'hậu duệ')` — a two-valued slot, so the top
  rung is only weakly pinned.
- `test_every_word_in_the_table_is_reached` checks `expected - seen` only; the
  sweep also produces words outside the table (hedges). Fine, but the name
  slightly overpromises.

None of this is a defect. It is the difference between "the ladders cannot go
out of step again" (guaranteed) and "the vocabulary is right" (not). Worth one
line in the module docstring so the next reader does not over-trust it.

## The forced file splits

- **No cycles.** DAG: `kinship → {affinal, blood, graph, terms}`; `affinal →
  {blood, explain, graph, lookup, affinal_terms, terms}`; `blood → {explain,
  lookup, terms}`; `explain/graph/lookup → terms`. Both `*_terms` modules import
  nothing. Verified by grep and by importing the modules under plain `python`
  with no `django.setup()`.
- **ORM-free.** No `.objects`, no `giapha.models`, no `giapha.selectors`, no
  `request` in any of the seven service modules. `test_kinship*.py` still run on
  `SimpleTestCase`.
- **"No logic changed in the move" — UNVERIFIABLE BY DIFF.** Every kinship file
  is still untracked (`??` in `git status`); there is no committed baseline to
  diff the split against. By reading, the extraction is clean: one definition per
  symbol, no duplicates across modules, `unrelated`/`result`/`blood_result`
  unchanged apart from docstrings. Taken on reading, not on evidence.
- All production files under 200 lines (largest `kinship_affinal.py` 148).
  Python 3.9-clean (no walrus, `match`, PEP 585/604). `test_kinship.py` at 501
  lines is a test file — outside the rule, and I would leave it.

## Cultural correctness — my own view on the three flagged calls

**`bác` for the mother's elder sibling — CORRECT, keep it.** Standard Northern
and the dictionary sense (`bác`: anh/chị của cha *hoặc mẹ*). Both the elder
brother and the elder sister of the mother are `bác` in the North. The hedges
`bác/cậu`, `bác/dì`, `bác/cậu/dì` enumerate exactly the live options at that key
and read naturally. No objection.

**1. `bác gái` vs plain `bác` for a bác's wife — AGREE with the fixer.**
`bác gái` is the ordinary Northern address form and it is what distinguishes her
from `bác trai` in the same conversation. A gia phả *text* would write `bác dâu`,
but this endpoint answers "what do I call this person", i.e. address form. The
asymmetric partner `('bác','nam') → 'bác'` (husband of a female bác) is right in
address too, where a text would write `bác rể`. Keep both.

**2. Stepmother deliberately omitted — AGREE, strongly.** Usage genuinely splits
(`mẹ` / `dì` / `mẹ kế`, regionally `má`), it is high-stakes, and the H3 hedge —
"there is a link, no everyday word, here is who it runs through" — is the right
output. One improvement, not blocking: the machine-readable half of that answer
is empty (M1 nulled `common_ancestor`/`path`), so a UI cannot render "vợ của Bố
bạn" and let the user pick; only the Vietnamese `explain` string carries it. A
`via: {id, ho_ten}` field would close that without re-introducing the misleading
`path`.

**3. Over-hedge at `gap == 1` with unknown gender — DO NOT accept it whole.**
Half is a two-row table fix and should be taken:

```python
(BANG, 1, NOI,   None, True): 'bác',
(BANG, 1, NGOAI, None, True): 'bác',
```

`bác` is gender-independent at `elder=True` — the table already stores the same
word under `'nam'` and `'nu'` — so `bác/chú/cô` for a *known-elder* relative of
unknown gender is not an honest hedge, it is a lost confident answer. The rows
are safe: `_candidate_keys` reaches an exact gendered row first, so nothing
known-gender changes. What remains (`elder=False`, gender unknown → `chú/cô`,
`cậu/dì`) is genuinely unavoidable without an `elder` slot in
`AMBIGUOUS_TERMS` — and that I would also add, because the current shape emits a
self-contradictory payload (N3).

---

## New / remaining defects

### N1 — HIGH. Which spouse the in-law walk routes through is still decided by autoincrement id. Confidently wrong vai vế.
`kinship_affinal.py:97`, `selectors/marriage.py::clan_spouse_pairs`

C2 fixed "B is my own spouse". It did not fix the general case: when the person
being routed through has more than one non-divorced marriage,
`sorted(spouses_of(...))` picks the lowest id — usually the *earlier*, i.e. the
dead one, since `clan_spouse_pairs` deliberately keeps `goa` and drops the
`status`/`order` columns entirely. The service is structurally unable to prefer
the live marriage.

Reproduced, both directions, `confident: True` throughout. `Dau` widowed from
`Anh(id 2, birth_order 1)`, now married to `Em(id 3, birth_order 3)`; `X` is a
third brother sitting *between* them at `birth_order 2`:

```
Dau -> X, spouses [(2,20),(3,20)]  =>  'em'  confident True
        explain: "Dau kết hôn với Anh. X gọi Anh là anh, ..."
Dau -> X, only the current husband =>  'anh' confident True
X -> Dau, spouses [(2,20),(3,20)]  =>  'chị' confident True
X -> Dau, only the current husband =>  'em'  confident True
```

The wife of the younger brother is told to call her husband's elder brother
`em`. Same failure mode and same trigger (levirate remarriage after a death) the
previous review called Critical for C2 — only the word is now `anh`/`em` rather
than `chị`. Pre-existing on the B side; **H4 newly extended it to the A side**,
which is worse, because married-in members are the H4 audience and `a` defaults
to the caller.

Fix: widen `clan_spouse_pairs` to carry `status` (and `order`), rank a
non-`goa` marriage above a `goa` one, make the tie-break inside
`_through_marriage` explicit and documented rather than incidental. One selector
change plus a sort key, plus a regression test in the shape above.

### N2 — MEDIUM. On the A-side path, `explain` justifies the wrong direction.
`kinship_affinal.py:145` — `_swapped` transposes the term dicts but reuses the
inner call's sentence verbatim, and that sentence was built with the names in
the other order.

```
a_calls_b = 'bố'
explain   = "ConDau kết hôn với Chong. Bo gọi Chong là con, nên xưng hô với
             ConDau theo quan hệ hôn nhân đó."
```

Every clause is true, but the sentence explains `b_calls_a` while the client
asked `a_calls_b`, and the word it justifies (`con`) is not the word displayed
(`bố`). Disclosed by the fixer as their open question 3; I rate it above "copy"
because `explain` is the plan's mechanism for making the answer trustworthy, and
here it argues for a different answer than the one shown. A second template, or
swap names/direction inside `_swapped`.

### N3 — LOW. Hedges can contradict confident data in the same payload.
`kinship_terms.py:152-161` — `AMBIGUOUS_TERMS` has no `elder` slot.

```
A(birth_order 2), B(birth_order 1, gioi_tinh 'khac'), full siblings:
  a_calls_b = 'anh/chị/em'  confident False 'thiếu giới tính'
  b_calls_a = 'em'          confident True
```

`b_calls_a = 'em'` states A is the elder branch, so `em` cannot be in A's hedge —
the response contradicts itself in two adjacent fields. Same shape at `gap == 1`
(`bác/chú/cô` where `bác` is certain). Never a wrong confident word, so Low, but
user-visible nonsense. Fix: the two `(…, None, True): 'bác'` rows plus an
`elder` slot in `AMBIGUOUS_TERMS`.

### N4 — LOW. `reason` now mixes ASCII slugs and Vietnamese prose on the axis clients branch on.
`kinship_terms.py:69`. `REASON_AFFINAL_NO_TERM = 'không có từ xưng hô thông
dụng'` sits in the same field as `REASON_NO_BLOOD = 'khong_cung_huyet_thong'`.
The whole point of H3 is that a client must distinguish "no link" from "link, no
word" — and the fix made that distinction expressible only as a diacritic
Vietnamese string that will be compared with `==` in a mobile client. The
pre-existing `'thiếu birth_order'` is the same smell, but those are display
hints; this one is a control-flow value. Raised by the fixer as their open
question 5 and rightly. ASCII slug plus a separate display map, before the wire
format has clients.

### N5 — LOW. `ông nội` / `bà ngoại` reach a married-in A unchanged, contradicting the affinal table's own reasoning.
`kinship_affinal.py:115` vs `kinship_affinal_terms.py:55-60`. `('ông nội','nu')
→ 'bà'` exists precisely because *"những từ đó hàm ý huyết thống"*. But on the
mirrored path `a_calls_b` is `blood['b_calls_a']` verbatim, so a con dâu is told
to call her husband's grandfather `ông nội`:

```
ConDau -> Ong  =>  a_calls_b 'ông nội' confident True
```

Defensible under the module's own "gọi theo chồng/vợ" rule, and arguably how
people actually speak — but the two comments in the two files disagree about
whether `ông nội` may be said by a non-descendant. Pick one and say so.

### N6 — INFO. `ancestor_index` rebuilds `parents_of` from `rows` on every call, and H4 roughly doubles the calls.
`kinship_graph.py:56-58`. Per request the view calls `resolve_kinship` up to
twice; each builds two indexes, and `affinal` now builds up to two more plus one
per spouse candidate on *each* side. Every one re-materialises a
`len(rows)`-entry dict. No queries added, but `clan_kinship_rows` is explicitly
exempt from `MAX_CLAN_PERSONS` (M4), so this is unbounded CPU on the largest
clans. Hoisting `parents_of` to a parameter is small if a big clan ever
complains. Not blocking.

---

## Claim sanity-check: "tests written first, red before, green after"

Checked on the fix I judge highest risk — **H4**, the only new algorithm (the
others are table edits or a hoisted `if`), and argument-swapping is the classic
place to be subtly wrong.

Reverted `affinal()` out-of-tree to the B-side-only body
(`return _through_marriage(rows, by_id, index_a, a_id, b_id, spouses)`), ran the
three kinship modules:

```
Ran 90 tests   FAILED (failures=3)
  test_wife_addresses_her_husbands_uncle_the_way_he_does
  test_wife_calls_her_husbands_father_bo_and_is_called_con
  test_wife_addresses_her_husbands_elder_cousin_as_anh
```

Exactly the three tests the fix report maps to H4, and nothing else — the tests
pin the fix specifically rather than passing incidentally. File restored and
`diff`ed identical; suite back to 560. The claim holds where I tested it. I did
not reproduce the full `failures=24` figure, but the C1 mutation (2 reciprocity
failures) and this one are consistent with it.

## Also confirmed

- `clan_edges` / `clan_edges_all` **untouched** — `git diff giapha/selectors/person.py` is a pure insertion of `clan_kinship_rows` at line 53; no other hunk.
- **No model or migration changes**: `makemigrations giapha --check --dry-run` → *No changes detected in app 'giapha'*; nothing matching `models|migrations` in `git status`.
- All production files < 200 lines; Python 3.9 / Django 3.1 compatible.
- Auth surface unchanged by the fixes (`IsAuthenticated + IsClanMember`; both ids validated against the clan's own non-deleted row set). No new PII: `explain` now names the spouse routed through, and that person is already visible to the same caller via `/tree`.
- No new queries. The 4-query ceiling in the view docstring is accurate and pinned by `test_worst_case_is_four_queries`.
- Tree left exactly as found; both temporary reverts restored and byte-diffed; probe file deleted; full suite re-confirmed at **560 passed / 4 skipped**.

## Recommended actions, in order

1. **N1** — carry `status` (and `order`) through `clan_spouse_pairs`, prefer the live marriage, document the tie-break. Regression test in the levirate shape. The only item I would block on.
2. **N2** — swap the direction in `explain` on the mirrored path.
3. **N3** + cultural note 3 — add `(BANG, 1, NOI/NGOAI, None, True): 'bác'`, then an `elder` slot in `AMBIGUOUS_TERMS`.
4. **N4** — ASCII slug for `REASON_AFFINAL_NO_TERM`, display text separate; do L2 at the same time.
5. **N5** — decide whether `ông nội` may be spoken by a non-descendant; make the two files agree.
6. **M5 residue** — `BINDING_GONE` and cross-clan-binding API tests.
7. One line in `test_kinship_reciprocity.py`'s docstring recording what the sweep does *not* constrain (gap 0/1 word choice, hedges).
8. `docs/system-architecture.md` still lacks the endpoint and the Northern-dialect decision — unchanged since the last pass, correctly out of scope for the fixer.

## Metrics

- Previous findings: 2 Critical **fixed**, 4 High **fixed**, 5 Medium (4 fixed, 1 partial), 5 Low (1 fixed, 4 declined reasonably).
- New findings: **0 Critical, 1 High, 1 Medium, 3 Low, 1 Info.**
- Suite: 560 passed / 4 skipped, before and after review. Migrations pending: 0. Production files > 200 lines: 0.
- Score: **8/10** (was 6/10).

## Unresolved questions

1. N1: should a `goa` marriage ever be routed through when a live one exists, or only when it is the *only* one? (The widow of the eldest brother is still `bác gái` to the clan, so "drop `goa`" is wrong; "rank it below a live marriage" is what I recommend.)
2. Is a `via: {id, ho_ten}` field wanted on affinal answers? It would let the UI say "vợ của Bố bạn" for the deliberately-unnamed stepmother — the strongest version of the H3 design.
3. Is `ông nội` acceptable from a con dâu (N5)? Product call, not engineering.
4. `REASON_AFFINAL_NO_TERM` as a slug — decide before the endpoint has clients, not after.
