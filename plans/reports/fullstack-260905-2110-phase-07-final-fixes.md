# Phase 07 kinship — final defect round (N1–N5, gap-1 over-hedge, reciprocity)

- Date: 2026-09-05
- Agent: fullstack-developer
- Fixing: `plans/reports/code-reviewer-260905-2054-phase-07-fix-verification.md`
- Prior: `plans/reports/fullstack-260905-2029-phase-07-review-fixes.md`

## Result

| | |
|---|---|
| Full suite | **579 passed / 4 skipped** (baseline 560/4; +19 net tests) |
| `makemigrations giapha --check --dry-run` | *No changes detected in app 'giapha'* |
| Production files > 200 lines | 0 (largest `kinship_terms.py` 197, `kinship_affinal.py` 194) |
| Models / migrations / `apis/` / `clan_edges*` touched | none (`git status` clean of all four; `person.py` diff still the single `clan_kinship_rows` insertion) |

## How failing-before was confirmed

One method for the whole round. **Step A** was a MECHANICAL, behaviour-free
widening applied first and verified green on its own: `clan_spouse_pairs`
started returning `(husband_id, wife_id, status, order)`, `spouses_of`
unpacked four instead of two, test fixtures gained a `marriage()` helper.
Routing was still `sorted()` by id. Re-ran the three kinship modules:
**`Ran 90 tests`, `OK`** — so nothing in step A changed an answer, and the
N1 test could then express the *wrong word* rather than a tuple-unpack
error.

**Step B** wrote every regression test. Pre-fix run:
**`Ran 109 tests`, `FAILED (failures=14, errors=1)`**. Post-fix: `Ran 109
tests`, `OK`. The 15, mapped to the finding each pins:

| Finding | Tests failing before, passing after |
|---|---|
| **N1** | `test_the_current_husband_outranks_the_late_one`, `test_that_answer_does_not_depend_on_which_row_was_entered_first`, `test_a_second_wife_is_ranked_by_marriage_order_not_by_id`, `test_two_equally_ranked_live_marriages_hedge_instead_of_guessing` |
| **N2** | `test_the_explanation_justifies_the_word_it_shows` |
| **N3** | `test_a_hedge_never_contradicts_the_confident_term_beside_it`, `test_a_hedge_never_offers_a_word_the_other_direction_rules_out` |
| **N4** | `test_every_reason_value_is_an_ascii_slug` |
| **N5** | `test_a_daughter_in_law_says_ong_not_ong_noi` |
| **gap-1** | `test_known_elder_of_unknown_gender_is_confidently_bac`, `test_known_younger_of_unknown_gender_hedges_only_chu_co`, `test_gender_hedge_propagates_through_the_marriage` |
| **reciprocity** | `test_every_hedge_the_sweep_produces_reciprocates_too`, `test_the_hedge_clan_really_does_produce_hedges`, `test_every_hedge_row_is_reachable` (ERROR: 5-slot key) |

Three tests that ENCODED the over-hedge were corrected in place, not deleted:
`test_missing_gender_hedges_across_all_three` →
`test_known_elder_of_unknown_gender_is_confidently_bac` (+ a new
`..._and_missing_birth_order_...` keeping the real hedge covered),
`test_sibling_of_unknown_gender_hedges_across_all_three` →
`test_a_hedge_never_contradicts_the_confident_term_beside_it` (+
`..._and_no_birth_order_hedges_all_three`).

Two tests written to guard against regression PASSED before and after, on
purpose: `test_one_marriage_alone_is_never_reported_as_ambiguous`,
`test_side_and_seniority_are_pinned_by_hand_not_only_depth`.

## Fixes

### N1 (HIGH) — which spouse the walk routes through

`clan_spouse_pairs` now carries `status` and `order` (one query, two extra
scalar columns, no join added). New module
`services/kinship_marriage_rows.py` states the rule once:

1. non-`goa` outranks `goa` — a widow stays her late husband's family's thím
   (his row is still kept), but once remarried the question is about the
   family she is in now;
2. among equals the lower `Marriage.order` wins — vợ cả before vợ lẽ;
3. the id is the TIE-BREAK, never the decision.

