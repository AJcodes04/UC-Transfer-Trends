from django.test import TestCase
from rest_framework.test import APIClient

from api.models import TransferData


def make_transfer_data(**kwargs):
    """
    Shortcut to create a TransferData row with sensible defaults.
    Tests only need to specify the fields they care about.
    """
    defaults = {
        'university': 'UCB',
        'year': 2023,
        'broad_discipline': 'Sciences',
        'college_school': 'Letters & Science',
        'major_name': 'Test Major',
        'applicants': 100,
        'admits': 50,
        'enrolls': 25,
        'admit_rate': 50,
        'yield_rate': 50,
    }
    defaults.update(kwargs)
    return TransferData.objects.create(**defaults)


# ─────────────────────────────────────────────────────────────────
# 1. GET /api/majors/  (MajorListView)
# ─────────────────────────────────────────────────────────────────
class MajorListViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        make_transfer_data(university='UCB', major_name='Chemistry', year=2023)
        make_transfer_data(university='UCLA', major_name='Chemistry', year=2023)
        make_transfer_data(university='UCB', major_name='Biology', year=2023)
        make_transfer_data(university='UCD', major_name='Physics', year=2022)

    def test_returns_200(self):
        response = self.client.get('/api/majors/')
        self.assertEqual(response.status_code, 200)

    def test_returns_distinct_majors(self):
        """Chemistry appears at 2 campuses but should only be listed once."""
        response = self.client.get('/api/majors/')
        self.assertEqual(len(response.data), 3)

    def test_returns_sorted_alphabetically(self):
        response = self.client.get('/api/majors/')
        self.assertEqual(list(response.data), ['Biology', 'Chemistry', 'Physics'])

    def test_empty_database(self):
        TransferData.objects.all().delete()
        response = self.client.get('/api/majors/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.data), [])


# ─────────────────────────────────────────────────────────────────
# 2. GET /api/majors/grouped/  (GroupedMajorListView)
# ─────────────────────────────────────────────────────────────────
class GroupedMajorListViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        # ── Active base majors ────────────────────────────────────
        make_transfer_data(university='UCB', major_name='Chemistry', year=2023, applicants=500)
        make_transfer_data(university='UCLA', major_name='Chemistry', year=2022, applicants=400)
        make_transfer_data(university='UCB', major_name='Biology', year=2023, applicants=300)

        # ── Regex grouping targets ────────────────────────────────
        # " - " delimiter → groups under Chemistry
        make_transfer_data(university='UCB', major_name='Chemistry - Biochemistry', year=2023, applicants=80)
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

        # ── Discontinued: HIDDEN (short-lived, 3yr span) ─────────
        make_transfer_data(university='UCB', major_name='Ancient Greek', year=2018, applicants=10)
        make_transfer_data(university='UCB', major_name='Ancient Greek', year=2017, applicants=10,
                           college_school='Humanities')
        make_transfer_data(university='UCB', major_name='Ancient Greek', year=2016, applicants=10,
                           college_school='Classics')

        # ── Discontinued: SHOWN (8yr span, passes history check) ──
        make_transfer_data(university='UCB', major_name='Latin', year=2018, applicants=15)
        make_transfer_data(university='UCB', major_name='Latin', year=2011, applicants=10,
                           college_school='Classics')

        # ── Standalone major (no sub-majors, no absorption) ───────
        make_transfer_data(university='UCB', major_name='Physics', year=2023, applicants=250)
        make_transfer_data(university='UCLA', major_name='Physics', year=2023, applicants=200)

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
        """'Chemistry - Biochemistry' should be a specialization under Chemistry."""
        response = self.client.get('/api/majors/grouped/')
        chem = self._find_group(response.data, 'Chemistry')
        self.assertIsNotNone(chem)
        self.assertIn('Chemistry - Biochemistry', self._related_names(chem))

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
        """Ancient Greek (2016-2018, 3yr span) should be filtered out."""
        response = self.client.get('/api/majors/grouped/')
        self.assertNotIn('Ancient Greek', self._all_group_names(response.data))

    def test_discontinued_long_history_shown(self):
        """Latin (2011-2018, 8yr span) should still appear."""
        response = self.client.get('/api/majors/grouped/')
        self.assertIn('Latin', self._all_group_names(response.data))

    # --- campus badges ---

    def test_campus_badges_base_major(self):
        """Chemistry is offered at UCB and UCLA."""
        response = self.client.get('/api/majors/grouped/')
        chem = self._find_group(response.data, 'Chemistry')
        self.assertEqual(chem['campuses'], ['UCB', 'UCLA'])

    def test_campus_badges_specialization(self):
        """'Chemistry - Biochemistry' is only at UCB."""
        response = self.client.get('/api/majors/grouped/')
        chem = self._find_group(response.data, 'Chemistry')
        spec = next(r for r in chem['related'] if r['name'] == 'Chemistry - Biochemistry')
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


# ─────────────────────────────────────────────────────────────────
# 3. GET /api/stats/by-major/<major>/  (MajorStatsView)
# ─────────────────────────────────────────────────────────────────
class MajorStatsViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        # ── Standard major across years and campuses ──────────────
        make_transfer_data(university='UCB', major_name='Chemistry', year=2023,
                           applicants=100, admits=40, enrolls=20,
                           admit_rate=40, yield_rate=50)
        make_transfer_data(university='UCB', major_name='Chemistry', year=2022,
                           applicants=90, admits=35, enrolls=18,
                           admit_rate=39, yield_rate=51,
                           college_school='Chemistry Dept')
        make_transfer_data(university='UCLA', major_name='Chemistry', year=2023,
                           applicants=120, admits=50, enrolls=25,
                           admit_rate=42, yield_rate=50)

        # ── Alias pair ────────────────────────────────────────────
        make_transfer_data(university='UCB', major_name='African American Studies', year=2023,
                           applicants=50, admits=30, enrolls=15,
                           admit_rate=60, yield_rate=50)
        make_transfer_data(university='UCLA', major_name='African-American Studies', year=2023,
                           applicants=40, admits=20, enrolls=10,
                           admit_rate=50, yield_rate=50)
        # Alias at same campus as canonical — different college_school for uniqueness
        make_transfer_data(university='UCB', major_name='African-American Studies', year=2023,
                           applicants=10, admits=5, enrolls=3,
                           admit_rate=50, yield_rate=60,
                           college_school='Social Sciences')

        # ── Major with slash in name ─────────────────────────────────
        make_transfer_data(university='UCI', major_name='Chicana/0 Studies', year=2023,
                           applicants=30, admits=15, enrolls=8,
                           admit_rate=50, yield_rate=53)

        # ── Unrelated major (should never leak into other queries) ─
        make_transfer_data(university='UCB', major_name='Physics', year=2023,
                           applicants=200, admits=80, enrolls=40)

    def test_returns_200(self):
        response = self.client.get('/api/stats/by-major/Chemistry/')
        self.assertEqual(response.status_code, 200)

    def test_returns_stats_for_major(self):
        """Should return 3 rows: UCB 2022, UCB 2023, UCLA 2023."""
        response = self.client.get('/api/stats/by-major/Chemistry/')
        self.assertEqual(len(response.data), 3)

    def test_aggregation_keys(self):
        """Each row should contain the expected stat fields."""
        response = self.client.get('/api/stats/by-major/Chemistry/')
        expected_keys = {
            'year', 'university',
            'total_applicants', 'total_admits', 'total_enrolls',
            'avg_admit_rate', 'avg_yield_rate',
            'avg_admit_gpa_min', 'avg_admit_gpa_max',
        }
        for row in response.data:
            self.assertTrue(expected_keys.issubset(row.keys()))

    def test_alias_consolidation(self):
        """Querying canonical name should include alias data.

        UCB has both 'African American Studies' (50 apps) and
        'African-American Studies' (10 apps). Since they share
        university+year, the ORM aggregates them into one row
        with total_applicants = 60.
        UCLA only has the alias (40 apps).
        """
        response = self.client.get('/api/stats/by-major/African American Studies/')
        rows = {r['university']: r for r in response.data}
        self.assertIn('UCB', rows)
        self.assertIn('UCLA', rows)
        self.assertEqual(rows['UCB']['total_applicants'], 60)
        self.assertEqual(rows['UCLA']['total_applicants'], 40)

    def test_alias_query_by_alias_name(self):
        """Querying by alias name does NOT trigger consolidation.

        Only the alias rows should be returned (UCB 10 + UCLA 40),
        not the canonical rows.
        """
        response = self.client.get('/api/stats/by-major/African-American Studies/')
        total = sum(r['total_applicants'] for r in response.data)
        self.assertEqual(total, 50)  # 10 + 40, not 100

    def test_does_not_return_other_majors(self):
        """Chemistry query should not include Physics data."""
        response = self.client.get('/api/stats/by-major/Chemistry/')
        universities_and_apps = [(r['university'], r['total_applicants']) for r in response.data]
        # Physics has 200 applicants at UCB — make sure it's not mixed in
        for uni, apps in universities_and_apps:
            if uni == 'UCB':
                self.assertNotEqual(apps, 200)

    def test_nonexistent_major_returns_empty(self):
        response = self.client.get('/api/stats/by-major/Nonexistent Major/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.data), [])

    def test_major_with_slash_in_name(self):
        """Majors with '/' in the name (e.g. 'Chicana/0 Studies') should resolve."""
        response = self.client.get('/api/stats/by-major/Chicana/0 Studies/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['total_applicants'], 30)

    def test_ordered_by_year_university(self):
        """Results should be sorted by year ascending, then university."""
        response = self.client.get('/api/stats/by-major/Chemistry/')
        pairs = [(r['year'], r['university']) for r in response.data]
        self.assertEqual(pairs, sorted(pairs))
