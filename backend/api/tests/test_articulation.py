from unittest import skipUnless
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from api.constants.institutions import CC_NAMES, UC_NAMES
from api.services import articulation
from api.services.articulation import (
    agreement_files,
    articulation_dir,
    count_rows,
    list_campuses,
    list_colleges,
    list_failed,
    list_majors,
    load_agreement,
    slugify,
)
from api.tests.factories import ArticulationDirTestCase, agreement

ALL_UCS = sorted(UC_NAMES)


class CountRowsTests(TestCase):

    def _group(self, logic, option_sizes, select_n=None):
        return {
            'group_logic': logic,
            'select_n': select_n,
            'options': [{'rows': [{}] * n} for n in option_sizes],
        }

    def test_flat_legacy_rows(self):
        self.assertEqual(count_rows({'sections': [{'rows': [{}, {}, {}]}]}), 3)

    def test_complete_all_sums_rows(self):
        data = {'sections': [{'groups': [self._group('COMPLETE_ALL', [2]), self._group('COMPLETE_ALL', [1])]}]}
        self.assertEqual(count_rows(data), 3)

    def test_select_one_counts_largest_pathway_once(self):
        data = {'sections': [{'groups': [self._group('SELECT_ONE', [2, 4, 3])]}]}
        self.assertEqual(count_rows(data), 4)

    def test_select_n_counts_n_not_pool_size(self):
        data = {'sections': [{'groups': [self._group('SELECT_N', [3], select_n=1)]}]}
        self.assertEqual(count_rows(data), 1)

    def test_empty_and_missing_sections(self):
        self.assertEqual(count_rows({}), 0)
        self.assertEqual(count_rows({'sections': [{'groups': [], 'rows': []}]}), 0)


class SlugifyTests(TestCase):

    def test_matches_scraper_filenames(self):
        cases = {
            'Computer Science, B.A.': 'computer_science_b_a',
            'Asian Religions/B.A.': 'asian_religions_b_a',
            'Chicana/o Studies, B.A.': 'chicana_o_studies_b_a',
            'Art & Design: Games, B.A.': 'art_design_games_b_a',
            '  Physics, B.S.  ': 'physics_b_s',
        }
        for name, slug in cases.items():
            self.assertEqual(slugify(name), slug, name)


class ArticulationDirTests(ArticulationDirTestCase):

    def test_rejects_non_slug_codes(self):
        (self.root / 'sbcc').mkdir()
        for bad in ('..', 'a/b', 'a b', '.hidden', '', 'SBCC/..'):
            self.assertIsNone(articulation_dir(bad), bad)

    def test_lowercases_and_requires_existing_dir(self):
        (self.root / 'sbcc' / 'ucb').mkdir(parents=True)
        self.assertEqual(articulation_dir('SBCC', 'UCB'), self.root / 'sbcc' / 'ucb')
        self.assertIsNone(articulation_dir('sbcc', 'ucla'))


class AgreementFilesTests(ArticulationDirTestCase):

    def test_newest_year_wins_per_slug_and_years_are_merged(self):
        old = self.write('sbcc', 'ucb', '2024-25', 'physics_b_a', agreement(year='2024-25'))
        self.write('sbcc', 'ucb', '2024-25', 'history_b_a', agreement('History, B.A.', '2024-25'))
        new = self.write('sbcc', 'ucb', '2025-26', 'physics_b_a', agreement(year='2025-26'))
        files = agreement_files('sbcc', 'ucb')
        self.assertEqual(set(files), {'physics_b_a', 'history_b_a'})
        self.assertEqual(files['physics_b_a'], new)
        self.assertNotEqual(files['physics_b_a'], old)

    def test_unknown_pair_is_empty(self):
        self.assertEqual(agreement_files('sbcc', 'ucb'), {})

    def test_list_majors_reads_name_year_and_row_count_and_skips_malformed(self):
        self.write('sbcc', 'ucb', '2024-25', 'physics_b_a', agreement('Physics, B.A.', '2024-25', rows=3))
        self.write('sbcc', 'ucb', '2025-26', 'history_b_a', agreement('History, B.A.', '2025-26', rows=2))
        self.write('sbcc', 'ucb', '2025-26', 'broken', text='{not json')
        with self.assertLogs('api.services.articulation', level='WARNING') as logs:
            majors = list_majors('sbcc', 'ucb')
        self.assertEqual(majors, [
            {'slug': 'history_b_a', 'name': 'History, B.A.', 'academic_year': '2025-26', 'row_count': 2},
            {'slug': 'physics_b_a', 'name': 'Physics, B.A.', 'academic_year': '2024-25', 'row_count': 3},
        ])
        self.assertIn('broken.json', logs.output[0])

    def test_list_majors_falls_back_to_slug_and_folder_year(self):
        self.write('sbcc', 'ucb', '2024-25', 'mystery', data={'sections': []})
        (major,) = list_majors('sbcc', 'ucb')
        self.assertEqual((major['name'], major['academic_year'], major['row_count']), ('mystery', '2024-25', 0))

    def test_load_agreement(self):
        self.write('sbcc', 'ucb', '2024-25', 'physics_b_a', agreement('Physics, B.A.'))
        self.assertEqual(load_agreement('sbcc', 'ucb', 'physics_b_a')['major'], 'Physics, B.A.')
        self.assertIsNone(load_agreement('sbcc', 'ucb', 'nope'))
        self.assertIsNone(load_agreement('sbcc', 'ucla', 'physics_b_a'))