`rank` returned to the caller is steps 1–2 only. When two candidates share a
`rank` and disagree on the word, `kinship_affinal` **hedges** — `confident:
False`, `reason: nhieu_hon_nhan_ngang_hang` — rather than let autoincrement
order decide. That case is realistic, not theoretical: `Marriage.order`
defaults to 1 and is per-husband, so a woman's two husbands both carry
`order=1` and only `status` separates them.

Probed, the review's exact reproducer:

```
goa + live   a='anh' True   b='em' True
             "Dâu kết hôn với Em. Em gọi X là anh, nên Dâu gọi X là anh."
both live    a='em' False   b='chị' False   nhieu_hon_nhan_ngang_hang
live only    a='anh' True   b='em' True
```

Row order reversed and the question asked in both directions: same words.
C2 not regressed — the self-check in `resolve_kinship` still sits above
`affinal` and `test_own_wife_wins_over_her_earlier_marriage_to_a_brother`
asserts both id orderings.

### N2 (MEDIUM) — `explain` on the mirrored path

`_swapped` is gone. `_through_marriage(..., mirrored=True)` transposes the
directions AND writes the sentence from A's side via the new
`explain_affinal_mirrored`. The template prints BOTH words, because they are
not always the same one (see N5):

```
Con dâu kết hôn với Chồng. Chồng gọi Bố là bố, nên Con dâu gọi Bố là bố.
Con dâu kết hôn với Chồng. Chồng gọi Ông nội là ông nội, nên Con dâu gọi Ông nội là ông.
```

The second line is why a one-word template would have been wrong: it would
have put a blood claim in the sentence that the answer itself refuses.

### gap-1 over-hedge — taken, and only the safe half

Added `(BANG, 1, NOI, None, True): 'bác'` and `(BANG, 1, NGOAI, None, True):
'bác'`. `_candidate_keys` reaches the exact gendered row first, so nothing
known-gender changed. The "never guess" guarantee is untouched: it is about
a missing `birth_order`, and every seniority-bearing word still needs one.
Docstring in `kinship_terms.py` now states that distinction explicitly.

### N3 (LOW) — hedges gained an `elder` slot

`AMBIGUOUS_TERMS` keys on the same five slots as `TERMS`, so `resolve_term`
uses ONE generator (`_candidate_keys`) for both tables — the hand-rolled
second lookup that caused H1 is now gone from the hedge path too. New rows:
`(BANG, 0, ·, None, True) → 'anh/chị'`, `(BANG, 1, NOI, None, False) →
'chú/cô'`, `(BANG, 1, NGOAI, None, False) → 'cậu/dì'`. The reviewer's
reproducer now reads `anh/chị` + `em`, not `anh/chị/em` + `em`.

`AFFINAL_TERMS` gained the six rows those narrower hedges key into
(`('chú/cô','nu') → thím`, `('cậu/dì','nam') → dượng`, …). One visible
consequence, deliberate: `test_gender_hedge_propagates_through_the_marriage`
now reads `dượng` instead of `bác/dượng` — the spouse's known gender rules
out the other branch. `confident` stays False, because the blood word behind
it is still hedged.

### N4 (LOW) — every `reason` is an ASCII slug

`thiếu birth_order` → `thieu_birth_order`, `thiếu giới tính` →
`thieu_gioi_tinh`, `không có từ xưng hô thông dụng` →
`khong_co_tu_xung_ho_thong_dung`; `+ nhieu_hon_nhan_ngang_hang`. Human
wording moved to `REASON_LABELS` and reaches the reader through `explain`
only (`_doubts` maps slug → label, falling back to the slug so an unmapped
one cannot vanish from the sentence).

**Response shape changed**, so per instruction:
`serializers/kinship.py::KinshipTermSerializer` docstring now lists all
seven values and says not to render `reason`; `test_kinship_api.py`'s
assertion asserts the slug AND that `explain` still carries `thiếu
birth_order`.

### N5 (LOW) — `ông nội` reaching a con dâu

