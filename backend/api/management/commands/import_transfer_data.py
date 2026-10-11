import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import TransferData
from api.services.csv_import import (
    first_present, parse_gpa_range, parse_int, parse_rate, read_rows, upsert,
)


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


# Maps (campus, shortened_name) -> canonical name so 2025+ data lines up
# with earlier years that used "College Of …" / "School Of …" prefixes.
COLLEGE_SCHOOL_ALIASES = {
    # UCB
    ('UCB', 'Business Administration'):      'School Of Business administration',
    ('UCB', 'Chemistry'):                    'College Of Chemistry',
    ('UCB', 'Engineering'):                  'College Of Engineering',
    ('UCB', 'Environmental Design'):         'College Of Environmental design',
    ('UCB', 'Letters & Science'):            'College Of Letters & science',
    ('UCB', 'Natural Resources'):            'College Of Natural resources',
    # UCD
    ('UCD', 'Agric & Environ Sciences'):     'College Of Agric & environ sciences',
    ('UCD', 'Biological Sciences'):          'College Of Biological sciences',
    ('UCD', 'Engineering'):                  'College Of Engineering',
    ('UCD', 'Letters & Science'):            'College Of Letters & science',
    # UCI
    ('UCI', 'Education'):                    'School Of Education',
    ('UCI', 'Engineering'):                  'School Of Engineering',
    ('UCI', 'Humanities'):                   'School Of Humanities',
    ('UCI', 'Nursing'):                      'School Of Nursing',
    ('UCI', 'Pharmacy & Pharm Sciences'):    'School Of Pharmacy & pharm sciences',
    ('UCI', 'Physical Sciences'):            'School Of Physical sciences',
    ('UCI', 'Population and Public Health'): 'School Of Public health',
    ('UCI', 'Social Sciences'):              'School Of Social sciences',
    ('UCI', 'The Arts'):                     'School Of The arts',
    # UCLA
    ('UCLA', 'Engineering & Applied Sci'):   'School Of Engineering & applied sci',
    ('UCLA', 'Letters & Science'):           'College Of Letters & science',
    ('UCLA', 'Music'):                       'School Of Music',
    ('UCLA', 'Nursing'):                     'School Of Nursing',
    ('UCLA', 'The Arts & Architecture'):     'School Of The arts & architecture',
    ('UCLA', 'Theater, Film and Television'): 'School Of Theater, film and television',
    # UCR
    ('UCR', 'Education'):                    'School Of Education',
    ('UCR', 'Engineering'):                  'College Of Engineering',
    ('UCR', 'Humanities & Social Sci'):      'College Of Humanities & social sci',
    ('UCR', 'Natural & Agricultural Sci'):   'College Of Natural & agricultural sci',
    ('UCR', 'Public Policy'):                'School Of Public policy',
    # UCSB
    ('UCSB', 'Engineering'):                 'College Of Engineering',
    ('UCSB', 'Letters & Science'):           'College Of Letters & science',
}


UNIQUE_FIELDS = ['university', 'year', 'major_name', 'college_school']
UPDATE_FIELDS = [
    'broad_discipline', 'applicants', 'admits', 'enrolls',
    'admit_gpa_min', 'admit_gpa_max', 'enroll_gpa_min', 'enroll_gpa_max',
    'admit_rate', 'yield_rate',
]
FILENAME_RE = re.compile(r'^([A-Z]+)-(\d{4})\.csv$')


class Command(BaseCommand):
    help = 'Import per-major transfer stats from data/csv.exports/majordata/<CAMPUS>-<year>.csv'

    def add_arguments(self, parser):
        default_dir = settings.BASE_DIR.parent / 'data' / 'csv.exports' / 'majordata'
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
                self.stderr.write(self.style.WARNING(f'Skipping {csv_file.name}: could not parse filename'))
                continue
            rows = self.parse_csv(csv_file, match.group(1), int(match.group(2)))
            inserted, updated = upsert(TransferData, rows, UNIQUE_FIELDS, UPDATE_FIELDS)
            total_inserted += inserted
            total_updated += updated
            self.stdout.write(f'  {csv_file.name}: {inserted} inserted, {updated} updated')

        self.stdout.write(self.style.SUCCESS(f'Done. {total_inserted} inserted, {total_updated} updated.'))

    def parse_csv(self, filepath, campus, year):
        rows = []
        for row in read_rows(filepath):
            major_name = title_case_major(row.get('Major name', ''))
            # UC exports include a placeholder row for unmatched college/major codes.
            if not major_name or major_name.lower() == 'invalid ccm combination':
                continue
            admit_gpa_min, admit_gpa_max = parse_gpa_range(row.get('Admit GPA range', ''))
            enroll_gpa_min, enroll_gpa_max = parse_gpa_range(
                first_present(row, 'Enroll GPA range', 'Enrollee GPA range')
            )
            college_school = row.get('College/School', '')
            rows.append(TransferData(
                university=campus,
                year=year,
                broad_discipline=row.get('Broad discipline', ''),
                college_school=COLLEGE_SCHOOL_ALIASES.get((campus, college_school), college_school),
                major_name=major_name,
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
