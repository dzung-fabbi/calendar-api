# Phase 07 kinship — review-fix implementation

- Date: 2026-09-05
- Agent: fullstack-developer
- Review fixed: `plans/reports/code-reviewer-260905-2016-phase-07-kinship.md`
- Spec: `plans/260905-1053-gia-pha-dong-ho/phase-07-may-tinh-xung-ho.md`

## Result

| | |
|---|---|
| Full suite | **560 passed / 4 skipped** (baseline 533/4; +27 net tests) |
| `makemigrations giapha --check --dry-run` | *No changes detected in app 'giapha'* |
| Production files > 200 lines | 0 |
| Models / migrations / `apis/` / `clan_edges*` touched | none |

## How failing-before was confirmed (single method, applied to all)

Wrote every regression test FIRST, ran the three kinship test modules against
unmodified production code, saved the failure list, then implemented. One
constant (`REASON_AFFINAL_NO_TERM`) had to be added before that run or the
test module would not import — it is a bare string with no consumer at that
point, so the run still measured pre-fix behaviour.

**Pre-fix run: `Ran 90 tests`, `FAILED (failures=24)`. Post-fix: `Ran 90 tests`, `OK`.**
The 24, mapped to the finding each one pins:

| Finding | Tests failing before, passing after |
|---|---|
| **C1** | `test_two_collateral_generations_down_is_chau_the_reciprocal_of_ong`, `..._three_..._chat_...`, `..._four_..._chut_...`, `test_five_collateral_generations_down_is_chit`, `ReciprocityTests.test_every_pair_addresses_each_other_consistently`, `test_collateral_and_direct_ladders_agree_below_the_ancestor` |
| **C2** | `test_own_wife_wins_over_her_earlier_marriage_to_a_brother` |
| **H1** | `test_sibling_without_birth_order_still_gets_a_word`, `test_female_sibling_without_birth_order_hedges_chi_em`, `test_cousin_without_birth_order_hedges_too`, `test_sibling_of_unknown_gender_hedges_across_all_three`, `test_maternal_aunt_without_birth_order_hedges_bac_di`, `TableIntegrityTests.test_every_hedge_row_is_reachable` |
| **H2** | `test_elder_brother_of_mother_is_bac_not_cau`, `test_maternal_uncle_without_birth_order_hedges_like_the_paternal_side`, `test_maternal_aunt_without_birth_order_hedges_bac_di` |
| **H3** | `test_stepmother_hedges_instead_of_claiming_no_relation`, `test_that_answer_names_the_spouse_it_went_through`, `test_wife_of_cu_is_addressed_cu`, `test_gender_hedge_propagates_through_the_marriage` |
| **H4** | `test_wife_addresses_her_husbands_uncle_the_way_he_does`, `test_wife_calls_her_husbands_father_bo_and_is_called_con`, `test_wife_addresses_her_husbands_elder_cousin_as_anh` |
| **M1** | `test_affinal_answer_names_no_common_ancestor` |
| **M2** | `test_hedged_affinal_term_says_what_is_missing` |

Two existing tests that encoded C1 were corrected in place, not worked around:
`test_two_collateral_generations_down_is_chat` → `..._is_chau_the_reciprocal_of_ong`,
`..._three_..._is_chut` → `..._is_chat_the_reciprocal_of_cu`. Both now assert
BOTH directions of the pair, so the same bug cannot come back one-sided.

## Fixes

### C1 — collateral descending ladder shifted one rung
`kinship_terms.py`. `-1 cháu, -2 cháu, -3 chắt, -4 chút, -5 chít`. Reciprocates
the ascending ladder exactly: ông↔cháu, cụ↔chắt, kỵ↔chút. `MAX_TABLE_GAP`
needed no change — `resolve_term` reads `TERMS` before the generic bound, so
`-5` is found; its comment now says so instead of claiming symmetry it does
not have.

**Reciprocity property test added** (`giapha/tests/test_kinship_reciprocity.py`):
a purpose-built clan (5 generations up, 6 down, both nội and ngoại, a
collateral branch 6 deep) is swept over every ordered pair; if A calls B a
word listed in `RECIPROCAL`, B must call A the documented counterpart.
Two supporting invariants in the same file:
`test_every_word_in_the_table_is_reached` (the sweep really does touch every
`TERMS` value, so it cannot silently stop covering the table) and
`test_every_affinal_row_keys_off_a_word_the_table_can_produce` (catches an
`AFFINAL_TERMS` row left keyed on a word the table no longer emits — which is
exactly what H2's edit would otherwise have created with `('cậu/dì', ·)`).

### C2 — own spouse checked before B's other marriages
`kinship.py::resolve_kinship`. `if a_id in spouses_of(spouses, b_id): return
married_couple(...)` sits above the walk, so the answer no longer depends on
autoincrement order. Test asserts both id orderings.

### H1 — hedge lookup now widens `side` too
`kinship_lookup.py`. Extracted `_widenings(side, gender)` and used it in BOTH
`_candidate_keys` and the hedge lookup — the reviewer's root cause (a
hand-rolled second fallback) is gone, not just its symptom. The three
`gap == 0` rows are now reachable; `test_every_hedge_row_is_reachable` asserts
every row in `AMBIGUOUS_TERMS` resolves, on both sides where the row is
side-agnostic, so a future dead row fails the suite.

