
from django.test import TestCase
from rest_framework.test import APIClient

from api.tests.factories import make_transfer_data


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

    def test_rates_are_weighted_by_volume(self):
        """UCB 2023 rows: 30/50 and 5/10 admits -> 35/60 = 58.33%, not the row mean of 55%."""
        response = self.client.get('/api/stats/by-major/African American Studies/')
        ucb = next(r for r in response.data if r['university'] == 'UCB')
        self.assertAlmostEqual(ucb['avg_admit_rate'], 58.33, places=2)
        self.assertAlmostEqual(ucb['avg_yield_rate'], 18 / 35 * 100, places=2)

    def test_zero_applicants_gives_null_rate(self):
        make_transfer_data(university='UCM', major_name='Ghost', year=2023,
                           applicants=0, admits=0, enrolls=0, admit_rate=None, yield_rate=None)
        response = self.client.get('/api/stats/by-major/Ghost/')
        self.assertIsNone(response.data[0]['avg_admit_rate'])
        self.assertIsNone(response.data[0]['avg_yield_rate'])

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
