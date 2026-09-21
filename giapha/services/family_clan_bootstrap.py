"""Plan "tạo dòng họ từ cây cá nhân" (`POST /v1/family/clans`) -- pure.

The copied set is the root, every descendant, and the spouses of all of
them. Parents outside the set (a spouse's parents, the root's parents) are
not copied, so those slots stay empty in the clan.

Clan marriages are gendered (husband/wife) while personal spouse links are
not: a pair maps to a marriage only when exactly one side can be the husband
(male, or unknown opposite a female) and the other the wife. Same-gender or
unknown/unknown pairs are skipped and reported -- the user fixes them in the
clan by hand rather than the server guessing.
"""

from giapha.services.tree import compute_generations, subtree_ids

_STATUS = {'married': 'dang_ket_hon', 'divorced': 'ly_hon'}


def copy_set(person_rows, spouse_rows, root_id):
    edges = [(row['id'], row['father_id'], row['mother_id']) for row in person_rows]
    lineage = subtree_ids(edges, root_id)
    spouses = set()
    for row in spouse_rows:
        a, b = row['person_a_id'], row['person_b_id']
        if a in lineage:
            spouses.add(b)
        if b in lineage:
            spouses.add(a)
    return lineage | spouses


def _husband_wife(gender_of, a, b):
    """`(husband, wife)`: husband male-or-unknown, wife female-or-unknown,
    not both unknown. None when no such assignment exists."""
    for husband, wife in ((a, b), (b, a)):
        gh, gw = gender_of[husband], gender_of[wife]
        if gh in ('male', 'unknown') and gw in ('female', 'unknown') and (gh, gw) != ('unknown', 'unknown'):
            return husband, wife
    return None


def plan_bootstrap(person_rows, spouse_rows, root_id):
    """`(ordered_ids, marriages, skipped_pairs)`.

    `ordered_ids`: ids to copy, parents before children (generation, then the
    family's own creation order) so each clan row can point at already
    created parents. `marriages`: `[(husband_id, wife_id, status)]`.
    """
    wanted = copy_set(person_rows, spouse_rows, root_id)
    rows = [row for row in person_rows if row['id'] in wanted]
    edges = [
        (row['id'], row['father_id'] if row['father_id'] in wanted else None,
         row['mother_id'] if row['mother_id'] in wanted else None)
        for row in rows
    ]
    generations = compute_generations(edges)
    position = {row['id']: index for index, row in enumerate(rows)}
    ordered = sorted(wanted, key=lambda pid: (generations.get(pid, 1), position[pid]))

    gender_of = {row['id']: row['gender'] for row in rows}
    marriages, skipped = [], []
    for row in spouse_rows:
        a, b = row['person_a_id'], row['person_b_id']
        if a not in wanted or b not in wanted:
            continue
        pair = _husband_wife(gender_of, a, b)
        if pair is None:
            skipped.append((a, b))
        else:
            marriages.append((pair[0], pair[1], _STATUS.get(row['type'], 'dang_ket_hon')))
    return ordered, marriages, skipped
