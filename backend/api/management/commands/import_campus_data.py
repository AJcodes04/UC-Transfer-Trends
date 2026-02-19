import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand

from api.models import CampusStats


class Command(BaseCommand):
    # Import campus-level stats from CSV files in data/csv.exports/campusdata

    def add_arguments(self, parser):
        default_dir = str(Path(__file__).resolve().parents[4] / 'data' / 'csv.exports' / 'campusdata')
        parser.add_argument('--data-dir', default=default_dir)

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
            year = self.parse_year(csv_file.name)
            if year is None:
                self.stderr.write(self.style.WARNING(f'Skipping {csv_file.name}: could not parse year'))
                continue

            rows = self.parse_csv(csv_file, year)
            created = CampusStats.objects.bulk_create(rows, ignore_conflicts=True)
            count = len(created)
            total_created += count
            self.stdout.write(f'  {csv_file.name}: {count} rows imported')

        self.stdout.write(self.style.SUCCESS(f'Done. {total_created} total rows imported.'))

    def parse_year(self, filename):
        # Expected format: campus-2024.csv
        match = re.match(r'^campus-(\d{4})\.csv$', filename)
        if not match:
            return None
        return int(match.group(1))

    def parse_csv(self, filepath, year):
        rows = []
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            reader.fieldnames = [name.strip() for name in reader.fieldnames]

            for row in reader:
                row = {k: v.strip() if v else '' for k, v in row.items() if k}

                campus = row.get('Campus', '')
                if not campus:
                    continue

                admit_gpa_min, admit_gpa_max = self.parse_gpa_range(row.get('Admit GPA range', ''))
                enroll_gpa_min, enroll_gpa_max = self.parse_gpa_range(
                    row.get('Enroll GPA range') or row.get('Enrollee GPA range', '')
                )

                rows.append(CampusStats(
                    campus=campus,
                    year=year,
                    applicants=self.parse_int(row.get('Applicants', '0')),
                    admits=self.parse_int(row.get('Admits', '0')),
                    enrolls=self.parse_int(row.get('Enrolls') or row.get('Enrollees', '0')),
                    admit_gpa_min=admit_gpa_min,
                    admit_gpa_max=admit_gpa_max,
                    enroll_gpa_min=enroll_gpa_min,
                    enroll_gpa_max=enroll_gpa_max,
                    admit_rate=self.parse_rate(row.get('Admit rate', '')),
                    yield_rate=self.parse_rate(row.get('Yield rate', '')),
                ))
        return rows

    def parse_gpa_range(self, value):
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
