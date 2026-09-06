"""DB-facing queries for Person.

Every read here filters `is_deleted=False` unless the function name says
otherwise (`*_any`) -- a soft-deleted person is still `father_id`/`mother_id`
on their children, so a selector that forgets the filter would silently
break the tree for every caller above it.
"""

from django.db.models import Q

from giapha.models import Person


def clan_edges(clan_id):
    """`[(id, father_id, mother_id), ...]` for every non-deleted Person in
    `clan_id`. One query, no full rows.

    ITS SIGNATURE MUST NOT CHANGE: six call sites unpack these rows as
    exactly three positional values --
    `selectors/tree.py`, `services/person_rules.py`, `views/person.py`,
    `views/person_list.py`, `views/person_revision.py` and
    `management/commands/recompute_generations.py`.

    THREE EDGE SHAPES EXIST ON PURPOSE -- read `clan_edges_all` and
    `clan_kinship_rows` before unifying any of them. This one is the
    *visible tree*: soft-deleted people are gone from it, which is exactly
    right for rendering and for the generation walk. Note that the giỗ
    follow resolution deliberately consumes `clan_edges_all`, NOT this, and
    the kinship calculator consumes only `clan_kinship_rows`.
    """
    return list(
        Person.objects.filter(clan_id=clan_id, is_deleted=False)
        .values_list('id', 'father_id', 'mother_id')
    )


def clan_edges_all(clan_id):
    """`clan_edges` INCLUDING soft-deleted rows -- the *connectivity* shape.

    DO NOT UNIFY THIS WITH `clan_edges`. A soft-deleted person is still the
    `father_id`/`mother_id` of their children, so walking the filtered edge
    list stops dead at them: soft-deleting one mistakenly-duplicated `ông`
    silently cut `cụ`, `kỵ` and everything above out of every descendant's
    giỗ reminders. Traversal must therefore pass THROUGH a soft-deleted
    person.

    That is safe only where the *answer* is separately restricted to
    non-deleted people -- currently the giỗ-follow resolution, whose
    candidate set comes from `selectors.gio.deceased_with_lunar_death`
    (`is_deleted=False`), so nobody is ever notified ABOUT a soft-deleted
    person. Every other caller (tree rendering, generation walk, phase 7
    kinship) wants `clan_edges` and its "deleted means gone" semantics.
    """
    return list(
        Person.objects.filter(clan_id=clan_id)
        .values_list('id', 'father_id', 'mother_id')
    )


def clan_kinship_rows(clan_id):
    """`[{'id', 'father_id', 'mother_id', 'birth_order', 'gioi_tinh', 'ho_ten'}, ...]`
    for every non-deleted Person in `clan_id`. One query.

    A THIRD EDGE SHAPE, ON PURPOSE -- see `clan_edges` / `clan_edges_all`
    above before "unifying" the three. The kinship calculator needs more than
    the parent links: `birth_order` decides bác vs chú, `gioi_tinh` decides
    chú vs cô, and `ho_ten` names the common ancestor in the response.
    Widening `clan_edges` instead is not an option: six call sites unpack its
    rows as exactly three positional values (see its own docstring for the
    list), and every one of them would break. Note that `gio_follow`'s
    resolution reads `clan_edges_all`, not `clan_edges`.

    DICTS, NOT TUPLES. Positional unpacking is precisely what made
    `clan_edges` impossible to extend; a dict row can gain a key without
    touching a single consumer. The cost is one dict per person instead of
    one tuple -- irrelevant next to the query itself.

    Soft-deleted people are excluded, matching `clan_edges` semantics: for a
    *visible* answer ("what do I call this person?") a deleted ancestor
    genuinely is gone, and letting the walk pass through them would let a
    removed person still shape the term shown to the user.

    EXEMPT FROM `settings.MAX_CLAN_PERSONS`, DELIBERATELY. Every other bulk
    clan read caps its row count; this one must not. The cap works by
    truncating, and a truncated row set here does not degrade the answer, it
    FALSIFIES it: a missing ancestor turns a real relative into
    `khong_cung_huyet_thong` with `confident: True`, which is precisely the
    output this endpoint exists to never produce. A wrong vai vế is worse
    than a slow request. The cost is bounded anyway -- one query, six columns,
    and the walk is O(clan size) per request.
    """
    return list(
        Person.objects.filter(clan_id=clan_id, is_deleted=False)
        .values('id', 'father_id', 'mother_id', 'birth_order', 'gioi_tinh', 'ho_ten')
    )


