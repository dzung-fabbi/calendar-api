"""Initial status of a new invite -- pure decision table, no ORM.

`active` (code minted immediately) when any of:
  * the caller is the owner;
  * the caller is a manager and the invite grants `viewer`;
  * the invite grants `viewer`, names a person, and that person is inside the
    caller's INVITE scope (`permissions_scope.invite_scope_ids`: downward
    only -- descendants and their spouses; `None` means the whole clan).

Everything else -- a person outside the scope, no person at all, or any
invite granting `editor` from a non-owner -- is `pending_approval`: an
approver must look at it before a redeemable code exists.
"""

STATUS_ACTIVE = 'active'
STATUS_PENDING = 'pending_approval'


def invite_initial_status(caller_role, invite_role, person_id, writable_ids):
    if caller_role == 'owner':
        return STATUS_ACTIVE
    if invite_role != 'viewer':
        return STATUS_PENDING
    if caller_role == 'manager':
        return STATUS_ACTIVE
    if person_id is None:
        return STATUS_PENDING
    if writable_ids is None or person_id in writable_ids:
        return STATUS_ACTIVE
    return STATUS_PENDING
