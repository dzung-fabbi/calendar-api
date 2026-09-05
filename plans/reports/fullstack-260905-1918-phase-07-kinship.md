# Phase 07 — Máy tính xưng hô — Implementation Report

- Date: 2026-09-05
- Plan: `plans/260905-1053-gia-pha-dong-ho/phase-07-may-tinh-xung-ho.md`
- Status: **completed**

## Files

**Created**
| File | Lines | Role |
|---|---|---|
| `giapha/services/kinship_terms.py` | 158 | vocabulary as DATA (TERMS / AMBIGUOUS_TERMS / AFFINAL_TERMS / reasons) |
| `giapha/services/kinship_graph.py` | 100 | `ancestor_index`, `best_common_ancestor`, `lowest_common_ancestor` |
| `giapha/services/kinship_lookup.py` | 103 | facts → word; `resolve_term`, `is_elder`, gender/name accessors |
| `giapha/services/kinship_explain.py` | 73 | the `explain` sentence |
| `giapha/services/kinship.py` | 197 | orchestration: blood result, marriage edges, `resolve_kinship` |
| `giapha/serializers/kinship.py` | 59 | response shape |
| `giapha/views/kinship.py` | 103 | `ClanKinshipAPIView` |
| `giapha/tests/test_kinship.py` | 312 | 46 cases, `SimpleTestCase`, no DB |
| `giapha/tests/test_kinship_api.py` | 185 | 17 API cases |

**Modified**
`giapha/selectors/person.py` (+`clan_kinship_rows`), `giapha/selectors/marriage.py`
(+`clan_spouse_pairs`), `giapha/urls.py`, `giapha/selectors/__init__.py`,
`giapha/serializers/__init__.py`, `giapha/views/__init__.py`.

No model, no migration, nothing under `apis/`. `clan_edges` / `clan_edges_all`
untouched.

## Decisions worth reviewing

1. **New selector, not a widened `clan_edges`** (per the correction). `clan_kinship_rows`
   returns **dicts** (`id, father_id, mother_id, birth_order, gioi_tinh, ho_ten`), one
   query. Dicts because positional unpacking is exactly what froze `clan_edges`'
   signature; a dict row can gain a key without touching a consumer. Docstring says why
   a third shape exists.
2. **`clan_spouse_pairs` went in `selectors/marriage.py`, not `person.py`** — it queries
   `Marriage`. Deviation from the stated file list; putting a Marriage query in
   `person.py` would have broken the module boundary. Excludes `ly_hon`, keeps `goa`
   (a widow is still your thím; a divorcée is not).
3. **Table key is `(kind, gap, side, gender, elder)`, not the plan's `(da, db, ...)`.**
   `(da, db)` collapses: a father's cousin (`3,2`) and an uncle (`2,1`) are the same
   word. Keying on the raw pair needs an unbounded table. `kind` = trực hệ (one of the
   pair IS the ancestor) vs bàng hệ — that is what separates `con`/`cháu` from
   `cháu`/`chắt`.
4. **`None` in a table slot is a key value, not a wildcard.** Entries that depend on
   seniority exist ONLY under `elder=True/False`, so an unknown `birth_order` finds
   nothing and falls to the hedge. That is the mechanism that makes guessing impossible
   rather than merely discouraged.
5. **Fail-OPEN on the safety counter**, and not by analogy with either neighbour. This
   is a read; a 500 helps nobody. It is *safe* because BFS discovers ancestors in
   non-decreasing depth order, so a truncated walk can only MISS a common ancestor,
   never invent a nearer one — worst case is `term: null`, never a wrong vai vế.
   Pinned by `test_truncated_walk_never_invents_a_nearer_ancestor`.
6. **Maternal side is not seniority-dependent** (`cậu`/`dì` regardless of `birth_order`),
   per the plan's table and ordinary Northern usage. Paternal side is
   (`bác` / `chú` / `cô`). Consequence: no `confident: false` noise on the maternal side.
7. **A == B** → 200, `term: null`, `reason: "cung_mot_nguoi"`. Same shape as the
   no-blood answer; `confident: true`, because "there is no term" is a finding, not a
   hedge.
