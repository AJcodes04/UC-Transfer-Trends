import csv
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand

from api.models import TransferData


# Words that stay lowercase in title case (unless they're the first word)
SMALL_WORDS = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in', 'nor',
               'of', 'on', 'or', 'so', 'the', 'to', 'up', 'yet', 'with'}

# Words that should always be uppercase
UPPERCASE_WORDS = {'bs', 'ba', 'ii', 'iii', 'iv'}


def _capitalize_word(word):
    """Capitalize a single word, handling sub-delimiters like / - ("""
    if not word:
        return word
    if word.lower() in UPPERCASE_WORDS:
        return word.upper()
    # Split on delimiters but keep them: "Pre-economics" -> ["Pre", "-", "economics"]
    parts = re.split(r'([/\-(])', word)
    result = []
    for part in parts:
        if not part or part in '/-(':
            result.append(part)
        else:
            result.append(part[0].upper() + part[1:])
    return ''.join(result)


def title_case_major(name):
    """Title-case a major name while keeping small words lowercase
    and preserving special patterns like 'Pre-', 'BS', '&'."""
    if not name:
        return name
    words = name.split()
    result = []
    for i, word in enumerate(words):
        if i == 0:
            result.append(_capitalize_word(word))
        elif word.lower() in SMALL_WORDS:
            result.append(word.lower())
        else:
            result.append(_capitalize_word(word))
    return ' '.join(result)


class Command(BaseCommand):
    # Import transfer data from CSV files in the data/csv.exports directory

    def add_arguments(self, parser):
        default_dir = str(Path(__file__).resolve().parents[4] / 'data' / 'csv.exports' / 'majordata')
        parser.add_argument(
            '--data-dir',
            default=default_dir,
        )

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])

        if not data_dir.exists():
            self.stderr.write(self.style.ERROR(f'Data directory not found: {data_dir}'))
            return

        csv_files = sorted(data_dir.glob('*.csv'))
        if not csv_files:
            self.stderr.write(self.style.ERROR(f'No CSV files found in {data_dir}'))
            return

        self.stdout.write(f'Found {len(csv_files)} CSV files in {data_dir}')
        total_created = 0

        for csv_file in csv_files:
            campus, year = self.parse_filename(csv_file.name)
            if campus is None:
                self.stderr.write(self.style.WARNING(f'Skipping {csv_file.name}: could not parse filename'))
                continue

            rows = self.parse_csv(csv_file, campus, year)
            created = TransferData.objects.bulk_create(rows, ignore_conflicts=True)
            count = len(created)
            total_created += count
            self.stdout.write(f'  {csv_file.name}: {count} rows imported')

        self.stdout.write(self.style.SUCCESS(f'Done. {total_created} total rows imported.'))

    def parse_filename(self, filename):
        match = re.match(r'^([A-Z]+)-(\d{4})\.csv$', filename)
        if not match:
            return None, None
        return match.group(1), int(match.group(2))

    def parse_csv(self, filepath, campus, year):
        rows = []
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Strip whitespace from header names
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

            for row in reader:
                # Strip values and skip empty rows
                row = {k: v.strip() if v else '' for k, v in row.items() if k}

                major_name = title_case_major(row.get('Major name', ''))
                if not major_name:
                    continue

                admit_gpa_min, admit_gpa_max = self.parse_gpa_range(row.get('Admit GPA range', ''))
                enroll_gpa_min, enroll_gpa_max = self.parse_gpa_range(row.get('Enroll GPA range', ''))

                rows.append(TransferData(
                    university=campus,
                    year=year,
                    broad_discipline=row.get('Broad discipline', ''),
                    college_school=row.get('College/School', ''),
                    major_name=major_name,
                    applicants=self.parse_int(row.get('Applicants', '0')),
                    admits=self.parse_int(row.get('Admits', '0')),
                    enrolls=self.parse_int(row.get('Enrolls', '0')),
                    admit_gpa_min=admit_gpa_min,
                    admit_gpa_max=admit_gpa_max,
                    enroll_gpa_min=enroll_gpa_min,
                    enroll_gpa_max=enroll_gpa_max,
                    admit_rate=self.parse_rate(row.get('Admit rate', '')),
                    yield_rate=self.parse_rate(row.get('Yield rate', '')),
                ))
        return rows

    def parse_gpa_range(self, value):
        #Parse "3.64 - 3.93" -> (Decimal('3.64'), Decimal('3.93'))
        if not value or value.lower() == 'masked':
            return None, None
        parts = value.split('-')
        if len(parts) != 2:
            return None, None
        try:
            return Decimal(parts[0].strip()), Decimal(parts[1].strip())
        except (InvalidOperation, ValueError):
            return None, None

    def parse_rate(self, value):
        # cleaning % sign then converting to int
        if not value:
            return None
        value = value.replace('%', '').strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def parse_int(self, value):
        if not value:
            return 0
        try:
            return int(value.replace(',', ''))
        except ValueError:
            return 0