**Fixed the term, not the comment.** `MARRIED_IN_SUBSTITUTES` (`ông nội` →
`ông`, `bà nội` → `bà`, `ông ngoại`/`bà ngoại` → `ông`/`bà`) is applied to
the word the married-in person borrows, in the one place both directions go
through. Reasoning, now written in the file: it is the SAME rule that
already produced `('ông nội','nu') → 'bà'` for a grandfather's second wife —
`nội`/`ngoại` asserts descent the speaker does not have — and this endpoint
answers address form, where "ông ơi" is what is said either way. Only the
four `nội`/`ngoại` words are substituted; `cụ ông`/`kỵ bà` mark gender, not
blood, and pass through unchanged (pinned by a test).

## Reciprocity test — strengthened and mutation-verified

`RECIPROCAL` left exactly as it was: hand-written and independent. Added two
more hand-written, independent layers plus a table-free property.

- **`BY_HAND`** — 18 pairs pinning WHICH WORD at gap 0 and gap 1, i.e. side
  and seniority, where `RECIPROCAL` is blind (everything reciprocates
  `cháu`). Includes `(TOI, BAC_NGOAI) → ('bác','cháu')` against
  `(TOI, CAU) → ('cậu','cháu')`, and asserts `confident` on both directions.
- **`HEDGE_ROWS` + `HEDGE_RECIPROCAL`** — a SECOND fixture built to be
  missing exactly the fields that produce hedges (the blood fixture assigns
  `birth_order` almost everywhere, which is why hedges barely occurred).
  Swept for reciprocal consistency; `bác/…` family → `cháu`, sibling hedges
  → sibling hedges, and the strong one, `anh/chị` → `em` only.
- **`RULED_OUT_BY`** — needs no table at all: if B confidently calls A `em`
  then A's own word must not still be offering `em`. This is N3 as a
  property over the whole sweep.
- **`test_the_hedge_clan_really_does_produce_hedges`** — the coverage guard,
  so the two sweeps above cannot quietly stop having anything to sweep.

**Mutation verification** (each applied, run, reverted, file byte-diffed
back with `diff`, confirmed identical):

1. `(BANG, 1, NGOAI, 'nam', True)` `bác` → `cậu` (re-introducing H2, which
   previously left this file **entirely green**):
   `test_kinship_reciprocity.py` now **FAILS** —
   `test_side_and_seniority_are_pinned_by_hand_not_only_depth`,
   `AssertionError: ('bác','cháu') != ('cậu','cháu') : cặp (130, 125)`.
2. Dropped the new `(BANG, 0, None, None, True): 'anh/chị'` hedge row:
   **4 failures** in the same file, including
   `test_a_hedge_never_offers_a_word_the_other_direction_rules_out`.

Module docstring records what each layer does and does not constrain.

## Files changed

| File | Lines | Change |
|---|---|---|
| `giapha/selectors/marriage.py` | 75 | N1 — `clan_spouse_pairs` carries `status`/`order` |
| `giapha/services/kinship_marriage_rows.py` | 68 | **new** — the ranking rule (forced by the 200-line limit) |
| `giapha/services/kinship_affinal.py` | 194 | N1 ranking + ambiguity hedge, N2 mirrored explain, N5 substitution |
| `giapha/services/kinship_affinal_terms.py` | 109 | N3 hedge rows, N5 `MARRIED_IN_SUBSTITUTES`, comment now agrees |
| `giapha/services/kinship_terms.py` | 197 | N4 slugs + `REASON_LABELS`, gap-1 `bác` rows, N3 `elder` slot |
| `giapha/services/kinship_lookup.py` | 126 | one generator for both tables |
| `giapha/services/kinship_explain.py` | 117 | `REASON_LABELS`, `explain_affinal_mirrored` |
| `giapha/services/kinship.py` | 75 | docstrings (row shape, pipeline map) |
| `giapha/serializers/kinship.py` | 83 | N4 — the `reason` contract, spelled out |
| `giapha/tests/test_kinship.py` | 686 | +4 classes, 3 tests corrected in place |
| `giapha/tests/test_kinship_reciprocity.py` | 373 | `BY_HAND`, hedge fixture + sweep, 5-slot keys |
| `giapha/tests/test_kinship_api.py` | 210 | N4 slug + `explain` assertion |

