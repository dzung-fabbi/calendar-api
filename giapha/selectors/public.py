"""DB-facing queries for the no-auth public gia phả surface (phase 9).

Deliberately its own module, not an extra branch bolted onto
`selectors/tree.py` / `selectors/person.py` -- those two are already close
to the 200-line ceiling (`docs/code-standards.md` -> Files), and "every read
reachable with no account" is a natural seam of its own, same reasoning as
`views/photo.py` / `views/photo_urls.py` splitting in phase 8.

DEFENCE IN DEPTH: every function below queries a LIVING person and a DEAD
person with two DIFFERENT, hand-picked field lists. A living person's row
literally never has `ten_huy`/birth or death columns/`que_quan`/
`nghe_nghiep`/`tieu_su`/`photo_key` loaded into memory -- so a bug in
`services.public_tree`/`services.public_person` or in
`serializers.public` cannot leak them; the data simply isn't there to read.
`mo_phan_lat`/`mo_phan_lng`/`mo_phan_note` are absent from BOTH field lists,
for anyone -- no branch here ever selects them. So is `parent_kind`: the
edge builder used to copy it into every parent edge, publishing
adoption/step-child status for living people (see
`services.public_tree.public_parent_edges_from_rows`).
"""

from giapha.models import Person
from giapha.services.public_tree import public_node_from_row, public_parent_edges_from_rows

_PUBLIC_DEAD_TREE_FIELDS = (
    'id', 'ho_ten', 'ten_huy', 'generation', 'branch', 'is_truong', 'birth_order',
    'birth_solar', 'death_solar', 'death_lunar_day', 'death_lunar_month', 'death_lunar_leap',
    'photo_key', 'father_id', 'mother_id',
)
_PUBLIC_LIVING_TREE_FIELDS = (
    'id', 'ho_ten', 'generation', 'branch', 'is_truong', 'birth_order',
    'father_id', 'mother_id',
)
_PUBLIC_DEAD_DETAIL_FIELDS = (
    'id', 'ho_ten', 'ten_huy', 'ten_tu', 'ten_hieu', 'thuy_hieu',
    'generation', 'branch', 'is_truong', 'birth_order',
    'birth_solar', 'death_solar', 'death_lunar_day', 'death_lunar_month', 'death_lunar_leap',
    'que_quan', 'nghe_nghiep', 'tieu_su', 'photo_key',
)
_PUBLIC_LIVING_DETAIL_FIELDS = (
    'id', 'ho_ten', 'generation', 'branch', 'is_truong', 'birth_order',
)


def _is_living(death_solar, death_lunar_day, death_lunar_month):
    """DELIBERATELY STRICTER than `services.tree.node_from_row`'s
    `has_death_info` (which is OR-semantics: ANY one of the three columns
    set means "has death info", so a partial record reads as DEAD -- on a
    public surface that is the fail-OPEN direction, since "dead" is what
    unlocks the full field list).
    The internal tree is authenticated -- failing open there means a staff
    member sees a slightly-wrong `is_living` on a record that should have
    been fixed. Here, failing open means publishing a living person's
    `ten_huy`/birth year/`que_quan`/`nghe_nghiep`/`tieu_su`/photo to the
    whole internet, so this predicate is written to require a COMPLETE
    death record (a solar date, OR both lunar day and lunar month) before
    it will call someone dead. A person with only `death_lunar_month` set
    -- possible via the admin's plain `ModelAdmin` (no `clean()`), a CSV
    import, a raw `queryset.update()`, or any path that bypasses
    `services.person_rules.validate_death_pair_complete` -- must still
    read as living on the public surface.

    `validate_death_pair_complete` is what keeps this invariant true for
    data written through the REST API; this predicate does not rely on
    that having run, it treats the row as untrusted input.
    """
    return death_solar is None and not (death_lunar_day is not None and death_lunar_month is not None)


def public_tree_payload(clan_id, ten_ho, *, max_persons, hide_living_details):
    """Public counterpart of `selectors.tree.tree_payload()`.

    Marriage edges are deliberately OMITTED at MVP -- a marriage's `status`
    (`ly_hon`/`goá`) is not on the phase-9 whitelist table and can itself be
    sensitive information about a living person; only parent edges (pure
    ids, already the point of a genealogy tree) are drawn. Revisit only as
    a deliberate, separate product decision.
    """
    id_rows = list(
        Person.objects.filter(clan_id=clan_id, is_deleted=False)
        .order_by('id')
        .values_list('id', 'death_solar', 'death_lunar_day', 'death_lunar_month')[:max_persons + 1]
    )
    truncated = len(id_rows) > max_persons
    if truncated:
        id_rows = id_rows[:max_persons]

    order_by_id = {row[0]: index for index, row in enumerate(id_rows)}
    dead_ids = [pid for pid, ds, dld, dlm in id_rows if not _is_living(ds, dld, dlm)]
    living_ids = [pid for pid, ds, dld, dlm in id_rows if _is_living(ds, dld, dlm)]

    dead_rows = (
        list(Person.objects.filter(id__in=dead_ids).values(*_PUBLIC_DEAD_TREE_FIELDS)) if dead_ids else []
    )
    living_rows = (
        list(Person.objects.filter(id__in=living_ids).values(*_PUBLIC_LIVING_TREE_FIELDS)) if living_ids else []
    )

    rows_by_id = {row['id']: (row, False) for row in dead_rows}
    rows_by_id.update({row['id']: (row, True) for row in living_rows})

    nodes = []
    edge_rows = []
    for person_id in sorted(rows_by_id, key=order_by_id.get):
        row, is_living = rows_by_id[person_id]
        nodes.append(public_node_from_row(row, is_living=is_living, hide_living_details=hide_living_details))
        edge_rows.append(row)

    return {
        'clan': {'id': clan_id, 'ten_ho': ten_ho},
        'nodes': nodes,
        'edges': public_parent_edges_from_rows(edge_rows),
        'truncated': truncated,
    }


def public_person_row(clan_id, person_id):
    """Returns `(row, is_living)`, or `(None, None)` if `person_id` doesn't
    resolve to a non-deleted Person in `clan_id`. Two queries: the first
    reads only the three columns needed to classify living/dead, the second
    re-queries with EXACTLY the field list that classification allows.

    TOCTOU, not locked: a death record could be written between the two
    queries, in which case this response uses the liveness (and field list)
    seen by the FIRST query. Not worth a `select_for_update()` at MVP -- a
    no-auth GET taking a row lock would be its own throttle-bypass-shaped
    footgun, and the very next request self-heals (re-reads both columns
    fresh). The second query intentionally does NOT repeat
    `is_deleted=False`: `person_id` only reached this line because the
    first query already proved it resolves to a non-deleted row in this
    clan, so the second query is a field-list projection of an id already
    known-good, not a fresh trust boundary.
    """
    liveness = (
        Person.objects.filter(clan_id=clan_id, id=person_id, is_deleted=False)
        .values('death_solar', 'death_lunar_day', 'death_lunar_month')
        .first()
    )
    if liveness is None:
        return None, None

    is_living = _is_living(
        liveness['death_solar'], liveness['death_lunar_day'], liveness['death_lunar_month'],
    )
    fields = _PUBLIC_LIVING_DETAIL_FIELDS if is_living else _PUBLIC_DEAD_DETAIL_FIELDS
    row = Person.objects.filter(clan_id=clan_id, id=person_id).values(*fields).first()
    return row, is_living
