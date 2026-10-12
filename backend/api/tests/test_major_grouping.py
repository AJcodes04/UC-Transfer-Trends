from django.test import TestCase

from api.models import Major
from api.services.major_grouping import group_majors
from api.services.major_sync import sync_major_groups
from api.tests.factories import major


class GroupMajorsFunctionTests(TestCase):
    """group_majors is pure over its inputs; Major rows only supply names and relationships."""

    def _rows(self, *spec):
        return [
            {'major_id': major(name).id, 'total_apps': apps, 'latest_year': latest, 'earliest_year': earliest}
            for name, apps, latest, earliest in spec
        ]

    def _group(self, rows, campus_rows=()):
        majors = {m.id: m for m in Major.objects.all()}
        return group_majors(rows, list(campus_rows), majors)

    def test_cutoff_follows_newest_data_year(self):
        rows = self._rows(('Physics', 10, 2030, 2030), ('Alchemy', 10, 2024, 2023))
        self.assertEqual([g['name'] for g in self._group(rows)], ['Physics'])
        rows = self._rows(('Physics', 10, 2028, 2028), ('Alchemy', 10, 2024, 2023))
        self.assertEqual(sorted(g['name'] for g in self._group(rows)), ['Alchemy', 'Physics'])

    def test_alias_merges_applicants_latest_year_and_campuses(self):
        rows = self._rows(('Economics', 100, 2022, 2022), ('Pre-Economics', 40, 2023, 2023))
        sync_major_groups()
        econ_id = Major.objects.get(name='Economics').id
        pre_id = Major.objects.get(name='Pre-Economics').id
        campus_rows = [{'major_id': econ_id, 'university': 'UCB'}, {'major_id': pre_id, 'university': 'UCLA'}]
        (econ,) = self._group(rows, campus_rows)
        self.assertEqual((econ['name'], econ['total_applicants'], econ['latest_year'], econ['campuses']),
                         ('Economics', 140, 2023, ['UCB', 'UCLA']))

    def test_child_lists_under_parent_only_when_parent_is_active(self):
        rows = self._rows(('Mathematics', 50, 2023, 2023), ('Mathematics - Applied Science', 5, 2023, 2023))
        sync_major_groups()
        (math,) = self._group(rows)
        self.assertEqual([r['name'] for r in math['related']], ['Mathematics - Applied Science'])
        rows = self._rows(('Mathematics', 50, 2010, 2009), ('Mathematics - Applied Science', 5, 2023, 2023))
        self.assertEqual([g['name'] for g in self._group(rows)], ['Mathematics - Applied Science'])

    def test_empty_input(self):
        self.assertEqual(self._group([]), [])


class SyncMajorGroupsTests(TestCase):

    def test_sets_canonical_for_aliases_and_parent_for_sub_majors_and_absorptions(self):
        for name in ('Chemistry', 'Chemistry - Organic', 'Biochemistry', 'Chemical Sciences', 'Physics'):
            major(name)
        aliases, grouped = sync_major_groups()
        by = {m.name: m for m in Major.objects.all()}
        self.assertEqual(by['Chemical Sciences'].canonical, by['Chemistry'])
        self.assertIsNone(by['Chemical Sciences'].parent)
        self.assertEqual(by['Chemistry - Organic'].parent, by['Chemistry'])
        self.assertEqual(by['Biochemistry'].parent, by['Chemistry'])
        self.assertIsNone(by['Physics'].parent)
        self.assertGreaterEqual(aliases, 1)
        self.assertGreaterEqual(grouped, 2)

    def test_absorption_flattens_grandchildren_and_is_idempotent(self):
        for name in ('Chemistry', 'Biochemistry', 'Biochemistry - Marine'):
            major(name)
        sync_major_groups()
        first = dict(Major.objects.values_list('name', 'parent__name'))
        self.assertEqual(first['Biochemistry - Marine'], 'Chemistry')
        sync_major_groups()
        self.assertEqual(dict(Major.objects.values_list('name', 'parent__name')), first)

    def test_creates_missing_canonical_rows_so_lone_aliases_still_merge(self):
        major('Pre-Statistics')
        sync_major_groups()
        self.assertEqual(Major.objects.get(name='Pre-Statistics').canonical.name, 'Statistics')
