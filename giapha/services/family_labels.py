"""Spec §4.8 -- turn the "Quan hệ với bạn" label of a standalone person into
the one graph edge it unambiguously names, relative to "tôi".

Only labels exactly one edge away from self (or two, through a parent that
already exists) are linkable. `Cụ / Tổ tiên`, `Cháu`, `Chắt`, `Hậu duệ` and
free text name no attachment point: the person is saved unlinked and
`plan_link` returns no plan and no hint. A linkable label whose precondition
fails (slot already taken, missing intermediate parent) also returns no plan
but DOES return a Vietnamese `hint` for the form to show.

Returns `(plan, hint)`. `plan` is one of:
    ('set_parent', child_id, slot)   -- new person becomes `slot` of `child_id`
    ('spouse',)                      -- link_spouse(self, new)
    ('child',)                       -- link_child(self, new)
    ('sibling',)                     -- copy self's father/mother onto new
    None
"""

from giapha.services.family_graph import FATHER, MOTHER, gender_fits_slot

SLOT_LABEL = {FATHER: 'Cha', MOTHER: 'Mẹ'}

# label -> (slot on self)
_PARENT_LABELS = {'cha': FATHER, 'mẹ': MOTHER}
# label -> (which parent of self to go through, which slot on that parent)
_GRANDPARENT_LABELS = {
    'ông nội': (FATHER, FATHER), 'bà nội': (FATHER, MOTHER),
    'ông ngoại': (MOTHER, FATHER), 'bà ngoại': (MOTHER, MOTHER),
}
_SPOUSE_LABELS = ('vợ', 'chồng')
_CHILD_LABELS = ('con',)
_SIBLING_LABELS = ('anh', 'chị', 'em')


def _normalize(label):
    return ' '.join((label or '').split()).casefold()


def plan_link(graph, self_id, label, new_gender):
    key = _normalize(label)
    if not key:
        return None, None
    if self_id is None or not graph.has(self_id):
        if key in _PARENT_LABELS or key in _GRANDPARENT_LABELS or key in _SPOUSE_LABELS \
                or key in _CHILD_LABELS or key in _SIBLING_LABELS:
            return None, 'Chưa đánh dấu "Đây là tôi" nên chưa nối được theo nhãn quan hệ.'
        return None, None

    if key in _PARENT_LABELS:
        return _plan_parent(graph, self_id, _PARENT_LABELS[key], new_gender)
    if key in _GRANDPARENT_LABELS:
        via, slot = _GRANDPARENT_LABELS[key]
        return _plan_grandparent(graph, self_id, via, slot, new_gender, label)
    if key in _SPOUSE_LABELS:
        return ('spouse',), None
    if key in _CHILD_LABELS:
        return ('child',), None
    if key in _SIBLING_LABELS:
        if not graph.has_any_parent(self_id):
            return None, 'Bạn chưa có cha hoặc mẹ trong cây nên chưa nối được anh chị em; hãy thêm cha/mẹ trước.'
        return ('sibling',), None
    return None, None


def _plan_parent(graph, child_id, slot, new_gender):
    if graph.parent_in_slot(child_id, slot) is not None:
        return None, 'Bạn đã khai {}; người này được lưu nhưng chưa nối vào cây.'.format(SLOT_LABEL[slot])
    if not gender_fits_slot(new_gender, slot):
        return None, 'Giới tính không hợp với ô {}; người này được lưu nhưng chưa nối vào cây.'.format(SLOT_LABEL[slot])
    return ('set_parent', child_id, slot), None


def _plan_grandparent(graph, self_id, via, slot, new_gender, label):
    parent_id = graph.parent_in_slot(self_id, via)
    if parent_id is None:
        return None, 'Chưa có {} của bạn để nối {}; hãy thêm {} trước.'.format(
            SLOT_LABEL[via], label.strip(), SLOT_LABEL[via],
        )
    if graph.parent_in_slot(parent_id, slot) is not None:
        return None, 'Bạn đã khai {}; người này được lưu nhưng chưa nối vào cây.'.format(label.strip())
    if not gender_fits_slot(new_gender, slot):
        return None, 'Giới tính không hợp với vai {}; người này được lưu nhưng chưa nối vào cây.'.format(label.strip())
    return ('set_parent', parent_id, slot), None
