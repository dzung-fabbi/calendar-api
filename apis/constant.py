"""The 60-term sexagenary cycle, derived rather than transcribed.

This used to be a hand-typed list of 60 strings; one of them (ĐINH DẬUu) had a
stray character, and nothing tied it to the identical sequence in the model
choices. Generating it from the stem and branch tables makes drift impossible.
"""

from apis.services.can_chi import CAN, CHI

SEXAGENARY_CYCLE_LENGTH = 60

CAN_CHI = [
    '{} {}'.format(CAN[index % len(CAN)], CHI[index % len(CHI)]).upper()
    for index in range(SEXAGENARY_CYCLE_LENGTH)
]
