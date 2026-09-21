"""`services.family_clan_field_map` round trips + `family_clan_matching` +
`family_clan_diff` + `family_clan_bootstrap` -- pure, no database."""

import datetime as dt

from django.test import SimpleTestCase

from giapha.services.family_clan_bootstrap import plan_bootstrap
from giapha.services.family_clan_diff import link_diff
from giapha.services.family_clan_field_map import clan_to_family, family_to_clan, family_to_clan_payload
from giapha.services.family_clan_matching import normalize_name, suggest_pairs


class FieldMapTests(SimpleTestCase):
    def test_round_trip_every_shared_field(self):
        clan = {
            'ho_ten': 'Nguyễn Văn Cụ', 'gioi_tinh': 'nam', 'da_mat': True,
            'birth_solar': dt.date(1900, 1, 2), 'death_solar': dt.date(1980, 2, 3),
            'death_lunar_day': 17, 'death_lunar_month': 12, 'death_lunar_leap': False,
        }
        family = clan_to_family(clan)
        self.assertEqual('male', family['gender'])
        self.assertTrue(family['deceased'])
        self.assertEqual(1979, family['lunar_death_year'])  # 3/2/1980 is still lunar 1979
        back = family_to_clan(family)
        for key, value in clan.items():
            self.assertEqual(value, back[key], key)

    def test_gender_mapping_and_death_markers_imply_deceased(self):
        for clan_gender, family_gender in (('nam', 'male'), ('nu', 'female'), ('khac', 'unknown')):
            self.assertEqual(family_gender, clan_to_family({
                'ho_ten': 'x', 'gioi_tinh': clan_gender, 'da_mat': False, 'birth_solar': None,
                'death_solar': None, 'death_lunar_day': 1, 'death_lunar_month': 1, 'death_lunar_leap': False,
            })['gender'])
        self.assertEqual('khac', family_to_clan({'gender': 'unknown'})['gioi_tinh'])

    def test_partial_and_payload(self):
        self.assertEqual({'ho_ten': 'A'}, family_to_clan({'name': 'A', 'note': 'riêng'}))
        payload = family_to_clan_payload({'solar_birth_date': dt.date(2000, 5, 6)})
        self.assertEqual('2000-05-06', payload['birth_solar'])


class MatchingTests(SimpleTestCase):
    def family(self):
        return [
            {'id': 'f_self', 'name': 'Nguyễn Văn An', 'father_id': 'f_dad', 'mother_id': None, 'solar_birth_date': None},
            {'id': 'f_dad', 'name': 'Nguyễn Văn Bình', 'father_id': None, 'mother_id': None, 'solar_birth_date': None},
            {'id': 'f_other', 'name': 'Trần Thị Hoa', 'father_id': None, 'mother_id': None,
             'solar_birth_date': dt.date(1990, 1, 1)},
            {'id': 'f_noyear', 'name': 'Lê Văn Tư', 'father_id': None, 'mother_id': None, 'solar_birth_date': None},
        ]

    def clan(self):
        return [
            {'id': 1, 'ho_ten': 'Nguyen Van An', 'father_id': 2, 'mother_id': None, 'birth_solar': None},
            {'id': 2, 'ho_ten': 'NGUYỄN VĂN BÌNH', 'father_id': None, 'mother_id': None, 'birth_solar': None},
            {'id': 3, 'ho_ten': 'Trần Thị Hoa', 'father_id': None, 'mother_id': None, 'birth_solar': dt.date(1990, 6, 1)},
            {'id': 4, 'ho_ten': 'Trần Thị Hoa', 'father_id': None, 'mother_id': None, 'birth_solar': dt.date(1991, 6, 1)},
            {'id': 5, 'ho_ten': 'Lê Văn Tư', 'father_id': None, 'mother_id': None, 'birth_solar': dt.date(1950, 1, 1)},
        ]

    def test_normalize(self):
        self.assertEqual('dang van du', normalize_name('  Đặng   Văn Dư '))

    def test_anchor_then_structure_then_name_year(self):
        out = suggest_pairs(self.family(), [], self.clan(), [], {}, anchor=('f_self', 1))
        by_person = {item['personId']: item for item in out}
        self.assertEqual(('high', 'self_binding'), (by_person['f_self']['confidence'], by_person['f_self']['reason']))
        self.assertEqual((2, 'high', 'father'), (by_person['f_dad']['clanPersonId'], by_person['f_dad']['confidence'],
                                                  by_person['f_dad']['reason']))
        self.assertEqual((3, 'low'), (by_person['f_other']['clanPersonId'], by_person['f_other']['confidence']))
        self.assertNotIn('f_noyear', by_person)  # no year -> no name-only guess

    def test_existing_links_are_anchors_and_never_resuggested(self):
        out = suggest_pairs(self.family(), [], self.clan(), [], {'f_self': 1})
        self.assertEqual({'f_dad'} | {'f_other'}, {item['personId'] for item in out})


class DiffAndBootstrapTests(SimpleTestCase):
    def test_diff_reports_father_and_spouse_mismatch(self):
        family = [
            {'id': 'a', 'name': 'A', 'father_id': 'x', 'mother_id': None, 'solar_birth_date': None},
            {'id': 'x', 'name': 'X', 'father_id': None, 'mother_id': None, 'solar_birth_date': None},
        ]
        clan = [
            {'id': 1, 'ho_ten': 'A', 'father_id': 2, 'mother_id': None, 'birth_solar': None},
            {'id': 2, 'ho_ten': 'Y', 'father_id': None, 'mother_id': None, 'birth_solar': None},
            {'id': 3, 'ho_ten': 'Vợ', 'father_id': None, 'mother_id': None, 'birth_solar': None},
        ]
        items = link_diff({'a': 1}, family, [], clan, [(1, 3)])
        self.assertEqual({'father', 'spouse'}, {item['field'] for item in items})

    def test_bootstrap_copies_lineage_and_spouses_parents_first(self):
        rows = [
            {'id': 'g', 'gender': 'male', 'father_id': None, 'mother_id': None},
            {'id': 'root', 'gender': 'male', 'father_id': 'g', 'mother_id': None},
            {'id': 'wife', 'gender': 'female', 'father_id': None, 'mother_id': None},
            {'id': 'kid', 'gender': 'female', 'father_id': 'root', 'mother_id': 'wife'},
            {'id': 'kid_h', 'gender': 'unknown', 'father_id': None, 'mother_id': None},
            {'id': 'x', 'gender': 'male', 'father_id': None, 'mother_id': None},
        ]
        spouses = [{'person_a_id': 'root', 'person_b_id': 'wife', 'type': 'married'},
                    {'person_a_id': 'kid', 'person_b_id': 'kid_h', 'type': 'divorced'}]
        ordered, marriages, skipped = plan_bootstrap(rows, spouses, 'root')
        self.assertEqual({'root', 'wife', 'kid', 'kid_h'}, set(ordered))
        self.assertLess(ordered.index('root'), ordered.index('kid'))
        self.assertIn(('root', 'wife', 'dang_ket_hon'), marriages)
        self.assertIn(('kid_h', 'kid', 'ly_hon'), marriages)
        self.assertEqual([], skipped)
