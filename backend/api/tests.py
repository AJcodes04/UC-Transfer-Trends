from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
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


# ─────────────────────────────────────────────────────────────────
# 4. Major lookup tables
# ─────────────────────────────────────────────────────────────────
class MajorTableTests(TestCase):

    def test_alias_and_absorption_tables_do_not_overlap(self):
        """A name is either a renamed major (alias) or a distinct grouped major (absorption), never both."""
        from api.constants.majors import MAJOR_ALIASES, MAJOR_ABSORPTIONS
        aliases = {a for names in MAJOR_ALIASES.values() for a in names}
        children = {c for names in MAJOR_ABSORPTIONS.values() for c in names}
        self.assertEqual(aliases & children, set())

    def test_alias_maps_to_single_canonical(self):
        from api.constants.majors import MAJOR_ALIASES
        seen = {}
        for canonical, names in MAJOR_ALIASES.items():
            for name in names:
                self.assertNotIn(name, seen, f'{name!r} aliased to both {seen.get(name)!r} and {canonical!r}')
                seen[name] = canonical


# ─────────────────────────────────────────────────────────────────
# 5. POST /api/transcript/upload/  (TranscriptUploadView)
# ─────────────────────────────────────────────────────────────────
class TranscriptRateLimitTests(TestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        self.settings_override = override_settings(ANTHROPIC_API_KEY='test-key')
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()

    def _pdf(self):
        return SimpleUploadedFile('t.pdf', b'%PDF-1.4 fake', content_type='application/pdf')

    def test_limiter_counts_to_limit_then_blocks(self):
        from api.views.transcript import DAILY_LIMIT, _check_rate_limit
        for i in range(DAILY_LIMIT):
            allowed, remaining = _check_rate_limit('1.2.3.4')
            self.assertTrue(allowed)
            self.assertEqual(remaining, DAILY_LIMIT - i - 1)
        allowed, remaining = _check_rate_limit('1.2.3.4')
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_invalid_upload_does_not_consume_quota(self):
        from django.core.cache import cache
        self.client.post('/api/transcript/upload/', {}, format='multipart')
        self.client.post('/api/transcript/upload/', {'file': SimpleUploadedFile('t.txt', b'x')}, format='multipart')
        self.assertIsNone(cache.get('transcript_ratelimit:127.0.0.1'))

    def test_over_limit_returns_429_with_header_and_limit_in_message(self):
        from django.core.cache import cache
        from api.views.transcript import DAILY_LIMIT
        cache.set('transcript_ratelimit:127.0.0.1', DAILY_LIMIT, timeout=60)
        response = self.client.post('/api/transcript/upload/', {'file': self._pdf()}, format='multipart')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['X-RateLimit-Remaining'], '0')
        self.assertIn(str(DAILY_LIMIT), response.data['error'])


# ─────────────────────────────────────────────────────────────────
# 6. Articulation helpers
# ─────────────────────────────────────────────────────────────────
class CountRowsTests(TestCase):

    def _group(self, logic, option_sizes, select_n=None):
        return {
            'group_logic': logic,
            'select_n': select_n,
            'options': [{'rows': [{}] * n} for n in option_sizes],
        }

    def test_flat_legacy_rows(self):
        from api.services.articulation import count_rows
        self.assertEqual(count_rows({'sections': [{'rows': [{}, {}, {}]}]}), 3)

    def test_complete_all_sums_rows(self):
        from api.services.articulation import count_rows
        data = {'sections': [{'groups': [self._group('COMPLETE_ALL', [2]), self._group('COMPLETE_ALL', [1])]}]}
        self.assertEqual(count_rows(data), 3)

    def test_select_one_counts_largest_pathway_once(self):
        from api.services.articulation import count_rows
        data = {'sections': [{'groups': [self._group('SELECT_ONE', [2, 4, 3])]}]}
        self.assertEqual(count_rows(data), 4)

    def test_select_n_counts_n_not_pool_size(self):
        from api.services.articulation import count_rows
        data = {'sections': [{'groups': [self._group('SELECT_N', [3], select_n=1)]}]}
        self.assertEqual(count_rows(data), 1)


class ArticulationFailedViewTests(TestCase):

    def setUp(self):
        import json, tempfile
        from pathlib import Path
        from api.services import articulation
        self.client = APIClient()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / 'sbcc' / 'ucb' / '2024-25').mkdir(parents=True)
        (root / 'sbcc' / 'ucb' / '2024-25' / 'physics_b_a.json').write_text('{}')
        (root / 'failed_scrapes.json').write_text(json.dumps([
            {'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2024-25', 'major': 'Physics, B.A.'},
            {'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2024-25', 'major': 'Celtic Studies, B.A.'},
            {'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2024-25', 'major': 'Celtic Studies, B.A.'},
            {'sending_code': 'SBCC', 'receiving_code': 'UCLA', 'academic_year': '2024-25', 'major': 'Art, B.A.'},
        ]))
        self.patches = [
            patch.object(articulation, 'ARTICULATION_DIR', root),
            patch.object(articulation, 'FAILED_SCRAPES_FILE', root / 'failed_scrapes.json'),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_hides_failures_that_were_later_scraped_and_dedupes(self):
        response = self.client.get('/api/articulation/sbcc/ucb/failed/')
        self.assertEqual([e['major'] for e in response.data], ['Celtic Studies, B.A.'])

    def test_scopes_to_requested_pair(self):
        response = self.client.get('/api/articulation/sbcc/ucla/failed/')
        self.assertEqual([e['major'] for e in response.data], ['Art, B.A.'])


class ArticulationPathSafetyTests(TestCase):

    def setUp(self):
        self.client = APIClient()

    def test_dot_dot_codes_are_rejected(self):
        self.assertEqual(self.client.get('/api/articulation/../campuses/').data, [])
        self.assertEqual(self.client.get('/api/articulation/../csv.exports/majors/').data, [])
        self.assertEqual(self.client.get('/api/articulation/../csv.exports/failed/').data, [])
        response = self.client.get('/api/articulation/../csv.exports/x/')
        self.assertEqual(response.status_code, 404)
        self.assertIn('error', response.data)

    def test_articulation_dir_rejects_non_slug_codes(self):
        from api.services.articulation import articulation_dir
        for bad in ('..', 'a/b', 'a b', '.hidden', ''):
            self.assertIsNone(articulation_dir(bad), bad)


class HealthViewTests(TestCase):

    def test_health_ok(self):
        response = APIClient().get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'status': 'ok'})


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


class ErrorShapeTests(TestCase):

    def test_drf_exceptions_render_as_error_key(self):
        from rest_framework.exceptions import NotFound, Throttled
        from api.errors import api_exception_handler
        self.assertEqual(api_exception_handler(NotFound('gone'), {}).data, {'error': 'gone'})
        response = api_exception_handler(Throttled(wait=7), {})
        self.assertEqual(response.status_code, 429)
        self.assertIn('error', response.data)
        self.assertEqual(response['Retry-After'], '7')

    def test_unknown_route_method_uses_error_key(self):
        response = APIClient().post('/api/health/')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(list(response.data), ['error'])


class SchemaTests(TestCase):

    def test_openapi_schema_lists_every_route(self):
        response = APIClient().get('/api/schema/?format=json')
        self.assertEqual(response.status_code, 200)
        paths = set(response.json()['paths'])
        for expected in ('/api/health/', '/api/majors/grouped/', '/api/stats/general/',
                         '/api/stats/by-major/{major}/', '/api/articulation/colleges/',
                         '/api/articulation/{cc_code}/{uc_code}/{major_slug}/', '/api/transcript/upload/'):
            self.assertIn(expected, paths)
