import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from api.models import CampusStats, TransferData
from api.services import articulation


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


def make_campus_stats(**kwargs):
    defaults = {
        'campus': 'UCB',
        'year': 2023,
        'applicants': 1000,
        'admits': 500,
        'enrolls': 250,
        'admit_rate': 50,
        'yield_rate': 50,
    }
    defaults.update(kwargs)
    return CampusStats.objects.create(**defaults)


def agreement(major='Physics, B.A.', year='2024-25', rows=1):
    """Minimal agreement JSON in the scraper's grouped format with `rows` COMPLETE_ALL rows."""
    return {
        'major': major,
        'academic_year': year,
        'sections': [{
            'section_title': 'PREPARATION FOR THE MAJOR',
            'groups': [{
                'group_logic': 'COMPLETE_ALL',
                'select_n': None,
                'options': [{'rows': [{} for _ in range(rows)]}],
            }],
            'rows': [],
        }],
    }


class ArticulationDirTestCase(TestCase):
    """Points the articulation service at a temp directory; write files with self.write()."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._patches = [
            patch.object(articulation, 'ARTICULATION_DIR', self.root),
            patch.object(articulation, 'FAILED_SCRAPES_FILE', self.root / 'failed_scrapes.json'),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()
        super().tearDown()

    def write(self, cc, uc, year, slug, data=None, text=None):
        folder = self.root / cc / uc / year
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'{slug}.json'
        path.write_text(text if text is not None else json.dumps(data if data is not None else agreement()))
        return path

    def write_failed(self, entries):
        (self.root / 'failed_scrapes.json').write_text(json.dumps(entries))
