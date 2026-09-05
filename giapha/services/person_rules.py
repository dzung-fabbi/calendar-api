"""Pure validation rules that protect the integrity of the family tree.

No ORM, no `request`, no Django model imports -- every function takes plain
data (edge tuples, dicts, ints) and either returns `None` or raises
`PersonValidationError` with a Vietnamese message. This is what lets
`tests/test_person_rules.py` run on `SimpleTestCase` with no database.

`no_cycle` is the most important rule here: a parent-child cycle would make
the phase-4 generation walk and the phase-7 kinship path loop forever, and
data entered through Django admin bypasses this module entirely -- so
`descendants()` carries its own safety counter and must survive already-
corrupt data rather than hang on it (and fail closed if that counter fires).
"""

from collections import deque

MIN_PARENT_CHILD_GAP_YEARS = 12


class PersonValidationError(Exception):
    """Raised by every `validate_*` function below. Callers (views) catch
    this and re-raise as `giapha.exceptions.BadRequestException(str(exc))`.
    """


def ids_from_edges(edges):
    """Set of every person id present in `edges` -- since `edges` always
    comes from `selectors.person.clan_edges(clan_id)`, membership in this set
    *is* the "same clan" check.
    """
    return {row[0] for row in edges}


def descendants(edges, root_id, max_iterations=None):
    """Every person reachable by walking forward (parent -> child) from
    `root_id`, via BFS over `edges` (`[(id, father_id, mother_id), ...]`).

    Bounded by a safety counter (`2 * len(edges) + 10` by default, override
    via `max_iterations` -- lets tests force the cap deterministically): a
    healthy tree never needs more than `len(edges)` hops, but data written
    outside the API (Django admin) can already contain a cycle.

    If the cap is ever exhausted, `queue` is still non-empty (BFS unfinished).
    The caller (`validate_no_cycle`) is the cycle gate for every write, so a
    partial set here would wave a real cycle through undetected -- fails
    CLOSED instead (raises) rather than returning a truncated result.
    """
    children_of = {}
    for person_id, father_id, mother_id in edges:
        if father_id is not None:
            children_of.setdefault(father_id, set()).add(person_id)
        if mother_id is not None:
            children_of.setdefault(mother_id, set()).add(person_id)

    visited = set()
    queue = deque([root_id])
    if max_iterations is None:
        max_iterations = 2 * len(edges) + 10
    iterations = 0
    while queue and iterations < max_iterations:
        iterations += 1
        current = queue.popleft()
        for child_id in children_of.get(current, ()):
            if child_id not in visited:
                visited.add(child_id)
                queue.append(child_id)

    if queue:
        raise PersonValidationError(
            'Không thể xác thực chu trình huyết thống: đồ thị dòng họ quá lớn hoặc dữ liệu bị hỏng.'
        )
    return visited


def validate_no_cycle(edges, person_id, father_id, mother_id):
    """Neither candidate parent may be a descendant of `person_id` -- that
    would close a cycle. No-op for a brand new person (`person_id is None`):
    nothing can already point to an id that doesn't exist yet.
    """
    if person_id is None:
        return
    descendant_ids = descendants(edges, person_id)
    if father_id is not None and father_id in descendant_ids:
        raise PersonValidationError(
            'Không thể gán cha vì người này là hậu duệ của chính đối tượng, sẽ tạo thành chu trình huyết thống.'
        )
    if mother_id is not None and mother_id in descendant_ids:
        raise PersonValidationError(
            'Không thể gán mẹ vì người này là hậu duệ của chính đối tượng, sẽ tạo thành chu trình huyết thống.'
        )


def validate_parent_in_same_clan(ids_in_clan, father_id, mother_id):
    if father_id is not None and father_id not in ids_in_clan:
        raise PersonValidationError('Cha phải thuộc cùng dòng họ.')
    if mother_id is not None and mother_id not in ids_in_clan:
        raise PersonValidationError('Mẹ phải thuộc cùng dòng họ.')


def validate_self_not_parent(person_id, father_id, mother_id):
    if person_id is None:
        return
    if father_id == person_id:
        raise PersonValidationError('Một người không thể là cha của chính mình.')
    if mother_id == person_id:
        raise PersonValidationError('Một người không thể là mẹ của chính mình.')


def _year_gap(earlier, later):
    """Full years between two `date`s, `later - earlier`. Negative if
    `later` actually precedes `earlier`.
    """
    years = later.year - earlier.year
    if (later.month, later.day) < (earlier.month, earlier.day):
        years -= 1
    return years


