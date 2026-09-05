# Phase 1: Scaffold giapha app - Report

Date: 2026-09-05

## Status: DONE

## Files created
- `giapha/__init__.py`, `giapha/apps.py` (GiaPhaConfig), `giapha/urls.py` (`urlpatterns = []`)
- `giapha/models/`: `__init__.py`(25L flat re-export), `choices.py`(40L), `clan.py`(65L, Clan/ClanMember/ClanInvite), `person.py`(88L), `marriage.py`(27L), `revision.py`(24L)
- `giapha/admin/`: `__init__.py`(7L), `clan.py`(27L, ClanAdmin+ClanMemberInline+ClanInviteAdmin), `person.py`(24L, PersonAdmin raw_id father/mother/clan + MarriageAdmin)
- `giapha/selectors/__init__.py`, `giapha/services/__init__.py`, `giapha/serializers/__init__.py`, `giapha/views/__init__.py`, `giapha/tests/__init__.py` — all empty
- `giapha/management/__init__.py`, `giapha/management/commands/__init__.py` — empty
- `giapha/migrations/0001_initial.py` — generated, reviewed by eye

## Files modified
- `djangopj/settings.py`: added `'giapha.apps.GiaPhaConfig'` right after `'apis.apps.ApisConfig'` in INSTALLED_APPS; added `MAX_CLAN_PERSONS = 5000` after LOGGING block
- `djangopj/urls.py`: added `path('api/gia-pha/', include('giapha.urls'))` after the `apis.urls` include

## Key decisions
- father/mother FK on_delete=SET_NULL (spec said "null" but no explicit on_delete; SET_NULL avoids cascading a whole subtree delete when a parent record is removed)
- ClanInvite kept a `created_at` field (spec table omitted it) — harmless audit field, consistent with every other model in the app, no behaviour
- `is_living` intentionally NOT on Person model per spec — left as a note for services/ in a later phase (not implemented, since phase 1 is models/admin only)

## Verification (ran inside Docker per script pattern, MSYS_NO_PATHCONV=1, pwd -W)
- `manage.py check --settings=djangopj.settings_test` -> "System check identified no issues (0 silenced)"
- `manage.py makemigrations giapha --settings=djangopj.settings_test` -> `0001_initial.py` generated; reviewed: 3 Person indexes present (`giapha_person_clan_gen_idx`, `giapha_person_clan_branch_idx`, `giapha_person_clan_gio_idx`), all FKs correct (clan/husband/wife/user CASCADE; father/mother/actor/created_by SET_NULL), unique_together on Marriage(husband,wife) and ClanMember(clan,user)
- `manage.py migrate --settings=djangopj.settings_test` -> all migrations incl. `giapha.0001_initial` applied OK against MySQL 5.7
- `./scripts/run-tests.sh` -> existing apis suite: 50 tests, OK, unaffected by new migration
- `grep -r "from apis" giapha/` -> empty
- All model files < 200 lines (largest: person.py 88L)

## Acceptance criteria checklist
- [x] check clean
- [x] makemigrations produced 0001_initial.py, 3 Person indexes + FKs verified
- [x] migrate clean on MySQL 5.7
- [x] run-tests.sh apis suite green (50 tests)
- [x] no model file > 200 lines
- [x] grep "from apis" empty
- [x] admin registers Clan(+ClanMember inline), Person(raw_id father/mother/clan, list_filter, search_fields ho_ten/ten_huy), Marriage

## Unresolved questions
- None blocking. Phase 2+ (permissions/serializers/views/services incl. `is_living` helper) intentionally left untouched as instructed.