`kinship_affinal.py` reached 241 lines with the ranking in it, so the
marriage-row reading moved to its own module. Real seam, not taste: "which
marriage do we answer through" is a policy about the family; the rest of
that file is which Vietnamese word comes out. No cycle — the new module
imports nothing.

## Docstrings the review proved false, corrected

- `_through_marriage`: "Spouses are tried in id order… stable answer" — that
  WAS the bug; replaced by the ranking rule.
- `_widenings`: "Shared by BOTH lookups below" — it now feeds
  `_candidate_keys`, which both lookups go through.
- `kinship.py`: the spouse row shape is a four-tuple.
- `kinship_terms.py` reason block: no longer claims the data-gap reasons are
  Vietnamese by design.
- `clan_spouse_pairs`: says why `status`/`order` travel and points at the
  ranking module (checked after the split; the reference is not stale).

## Cultural calls — flagged, not guessed

1. **`ông` for a con dâu addressing her husband's grandfather (N5).** I
   applied it and gave the reason in the file. It is a product call: if this
   clan expects a wife to say `ông nội` exactly as her husband does, delete
   four rows from `MARRIED_IN_SUBSTITUTES` and one test flips.
2. **`thím` for the wife of a `chú/cô` hedge** (`('chú/cô','nu')`). The
   spouse's gender rules the pair down to `chú`, so `thím` follows. I am
   confident in the word; less so that emitting a single confident-looking
   word off a hedged blood term reads well — `confident` is False and
   `explain` says why, which I judged sufficient.
3. **`dượng` where the pair used to read `bác/dượng`.** Same shape. Narrower
   and, I believe, more correct — but it is a visible change to an answer the
   previous review saw and approved in its wider form.

## Unresolved questions

1. Should a `goa` marriage be routed through at all when a live one exists?
   Implemented as the reviewer recommended (ranked below, never dropped), so
   the widow of the eldest brother is still `bác gái` to the clan. Confirm
   that is the product intent before it has clients.
2. `nhieu_hon_nhan_ngang_hang` currently fires whenever two same-`rank`
   marriages produce different words — including two live marriages both
   left at the `order=1` default by a data-entry UI that never asked. That
   may be common enough to be noise. A `Marriage.order` uniqueness rule per
   person would remove the class; out of scope here (model change).
3. The six new `AFFINAL_TERMS` hedge rows (`('anh/chị', ·)`, `('chú/cô', ·)`,
   `('cậu/dì', ·)`) are covered by the "no dead row" integrity test but not
   by an end-to-end case each. Only `('cậu/dì','nam')` is exercised for real.
4. `via: {id, ho_ten}` on affinal answers (reviewer's open question 2) — not
   done, not in the assigned list. `explain` still names the spouse.
5. `test_kinship.py` is now 686 lines. Test files are outside the 200-line
   rule and splitting means sharing the fixture across modules; left alone
   under "no refactoring for taste", but it is past the point where I would
   normally split it.
6. M5 residue (`BINDING_GONE`, cross-clan-binding API tests) and
   `docs/system-architecture.md` still lack the endpoint — both out of this
   round's scope, still open from the previous review.

**Status:** DONE_WITH_CONCERNS
**Summary:** N1, N2, N3, N4, N5 and the gap-1 over-hedge all fixed with regression tests confirmed failing before (14 failures + 1 error) and passing after; the reciprocity file gained a hand-written side/seniority table, a second hedge-bearing fixture with its own reciprocal sweep, and a table-free contradiction property, mutation-verified by flipping `bác`→`cậu` (which previously left that file entirely green); full suite 579 passed / 4 skipped, migration check clean.
**Concerns/Blockers:** Three answers visibly changed shape for the better but were approved in their older form by the last review — `dượng` in place of `bác/dượng`, `ông` in place of `ông nội` for a con dâu, and every `reason` value now an ASCII slug (a wire-format change; serializer docstring and tests updated). The N5 call is a product decision I made rather than deferred, and it is a four-row revert if the owner disagrees.