8. **`a` omitted** → `ClanMember.person`. Unbound caller → 400 naming `/toi-la`. A stale
   binding (person soft-deleted) gets its own message rather than being reported as a
   bad `a` the caller never sent.
9. **Marriage query is lazy** — loaded only after the blood walk fails, because an
   in-law term is unreachable while a blood link exists. This is what keeps the common
   case at 2 queries.
10. **Affinal `b_calls_a` is copied unchanged from the blood relative** ("gọi theo
    chồng/vợ"). Hedges propagate as hedges (`bác/chú` → `bác/thím`), never harden.
11. Five service modules instead of the plan's two — the 200-line rule. Each is one
    concern: data / graph / word / sentence / assembly.

## Verification

| Check | Result |
|---|---|
| `./scripts/run-tests.sh` (full) | **533 tests, OK, 4 skipped** (baseline 470 + 63 new) |
| `giapha.tests.test_kinship` + `test_kinship_api` | 63 passed |
| `makemigrations giapha --check --dry-run` | `No changes detected in app 'giapha'` |
| Query budget | `assertNumQueries(2)` explicit-`a` + blood; 3 when `a` defaults; 3 when no blood |
| Production files > 200 lines | none |

Coverage of the plan's mapping table: bác/chú/cô (elder+younger, both genders),
cậu/dì, anh/chị/em, cousins ranked by branch not age, thím/mợ/dượng/chồng-của-cô via
`Marriage`, own spouse, ông nội/bà nội/ông ngoại/bà ngoại, cụ/kỵ, tổ tiên beyond 4,
con/cháu/chắt/chút/chít both ladders, hậu duệ beyond 5, collateral ông/cụ/chắt/chút,
missing `birth_order`, equal `birth_order`, missing `gioi_tinh`, A==B, no common
ancestor, unknown id, hand-entered cycle, truncated walk.

## Success criteria (plan)

- [x] bác / chú / cô correct with `birth_order`
- [x] nội vs ngoại correct (chú vs cậu, cô vs dì)
- [x] thím / mợ / dượng via marriage edge
- [x] 3–5 generation gaps → chắt / chút / chít
- [x] missing `birth_order` → `confident: false`, no guess
- [x] no blood relation → 200 with `term: null`
- [x] all service tests on `SimpleTestCase`
- [x] endpoint ≤ 2 queries (common case, pinned)

## Environment note

Docker Desktop's Linux engine was wedged (`init control API` unresponsive for ~45 min,
every call 500). Recovered with `wsl --shutdown` + force-stop of the Docker Desktop
processes + relaunch. A half-created `test_django-db` from the interrupted run had to be
dropped manually before the suite would start. Nothing project-related; recorded in case
it recurs.

## Not done (out of scope, flagged)

- `docs/` not updated — no docs task was assigned. `docs/system-architecture.md` should
  eventually record the endpoint and the Northern-dialect decision.
- Phase file / `plan.md` status boxes not ticked — not in the file-ownership list.

## Unresolved questions

1. **Northern `bác` for a father's elder sister** is encoded as `bác` (not `cô`). Correct
   for the North; a Southern user will read it as wrong. Region option is deliberately
   YAGNI — confirm that is acceptable for MVP.
2. **A-side affinity is not implemented.** If A married into the clan and B is a blood
   relative of A's spouse, the answer is "no blood relation". Plan step 5 specifies only
   the B-side direction. Worth a phase-8 note?
3. **`parent_kind`** (`ruot`/`nuoi`/`ke`) is ignored — an adopted child gets the same
   terms as a natural one. Almost certainly what users want, but it is an unstated
   assumption.
4. **`AFFINAL_TERMS` has no entry above `ông`/`bà`.** The spouse of a `cụ` or `kỵ` falls
   back to "no blood relation" rather than a hedge. Rare; silence chosen over invention.
5. **Tie-break when two ancestors are equally near** (e.g. full siblings share both
   father and mother) picks the lower id, so `common_ancestor` on a full-sibling pair is
   usually the father. Deterministic, but arbitrary — is "prefer the father" the
   intended display?