class ListCollegesAndCampusesTests(ArticulationDirTestCase):

    def _college(self, code, ucs):
        for uc in ucs:
            (self.root / code / uc).mkdir(parents=True)

    def test_only_fully_scraped_colleges_are_listed(self):
        self._college('sbcc', ALL_UCS)
        self._college('arc', ALL_UCS[:-1])
        self._college('zzz', ALL_UCS)
        (self.root / '_debug').mkdir()
        (self.root / 'stray.json').write_text('{}')
        self.assertEqual(list_colleges(), [
            {'code': 'sbcc', 'name': CC_NAMES['sbcc']},
            {'code': 'zzz', 'name': 'ZZZ'},
        ])

    def test_missing_root_is_empty(self):
        self._tmp.cleanup()
        self.assertEqual(list_colleges(), [])
        self._tmp = type(self._tmp)()

    def test_list_campuses_sorted_with_names(self):
        self._college('sbcc', ['ucsb', 'ucb'])
        (self.root / 'sbcc' / 'readme.txt').write_text('x')
        self.assertEqual(list_campuses('SBCC'), [
            {'code': 'ucb', 'name': UC_NAMES['ucb']},
            {'code': 'ucsb', 'name': UC_NAMES['ucsb']},
        ])
        self.assertEqual(list_campuses('nope'), [])


class ListFailedTests(ArticulationDirTestCase):

    def setUp(self):
        super().setUp()
        self.write('sbcc', 'ucb', '2024-25', 'physics_b_a')
        self.write_failed([
            {'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2024-25', 'major': 'Physics, B.A.'},
            {'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2024-25', 'major': 'Celtic Studies, B.A.'},
            {'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2024-25', 'major': 'Celtic Studies, B.A.'},
            {'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2025-26', 'major': 'Celtic Studies, B.A.'},
            {'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2024-25', 'major': 'Art, B.A.'},
            {'sending_code': 'SBCC', 'receiving_code': 'UCLA', 'academic_year': '2024-25', 'major': 'Dance, B.A.'},
        ])

    def test_hides_scraped_dedupes_per_year_and_sorts(self):
        self.assertEqual(list_failed('sbcc', 'ucb'), [
            {'major': 'Art, B.A.', 'academic_year': '2024-25'},
            {'major': 'Celtic Studies, B.A.', 'academic_year': '2024-25'},
            {'major': 'Celtic Studies, B.A.', 'academic_year': '2025-26'},
        ])

    def test_scopes_to_pair(self):
        self.assertEqual([e['major'] for e in list_failed('sbcc', 'ucla')], ['Dance, B.A.'])

    def test_missing_or_malformed_log_is_empty(self):
        (self.root / 'failed_scrapes.json').unlink()
        self.assertEqual(list_failed('sbcc', 'ucb'), [])
        (self.root / 'failed_scrapes.json').write_text('[broken')
        with self.assertLogs('api.services.articulation', level='WARNING'):
            self.assertEqual(list_failed('sbcc', 'ucb'), [])


