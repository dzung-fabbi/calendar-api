---
name: project-scope-derived-from-mutable-edges
description: giapha row-level write scope is computed from tree edges the scoped writer can themselves mutate -- always probe for self-escalation
metadata:
  type: project
---

`giapha/permissions_scope.py` derives a verified member's writable set from the live graph
(parents, descendants, spouses of descendants, unverified siblings). Found 2026-09-19
(plan 260919 review, all PROVEN by probe): a scoped viewer could (a) PATCH own `father_id`
to anyone -> that person becomes "parent" -> writable; (b) POST a marriage between an
in-scope node and anyone (spec allows "1 side in scope") -> spouse becomes writable;
(c) mint an auto-active person-bound invite for their own parent, join with an alt account
(auto-verified) -> alt's scope climbs one generation; repeatable to the root.
Also branch editors (editor + `scope_root_person`) escaped via `restore` (still
`IsClanEditor`) and self-bind to any node (editor roles auto-verify).

**Why:** the spec reasoned about "who may edit X" but not "who may change the edges that
decide who may edit X".

**How to apply:** on any change to scope rules, write views, invites or bindings, probe
the sequence "edit an edge/binding I'm allowed to edit, then edit a node I wasn't".
Probe harness: [[feedback-verify-claims-with-throwaway-probes]] (scratchpad module mounted
as `/probe`, `PYTHONPATH=/probe`, `manage.py test probe_zz.test_probe`).
