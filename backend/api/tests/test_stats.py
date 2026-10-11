from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from api.tests.factories import make_campus_stats, make_transfer_data


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

    def test_gpa_bounds_are_min_and_max_across_rows(self):
        make_transfer_data(university='UCD', major_name='Geology', year=2023, college_school='A',
                           admit_gpa_min=Decimal('3.20'), admit_gpa_max=Decimal('3.80'))
        make_transfer_data(university='UCD', major_name='Geology', year=2023, college_school='B',
                           admit_gpa_min=Decimal('3.10'), admit_gpa_max=Decimal('3.95'))
        row = self.client.get('/api/stats/by-major/Geology/').json()[0]
        self.assertEqual((row['avg_admit_gpa_min'], row['avg_admit_gpa_max']), (3.1, 3.95))


class SchoolStatsViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        make_transfer_data(university='UCB', year=2023, college_school='College Of Chemistry',
                           major_name='Chemistry', applicants=100, admits=40, enrolls=20)
        make_transfer_data(university='UCB', year=2023, college_school='College Of Letters & science',
                           major_name='Physics', applicants=200, admits=50, enrolls=25)
        make_transfer_data(university='UCB', year=2023, college_school='College Of Letters & science',
                           major_name='History', applicants=20, admits=18, enrolls=9)
        make_transfer_data(university='UCB', year=2022, college_school='College Of Chemistry',
                           major_name='Chemistry', applicants=90, admits=45, enrolls=30)
        make_transfer_data(university='UCLA', year=2023, college_school='College Of Letters & science',
                           major_name='Physics', applicants=999, admits=1, enrolls=1)

    def test_groups_by_year_and_college_for_one_campus(self):
        rows = self.client.get('/api/stats/by-school/UCB/').data
        self.assertEqual([(r['year'], r['college_school']) for r in rows], [
            (2022, 'College Of Chemistry'),
            (2023, 'College Of Chemistry'),
            (2023, 'College Of Letters & science'),
        ])

    def test_totals_and_weighted_rate_within_a_college(self):
        rows = self.client.get('/api/stats/by-school/UCB/').data
        ls = next(r for r in rows if r['year'] == 2023 and r['college_school'].startswith('College Of Letters'))
        self.assertEqual((ls['total_applicants'], ls['total_admits'], ls['total_enrolls']), (220, 68, 34))
        self.assertAlmostEqual(ls['avg_admit_rate'], 68 / 220 * 100, places=4)
        self.assertAlmostEqual(ls['avg_yield_rate'], 50.0, places=4)

    def test_unknown_campus_is_empty(self):
        response = self.client.get('/api/stats/by-school/UCX/')
        self.assertEqual((response.status_code, response.data), (200, []))


class CampusMajorStatsViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        make_transfer_data(university='UCLA', year=2023, major_name='Economics', college_school='A',
                           applicants=100, admits=50, enrolls=25)
        make_transfer_data(university='UCLA', year=2023, major_name='Pre-Economics', college_school='B',
                           applicants=60, admits=30, enrolls=15)
        make_transfer_data(university='UCLA', year=2023, major_name='Physics', applicants=10, admits=5, enrolls=1)
        make_transfer_data(university='UCLA', year=2022, major_name='Physics', applicants=12, admits=6, enrolls=3)
        make_transfer_data(university='UCB', year=2023, major_name='Economics', applicants=500, admits=5, enrolls=5)

    def test_alias_rows_merge_under_canonical_name(self):
        rows = self.client.get('/api/stats/campus-majors/UCLA/').data
        names = sorted(r['major_name'] for r in rows if r['year'] == 2023)
        self.assertEqual(names, ['Economics', 'Physics'])
        econ = next(r for r in rows if r['major_name'] == 'Economics')
        self.assertEqual((econ['total_applicants'], econ['total_admits'], econ['total_enrolls']), (160, 80, 40))
        self.assertAlmostEqual(econ['avg_admit_rate'], 50.0)

    def test_rows_use_major_name_key_and_are_ordered(self):
        rows = self.client.get('/api/stats/campus-majors/UCLA/').data
        self.assertNotIn('display_name', rows[0])
        self.assertEqual([(r['year'], r['major_name']) for r in rows],
                         [(2022, 'Physics'), (2023, 'Economics'), (2023, 'Physics')])

    def test_other_campuses_excluded_and_unknown_campus_empty(self):
        econ = next(r for r in self.client.get('/api/stats/campus-majors/UCLA/').data if r['major_name'] == 'Economics')
        self.assertEqual(econ['total_applicants'], 160)
        self.assertEqual(self.client.get('/api/stats/campus-majors/UCX/').data, [])


class GeneralStatsViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        make_campus_stats(campus='UCLA', year=2023, applicants=30000, admits=7000, enrolls=3500,
                          admit_gpa_min=Decimal('3.50'), admit_gpa_max=Decimal('4.00'))
        make_campus_stats(campus='UCB', year=2023)
        make_campus_stats(campus='UCB', year=2022, admit_rate=None, yield_rate=None)

    def test_returns_one_row_per_campus_year_ordered(self):
        rows = self.client.get('/api/stats/general/').data
        self.assertEqual([(r['year'], r['campus']) for r in rows], [(2022, 'UCB'), (2023, 'UCB'), (2023, 'UCLA')])

    def test_rows_pass_stored_values_through_with_numeric_gpas(self):
        rows = self.client.get('/api/stats/general/').json()
        ucla = next(r for r in rows if r['campus'] == 'UCLA')
        self.assertEqual(ucla, {
            'year': 2023, 'campus': 'UCLA', 'applicants': 30000, 'admits': 7000, 'enrolls': 3500,
            'admit_rate': 50, 'yield_rate': 50, 'admit_gpa_min': 3.5, 'admit_gpa_max': 4.0,
        })
        ucb_2022 = next(r for r in rows if r['year'] == 2022)
        self.assertIsNone(ucb_2022['admit_rate'])
        self.assertIsNone(ucb_2022['admit_gpa_min'])
