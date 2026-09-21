"""Plan a `PUT /v1/family/import` -- pure, no ORM.

Everyone is imported; an edge that breaks a rule is dropped and reported in
`skipped_edges` (spec §12). Edges are judged by the SAME rules as the live
API (`services.family_rules`), on an in-memory `FamilyGraph` keyed by the
client ids, in a fixed order -- persons sorted by (`createdAt`, `id`), father
before mother, spouses in the order they appear -- so the same snapshot
always yields the same result.

    parent edge dropped:  DANGLING_FATHER/MOTHER, SELF_PARENT, GENDER_MISMATCH,
                          PARENT_CYCLE
    spouse dropped:       SELF_SPOUSE, DANGLING_SPOUSE
    spouse kept + warned: SPOUSE_IS_ANCESTOR (same as §4.4)
"""

from giapha.services.family_graph import FATHER, MOTHER, FamilyGraph, canonical_pair
from giapha.services.family_import_fields import normalize_person
from giapha.services.family_issue import FamilyRuleError
from giapha.services.family_rules import check_link_spouse, check_set_parent

SPOUSE_TYPES = ('married', 'divorced')


class ImportPlan:
    def __init__(self):
        self.persons = []        # [(client_id, model_fields)] in import order
        self.parents = []        # [(child_cid, slot, parent_cid, rel)]
        self.spouses = []        # [(a_cid, b_cid, type)] canonical, unique
        self.self_id = None
        self.skipped_edges = []
        self.warnings = []


def _ref(value):
    """A client id reference, or None. Numbers are stringified (they can only
    dangle); anything else unhashable/odd becomes None."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _skip(plan, exc):
    plan.skipped_edges.append(exc.to_error())


def _sort_key(item):
    created = item[1]['created_at']
    return (created.timestamp() if created else float('inf'), str(item[0]))


def _unique_persons(raw_persons, plan):
    """Normalise each person; a repeated client id keeps its first row."""
    seen = {}
    for raw in raw_persons:
        client_id = raw['id']
        if client_id in seen:
            plan.warnings.append({'personId': client_id, 'field': 'id', 'message': 'Trùng id, đã bỏ bản sau.'})
            continue
        fields, warnings = normalize_person(raw)
        plan.warnings.extend(warnings)
        seen[client_id] = (raw, fields)
    return seen


def _plan_parents(plan, graph, ordered, raw_by_id):
    for client_id, _fields in ordered:
        raw = raw_by_id[client_id]
        for slot in (FATHER, MOTHER):
            parent_id = _ref(raw.get(slot + 'Id'))
            if parent_id is None:
                continue
            try:
                check_set_parent(graph, client_id, slot, parent_id)
            except FamilyRuleError as exc:
                _skip(plan, exc)
                continue
            graph.set_parent(client_id, slot, parent_id)
            rel = 'adopted' if raw.get(slot + 'Rel') == 'adopted' else None
            plan.parents.append((client_id, slot, parent_id, rel))


def _plan_spouses(plan, graph, ordered, raw_by_id):
    seen_pairs = set()
    for client_id, _fields in ordered:
        spouses = raw_by_id[client_id].get('spouses') or []
        for link in spouses if isinstance(spouses, list) else []:
            if not isinstance(link, dict):
                continue
            other_id = _ref(link.get('id'))
            try:
                warn = check_link_spouse(graph, client_id, other_id)
            except FamilyRuleError as exc:
                _skip(plan, exc)
                continue
            pair = canonical_pair(client_id, other_id)
            if pair in seen_pairs:
                continue  # the other direction of a pair already planned
            seen_pairs.add(pair)
            if warn:
                plan.warnings.append({'personId': client_id, 'field': 'spouses', 'message': warn['message']})
            spouse_type = link.get('type') if link.get('type') in SPOUSE_TYPES else 'married'
            graph.add_spouse(pair[0], pair[1], spouse_type)
            plan.spouses.append((pair[0], pair[1], spouse_type))


def plan_import(raw_persons, self_id):
    """`raw_persons`: client `Person` dicts, each with a string `id`."""
    plan = ImportPlan()
    by_id = _unique_persons(raw_persons, plan)
    ordered = sorted(((cid, fields) for cid, (_raw, fields) in by_id.items()), key=_sort_key)
    plan.persons = ordered
    raw_by_id = {cid: raw for cid, (raw, _fields) in by_id.items()}

    graph = FamilyGraph([{'id': cid, 'gender': fields['gender']} for cid, fields in ordered])
    _plan_parents(plan, graph, ordered, raw_by_id)
    _plan_spouses(plan, graph, ordered, raw_by_id)

    if self_id is not None and self_id not in raw_by_id:
        plan.warnings.append({'personId': self_id, 'field': 'selfId', 'message': 'selfId không có trong danh sách, đã bỏ.'})
    else:
        plan.self_id = self_id
    return plan
