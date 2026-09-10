"""`IssueCode` + Vietnamese messages for the personal family API (spec §4.1).

`FamilyRuleError` is raised by `services.family_rules` / `services.family_labels`
and by the `/v1/family` views; `views.family_base.FamilyAPIView.handle_exception`
turns it into the spec's error envelope:

    {"ok": false, "error": {"code", "personId", "otherId", "message"}}

Messages are the sentences the app already shows, so the UI can render
`message` verbatim. Codes beyond the spec table (`GENDER_MISMATCH`,
`NO_PARENT_FOR_SIBLING`, `SELF_ALREADY_SET`, `PERSON_NOT_FOUND`, `VALIDATION`,
`FAMILY_FULL`, and the warning `OTHER_PARENT_NOT_CANDIDATE`) cover checks the
spec asks the server to enforce but did not name.
"""

MESSAGES = {
    'SELF_PARENT': 'Một người không thể là cha/mẹ của chính mình.',
    'SELF_SPOUSE': 'Một người không thể là vợ/chồng của chính mình.',
    'PARENT_CYCLE': 'Không đặt được: người này đang là con cháu trong nhánh đó, nối vào sẽ tạo vòng lặp.',
    'PARENT_SLOT_TAKEN': 'Ô cha/mẹ này đã có người. Muốn thay phải gỡ người cũ trước.',
    'PARENT_SLOT_TAKEN_FATHER': 'Người này đã có cha. Cha dượng nên nhập là vợ/chồng của mẹ.',
    'PARENT_SLOT_TAKEN_MOTHER': 'Người này đã có mẹ. Mẹ kế nên nhập là vợ/chồng của cha.',
    'DANGLING_FATHER': 'Không tìm thấy người được chọn làm cha.',
    'DANGLING_MOTHER': 'Không tìm thấy người được chọn làm mẹ.',
    'DANGLING_SPOUSE': 'Không tìm thấy người được chọn làm vợ/chồng.',
    'SPOUSE_IS_ANCESTOR': 'Hai người này đang là trực hệ (ông–cháu, cha–con…). Đã lưu, hãy kiểm tra lại.',
    'GENDER_MISMATCH': 'Giới tính không hợp với ô này: nam không vào ô mẹ, nữ không vào ô cha.',
    'NO_PARENT_FOR_SIBLING': 'Người này chưa có cha và mẹ nên chưa thể thêm anh chị em. Hãy thêm cha hoặc mẹ trước.',
    'SELF_ALREADY_SET': 'Đã có người được đánh dấu là "tôi". Hãy gỡ đánh dấu cũ trước khi đổi.',
    'PERSON_NOT_FOUND': 'Không tìm thấy người này trong gia phả.',
    'FAMILY_FULL': 'Gia phả đã đạt giới hạn {} người.',
    'OTHER_PARENT_NOT_CANDIDATE': 'Người được chọn làm cha/mẹ còn lại không phải vợ/chồng hay đồng phụ huynh hợp lệ; ô đó để trống.',
    'VALIDATION': 'Dữ liệu không hợp lệ.',
}


class FamilyRuleError(Exception):
    """One rule violation. `status` is the HTTP status the view should use
    (400 for every rule, 404 for `PERSON_NOT_FOUND`). `extra` is merged into
    the `error` object -- used for `fields` on `VALIDATION`.
    """

    def __init__(self, code, message=None, person_id=None, other_id=None, status=400, extra=None):
        self.code = code
        self.message = message or MESSAGES.get(code, MESSAGES['VALIDATION'])
        self.person_id = person_id
        self.other_id = other_id
        self.status = status
        self.extra = extra or {}
        super().__init__(self.message)

    def to_error(self):
        error = {
            'code': self.code,
            'personId': str(self.person_id) if self.person_id is not None else None,
            'otherId': str(self.other_id) if self.other_id is not None else None,
            'message': self.message,
        }
        error.update(self.extra)
        return error


def not_found(person_id):
    return FamilyRuleError('PERSON_NOT_FOUND', person_id=person_id, status=404)


def warning(code, person_id=None, other_id=None):
    """A non-blocking issue in the shape the success envelope carries."""
    return {
        'code': code,
        'personId': str(person_id) if person_id is not None else None,
        'otherId': str(other_id) if other_id is not None else None,
        'message': MESSAGES[code],
    }