def birth_solar_by_id(clan_id):
    """`{id: birth_solar_or_None}` for every non-deleted Person in `clan_id`.

    Loaded once per write request (single or bulk) so `parent_born_before_child`
    doesn't re-query per record.
    """
    return dict(
        Person.objects.filter(clan_id=clan_id, is_deleted=False).values_list('id', 'birth_solar')
    )


def get_person_or_none(clan_id, person_id):
    return (
        Person.objects.filter(clan_id=clan_id, id=person_id, is_deleted=False)
        .select_related('father', 'mother')
        .first()
    )


def get_person_any(clan_id, person_id):
    """Same as `get_person_or_none` but includes soft-deleted rows -- used by
    the revisions/restore endpoints, which must keep working after a delete.
    """
    return (
        Person.objects.filter(clan_id=clan_id, id=person_id)
        .select_related('father', 'mother')
        .first()
    )


def persons_of(clan_id):
    return (
        Person.objects.filter(clan_id=clan_id, is_deleted=False)
        .select_related('father', 'mother')
        .order_by('id')
    )


def search_persons(clan_id, *, q=None, generation=None, branch=None, death_year=None):
    """`persons_of(clan_id)` narrowed by `GET /persons?q=&generation=&branch=&death_year=`.

    `q` matches `ho_ten` OR `ten_huy` (`icontains`, relying on the DB's
    `utf8_unicode_ci` collation -- see `docs/system-architecture.md`); the
    other three are exact filters. Falsy/`None` values are no-ops so the
    plain list view keeps working unchanged when no filter is given.
    """
    queryset = persons_of(clan_id)
    if q:
        queryset = queryset.filter(Q(ho_ten__icontains=q) | Q(ten_huy__icontains=q))
    if generation is not None:
        queryset = queryset.filter(generation=generation)
    if branch:
        queryset = queryset.filter(branch=branch)
    if death_year is not None:
        queryset = queryset.filter(death_solar__year=death_year)
    return queryset


def active_person_count(clan_id):
    return Person.objects.filter(clan_id=clan_id, is_deleted=False).count()


def photo_keys_for(clan_id, person_ids):
    """`{id: photo_key}` for every non-deleted Person among `person_ids` that
    belongs to `clan_id`. An id from another clan, or one that doesn't exist
    (or is soft-deleted), is silently absent from the result rather than
    raising -- `views.photo.ClanPhotoUrlsAPIView` relies on this so a client
    mixing in ids from a clan it also belongs to just gets those ids dropped,
    never another clan's photo.
    """
    return dict(
        Person.objects.filter(clan_id=clan_id, id__in=person_ids, is_deleted=False)
        .values_list('id', 'photo_key')
    )


def children_count(person_id):
    """Number of Persons -- soft-deleted or not -- that reference `person_id`
    as father or mother. Deliberately counts soft-deleted children too
    (unlike every other selector in this module): a soft-deleted child still
    carries `father_id`/`mother_id`, and if it is later restored while its
    parent was allowed to be deleted, it would point at a person that no
    longer exists in any live view (H4). Blocking the parent's delete while
    ANY such pointer exists -- live or not -- is simpler and safer than
    nulling it out at delete time.
    """
    return Person.objects.filter(Q(father_id=person_id) | Q(mother_id=person_id)).count()
