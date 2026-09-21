# Code review: shared clan tree collaboration (plan 260919, P1–P6)

Reviewer: code-reviewer subagent (report saved by lead). Score before fixes: 5.5/10.

## Critical (all PROVEN by probes) — FIXED
- C1 re-parenting own node under outsider widens scope → `permissions_scope.require_parent_change_write` on PATCH; restore checks restored parents.
- C2 marriage pulls any relative into scope → `require_marriage_write`: both partners in scope, or other partner unattached (no parents, no marriage).
- C3 invite ladder (invite own parent → alt account verified → climb) → `invite_scope_ids`: active only for downward (descendants + spouses, not self/root); else pending.

## High — FIXED
- H1 branch editor restore outside branch → `require_write` in restore.
- H2 branch editor self-binds anywhere, auto-verified → `binding_auto_verified`.
- H3 invites survive creator removal → deleted on member removal.

## Medium — FIXED
- M1 link import ignored FAMILY_MAX_PERSONS → capacity check.
- M2 CR list N+1 + unbounded → select_related target_marriage, default status=pending, cap 200.
- M3 linked-edit/contribute CRs skipped pending cap + pushed all reviewers → single `submit_change_request`.
- M4 staleness read vs apply race → approve passes `expected_version=base_version`, VersionConflict → 409 stale.

## Low
- L1 expiry vs concurrent approve → guarded update. FIXED
- L2 contribute ignores create_links failure → raises LINK_CONFLICT (rollback). FIXED
- L3 child with in-scope father + arbitrary mother → every given parent must be in scope. FIXED
- L4 import replay after family emptied returns stale ids. OPEN (low)
- L5 some views call ORM directly (family_import, family_linked_edit). OPEN (layering debt)
- L6 photo.py 226, tree.py 210 lines (pre-existing). OPEN

## Unresolved questions
1. C2 fix narrows spec "≥1 partner in scope" to "or other partner unattached" — product confirm.
2. C3: invites for own parents/siblings now always need approval — product confirm.
3. Should trưởng chi verify a binding AT the branch root (grants root's parents/siblings)?
