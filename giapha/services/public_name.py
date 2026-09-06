"""Name handling for the public gia phả page (phase 9).

Pure Python, no ORM, no `request` -- `abbreviate_name` has its own
`SimpleTestCase` unit tests (`tests/test_public_name.py`).
"""

# Returned instead of a name whenever "abbreviating" it would not actually
# hide anything (see `abbreviate_name`'s NO-OP GUARD below). Neutral on
# purpose -- it says "this position in the tree is occupied by someone
# living" without naming them, same intent as `is_living`/withheld dates.
LIVING_NAME_PLACEHOLDER = '(Đang sống)'


def abbreviate_name(ho_ten):
    """`"Nguyễn Đình An"` -> `"Nguyễn Đình A."`. Only the LAST token (the
    given name) is reduced to its first letter + a period; every earlier
    token (họ/tên đệm) is left intact so the tree still reads as a real
    Vietnamese name, just without the part that -- combined with a birth
    date -- would let a stranger impersonate a living person.

    - A single-word name abbreviates that one word (`"An"` -> `"A."`).
    - The initial is upper-cased even when the input is all lowercase
      (`"nguyen dinh an"` -> `"nguyen dinh A."`) -- intended: the initial
      is presentational (Vietnamese given names are capitalised), it is
      not additional information about the person, so it is fine for it
      to not literally match the input's casing.
    - Repeated/leading/trailing internal whitespace is irrelevant --
      `str.split()` with no argument already collapses it.
    - Empty or whitespace-only input returns `''` unchanged. This must never
      raise: it runs on every living person on a public tree, and a
      malformed `ho_ten` (blank by data-entry mistake) is not a reason to
      500 an otherwise-fine public page.

    NO-OP GUARD (security fix, phase-9 review L3): when the given name is
    only ONE character, "abbreviating" it to its first letter + a period
    emits that exact character back plus punctuation -- i.e. the full
    given name, undisguised (`"李 小 龍"` -> `"李 小 龍."`, a living person's
    complete name published under `hide_living_details=True`). This cannot
    be fixed by abbreviating harder: the given name IS one character, there
    is nothing shorter to cut it to. Once abbreviation cannot shorten the
    name at all, the ENTIRE name is replaced by `LIVING_NAME_PLACEHOLDER`
    (not just the given-name token) -- leaving `rest` visible would still
    publish the surname/tên đệm of someone the caller could otherwise not
    identify at all. Applies uniformly whether the one-character given name
    came from a multi-word name or was the whole (single-word) input.

    Same guard incidentally fixes a cosmetic double-period bug: a given
    name that was itself the single character `"."` used to abbreviate to
    `".."` (`given_name[0].upper() + '.'`); it now falls into the `<= 1`
    case above like any other one-character given name.
    """
    tokens = ho_ten.split()
    if not tokens:
        return ''
    *rest, given_name = tokens
    if len(given_name) <= 1:
        return LIVING_NAME_PLACEHOLDER
    abbreviated = given_name[0].upper() + '.'
    return ' '.join(rest + [abbreviated]) if rest else abbreviated


def public_display_name(ho_ten, *, is_living, hide_living_details):
    """The `ho_ten` a no-auth caller may see.

    A dead person, or a living one when the clan owner has explicitly set
    `Clan.hide_living_details=False`, gets the real name. A living person
    under the default `hide_living_details=True` gets only
    `abbreviate_name(ho_ten)` -- name + real birth date is the
    impersonation pair the phase-9 spec forbids; never sending the birth
    date at all (enforced in `services.public_tree` / `services.
    public_person`, which simply never populate it for a living person) is
    the other half of that mitigation.
    """
    if is_living and hide_living_details:
        return abbreviate_name(ho_ten)
    return ho_ten