### H2 — strict Northern rule adopted; table now matches the docstring
`kinship_terms.py`. `(BANG, 1, NGOAI, ·, True) → bác`, `('nam', False) → cậu`,
`('nu', False) → dì`. Maternal hedges added: `bác/cậu`, `bác/dì`,
`bác/cậu/dì`. The old `elder=None` maternal rows are gone, so there is no
longer anywhere a seniority-bearing word returns `confident: true` without a
`birth_order` behind it. Docstring rewritten to state the rule and to record
that the table used to contradict it.

Affinal consequences: `mợ` stays `cậu`'s wife (so it now follows seniority
automatically), `('bác', 'nu') → bác gái`, and hedge rows `('bác/cậu','nu') →
bác gái/mợ`, `('bác/dì','nam') → bác/dượng`, `('bác/cậu/dì', ·)`.

### H3 — a marriage link with no word hedges instead of denying the relation
`kinship_affinal.py` + `kinship_affinal_terms.py`. New reason
`REASON_AFFINAL_NO_TERM = 'không có từ xưng hô thông dụng'`, returned with
`confident: False` and with the spouse named in `explain`. `REASON_NO_BLOOD`
(`confident: True`) is now reachable only when both marriage walks came back
empty — verified by `test_a_real_stranger_still_reports_no_blood_confidently`.
Missing rows added: `cụ`, `kỵ`, `chắt`, `chút`, `chít`, the `ông nội`/`bà
ngoại` family (second spouse of a grandparent → `ông`/`bà`, not `ông nội`,
which implies blood), and every gender hedge including the `('bác/cậu/dì',
'nam')` case the reviewer used to falsify hedge propagation.

### H4 — A-side affinity implemented
`kinship_affinal.py::affinal` calls the same `_through_marriage` twice with
the arguments swapped and swaps the second result back; there is one
implementation, not two. A named word wins over a hedge whichever side
produced it. A con dâu now gets `bố`/`chú`/`anh` for her husband's family and
is called `con`/`cháu`/`em` back.

