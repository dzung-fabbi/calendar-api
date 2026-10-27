"""`services.family_import` + `family_import_fields` -- pure, no database."""

from django.test import SimpleTestCase

from giapha.services.family_import import plan_import
from giapha.services.family_import_fields import UNNAMED, normalize_person


def person(pid, gender='male', created=1, **extra):
    row = {'id': pid, 'name': 'N ' + pid, 'gender': gender, 'createdAt': created * 1000}
    row.update(extra)
    return row


def codes(plan):
    return [edge['code'] for edge in plan.skipped_edges]


class NormalizeFieldTests(SimpleTestCase):
    def test_bad_values_are_repaired_with_warnings(self):
        fields, warnings = normalize_person({
            'id': 'fam_1', 'name': '  ', 'gender': 'x', 'solarBirthDate': '2000-01-01',
            'birthTime': '25:00', 'lunarDeathDay': 31, 'lunarDeathMonth': 13,
            'relationship': 'r' * 30, 'note': 'n' * 510, 'gioEventId': 'gio_old_1',
        })
        self.assertEqual(UNNAMED, fields['name'])
        self.assertEqual('unknown', fields['gender'])
        self.assertIsNone(fields['solar_birth_date'])
        self.assertIsNone(fields['birth_time'])
        self.assertIsNone(fields['lunar_death_day'])
        self.assertIsNone(fields['lunar_death_month'])
        self.assertEqual(24, len(fields['relationship']))
        self.assertEqual(500, len(fields['note']))
        self.assertEqual('gio_old_1', fields['gio_event_id'])
        warned = {w['field'] for w in warnings}
        self.assertTrue({'name', 'gender', 'solarBirthDate', 'birthTime', 'lunarDeathDay',
                         'lunarDeathMonth', 'relationship', 'note'} <= warned)

    def test_contact_fields_are_trimmed_cut_and_warned(self):
        fields, warnings = normalize_person({
            'id': 'fam_2', 'name': 'A', 'phone': ' 0' * 15, 'education': 'e' * 41,
            'occupation': '  Kỹ sư  ', 'note': 'n' * 500,
        })
        self.assertEqual(20, len(fields['phone']))
        self.assertEqual(40, len(fields['education']))
        self.assertEqual('Kỹ sư', fields['occupation'])
        self.assertEqual(500, len(fields['note']))
        self.assertEqual({'phone', 'education'}, {w['field'] for w in warnings})
        self.assertIn('20', next(w['message'] for w in warnings if w['field'] == 'phone'))

    def test_blank_or_non_string_contact_fields_become_null(self):
        fields, warnings = normalize_person({'id': 'x', 'name': 'A', 'phone': '   ', 'education': 12, 'occupation': ''})
        self.assertEqual((None, None, None), (fields['phone'], fields['education'], fields['occupation']))
        self.assertEqual([], warnings)

    def test_long_name_is_cut(self):
        fields, warnings = normalize_person({'id': 'x', 'name': 'a' * 70})
        self.assertEqual(60, len(fields['name']))
        self.assertEqual('name', warnings[0]['field'])

    def test_client_timestamps_kept_and_solar_death_derived(self):
        fields, _ = normalize_person({'id': 'x', 'name': 'A', 'createdAt': 1690000000000,
                                      'lunarDeathDay': 1, 'lunarDeathMonth': 1, 'lunarDeathYear': 2020})
        self.assertEqual(1690000000, int(fields['created_at'].timestamp()))
        self.assertIsNotNone(fields['solar_death_date'])


class PlanImportTests(SimpleTestCase):
    def test_clean_tree_keeps_every_edge(self):
        plan = plan_import([
            person('f', spouses=[{'id': 'm', 'type': 'married'}]),
            person('m', 'female', spouses=[{'id': 'f', 'type': 'married'}]),
            person('c', created=2, fatherId='f', motherId='m', fatherRel='adopted'),
        ], 'c')
        self.assertEqual([], plan.skipped_edges)
        self.assertEqual({('c', 'father', 'f', 'adopted'), ('c', 'mother', 'm', None)}, set(plan.parents))
        self.assertEqual(1, len(plan.spouses))
        self.assertEqual('c', plan.self_id)

    def test_cycle_drops_exactly_one_edge_and_keeps_people(self):
        plan = plan_import([person('a', created=1, fatherId='b'), person('b', created=2, fatherId='a')], None)
        self.assertEqual(2, len(plan.persons))
        self.assertEqual(['PARENT_CYCLE'], codes(plan))
        self.assertEqual([('a', 'father', 'b', None)], plan.parents)

    def test_dangling_self_parent_and_gender_mismatch(self):
        plan = plan_import([
            person('a', fatherId='ghost'),
            person('b', motherId='b'),
            person('c', motherId='d'),
            person('d', 'male'),
        ], None)
        self.assertEqual(['DANGLING_FATHER', 'SELF_PARENT', 'GENDER_MISMATCH'], codes(plan))
        self.assertEqual([], plan.parents)

    def test_spouses_one_sided_self_and_dangling(self):
        plan = plan_import([
            person('a', spouses=[{'id': 'b'}, {'id': 'a'}, {'id': 'zz'}]),
            person('b', 'female'),
        ], None)
        self.assertEqual(1, len(plan.spouses))
        self.assertEqual(['SELF_SPOUSE', 'DANGLING_SPOUSE'], codes(plan))

    def test_spouse_is_ancestor_kept_with_warning(self):
        plan = plan_import([person('a'), person('b', 'female', created=2, fatherId='a', spouses=[{'id': 'a'}])], None)
        self.assertEqual(1, len(plan.spouses))
        self.assertTrue(any(w['field'] == 'spouses' for w in plan.warnings))

    def test_dangling_self_id_is_dropped(self):
        plan = plan_import([person('a')], 'ghost')
        self.assertIsNone(plan.self_id)
        self.assertEqual('selfId', plan.warnings[-1]['field'])

    def test_order_is_deterministic(self):
        rows = [person('x{}'.format(i), created=500 - i, fatherId='x{}'.format(i + 1)) for i in range(50)]
        rows.append(person('x50', created=1, fatherId='x0'))  # closes a cycle
        first = plan_import(rows, None)
        second = plan_import(list(reversed(rows)), None)
        self.assertEqual(first.parents, second.parents)
        self.assertEqual(first.skipped_edges, second.skipped_edges)
        self.assertEqual(1, len(first.skipped_edges))
