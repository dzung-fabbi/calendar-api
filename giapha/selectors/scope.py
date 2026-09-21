"""DB reads behind the write-scope check (`giapha.permissions_scope`).

Exactly two queries, whatever the clan size: one over Person (edges plus the
"claimed and verified" flag via the reverse OneToOne, a LEFT JOIN) and one
over Marriage. The walk itself is pure -- `services.family_scope`.
"""

from giapha.models import Marriage, Person


def scope_graph(clan_id):
    """`(parent_edges, marriage_pairs, verified_person_ids)` for `clan_id`.

    Non-deleted persons only: a soft-deleted node is gone from the tree and
    must not be editable through anyone's scope. Every marriage is kept
    (divorced too) -- the scope asks "is this my family's record", not
    "what do I call them".
    """
    rows = (
        Person.objects.filter(clan_id=clan_id, is_deleted=False)
        .values_list('id', 'father_id', 'mother_id', 'member_link__person_verified')
    )
    parent_edges = []
    verified_ids = set()
    for person_id, father_id, mother_id, verified in rows:
        parent_edges.append((person_id, father_id, mother_id))
        if verified:
            verified_ids.add(person_id)

    marriage_pairs = list(
        Marriage.objects.filter(husband__clan_id=clan_id).values_list('husband_id', 'wife_id')
    )
    return parent_edges, marriage_pairs, verified_ids


def is_unattached(clan_id, person_id):
    """Live person of `clan_id` with no parents and no marriage -- a node just
    created to be someone's spouse. Only such a person may be married to an
    in-scope person by a scoped writer (review C2): marrying an existing
    relative would pull them into the writer's scope.
    """
    person = Person.objects.filter(clan_id=clan_id, id=person_id, is_deleted=False).only(
        'father_id', 'mother_id').first()
    if person is None or person.father_id or person.mother_id:
        return False
    return not Marriage.objects.filter(husband_id=person_id).exists() and \
        not Marriage.objects.filter(wife_id=person_id).exists()
