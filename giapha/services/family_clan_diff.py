"""Structure differences between linked pairs -- pure (spec §14.4).

Structure is kept separately in each tree and never auto-corrected; this only
REPORTS where a linked person's father, mother or spouses disagree, so the
user can fix their own tree (or propose a fix to the clan).

Comparison happens in clan-id space: a family relative "is" clan person X
only if it is linked to X. Items:

    {personId, clanPersonId, field: father|mother|spouse,
     family: {personId, name} | None, clan: {clanPersonId, name} | None}
"""


def _family_ref(fid, family_names):
    return {'personId': str(fid), 'name': family_names.get(fid)} if fid is not None else None


def _clan_ref(cid, clan_names):
    return {'clanPersonId': cid, 'name': clan_names.get(cid)} if cid is not None else None


def link_diff(links, family_rows, family_spouses, clan_rows, clan_spouses):
    """`links`: `{family_id: clan_id}` (one clan). Rows as in
    `services.family_clan_matching`."""
    fam = {row['id']: row for row in family_rows}
    clan = {row['id']: row for row in clan_rows}
    family_names = {fid: row['name'] for fid, row in fam.items()}
    clan_names = {cid: row['ho_ten'] for cid, row in clan.items()}
    reverse = {cid: fid for fid, cid in links.items()}

    def spouse_map(pairs):
        out = {}
        for a, b in pairs:
            out.setdefault(a, set()).add(b)
            out.setdefault(b, set()).add(a)
        return out

    fam_spouses, clan_sp = spouse_map(family_spouses), spouse_map(clan_spouses)
    items = []
    for fid, cid in sorted(links.items(), key=lambda pair: pair[1]):
        if fid not in fam or cid not in clan:
            continue
        base = {'personId': str(fid), 'clanPersonId': cid}
        for field in ('father', 'mother'):
            f_rel, c_rel = fam[fid][field + '_id'], clan[cid][field + '_id']
            if links.get(f_rel) != c_rel and not (f_rel is None and c_rel is None):
                items.append(dict(base, field=field, family=_family_ref(f_rel, family_names),
                                  clan=_clan_ref(c_rel, clan_names)))
        mapped = {links[s] for s in fam_spouses.get(fid, ()) if s in links}
        clan_side = clan_sp.get(cid, set())
        for c_spouse in sorted(clan_side - mapped):
            items.append(dict(base, field='spouse', family=_family_ref(reverse.get(c_spouse), family_names),
                              clan=_clan_ref(c_spouse, clan_names)))
        for c_spouse in sorted(mapped - clan_side):
            items.append(dict(base, field='spouse', family=_family_ref(reverse[c_spouse], family_names), clan=None))
    return items