class ArticulationEndpointTests(ArticulationDirTestCase):
    """Walk the whole flow through the URLs: colleges -> campuses -> majors -> detail."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        for uc in ALL_UCS:
            (self.root / 'sbcc' / uc).mkdir(parents=True)
        self.write('sbcc', 'ucb', '2024-25', 'physics_b_a', agreement('Physics, B.A.', rows=2))
        self.write('sbcc', 'ucb', '2024-25', 'failed', agreement('Failed Studies, B.A.'))
        self.write_failed([{'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2024-25', 'major': 'Art, B.A.'}])

    def test_full_navigation_flow(self):
        colleges = self.client.get('/api/articulation/colleges/').data
        self.assertEqual([c['code'] for c in colleges], ['sbcc'])
        campuses = self.client.get(f"/api/articulation/{colleges[0]['code']}/campuses/").data
        self.assertEqual([c['code'] for c in campuses], ALL_UCS)
        majors = self.client.get('/api/articulation/sbcc/ucb/majors/').data
        self.assertEqual([m['slug'] for m in majors], ['failed', 'physics_b_a'])
        detail = self.client.get('/api/articulation/sbcc/ucb/physics_b_a/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['major'], 'Physics, B.A.')

    def test_failed_route_wins_over_a_major_slug_named_failed(self):
        response = self.client.get('/api/articulation/sbcc/ucb/failed/')
        self.assertEqual(response.data, [{'major': 'Art, B.A.', 'academic_year': '2024-25'}])

    def test_unknown_major_is_404_with_error_key(self):
        response = self.client.get('/api/articulation/sbcc/ucb/nope/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(list(response.data), ['error'])

    def test_dot_dot_codes_are_rejected(self):
        self.assertEqual(self.client.get('/api/articulation/../campuses/').data, [])
        self.assertEqual(self.client.get('/api/articulation/../x/majors/').data, [])
        self.assertEqual(self.client.get('/api/articulation/../x/failed/').data, [])
        self.assertEqual(self.client.get('/api/articulation/../x/y/').status_code, 404)


@skipUnless(articulation.ARTICULATION_DIR.is_dir(), 'scraped articulation data not present')
class RealDataSmokeTests(TestCase):
    """Cheap checks against the committed data set; directory listings only."""

    def test_every_scraped_college_has_a_display_name(self):
        codes = {c['code'] for c in list_colleges()}
        self.assertGreater(len(codes), 50)
        self.assertEqual(sorted(codes - set(CC_NAMES)), [])

    def test_every_campus_folder_is_a_known_uc(self):
        for cc in list_colleges():
            for campus in list_campuses(cc['code']):
                self.assertIn(campus['code'], UC_NAMES, cc['code'])


class ListingCacheTests(ArticulationDirTestCase):

    def test_majors_list_is_cached_until_the_folder_changes(self):
        self.write('sbcc', 'ucb', '2024-25', 'physics_b_a', agreement('Physics, B.A.'))
        self.assertEqual([m['slug'] for m in list_majors('sbcc', 'ucb')], ['physics_b_a'])
        with patch('api.services.articulation._build_majors') as build:
            list_majors('sbcc', 'ucb')
            build.assert_not_called()
        self.write('sbcc', 'ucb', '2025-26', 'history_b_a', agreement('History, B.A.', '2025-26'))
        self.assertEqual([m['slug'] for m in list_majors('sbcc', 'ucb')], ['history_b_a', 'physics_b_a'])

    def test_colleges_list_refreshes_when_a_campus_folder_appears(self):
        for uc in ALL_UCS[:-1]:
            (self.root / 'sbcc' / uc).mkdir(parents=True)
        self.assertEqual(list_colleges(), [])
        (self.root / 'sbcc' / ALL_UCS[-1]).mkdir()
        self.assertEqual([c['code'] for c in list_colleges()], ['sbcc'])

    def test_failed_list_refreshes_when_the_log_is_rewritten(self):
        self.write_failed([{'sending_code': 'SBCC', 'receiving_code': 'UCB', 'academic_year': '2024-25', 'major': 'Art, B.A.'}])
        self.assertEqual([e['major'] for e in list_failed('sbcc', 'ucb')], ['Art, B.A.'])
        self.write_failed([])
        self.assertEqual(list_failed('sbcc', 'ucb'), [])
