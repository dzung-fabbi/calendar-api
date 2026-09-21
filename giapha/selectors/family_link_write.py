"""ORM writes for personal-tree <-> clan links (plan 260919 phase 4):
bootstrap a clan from a tree, confirm links, import clan persons.

Callers run these inside `transaction.atomic()` after membership/permission
checks; rule checks on personal-tree edges happen in the view with
`services.family_rules`, like every other `/v1/family` mutation.
"""

from django.db import IntegrityError, transaction

from giapha.models import Clan, ClanMember, FamilyPerson, FamilyPersonLink, Marriage, Person
from giapha.services.family_clan_field_map import clan_to_family, family_to_clan
from giapha.services.family_issue import FamilyRuleError
from giapha.services.tree import compute_generations


def create_links(family, clan_id, pairs, user):
    """`pairs`: `[(family_person_id, clan_person_id)]`. Returns False (and
    writes nothing) when a uniqueness constraint says one side is already
    linked -- the caller answers 400."""
    try:
        with transaction.atomic():
            FamilyPersonLink.objects.bulk_create([
                FamilyPersonLink(family=family, family_person_id=fid, clan_id=clan_id,
                                 clan_person_id=cid, linked_by=user)
                for fid, cid in pairs
            ])
    except IntegrityError:
        return False
    return True


def bootstrap_clan(user, family, rows_by_id, ordered_ids, marriages, ten_ho, thuy_to, self_id):
    """Create the clan + owner membership + one clan Person per copied family
    person (parents first) + marriages + links. Returns the Clan."""
    clan = Clan.objects.create(ten_ho=ten_ho, thuy_to=thuy_to or '')
    member = ClanMember.objects.create(clan=clan, user=user, role='owner')

    clan_id_of = {}
    for fid in ordered_ids:
        row = rows_by_id[fid]
        fields = family_to_clan(row)
        person = Person.objects.create(
            clan=clan, father_id=clan_id_of.get(row['father_id']), mother_id=clan_id_of.get(row['mother_id']),
            birth_order=row.get('birth_order'), **fields
        )
        clan_id_of[fid] = person.id

    created = list(Person.objects.filter(clan=clan).only('id', 'father_id', 'mother_id', 'generation'))
    generations = compute_generations([(p.id, p.father_id, p.mother_id) for p in created])
    for person in created:
        person.generation = generations.get(person.id)
    Person.objects.bulk_update(created, ['generation'])

    next_order = {}
    for husband, wife, status in marriages:
        husband_id = clan_id_of[husband]
        next_order[husband_id] = next_order.get(husband_id, 0) + 1
        Marriage.objects.create(husband_id=husband_id, wife_id=clan_id_of[wife],
                                order=next_order[husband_id], status=status)

    FamilyPersonLink.objects.bulk_create([
        FamilyPersonLink(family=family, family_person_id=fid, clan=clan, clan_person_id=cid, linked_by=user)
        for fid, cid in clan_id_of.items()
    ])
    if self_id in clan_id_of:
        member.person_id = clan_id_of[self_id]
        member.person_verified = True
        member.save(update_fields=['person', 'person_verified'])
    return clan


def link_contributed_person(cr, clan_person):
    """After approving a "đóng góp" (`cr.family_person` set), link the new
    clan person back to the contributor's node -- if that node still exists,
    is still unlinked in this clan, and its owner is still a member. Best
    effort: a lost race simply leaves it unlinked."""
    if cr.action != 'create_person' or clan_person is None or cr.family_person_id is None:
        return False
    family_person = FamilyPerson.objects.select_related('family').filter(id=cr.family_person_id).first()
    if family_person is None or not ClanMember.objects.filter(
            clan_id=cr.clan_id, user_id=family_person.family.user_id).exists():
        return False
    return create_links(family_person.family, cr.clan_id, [(family_person.id, clan_person.id)], cr.proposer)


def import_clan_persons(family, clan_id, clan_rows, user):
    """Create one FamilyPerson per clan row (shared fields) and link it.
    Returns `{clan_person_id: family_person_id}` for the new persons."""
    created = {}
    for row in clan_rows:
        person = FamilyPerson.objects.create(family=family, **clan_to_family(row))
        created[row['id']] = person.id
    if not create_links(family, clan_id, [(fid, cid) for cid, fid in created.items()], user):
        raise FamilyRuleError('LINK_CONFLICT')
    return created
