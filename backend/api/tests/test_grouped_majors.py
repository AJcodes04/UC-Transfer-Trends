
from django.test import TestCase
from rest_framework.test import APIClient

from api.services.major_sync import sync_major_groups
from api.tests.factories import make_transfer_data


class GroupedMajorListViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        # ── Active base majors ────────────────────────────────────
        make_transfer_data(university='UCB', major_name='Chemistry', year=2023, applicants=500)
        make_transfer_data(university='UCLA', major_name='Chemistry', year=2022, applicants=400)
        make_transfer_data(university='UCB', major_name='Biology', year=2023, applicants=300)

        # ── Regex grouping targets ────────────────────────────────
        # " - " delimiter → groups under Chemistry
        make_transfer_data(university='UCB', major_name='Chemistry - Environmental', year=2023, applicants=80)
        # " (" delimiter → groups under Chemistry
        make_transfer_data(university='UCLA', major_name='Chemistry (Organic)', year=2023, applicants=60)

        # ── Explicit absorption targets ───────────────────────────
        # "Biochemistry" is in MAJOR_ABSORPTIONS['Chemistry']
        make_transfer_data(university='UCD', major_name='Biochemistry', year=2023, applicants=200)
        # "Cell Biology" is in MAJOR_ABSORPTIONS['Biology']
        make_transfer_data(university='UCB', major_name='Cell Biology', year=2023, applicants=90)

        # ── Alias targets ────────────────────────────────────────
        make_transfer_data(university='UCB', major_name='African American Studies', year=2023, applicants=50)
        make_transfer_data(university='UCLA', major_name='African-American Studies', year=2023, applicants=30)

        # ── Discontinued: HIDDEN (last seen 2015, newest data 2023, 3yr span) ──
        make_transfer_data(university='UCB', major_name='Ancient Greek', year=2015, applicants=10)
        make_transfer_data(university='UCB', major_name='Ancient Greek', year=2014, applicants=10,
                           college_school='Humanities')
        make_transfer_data(university='UCB', major_name='Ancient Greek', year=2013, applicants=10,
                           college_school='Classics')

        # ── Discontinued: SHOWN (8yr span, passes history check) ──
        make_transfer_data(university='UCB', major_name='Latin', year=2015, applicants=15)
        make_transfer_data(university='UCB', major_name='Latin', year=2008, applicants=10,
                           college_school='Classics')

        # ── Standalone major (no sub-majors, no absorption) ───────
        make_transfer_data(university='UCB', major_name='Physics', year=2023, applicants=250)
        make_transfer_data(university='UCLA', major_name='Physics', year=2023, applicants=200)

        sync_major_groups()

    # --- helpers ---

    def _find_group(self, data, name):
        """Return the first group dict with the given name, or None."""
        for group in data:
            if group['name'] == name:
                return group
        return None

    def _related_names(self, group):
        """Extract just the names from a group's related list."""
        return [r['name'] for r in group['related']]

    def _all_group_names(self, data):
        """Return all top-level group names."""
        return [g['name'] for g in data]

    # --- basic ---

    def test_returns_200(self):
        response = self.client.get('/api/majors/grouped/')
        self.assertEqual(response.status_code, 200)

    # --- regex grouping ---

    def test_regex_grouping_dash_delimiter(self):
        """'Chemistry - Environmental' should be a specialization under Chemistry."""
        response = self.client.get('/api/majors/grouped/')
        chem = self._find_group(response.data, 'Chemistry')
        self.assertIsNotNone(chem)
        self.assertIn('Chemistry - Environmental', self._related_names(chem))

    def test_regex_grouping_paren_delimiter(self):
        """'Chemistry (Organic)' should be a specialization under Chemistry."""
        response = self.client.get('/api/majors/grouped/')
        chem = self._find_group(response.data, 'Chemistry')
        self.assertIn('Chemistry (Organic)', self._related_names(chem))

    # --- explicit absorption ---

    def test_explicit_absorption_under_chemistry(self):
        """'Biochemistry' is in MAJOR_ABSORPTIONS and should be under Chemistry."""
        response = self.client.get('/api/majors/grouped/')
        chem = self._find_group(response.data, 'Chemistry')
        self.assertIn('Biochemistry', self._related_names(chem))
        # Should NOT be a top-level group
        self.assertNotIn('Biochemistry', self._all_group_names(response.data))

    def test_explicit_absorption_under_biology(self):
        """'Cell Biology' is in MAJOR_ABSORPTIONS and should be under Biology."""
        response = self.client.get('/api/majors/grouped/')
        bio = self._find_group(response.data, 'Biology')
        self.assertIsNotNone(bio)
        self.assertIn('Cell Biology', self._related_names(bio))
        self.assertNotIn('Cell Biology', self._all_group_names(response.data))

    # --- alias handling ---

    def test_alias_merges_applicants(self):
        """Alias data (30) should merge into canonical (50) = 80 total."""
        response = self.client.get('/api/majors/grouped/')
        aas = self._find_group(response.data, 'African American Studies')
        self.assertIsNotNone(aas)
        self.assertEqual(aas['total_applicants'], 80)

    def test_alias_not_shown_as_group(self):
        """The alias name should not appear as a top-level group."""
        response = self.client.get('/api/majors/grouped/')
        self.assertNotIn('African-American Studies', self._all_group_names(response.data))

    def test_alias_not_shown_as_specialization(self):
        """The alias name should not appear in any group's related list."""
        response = self.client.get('/api/majors/grouped/')
        for group in response.data:
            self.assertNotIn('African-American Studies', self._related_names(group))

    # --- discontinued filter ---

    def test_discontinued_short_lived_hidden(self):
        """Ancient Greek (2013-2015, 3yr span, 8 years stale) should be filtered out."""
        response = self.client.get('/api/majors/grouped/')
        self.assertNotIn('Ancient Greek', self._all_group_names(response.data))

    def test_discontinued_long_history_shown(self):
        """Latin (2008-2015, 8yr span) should still appear."""
        response = self.client.get('/api/majors/grouped/')
        self.assertIn('Latin', self._all_group_names(response.data))

    # --- campus badges ---

    def test_campus_badges_base_major(self):
        """Chemistry is offered at UCB and UCLA."""
        response = self.client.get('/api/majors/grouped/')
        chem = self._find_group(response.data, 'Chemistry')
        self.assertEqual(chem['campuses'], ['UCB', 'UCLA'])

    def test_campus_badges_specialization(self):
        """'Chemistry - Environmental' is only at UCB."""
        response = self.client.get('/api/majors/grouped/')
        chem = self._find_group(response.data, 'Chemistry')
        spec = next(r for r in chem['related'] if r['name'] == 'Chemistry - Environmental')
        self.assertEqual(spec['campuses'], ['UCB'])

    def test_campus_badges_alias_merged(self):
        """African American Studies campuses should include UCLA from the alias."""
        response = self.client.get('/api/majors/grouped/')
        aas = self._find_group(response.data, 'African American Studies')
        self.assertIn('UCB', aas['campuses'])
        self.assertIn('UCLA', aas['campuses'])

    # --- structure & ordering ---

    def test_standalone_major_no_related(self):
        """Physics has no sub-majors, absorptions, or aliases."""
        response = self.client.get('/api/majors/grouped/')
        physics = self._find_group(response.data, 'Physics')
        self.assertIsNotNone(physics)
        self.assertEqual(physics['related'], [])

    def test_sorted_by_total_applicants_descending(self):
        """Groups should be ordered from most to fewest total applicants."""
        response = self.client.get('/api/majors/grouped/')
        totals = [g['total_applicants'] for g in response.data]
        self.assertEqual(totals, sorted(totals, reverse=True))

    def test_response_structure(self):
        """Each group should have the expected keys; each related item too."""
        response = self.client.get('/api/majors/grouped/')
        for group in response.data:
            self.assertIn('name', group)
            self.assertIn('total_applicants', group)
            self.assertIn('related', group)
            self.assertIn('campuses', group)
            for rel in group['related']:
                self.assertIn('name', rel)
                self.assertIn('campuses', rel)