def validate_parent_born_before_child(child_birth, father_birth, mother_birth, force=False):
    """Cha/mẹ phải sinh trước con ít nhất `MIN_PARENT_CHILD_GAP_YEARS` năm,
    khi biết đủ cả hai ngày sinh. `force=True` (chỉ chủ sở hữu được dùng, xem
    view) bỏ qua luật này -- gia phả cũ hay có ngày sinh xấp xỉ/sai lệch, nếu
    không có lối thoát này người dùng sẽ mắc kẹt khi nhập dữ liệu tổ tiên thật.
    """
    if force or child_birth is None:
        return
    for parent_birth, label in ((father_birth, 'cha'), (mother_birth, 'mẹ')):
        if parent_birth is None:
            continue
        if _year_gap(parent_birth, child_birth) < MIN_PARENT_CHILD_GAP_YEARS:
            raise PersonValidationError(
                'Khoảng cách tuổi giữa {} và con phải tối thiểu {} năm; '
                'dùng force=true (chủ sở hữu) nếu dữ liệu chắc chắn đúng.'.format(
                    label, MIN_PARENT_CHILD_GAP_YEARS,
                )
            )


def validate_death_after_birth(birth_solar, death_solar):
    if birth_solar is not None and death_solar is not None and death_solar < birth_solar:
        raise PersonValidationError('Ngày mất phải sau ngày sinh.')


def validate_lunar_death_valid(death_lunar_month, death_lunar_day):
    if death_lunar_month is not None and not (1 <= death_lunar_month <= 12):
        raise PersonValidationError('Tháng mất âm lịch phải trong khoảng 1-12.')
    if death_lunar_day is not None and not (1 <= death_lunar_day <= 30):
        raise PersonValidationError('Ngày mất âm lịch phải trong khoảng 1-30.')


def validate_death_pair_complete(death_lunar_day, death_lunar_month):
    if (death_lunar_day is None) != (death_lunar_month is None):
        raise PersonValidationError('Ngày và tháng mất âm lịch phải có đủ cả hai hoặc để trống cả hai.')


def validate_clan_size_cap(current_count, max_persons):
    if current_count >= max_persons:
        raise PersonValidationError('Dòng họ đã đạt giới hạn {} thành viên.'.format(max_persons))


def validate_marriage_distinct(husband_id, wife_id):
    if husband_id == wife_id:
        raise PersonValidationError('Chồng và vợ không thể là cùng một người.')


def validate_marriage_order_unique(existing_orders, order, exclude_marriage_id=None):
    """`existing_orders`: `[(marriage_id, order), ...]` for the same husband."""
    for marriage_id, existing_order in existing_orders:
        if marriage_id == exclude_marriage_id:
            continue
        if existing_order == order:
            raise PersonValidationError('Thứ tự hôn nhân này đã tồn tại cho người chồng này.')


def validate_person_write(payload, *, edges, ids_in_clan, birth_map, existing_count, max_persons,
                           force=False, person_id=None):
    """Run every Person-level rule for one write. `payload` is a dict with
    (at least) `father_id`, `mother_id`, `birth_solar`, `death_solar`,
    `death_lunar_day`, `death_lunar_month` -- the keys `services.revision`
    and the serializers already use, so callers can pass `validated_data`
    (create) or a merged current+incoming dict (update) directly.

    `person_id` is `None` for a create (skips `self_not_parent`, applies the
    clan-size cap) and the existing pk for an update (skips the cap, applies
    `self_not_parent`).
    """
    father_id = payload.get('father_id')
    mother_id = payload.get('mother_id')

    validate_self_not_parent(person_id, father_id, mother_id)
    validate_parent_in_same_clan(ids_in_clan, father_id, mother_id)
    validate_no_cycle(edges, person_id, father_id, mother_id)
    validate_death_after_birth(payload.get('birth_solar'), payload.get('death_solar'))
    validate_lunar_death_valid(payload.get('death_lunar_month'), payload.get('death_lunar_day'))
    validate_death_pair_complete(payload.get('death_lunar_day'), payload.get('death_lunar_month'))
    validate_parent_born_before_child(
        payload.get('birth_solar'), birth_map.get(father_id), birth_map.get(mother_id), force=force,
    )
    if person_id is None:
        validate_clan_size_cap(existing_count, max_persons)
