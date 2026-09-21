"""Suggest personal-tree <-> clan person pairs -- pure, no ORM (spec §14.3).

Never links anything: the user confirms every pair (`POST /links`).

1. Anchors: pairs already linked, plus (selfId <-> the user's binding in the
   clan) when neither side is linked yet.
2. Structure (confidence `high`): from each anchor, walk father<->father,
   mother<->mother, spouse<->spouse, child<->child, pairing only when the
   normalised names match (and, among several same-named children, only an
   unambiguous one). Newly paired people become anchors in turn.
3. Name only (confidence `low`): the rest, when the diacritic-free
   lowercase names match AND both sides have the SAME birth year. A missing
   year on either side means no name-only suggestion at all -- "Nguyễn Văn
   Hùng" alone is not evidence.

Inputs are plain dicts:
  family rows: {id, name, father_id, mother_id, solar_birth_date}
  clan rows:   {id, ho_ten, father_id, mother_id, birth_solar}
  *_spouses:   iterables of (a, b) pairs
"""

import unicodedata
from collections import deque

HIGH, LOW = 'high', 'low'


def normalize_name(name):
    text = unicodedata.normalize('NFD', (name or '').replace('đ', 'd').replace('Đ', 'D'))
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    return ' '.join(text.lower().split())


class _Side:
    def __init__(self, rows, spouse_pairs, name_key, birth_key):
        self.rows = {row['id']: row for row in rows}
        self.names = {pid: normalize_name(row[name_key]) for pid, row in self.rows.items()}
        self.years = {pid: (row[birth_key].year if row[birth_key] else None) for pid, row in self.rows.items()}
        self.children, self.spouses = {}, {}
        for row in rows:
            for key in ('father_id', 'mother_id'):
                if row[key] in self.rows:
                    self.children.setdefault(row[key], []).append(row['id'])
        for a, b in spouse_pairs:
            if a in self.rows and b in self.rows:
                self.spouses.setdefault(a, []).append(b)
                self.spouses.setdefault(b, []).append(a)

    def related(self, pid):
        row = self.rows[pid]
        return {
            'father': [row['father_id']] if row['father_id'] in self.rows else [],
            'mother': [row['mother_id']] if row['mother_id'] in self.rows else [],
            'spouse': self.spouses.get(pid, []),
            'child': self.children.get(pid, []),
        }


def _unique_name_match(fam, clan, f_ids, c_ids):
    """Pairs (f, c) whose normalised name occurs exactly once on each side."""
    f_by_name, c_by_name = {}, {}
    for fid in f_ids:
        f_by_name.setdefault(fam.names[fid], []).append(fid)
    for cid in c_ids:
        c_by_name.setdefault(clan.names[cid], []).append(cid)
    return [(f[0], c_by_name[name][0]) for name, f in f_by_name.items()
            if name and len(f) == 1 and len(c_by_name.get(name, ())) == 1]


def suggest_pairs(family_rows, family_spouses, clan_rows, clan_spouses, linked, anchor=None):
    """`linked`: `{family_id: clan_id}` already linked. `anchor`: optional
    `(self_family_id, bound_clan_id)`. Returns `[{personId, clanPersonId,
    confidence, reason}]` (ids as given)."""
    fam = _Side(family_rows, family_spouses, 'name', 'solar_birth_date')
    clan = _Side(clan_rows, clan_spouses, 'ho_ten', 'birth_solar')
    used_f, used_c = set(linked), set(linked.values())
    out = []

    def take(fid, cid, confidence, reason):
        used_f.add(fid)
        used_c.add(cid)
        out.append({'personId': fid, 'clanPersonId': cid, 'confidence': confidence, 'reason': reason})

    queue = deque(pair for pair in linked.items() if pair[0] in fam.rows and pair[1] in clan.rows)
    if anchor and anchor[0] in fam.rows and anchor[1] in clan.rows and anchor[0] not in used_f and anchor[1] not in used_c:
        take(anchor[0], anchor[1], HIGH, 'self_binding')
        queue.append(anchor)

    while queue:
        fid, cid = queue.popleft()
        f_rel, c_rel = fam.related(fid), clan.related(cid)
        for kind in ('father', 'mother', 'spouse', 'child'):
            f_free = [pid for pid in f_rel[kind] if pid not in used_f]
            c_free = [pid for pid in c_rel[kind] if pid not in used_c]
            for f_new, c_new in _unique_name_match(fam, clan, f_free, c_free):
                take(f_new, c_new, HIGH, kind)
                queue.append((f_new, c_new))

    clan_index = {}
    for cid in clan.rows:
        if cid not in used_c and clan.years[cid] is not None and clan.names[cid]:
            clan_index.setdefault((clan.names[cid], clan.years[cid]), []).append(cid)
    for fid in fam.rows:
        if fid in used_f or fam.years[fid] is None:
            continue
        for cid in clan_index.get((fam.names[fid], fam.years[fid]), ()):
            out.append({'personId': fid, 'clanPersonId': cid, 'confidence': LOW, 'reason': 'name_birth_year'})
    return out
