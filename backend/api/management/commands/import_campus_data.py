import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import CampusStats
from api.services.csv_import import (
    first_present,
    parse_gpa_range,
    parse_int,
    parse_rate,
    read_rows,
    upsert,
)

UNIQUE_FIELDS = ['campus', 'year']
UPDATE_FIELDS = [
    'applicants', 'admits', 'enrolls',
    'admit_gpa_min', 'admit_gpa_max', 'enroll_gpa_min', 'enroll_gpa_max',
    'admit_rate', 'yield_rate',
]
FILENAME_RE = re.compile(r'^campus-(\d{4})\.csv$')


class Command(BaseCommand):
    help = 'Import campus-level stats from data/csv.exports/campusdata/campus-<year>.csv'

    def add_arguments(self, parser):
        default_dir = settings.BASE_DIR.parent / 'data' / 'csv.exports' / 'campusdata'
        parser.add_argument('--data-dir', default=str(default_dir))

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        csv_files = sorted(data_dir.glob('*.csv')) if data_dir.is_dir() else []
        if not csv_files:
            self.stderr.write(self.style.ERROR(f'No CSV files found in {data_dir}'))
            return

        self.stdout.write(f'Found {len(csv_files)} CSV files in {data_dir}')
        total_inserted = total_updated = 0
        for csv_file in csv_files:
            match = FILENAME_RE.match(csv_file.name)
            if not match:
                self.stderr.write(self.style.WARNING(f'Skipping {csv_file.name}: could not parse year'))
                continue
            rows = self.parse_csv(csv_file, int(match.group(1)))
            inserted, updated = upsert(CampusStats, rows, UNIQUE_FIELDS, UPDATE_FIELDS)
            total_inserted += inserted
            total_updated += updated
            self.stdout.write(f'  {csv_file.name}: {inserted} inserted, {updated} updated')

        self.stdout.write(self.style.SUCCESS(f'Done. {total_inserted} inserted, {total_updated} updated.'))

    def parse_csv(self, filepath, year):
        rows = []
        for row in read_rows(filepath):
            campus = row.get('Campus', '')
            if not campus:
                continue
            admit_gpa_min, admit_gpa_max = parse_gpa_range(row.get('Admit GPA range', ''))
            enroll_gpa_min, enroll_gpa_max = parse_gpa_range(
                first_present(row, 'Enroll GPA range', 'Enrollee GPA range')
            )
            rows.append(CampusStats(
                campus=campus,
                year=year,
                applicants=parse_int(row.get('Applicants')),
                admits=parse_int(row.get('Admits')),
                enrolls=parse_int(first_present(row, 'Enrolls', 'Enrollees')),
                admit_gpa_min=admit_gpa_min,
                admit_gpa_max=admit_gpa_max,
                enroll_gpa_min=enroll_gpa_min,
                enroll_gpa_max=enroll_gpa_max,
                admit_rate=parse_rate(row.get('Admit rate')),
                yield_rate=parse_rate(row.get('Yield rate')),
            ))
        return rows
