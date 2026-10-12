import io
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from api.management.commands.import_transfer_data import title_case_major
from api.models import CampusStats, TransferData

MAJOR_HEADER = ('Broad discipline,College/School ,Major name,Applicants,Admits,Enrolls,'
                'Admit GPA range,Enroll GPA range,Admit rate,Yield rate,')
MAJOR_HEADER_2025 = ('Broad discipline\tCollege/School\tMajor name\tApplicants\tAdmits\tEnrollees\t'
                     'Admit GPA range\tEnrollee GPA range\tAdmit rate\tYield rate\t')
CAMPUS_HEADER = 'Campus,Applicants,Admits,Enrolls,Admit GPA range,Enroll GPA range,Admit rate,Yield rate,'


def run(command, data_dir):
    out, err = io.StringIO(), io.StringIO()
    call_command(command, data_dir=str(data_dir), stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


class TitleCaseMajorTests(TestCase):

    def test_cases(self):
        cases = {
            'pre-economics': 'Pre-Economics',
            'Pre-economics': 'Pre-Economics',
            'engineering - electrical bs': 'Engineering - Electrical BS',
            'history of art and architecture': 'History of Art and Architecture',
            'mathematics/economics': 'Mathematics/Economics',
            'art (studio)': 'Art (Studio)',
            'molecular, cell, & developmental biology': 'Molecular, Cell, & Developmental Biology',
            'the arts': 'The Arts',
            'spanish iii': 'Spanish III',
            '': '',
        }
        for raw, expected in cases.items():
            self.assertEqual(title_case_major(raw), expected, raw)


class ImportTransferDataTests(TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        (self.dir / 'UCB-2023.csv').write_text('\n'.join([
            MAJOR_HEADER,
            'Sciences,Letters & Science ,chemistry,"1,234",400,100,3.64 - 3.93,3.70 - 3.90,32%,25%,',
            'Arts,Letters & Science,pre-history,50,10,5,Masked,Masked,20%,50%,',
            'Unknown,Not applicable,Invalid ccm combination,99,99,99,,,,,',
            ',,,,,,,,,,',
        ]), encoding='utf-8')
        (self.dir / 'UCM-2018.csv').write_text('\n'.join([
            MAJOR_HEADER_2025,
            'Sciences\tNot applicable\tBiological Sciences\t101\t45\t9\t3.24 - 3.85\t3.30 - 3.60\t45%\t20%\t',
        ]), encoding='utf-16')
        (self.dir / 'bad-name.csv').write_text(MAJOR_HEADER + '\n', encoding='utf-8')
        (self.dir / 'notes.txt').write_text('ignore me')

    def tearDown(self):
        self._tmp.cleanup()

    def test_imports_rows_with_normalization(self):
        out, err = run('import_transfer_data', self.dir)
        self.assertEqual(TransferData.objects.count(), 3)
        chem = TransferData.objects.get(major__name='Chemistry')
        self.assertEqual(chem.campus.code, 'UCB')
        self.assertEqual(chem.college_school, 'College Of Letters & science')
        self.assertEqual((chem.applicants, chem.admits, chem.enrolls), (1234, 400, 100))
        self.assertEqual((chem.admit_gpa_min, chem.enroll_gpa_max), (Decimal('3.64'), Decimal('3.90')))
        self.assertEqual((chem.admit_rate, chem.yield_rate), (32, 25))
        masked = TransferData.objects.get(major__name='Pre-History')
        self.assertIsNone(masked.admit_gpa_min)
        self.assertFalse(TransferData.objects.filter(major__name__icontains='invalid').exists())
        self.assertIn('UCB-2023.csv: 2 inserted, 0 updated', out)
        self.assertIn('Done. 3 inserted, 0 updated.', out)
        self.assertIn('Majors synced', out)
        self.assertIn('Skipping bad-name.csv', err)

    def test_reads_utf16_tab_exports_with_2025_column_names(self):
        run('import_transfer_data', self.dir)
        bio = TransferData.objects.get(campus__code='UCM', year=2018)
        self.assertEqual((bio.major.name, bio.enrolls, bio.enroll_gpa_min), ('Biological Sciences', 9, Decimal('3.30')))

    def test_rerun_updates_changed_rows_instead_of_skipping(self):
        run('import_transfer_data', self.dir)
        path = self.dir / 'UCB-2023.csv'
        path.write_text(path.read_text().replace('"1,234",400', '"1,300",450'), encoding='utf-8')
        out, _ = run('import_transfer_data', self.dir)
        chem = TransferData.objects.get(major__name='Chemistry')
        self.assertEqual((chem.applicants, chem.admits), (1300, 450))
        self.assertEqual(TransferData.objects.count(), 3)
        self.assertIn('Done. 0 inserted, 3 updated.', out)

    def test_duplicate_key_within_a_file_keeps_last_row(self):
        path = self.dir / 'UCB-2023.csv'
        path.write_text(path.read_text() + '\nSciences,Letters & Science,chemistry,7,7,7,,,7%,7%,', encoding='utf-8')
        run('import_transfer_data', self.dir)
        self.assertEqual(TransferData.objects.get(major__name='Chemistry').applicants, 7)

    def test_missing_directory_reports_error_without_raising(self):
        out, err = run('import_transfer_data', self.dir / 'nowhere')
        self.assertIn('No CSV files found', err)
        self.assertEqual(TransferData.objects.count(), 0)


class ImportCampusDataTests(TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        (self.dir / 'campus-2024.csv').write_text('\n'.join([
            CAMPUS_HEADER,
            'UCB,"20,000",5000,2500,3.70 - 3.98,3.80 - 3.99,25%,50%,',
            'UCLA,30000,7000,3500,,,23%,50%,',
            ',,,,,,,,',
        ]), encoding='utf-8')
        (self.dir / 'UCB-2024.csv').write_text(CAMPUS_HEADER + '\n', encoding='utf-8')

    def tearDown(self):
        self._tmp.cleanup()

    def test_imports_and_is_idempotent(self):
        out, err = run('import_campus_data', self.dir)
        self.assertEqual(CampusStats.objects.count(), 2)
        ucb = CampusStats.objects.get(campus__code='UCB', year=2024)
        self.assertEqual((ucb.applicants, ucb.admit_gpa_max, ucb.admit_rate), (20000, Decimal('3.98'), 25))
        self.assertIsNone(CampusStats.objects.get(campus__code='UCLA').admit_gpa_min)
        self.assertIn('Skipping UCB-2024.csv', err)
        self.assertIn('Done. 2 inserted, 0 updated.', out)
        out, _ = run('import_campus_data', self.dir)
        self.assertIn('Done. 0 inserted, 2 updated.', out)
        self.assertEqual(CampusStats.objects.count(), 2)
