"""In-memory index over one personal family tree (spec §2.1, §5).

Built once per request from plain rows (`selectors.family.load_graph`) and
queried by `services.family_rules` / `services.family_labels` and the
`/v1/family` views. No ORM. Everything the app derives on read -- children,
siblings' parents, co-parents, ancestors, descendants -- is derived here the
same way, so tree and detail screens never disagree with the server.

Ids are whatever the caller passes (uuid.UUID from the ORM, also uuid.UUID
from DRF's `UUIDField`) -- the index never converts them.
"""

from giapha.services.person_rules import descendants

FATHER, MOTHER = 'father', 'mother'
SLOTS = (FATHER, MOTHER)


def other_slot(slot):
    return MOTHER if slot == FATHER else FATHER


def slot_for_parent_gender(gender):
    """Which slot a parent of `gender` occupies: `'female'` -> mẹ, everything
    else (including `'unknown'`) -> cha. Spec §4.6."""
    return MOTHER if gender == 'female' else FATHER


def gender_fits_slot(gender, slot):
    """Nam không vào ô mẹ, nữ không vào ô cha; `'unknown'` fits both."""
    if slot == FATHER:
        return gender != 'female'
    return gender != 'male'


def canonical_pair(a, b):
    """The one ordering a spouse pair is stored under (`FamilySpouse`)."""
    return (a, b) if str(a) < str(b) else (b, a)


class FamilyGraph:
    def __init__(self, person_rows, spouse_rows=()):
        # `person_rows`: dicts with at least `id`, `father_id`, `mother_id`,
        # `gender`. `spouse_rows`: dicts with `person_a_id`, `person_b_id`, `type`.
        self.persons = {}
        self.children = {}
        self.spouses = {}
        for row in person_rows:
            self.add_person(row)
        for row in spouse_rows:
            self.add_spouse(row['person_a_id'], row['person_b_id'], row['type'])

    # -- mutation of the in-memory index (mirrors what a write just did) ----

    def add_person(self, row):
        self.persons[row['id']] = {
            'id': row['id'], 'gender': row.get('gender', 'unknown'),
            'father_id': row.get('father_id'), 'mother_id': row.get('mother_id'),
        }
        for slot in SLOTS:
            parent_id = row.get(slot + '_id')
            if parent_id is not None:
                self.children.setdefault(parent_id, []).append(row['id'])

    def set_parent(self, child_id, slot, parent_id):
        key = slot + '_id'
        old = self.persons[child_id][key]
        if old is not None and child_id in self.children.get(old, ()):
            self.children[old].remove(child_id)
        self.persons[child_id][key] = parent_id
        if parent_id is not None:
            self.children.setdefault(parent_id, []).append(child_id)

    def add_spouse(self, a, b, spouse_type='married'):
        self.spouses.setdefault(a, {})[b] = spouse_type
        self.spouses.setdefault(b, {})[a] = spouse_type

    # -- reads -------------------------------------------------------------

    def has(self, person_id):
        return person_id in self.persons

    def gender(self, person_id):
        return self.persons[person_id]['gender']

    def parent_in_slot(self, person_id, slot):
        return self.persons[person_id][slot + '_id']

    def has_any_parent(self, person_id):
        row = self.persons[person_id]
        return row['father_id'] is not None or row['mother_id'] is not None

    def children_of(self, person_id):
        return list(self.children.get(person_id, ()))

    def spouses_of(self, person_id):
        """`{other_id: type}` -- explicit spouse edges only."""
        return dict(self.spouses.get(person_id, {}))

    def co_parents_of(self, person_id):
        """People who share a child with `person_id` but are not necessarily
        married to them (spec §4.6: "có con chung ≠ đã cưới")."""
        found = set()
        for child_id in self.children_of(person_id):
            for slot in SLOTS:
                other = self.parent_in_slot(child_id, slot)
                if other is not None and other != person_id:
                    found.add(other)
        return found

    def partners_of(self, person_id):
        """Spec's `getPartners`: explicit spouses + co-parents."""
        return set(self.spouses_of(person_id)) | self.co_parents_of(person_id)

    def ancestors_of(self, person_id):
        """Every id reachable upward via father/mother. Visited-set guarded so
        already-corrupt data (a cycle written outside the API) terminates."""
        seen = set()
        stack = [person_id]
        while stack:
            current = stack.pop()
            row = self.persons.get(current)
            if row is None:
                continue
            for slot in SLOTS:
                parent_id = row[slot + '_id']
                if parent_id is not None and parent_id not in seen:
                    seen.add(parent_id)
                    stack.append(parent_id)
        return seen

    def descendants_of(self, person_id):
        return descendants(self.edges(), person_id)

    def is_lineal(self, a, b):
        """True when one is an ancestor of the other (spec `SPOUSE_IS_ANCESTOR`)."""
        return b in self.ancestors_of(a) or a in self.ancestors_of(b)

    def edges(self):
        return [(row['id'], row['father_id'], row['mother_id']) for row in self.persons.values()]
