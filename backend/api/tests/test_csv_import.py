
from django.test import TestCase


class CsvImportHelperTests(TestCase):

    def test_value_parsers(self):
        from decimal import Decimal

        from api.services.csv_import import parse_gpa_range, parse_int, parse_rate
        self.assertEqual(parse_gpa_range('3.64 - 3.93'), (Decimal('3.64'), Decimal('3.93')))
        self.assertEqual(parse_gpa_range('Masked'), (None, None))
        self.assertEqual(parse_gpa_range(''), (None, None))
        self.assertEqual(parse_rate('52%'), 52)
        self.assertIsNone(parse_rate(''))
        self.assertIsNone(parse_rate(None))
        self.assertEqual(parse_int('1,234'), 1234)
        self.assertEqual(parse_int(None), 0)

    def test_read_rows_handles_utf16_tab_and_utf8_comma(self):
        import tempfile
        from pathlib import Path

        from api.services.csv_import import read_rows
        with tempfile.TemporaryDirectory() as tmp:
            utf8 = Path(tmp) / 'a.csv'
            utf8.write_text('Campus ,Applicants\nUCB, 10 \n', encoding='utf-8')
            utf16 = Path(tmp) / 'b.csv'
            utf16.write_text('Campus\tApplicants\nUCLA\t20\n', encoding='utf-16')
            self.assertEqual(list(read_rows(utf8)), [{'Campus': 'UCB', 'Applicants': '10'}])
            self.assertEqual(list(read_rows(utf16)), [{'Campus': 'UCLA', 'Applicants': '20'}])

    def test_upsert_reports_inserted_then_updated_and_dedupes(self):
        from api.models import CampusStats
        from api.services.csv_import import upsert
        fields = ['applicants', 'admits', 'enrolls']
        rows = [CampusStats(campus='UCB', year=2024, applicants=1, admits=1, enrolls=1),
                CampusStats(campus='UCB', year=2024, applicants=5, admits=2, enrolls=1)]
        self.assertEqual(upsert(CampusStats, rows, ['campus', 'year'], fields), (1, 0))
        self.assertEqual(CampusStats.objects.get(campus='UCB', year=2024).applicants, 5)
        rows = [CampusStats(campus='UCB', year=2024, applicants=9, admits=2, enrolls=1)]
        self.assertEqual(upsert(CampusStats, rows, ['campus', 'year'], fields), (0, 1))
        self.assertEqual(CampusStats.objects.get(campus='UCB', year=2024).applicants, 9)

    def test_malformed_values_degrade_to_none_or_zero(self):
        from api.services.csv_import import parse_gpa_range, parse_int, parse_rate
        self.assertEqual(parse_gpa_range('3.5'), (None, None))
        self.assertEqual(parse_gpa_range('abc - def'), (None, None))
        self.assertIsNone(parse_rate('n/a%'))
        self.assertEqual(parse_int('abc'), 0)
