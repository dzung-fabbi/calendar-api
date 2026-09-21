---
name: feedback-verify-claims-with-throwaway-probes
description: In this repo, review behavioural claims by writing and running throwaway probe tests — docstrings and plan files here are confidently wrong often enough that reading is not review
metadata:
  type: feedback
---

When reviewing `giapha/`, do not accept a docstring's or plan file's description of
behaviour. Write a temporary test module (`giapha/tests/test_zz_review_probe.py`), run it
with `./scripts/run-tests.sh giapha.tests.test_zz_review_probe`, then delete it before
reporting.

**Why:** this codebase has unusually rich, confident prose in docstrings and phase plans,
and that prose has repeatedly turned out to be false while the surrounding code compiles
and the suite stays green. Phase 5: the plan was wrong about Tết 1985 and the code was
right (see [[project-giapha-lunar-1985-discrepancy]]). Phase 6: three module docstrings
asserted a retry that arithmetically cannot happen, a safety counter that is unreachable,
and a leak that was only half-closed — a full green suite (450 tests) hid all of it. The
prose is the least reliable artefact here, not the most.

**How to apply:** any review finding phrased as "the docstring says X" needs an executed
probe before it goes in the report. Probes are cheap — the suite boots in ~5s against the
compose MySQL. Report findings as PROVEN with the probe output pasted in; the lead acts on
those immediately and argues with unproven ones. Related: [[giapha-lunar-verification-method]].

**Corollary observed 2026-09-05 (phase 6 fix verification):** the *fix* reports here are
more reliable than the docstrings. When a fix report claims "I reverted each fix and
watched the matching test go red", spot-checking ONE (the highest-risk) has been enough —
the C1 revert went red exactly as claimed. Spend the probe budget on what the fix report
does NOT claim instead: sibling code paths of the same bug class (H2 fixed the OAuth mint
path and missed the credentials-file read, same module, same failure class) and the
concurrency window a single-process test cannot see.

**Phase 7 confirmation + faster probe route (2026-09-05):** `giapha/services/` is ORM-free
by house rule, so pure-service probes do NOT need Docker — a plain `python probe.py` with
`sys.path.insert(0, repo_root)` imports `giapha.services.*` directly and runs in under a
second. Use the scratchpad for these, keep `./scripts/run-tests.sh` for view/selector work
only. Pattern held again: the phase-7 `kinship_terms.py` docstring stated a Northern rule
("elder sibling of EITHER parent is bác") that its own table contradicts, and the module's
fail-open safety argument was false as written. Both were invisible by reading and obvious
in one probe.

**Highest-yield probe for table-driven features: the reciprocal sweep.** Loop every ordered
pair in a small fixture and print `a_calls_b | b_calls_a` side by side. Phase 7's headline
defect (collateral `ông` paired with `chắt`, where the correct counterpart is `cháu`) was
invisible in 46 green table tests because each test asserted one direction only — the
suite re-asserted the same dict the code reads. Any lookup table with two directions gets
this sweep before anything else.

**Phase 8 corollary — the two highest-yield probes so far (2026-09-05):**

1. **Mutation-test the guard the spec calls mandatory.** Comment out the single
   check the plan file marks "bắt buộc" and re-run the phase's own suite. Phase 8:
   deleting `if meta is None: raise BadRequestException(...)` (the HEAD-object
   existence check, the whole reason the confirm step exists) left 26/26 green,
   because the boto3 mock's `head_object` never returns a 404. Deleting the
   prefix check DID go red. Do this before writing any "test quality" paragraph —
   it converts an opinion into a fact in two runs.
2. **Any "field X has exactly one write path" claim must be checked against
   `POST .../restore/{revision_id}`.** `services/revision.snapshot()` walks
   `person._meta.fields` and excludes only a small `_EXCLUDED_FIELDS` set, and
   `restore()` `setattr`s everything back followed by a full `person.save()`. So
   removing a field from `PersonWriteSerializer._WRITE_FIELDS` does NOT close it:
   restore re-applies whatever a historic revision payload holds, with none of the
   new endpoint's validation. Phase 8's `photo_key` fell into exactly this hole.
   Grep `_EXCLUDED_FIELDS` whenever a review touches Person write permissions.

**Also settled in phase 8, so nobody re-litigates it:** `apis/tests/shape.py`
snapshots are *shape* snapshots (`shape_of()` reduces every scalar to a type name),
so nondeterministic response values — presigned URLs, timestamps — do NOT break
them; only `assert_value_matches` would. And `boto3.generate_presigned_url` makes
zero network calls (proven by monkeypatching `socket.socket` to raise), at ~0.3 ms
each; any comment claiming presigning costs "one S3 request" is wrong.

**Social-login-removal review corollary — probing the HTTP layer without touching the repo
(2026-09-06):** when the task forbids editing the working tree, do NOT add a probe test
module. Write the probe to the scratchpad and mount it as a SECOND volume:
`docker run --rm --network calendar-api_default -v "$(pwd -W):/code" -v "$SCRATCH:/probe"
-w /code -e DB_HOST=db calendar-api-test:latest python /probe/probe.py`, with the script
doing `sys.path.insert(0,'/code')`, `DJANGO_SETTINGS_MODULE=djangopj.settings_test`,
`django.setup()`, `setup_test_environment()`, `connection.creation.create_test_db(autoclobber=True)`,
then driving `django.test.Client` directly. Full HTTP stack, no repo mutation, ~10 s.
Note `./scripts/run-tests.sh` may fail at its `docker build` step (registry timeouts) while
`calendar-api-test:latest` is already current — bypass the build, do not "fix" the script.

**Highest-yield probe for any DRF view rewrite: sweep the `Accept` header and the body
shape.** Setting `renderer_classes = (JSONRenderer,)` on a view that previously used the
project defaults silently converts `Accept: text/html` from 200 into **406**, and any
`_copy_body`-style helper that calls `data.items()` 500s on a JSON body that is a list,
string, number or `null`. Neither is visible in a green suite. Loop
`['*/*','application/json','text/html','application/xml']` and
`['[1,2,3]','"x"','null','42','','{oops']` against every rewritten endpoint before writing
the report.