**Both A and B married in:** documented and pinned by
`test_two_people_who_both_married_in_get_no_derived_term` — stays
`khong_cung_huyet_thong`. Naming it (chị dâu = wife of my husband's brother)
needs two marriage hops plus a rule for which spouse to route through; out of
scope, stated in `resolve_kinship`'s and `affinal`'s docstrings rather than
left for a caller to discover.

## Mediums / Lows

| Item | Action |
|---|---|
| M1 affinal `path`/`common_ancestor` misleading | **Fixed** — nulled, consistent with `_married_couple`. Serializer docstrings corrected; `explain` names the spouse instead. Chose null over a `via` field: KISS, and the client contract already handles null. |
| M2 `explain_affinal` never hedges | **Fixed** — `_doubts(*entries)` appended on both affinal branches. |
| M3 `assertNumQueries` vacuous | **Fixed** — all three assert `200` + the term. Fourth test added pinning the true worst case (4: role + binding + rows + marriages); view docstring now states the ceiling instead of asking the reader to multiply. |
| M4 `clan_kinship_rows` ignores `MAX_CLAN_PERSONS` | **Fixed as an explicit documented exemption**, no cap added. A truncated row set here does not degrade the answer, it falsifies it (real relative → `khong_cung_huyet_thong`, `confident: True`). A count-first guard would cost a query and break the 2-query budget for every request to protect a case no clan has reached. |
| L1 fail-open docstrings assert something false | **Fixed** — `kinship_graph` docstring now says truncation CAN select a farther surviving ancestor and emit a confident wrong term, and that safety comes from the counter being unreachable, not from BFS order. `test_truncated_walk_never_invents_a_nearer_ancestor` renamed to `..._stops_early_instead_of_raising`; its docstring no longer claims the property it never tested. |
| L2 ASCII slugs in Vietnamese sentences | **Declined** — cosmetic, and H1 removed the common path that surfaced `ngoai_bang_tu_vung` to users. |
| L3 `member_binding` needless `select_related` | **Declined** — not in scope; same query count. |
| L4 unknown id == confident stranger | **Declined** — the view guards it; changing the service contract is out of scope. |
| L5 `path.side` on full siblings | **Declined** — deterministic and documented. |
| M5 extra API tests (cross-clan binding, stale binding) | **Declined** — not in the assigned list; behaviour already correct per the review. |

## Structural change forced by the 200-line rule

`kinship.py` reached 271 lines and `kinship_terms.py` 231 once H3/H4 landed.
Split along existing seams, no logic moved between concerns:

- `kinship_blood.py` (77) — `result` / `unrelated` / `blood_result`, i.e. the
  response shape. Needed by both callers below; keeping it in `kinship.py`
  would have made `kinship_affinal` → `kinship` a cycle.
- `kinship_affinal.py` (148) — the whole marriage half.
- `kinship_affinal_terms.py` (81) — `AFFINAL_TERMS` / `SPOUSE_TERMS`.
- `kinship.py` (72) — `resolve_kinship` only: blood, else marriage, else no link.

`kinship.py`'s pipeline map lists all seven modules. Not a taste refactor —
without it two files ship over the limit.

## Files changed

| File | Lines | Change |
|---|---|---|
| `giapha/services/kinship.py` | 72 | reduced to `resolve_kinship`; C2 hoist; docstrings |
| `giapha/services/kinship_blood.py` | 77 | **new** (extracted) |
| `giapha/services/kinship_affinal.py` | 148 | **new** — H3 + H4 + M1 |
| `giapha/services/kinship_affinal_terms.py` | 81 | **new** (extracted) — H2/H3 rows |
| `giapha/services/kinship_terms.py` | 162 | C1 ladder, H2 rows + hedges, docstrings |
| `giapha/services/kinship_lookup.py` | 114 | H1 `_widenings` |
| `giapha/services/kinship_explain.py` | 82 | M2 |
| `giapha/services/kinship_graph.py` | 107 | L1 docstring |
| `giapha/selectors/person.py` | +11 | M4 exemption docstring |
| `giapha/views/kinship.py` | 106 | M3 budget docstring |
| `giapha/serializers/kinship.py` | 65 | M1 docstrings |
| `giapha/tests/test_kinship.py` | 501 | corrected C1 tests; +18 |
| `giapha/tests/test_kinship_reciprocity.py` | 187 | **new** — property + integrity |
| `giapha/tests/test_kinship_api.py` | 208 | M3 |

## Cultural calls — flagged rather than guessed

1. **`bác` for the elder sibling of the mother** — implemented per the owner
   decision. It is what the module's own docstring always claimed.
2. **`bác gái` for the wife of a `bác`** — applied to the single key
   `('bác','nu')`, so it covers the paternal and maternal `bác` alike. I
   believe this is uniform in Northern usage; if a clan says plain `bác`, it
   is a one-line table edit.
3. **Stepmother deliberately left OUT of `AFFINAL_TERMS`.** Usage genuinely
   varies (`mẹ` / `dì` / `mẹ kế`) and picking one is a guess. She therefore
   comes back as the H3 hedge — a link acknowledged, no word asserted. Same
   for `('mẹ','nam')`. This is the design principle applied, not an omission.
4. **`('ông nội','nu') → bà`, not `bà nội`.** A grandfather's second wife is
   addressed `bà`; `bà nội` asserts blood she does not have.
5. **Over-hedge, knowingly accepted:** a relative of unknown gender at
   `gap == 1` returns `bác/chú/cô` (or `bác/cậu/dì`) even when `birth_order`
   IS known and rules `bác` in or out. `AMBIGUOUS_TERMS` has no `elder` slot.
   Pre-existing on the paternal side; H2 gave the maternal side the same
   shape. An honest over-hedge, never a wrong word.

## Unresolved questions

1. **Collateral `cháu` at a 2-generation gap** — the reciprocal argument
   (ông↔cháu) is unambiguous and the plan's `chênh 3 đời → chắt` now agrees,
   but the reviewer's question stands: does any real gia phả text write
   `chắt` collaterally at gap 2? Worth one check against a printed gia phả.
2. **`bác gái` vs `bác`** for a bác's wife — see call 2 above.
3. **A-side `explain` is phrased from B's side**: "Con dâu kết hôn với Tôi.
   Bác ngoại gọi Tôi là cháu, nên xưng hô với Con dâu theo quan hệ hôn nhân
   đó." Every clause is true, but it explains `b_calls_a` while the client is
   usually asking about `a_calls_b`. A second sentence template would fix it;
   I did not add one because it is copy, not correctness.
4. **Test file size**: `test_kinship.py` is 501 lines (was 312). Production
   files are all under 200; splitting the marriage classes into their own
   module would need the shared fixture imported across test modules. Left
   alone as taste — say the word and it is a 10-minute move.
5. Should `REASON_AFFINAL_NO_TERM` be an ASCII slug like `REASON_NO_BLOOD`
   rather than Vietnamese? It is currently rendered straight into `explain`,
   which reads well, but it is also the value a client would branch on. This
   is the L2 split done properly and I did not want to invent wire format.

**Status:** DONE_WITH_CONCERNS
**Summary:** C1, C2, H1, H2, H3, H4 all fixed with regression tests confirmed failing before (24 failures) and passing after; reciprocity property test plus two table-integrity invariants added; every docstring the review proved false corrected; full suite 560 passed / 4 skipped, migration check clean.
**Concerns/Blockers:** Three cultural calls carry residual uncertainty and are listed above rather than buried — chiefly whether `bác gái` or plain `bác` names a bác's wife, and the deliberate refusal to name a stepmother. The 200-line rule forced a 3-way module split of `kinship.py`/`kinship_terms.py`; no logic moved between concerns, but it is a larger diff than a table fix.
