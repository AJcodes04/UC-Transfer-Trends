from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient


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
        import json
        import tempfile
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
