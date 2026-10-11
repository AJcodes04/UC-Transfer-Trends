
from django.test import TestCase


class GroupMajorsFunctionTests(TestCase):
    """group_majors is pure: exercise it without the database."""

    def _row(self, name, apps=10, latest=2023, earliest=2023):
        return {'major_name': name, 'total_apps': apps, 'latest_year': latest, 'earliest_year': earliest}

    def test_cutoff_follows_newest_data_year(self):
        from api.services.major_grouping import group_majors
        rows = [self._row('Physics', latest=2030), self._row('Alchemy', latest=2024, earliest=2023)]
        names = [g['name'] for g in group_majors(rows, [])]
        self.assertEqual(names, ['Physics'])
        rows = [self._row('Physics', latest=2028), self._row('Alchemy', latest=2024, earliest=2023)]
        names = [g['name'] for g in group_majors(rows, [])]
        self.assertEqual(sorted(names), ['Alchemy', 'Physics'])

    def test_alias_merges_applicants_latest_year_and_campuses(self):
        from api.services.major_grouping import group_majors
        rows = [self._row('Economics', apps=100, latest=2022), self._row('Pre-Economics', apps=40, latest=2023)]
        campus_rows = [{'major_name': 'Economics', 'university': 'UCB'}, {'major_name': 'Pre-Economics', 'university': 'UCLA'}]
        (econ,) = group_majors(rows, campus_rows)
        self.assertEqual((econ['total_applicants'], econ['latest_year'], econ['campuses']), (140, 2023, ['UCB', 'UCLA']))

    def test_empty_input(self):
        from api.services.major_grouping import group_majors
        self.assertEqual(group_majors([], []), [])

    def test_absorbed_child_is_moved_out_of_its_regex_group(self):
        from api.services.major_grouping import group_majors
        rows = [self._row('Mathematics'), self._row('Mathematics - Applied Science'), self._row('Physics')]
        (math, *_rest) = [g for g in group_majors(rows, []) if g['name'] == 'Mathematics']
        self.assertEqual([r['name'] for r in math['related']], ['Mathematics - Applied Science'])
        self.assertNotIn('Mathematics - Applied Science', [g['name'] for g in group_majors(rows, [])])
