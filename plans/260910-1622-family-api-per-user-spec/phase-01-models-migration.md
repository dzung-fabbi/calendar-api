# Phase 1 — Models + migration

**Priority:** P0 · **Status:** ✅ Done

## Files
- Create `giapha/models/family.py`: `Family`, `FamilyPerson`, `FamilySpouse`
- Edit `giapha/models/__init__.py`, `giapha/models/choices.py` (thêm `FAMILY_GENDER`, `FAMILY_PARENT_REL`, `FAMILY_SPOUSE_REL`)
- Create `giapha/migrations/0009_family_person_spouse.py` (makemigrations)

## Thiết kế
- `Family.user` OneToOne(User) — một user một gia phả. `self_person` FK SET_NULL (spec 2.2, 2.6).
- `FamilyPerson.id` UUID pk (spec 3.1). `father`/`mother` self-FK SET_NULL (xoá không lan).
  `father_rel`/`mother_rel` null = blood. Ngày dương `DateField`; giờ `CharField(5)` "HH:mm".
  `lunar_leap` `BooleanField(null=True)`. `relationship` 24, `note` 200, `gio_event_id` 64.
- `FamilySpouse` (family, person_a, person_b, type) unique (a,b); service ghi canonical a<b theo str(uuid).

## Success
- `makemigrations --check` sạch; `migrate` chạy trên MySQL 5.7.
