import json
import logging
import re
from pathlib import Path

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import (
    Sum, Max, Min, Case, When, Value, CharField, FloatField, ExpressionWrapper,
)
from django.db.models.functions import NullIf
from django_filters import rest_framework as filters

from .models import TransferData, CampusStats
from .serializers import TransferDataSerializer

logger = logging.getLogger(__name__)

ARTICULATION_DIR = Path(__file__).resolve().parent.parent.parent / 'data' / 'articulation'
# The scraper writes every major/campus combo it could NOT fetch here. We surface
# these to users so the major list is transparent about what's missing rather than
# silently omitting agreements that assist.org failed to return.
FAILED_SCRAPES_FILE = ARTICULATION_DIR / 'failed_scrapes.json'


def _count_rows(agreement_data: dict) -> int:
    """Number of UC requirements a student must satisfy; alternatives in a choice group count once."""
    count = 0
    for section in agreement_data.get('sections', []):
        groups = section.get('groups', [])
        if not groups:
            count += len(section.get('rows', []))
            continue
        for group in groups:
            option_sizes = [len(o.get('rows', [])) for o in group.get('options', [])]
            logic = group.get('group_logic')
            if logic == 'SELECT_ONE':
                count += max(option_sizes, default=0)
            elif logic == 'SELECT_N' and group.get('select_n'):
                count += min(group['select_n'], sum(option_sizes))
            else:
                count += sum(option_sizes)
    return count


class TransferDataFilter(filters.FilterSet):
    university = filters.CharFilter(field_name='university')
    year = filters.NumberFilter(field_name='year')
    major_name = filters.CharFilter(field_name='major_name', lookup_expr='icontains')
    broad_discipline = filters.CharFilter(field_name='broad_discipline', lookup_expr='icontains')

    class Meta:
        model = TransferData
        fields = ['university', 'year', 'major_name', 'broad_discipline']


class TransferDataListView(generics.ListAPIView):
    queryset = TransferData.objects.all()
    serializer_class = TransferDataSerializer
    filterset_class = TransferDataFilter


class UniversityListView(APIView):
    def get(self, request):
        universities = (
            TransferData.objects
            .values_list('university', flat=True)
            .distinct()
            .order_by('university')
        )
        return Response(list(universities))

_SUB_MAJOR_RE = re.compile(r'^(.+?)(\s*[-/(:]|\s+with\s|\s+w/)', re.IGNORECASE)
MAJOR_ALIASES = {
    'Communication': ['Communication Studies', 'Communication Arts'],
    'African American Studies': ['African-American Studies'],
    'Astrophysics' : ['Astronomy and Astrophysics'],
    'Asian Studies': [
        'Pre-Asian Studies',
    ],
    'Applied Mathematics' : [
        'Pre-Applied Mathematics',
        'Applied and Computational Mathematics',
    ],
    'Business Economics': [
        'Pre-Business Economics',
        'Business Management - Economics',
        'Management and Business Economics',
    ],
    'Biology': [
        'Biological Sciences',
    ],
    'Biochemistry' : [
        'Chemistry - Biochemistry',
        'Biochemistry- Molecular Biology'

    ],
    'Cognitive Science': ['Cognitive Sciences'],
    'Chicano Studies': [
        'Chicana & Chicano Studies',
        'Chicana/0 Studies',
        'Chicano/Latino Studies',
        'Chicanx Latinx Studies',
        'Chicana Studies',
    ],
    'Aerospace Engineering': ['Aerospace Science and Engineering'],
    'Electrical Engineering': ['Electrical Engineering - BS', 'Engineering - Electrical'],
    'Environmental Science':[
        'Environmental Studies',
    ],
    'Civil Engineering': ['Engineering - Civil'],
    'Mechanical Engineering': ['Engineering - Mechanical'],
    'Molecular & Cell Biology': [
        'Molecular, Cell, & Developmental Biology',
        'Cell, Molecular, & Developmental Biology',
        'Molecular & Cell Biology - Pl1 - 1',
        'Molecular & Cell Biology - Pl1 - 2',
        'Molecular & Cell Biology - Pl1 - 3',
        'Molecular & Cell Biology - Pl2 - 2',
        'Molecular & Cell Biology - Pl2 - 3',
    ],
    'Architecture': [
        'Architectural Studies',
    ],
    'Chemistry':[
        'Chemical Sciences',
    ],
    'Dance': [
        'Dance & Performance Studies',
    ],
    'Film': [
        'Film & Television',
        'Film and Digital Media',
        'Film and Media Studies',
        'Film Studies',
    ],
    "Global Studies" : [
        "Pre-Global Studies",
    ],
    'Human Development' : [
        'Human Developmental Sciences',
        'Pre-Human Development',
    ],
    'History' : [
        'Pre-History',
    ],
    'Art': [
        'Art - Studio',
    ],
    'Economics' : [
        'Pre-Economics',
        'Bachelor of Science in Economics'
    ],
    'Linguistics':[
        'Applied Linguistics',
        'Applied Linguistics and Multilingualism',
    ],
    'Statistics': [
        'Pre-Statistics'
    ],
    'Political Science':[
        'Pre-Political Science',
    ],
    'Materials Science & Engineering':[
        'Materials Engineering',
        'Materials Science',
    ],
    'Marine Science' : [
        'Marine and Coastal Science',
    ],
    'Mathematics' :[
        'Pre-Mathematics'
    ],
    "Psychology" : [
        "Pre-Psychology",
    ],
    "Sociology" : [
        "Pre-Sociology",
    ],
}

# MAJOR_ALIASES is keyed canonical -> aliases, which is the wrong direction for the
# per-row lookup "what is this name's canonical form?". Invert it once at import so
# that lookup is a single hash hit instead of a scan over every canonical + alias.
ALIAS_TO_CANONICAL = {
    alias: canonical
    for canonical, aliases in MAJOR_ALIASES.items()
    for alias in aliases
}

MAJOR_ABSORPTIONS = {
    'Asian American Studies': [
        'Asian American and Asian Diaspora Studies',
    ],
    'Animal Sciences':[
        'Animal Science & Management',
        'Animal Biology',
    ],
    'Anthropology': [
        'Biological Anthropology',
    ],
    'Mathematics': [
        'Pre-Mathematics - Computer Science',
        'Pre-Mathematics for Teaching',
        'Pre-Mathematics of Computation',
        'Pre-Mathematics/Applied Science',
        'Pre-Mathematics/Economics',
        'Mathematics - Applied Science',
        'Mathematics & Science Computation',
        'Mathematics for Secondary School',
        'Mathematics Theory & Computation',
        'Mathematical Analytics and Operations Research',
        'Mathematical Sciences',
        'Applied Mathematics',
        'Mathematics Education'
    ],
    'Chemistry': [
        'Chemical Biology',
        'Biochemistry',
        'Pharmaceutical Chemistry',
        'Pharmacological Chemistry',
        'Applied Chemistry',
        'Chemical Physics',
        'Molecular Synthesis',
    ],
    'Engineering': [
        'Chemical Engineering and Materials Science and Engineering',
        'Chemical Engineering and Nuclear Engineering',
        'Mechanical Engineering and Nuclear Engineering',
        'Materials Science and Engineering and Mechanical Engineering',
        'Electrical Engineering & Computer Sciences & Materials Science and Engineering',
        'Electrical Engineering and Computer Sciences and Nuclear Engineering',
        'Energy Engineering',
        'Engineering Mathematics - Mathematics Science',
    ],
    'Biology': [
        'Molecular & Cell Biology',
        'Cell Biology',
        'Microbial Biology',
        'Molecular Environmental Biology',
        'Molecular Toxicology',
        'Integrative Biology',
        'Evolution, Ecology & Biodiversity',
        'Biochemistry & Cell Biology',
        'Genetics & Plant Biology',
        'Genetics and Genomics',
        'Global Disease Biology',
        'Human Biology',
        'Microbiology',
        'Molecular & Medical Microbiology',
        'Molecular Biology',
        'Plant Biology',
        'Pre Human Biology and Society',
        'Pre-Computational & Systems Biology',
        'Pre-Microbiology - Immunology - Molecular Genetics',
        'Pre-Psychobiology',
    ],
    'Political Science': [
        'Political Economy',
        'Public Policy',
        'History of Public Policy',
        'History of Public Policy and Law',
    ],
    'Psychology': [
        'Biopsychology',
        'Psychological Science',
        'Psychological and Brain Science',
        'Psychology and Law & Society',
        'Psychology & Social Behavior',
    ],
    'Asian Studies': [
        'Asian Studies Area I',
        'Asian Studies Area II',
        'East Asian Studies',
        'East Asian Cultures',
        'East Asian Religion, Thought, and Culture',
        'Asian Humanities',
        'Asian Languages and Linguistics',
    ],
    'Chinese': [
        'Chinese Language & Literature',
        'Chinese Studies',
    ],
    'Data Science': [
        'Pre-Data Theory',
        'Pre-Statistics and Data Science'
    ],
    'Environmental Science':[
        'Environmental Science and Management',
        'Environmental Science and Policy',
        'Environmental Earth Science',
        'Environmental Studies/Economics',
    ],
    'Japanese': [
        'Japanese Language & Literature',
        'Japanese Studies',
    ],
    'Gender & Women\'s Studies': [
        'Gender Studies',
        'Gender and Sexuality Studies',
        'Gender, Sexuality, and Women\'s Studies',
        'Feminist Studies',
    ],
    'Theater': [
        'Theater and Performance Studies',
        'Theater Arts',
        'Theatre and Dance',
        'Theatre, Film and Digital Production',
    ],
    'Ecology, Behavior & Evolution': [
        'Ecology & Evolution',
        'Ecology & Evolutionary Biology',
    ],
    'Geology': [
        'Geosciences',
        'Geophysics',
        'Earth Science',
        'Engineering Geology',
    ],
    'Music': [
        'Music Composition',
        'Music History and Industry',
        'Music Industry',
        'Music Performance',
        'Musicology',
        'Ethnomusicology',
        'Music & Culture',
    ],
    'Public Health': [
        'Public Health Policy',
        'Public Health Sciences',
        'Pre-Public Health',
        'Bachelor of Science in Public Health W/ Concentration in Community Hlth Sci',
        'Bachelor of Science in Public Health W/ Concentration in Hlth Policy and Mgmt Sc',
        'Bachelor of Science in Public Health W/ Concentration in Medicine Science',
        'Bachelor of Science in Public Health W/Con in Epidemiology',
    ],
    'Robotics': [
        'Robotics Engineering BS',
    ],
    'Urban Studies': [
        'Urban Studies & Planning',
    ],
    'Computer Science': [
        'Computer Science with Business Applications',
        'Software Engineering',
        'Linguistics & Computer Science',
        'Computer Game Science',
    ],
    'Cognitive Science': [
        'Pre-Cognitive Science',
    ],
    'Economics': [
        'Environmental Economics & Policy',
        'Global Economics',
        'Managerial Economics',
        'Quantitative Economics',
        'Economics and Accounting',
    ],
    'Physics': [
        'Applied Physics',
    ],
}


class MajorListView(APIView):
    def get(self, request):
        majors = (
            TransferData.objects
            .values_list('major_name', flat=True)
            .distinct()
            .order_by('major_name')
        )
        return Response(list(majors))


class GroupedMajorListView(APIView):
    DISCONTINUED_BEFORE = 2020
    MIN_HISTORY_YEARS = 6

    def get(self, request):
        major_agg = {
            row['major_name']: row
            for row in (
                TransferData.objects
                .values('major_name')
                .annotate(
                    total_apps=Sum('applicants'),
                    latest_year=Max('year'),
                    earliest_year=Min('year'),
                )
            )
        }
        active_majors = {
            name: row['total_apps']
            for name, row in major_agg.items()
            if row['latest_year'] >= self.DISCONTINUED_BEFORE
            or (row['latest_year'] - row['earliest_year'] + 1) >= self.MIN_HISTORY_YEARS
        }

        major_latest = {
            name: row['latest_year']
            for name, row in major_agg.items()
            if name in active_majors
        }

        for canonical, aliases in MAJOR_ALIASES.items():
            for alias in aliases:
                if alias in active_majors:
                    active_majors.setdefault(canonical, 0)
                    active_majors[canonical] += active_majors.pop(alias)
                    if alias in major_latest:
                        major_latest.setdefault(canonical, 0)
                        major_latest[canonical] = max(
                            major_latest.get(canonical, 0),
                            major_latest.pop(alias),
                        )

        all_names = set(active_majors.keys())
        major_apps = active_majors

        major_campuses = {}
        for row in (
            TransferData.objects
            .values('major_name', 'university')
            .distinct()
        ):
            name = ALIAS_TO_CANONICAL.get(row['major_name'], row['major_name'])
            if name in all_names:
                major_campuses.setdefault(name, set()).add(row['university'])

        groups = {}
        assigned = set()

        for name in sorted(all_names):
            match = _SUB_MAJOR_RE.match(name)
            if match:
                candidate_base = match.group(1).strip()
                if candidate_base in all_names and candidate_base != name:
                    if candidate_base not in groups:
                        groups[candidate_base] = []
                    groups[candidate_base].append(name)
                    assigned.add(name)
                    continue
            if name not in groups:
                groups[name] = []

        for parent, children in MAJOR_ABSORPTIONS.items():
            if parent not in all_names:
                continue
            if parent not in groups:
                groups[parent] = []
            for child in children:
                if child not in all_names:
                    continue
                if child in groups:
                    groups[parent].extend(groups.pop(child))
                else:
                    for other_base, other_related in groups.items():
                        if child in other_related:
                            other_related.remove(child)
                            break
                if child not in groups[parent]:
                    groups[parent].append(child)
                assigned.add(child)

        result = []
        for base, related in groups.items():
            result.append({
                'name': base,
                'total_applicants': major_apps.get(base, 0),
                'latest_year': major_latest.get(base, 0),
                'related': sorted(
                    [{'name': r, 'campuses': sorted(major_campuses.get(r, [])),
                      'latest_year': major_latest.get(r, 0)}
                     for r in related],
                    key=lambda x: x['name'],
                ),
                'campuses': sorted(major_campuses.get(base, [])),
            })

        result.sort(key=lambda x: x['total_applicants'], reverse=True)
        return Response(result)


class DisciplineListView(APIView):
    def get(self, request):
        disciplines = (
            TransferData.objects
            .values_list('broad_discipline', flat=True)
            .distinct()
            .order_by('broad_discipline')
        )
        return Response(list(disciplines))


def _weighted_rate(numerator, denominator):
    """Percent of summed numerator over summed denominator; null when the denominator is zero."""
    return ExpressionWrapper(
        Sum(numerator) * 100.0 / NullIf(Sum(denominator), 0),
        output_field=FloatField(),
    )


STAT_AGGREGATES = {
    'total_applicants': Sum('applicants'),
    'total_admits': Sum('admits'),
    'total_enrolls': Sum('enrolls'),
    'avg_admit_rate': _weighted_rate('admits', 'applicants'),
    'avg_yield_rate': _weighted_rate('enrolls', 'admits'),
    'avg_admit_gpa_min': Min('admit_gpa_min'),
    'avg_admit_gpa_max': Max('admit_gpa_max'),
}


class GeneralStatsView(APIView):
    def get(self, request):
        stats = (
            CampusStats.objects
            .values(
                'year', 'campus', 'applicants', 'admits', 'enrolls',
                'admit_rate', 'yield_rate', 'admit_gpa_min', 'admit_gpa_max',
            )
            .order_by('year', 'campus')
        )
        return Response(list(stats))


class SchoolStatsView(APIView):
    def get(self, request, school):
        stats = (
            TransferData.objects
            .filter(university=school)
            .values('year', 'college_school')
            .annotate(**STAT_AGGREGATES)
            .order_by('year', 'college_school')
        )
        return Response(list(stats))


class CampusMajorStatsView(APIView):
    def get(self, request, campus):
        # Only merge aliases (same major, different name), not absorptions
        # (distinct majors grouped for navigation only).
        whens = []
        for canonical, aliases in MAJOR_ALIASES.items():
            for alias in aliases:
                whens.append(When(major_name=alias, then=Value(canonical)))

        qs = TransferData.objects.filter(university=campus)

        if whens:
            qs = qs.annotate(
                display_name=Case(
                    *whens,
                    default='major_name',
                    output_field=CharField(),
                )
            )
            group_field = 'display_name'
        else:
            group_field = 'major_name'

        stats = list(
            qs
            .values('year', group_field)
            .annotate(**STAT_AGGREGATES)
            .order_by('year', group_field)
        )

        if group_field != 'major_name':
            for row in stats:
                row['major_name'] = row.pop(group_field)

        return Response(stats)


class MajorStatsView(APIView):
    def get(self, request, major):
        names = [major]
        for canonical, aliases in MAJOR_ALIASES.items():
            if major == canonical:
                names.extend(aliases)
                break

        stats = (
            TransferData.objects
            .filter(major_name__in=names)
            .values('year', 'university')
            .annotate(**STAT_AGGREGATES)
            .order_by('year', 'university')
        )
        return Response(list(stats))


CC_NAMES = {
    'ahc': 'Allan Hancock College',
    'alameda': 'College of Alameda',
    'arc': 'American River College',
    'avc': 'Antelope Valley College',
    'bakerfld': 'Bakersfield College',
    'barstow': 'Barstow Community College',
    'butte': 'Butte College',
    'cabrillo': 'Cabrillo College',
    'camino': 'El Camino College',
    'canada': 'Cañada College',
    'canyons': 'College of the Canyons',
    'cerritos': 'Cerritos College',
    'cerro': 'Cerro Coso Community College',
    'chabot': 'Chabot College',
    'chaffey': 'Chaffey College',
    'citrus': 'Citrus College',
    'clovis': 'Clovis Community College',
    'coastlin': 'Coastline Community College',
    'columbia': 'Columbia College',
    'compton': 'Compton College',
    'contra': 'Contra Costa College',
    'copper': 'Copper Mountain College',
    'crafton': 'Crafton Hills College',
    'crc': 'Cosumnes River College',
    'cuesta': 'Cuesta College',
    'cuyamaca': 'Cuyamaca College',
    'cypress': 'Cypress College',
    'dac': 'De Anza College',
    'desert': 'College of the Desert',
    'diablo': 'Diablo Valley College',
    'evergrn': 'Evergreen Valley College',
    'feather': 'Feather River College',
    'folsom': 'Folsom Lake College',
    'foothill': 'Foothill College',
    'fresno': 'Fresno City College',
    'fullrton': 'Fullerton College',
    'gavilan': 'Gavilan College',
    'glendale': 'Glendale Community College',
    'gmcc': 'Grossmont College',
    'gwc': 'Golden West College',
    'hartnell': 'Hartnell College',
    'imperial': 'Imperial Valley College',
    'irvine': 'Irvine Valley College',
    'krc': 'Reedley College',
    'lacc': 'Los Angeles City College',
    'laec': 'East Los Angeles College',
    'lahc': 'Los Angeles Harbor College',
    'lamc': 'Los Angeles Mission College',
    'laney': 'Laney College',
    'lapc': 'Los Angeles Pierce College',
    'lasc': 'Los Angeles Southwest College',
    'lassen': 'Lassen Community College',
    'latt': 'Los Angeles Trade Technical College',
    'lavc': 'Los Angeles Valley College',
    'lawc': 'West Los Angeles College',
    'lbcc': 'Long Beach City College',
    'marin': 'College of Marin',
    'mateo': 'College of San Mateo',
    'mcc': 'Madera Community College',
    'medanos': 'Los Medanos College',
    'mendocin': 'Mendocino College',
    'merced': 'Merced College',
    'merritt': 'Merritt College',
    'mesa': 'San Diego Mesa College',
    'miracsta': 'MiraCosta College',
    'miramar': 'San Diego Miramar College',
    'mission': 'Mission College',
    'modesto': 'Modesto Junior College',
    'monterey': 'Monterey Peninsula College',
    'moorpark': 'Moorpark College',
    'mtsac': 'Mount San Antonio College',
    'mtsjc': 'Mt. San Jacinto College',
    'mvc': 'Moreno Valley College',
    'napa': 'Napa Valley College',
    'norco': 'Norco College',
    'occ': 'Orange Coast College',
    'ohlone': 'Ohlone College',
    'oxnard': 'Oxnard College',
    'palomar': 'Palomar College',
    'palovrde': 'Palo Verde College',
    'pasadena': 'Pasadena City College',
    'porter': 'Porterville College',
    'positas': 'Las Positas College',
    'rcc': 'Riverside City College',
    'redwoods': 'College of the Redwoods',
    'riohondo': 'Rio Hondo College',
    'rsc': 'Santa Ana College',
    'saddlbk': 'Saddleback College',
    'santiago': 'Santiago Canyon College',
    'sbcc': 'Santa Barbara City College',
    'sbvc': 'San Bernardino Valley College',
    'scc': 'Sacramento City College',
    'sdcc': 'San Diego City College',
    'sequoias': 'College of the Sequoias',
    'sfcity': 'City College of San Francisco',
    'shasta': 'Shasta College',
    'sierra': 'Sierra College',
    'siskiyou': 'College of the Siskiyous',
    'sjcc': 'San Jose City College',
    'sjdelta': 'San Joaquin Delta College',
    'skyline': 'Skyline College',
    'smcc': 'Santa Monica College',
    'solano': 'Solano Community College',
    'src': 'Santa Rosa Junior College',
    'swstrn': 'Southwestern College',
    'taft': 'Taft College',
    'tahoe': 'Lake Tahoe Community College',
    'ventura': 'Ventura College',
    'vista': 'Berkeley City College',
    'vvcc': 'Victor Valley College',
    'wcc': 'Woodland Community College',
    'whc': 'Coalinga College',
    'whcl': 'Lemoore College',
    'wvc': 'West Valley College',
    'yuba': 'Yuba College',
}

UC_NAMES = {
    'ucb': 'University of California, Berkeley',
    'ucd': 'University of California, Davis',
    'uci': 'University of California, Irvine',
    'ucla': 'University of California, Los Angeles',
    'ucm': 'University of California, Merced',
    'ucr': 'University of California, Riverside',
    'ucsb': 'University of California, Santa Barbara',
    'ucsc': 'University of California, Santa Cruz',
    'ucsd': 'University of California, San Diego',
}


class ArticulationCollegesView(APIView):
    def get(self, request):
        all_ucs = set(UC_NAMES.keys())
        colleges = []
        if ARTICULATION_DIR.is_dir():
            for cc_dir in sorted(ARTICULATION_DIR.iterdir()):
                if cc_dir.is_dir() and not cc_dir.name.startswith('_'):
                    uc_dirs = {d.name for d in cc_dir.iterdir() if d.is_dir()}
                    if not all_ucs.issubset(uc_dirs):
                        continue
                    code = cc_dir.name
                    colleges.append({
                        'code': code,
                        'name': CC_NAMES.get(code, code.upper()),
                    })
        return Response(colleges)


class ArticulationUCsView(APIView):
    def get(self, request, cc_code):
        cc_dir = ARTICULATION_DIR / cc_code.lower()
        campuses = []
        if cc_dir.is_dir():
            for uc_dir in sorted(cc_dir.iterdir()):
                if uc_dir.is_dir():
                    code = uc_dir.name
                    campuses.append({
                        'code': code,
                        'name': UC_NAMES.get(code, code.upper()),
                    })
        return Response(campuses)


def _slugify(text):
    """Mirror of the scraper's filename slug so failure-log major names can be matched to files."""
    text = re.sub(r'[&/]+', '_', text.lower().strip())
    return re.sub(r'[^a-z0-9]+', '_', text).strip('_')


def _agreement_files(cc_code, uc_code):
    """Map major slug -> newest agreement file across every academic year folder."""
    uc_dir = ARTICULATION_DIR / cc_code.lower() / uc_code.lower()
    if not uc_dir.is_dir():
        return {}
    files = {}
    for year_dir in sorted((d for d in uc_dir.iterdir() if d.is_dir()), key=lambda d: d.name):
        for json_file in year_dir.glob('*.json'):
            files[json_file.stem] = json_file
    return files


class ArticulationMajorsView(APIView):
    def get(self, request, cc_code, uc_code):
        majors = []
        for slug, json_file in sorted(_agreement_files(cc_code, uc_code).items()):
            try:
                data = json.loads(json_file.read_text())
            except json.JSONDecodeError:
                logger.warning('Skipping malformed agreement file %s', json_file)
                continue
            majors.append({
                'slug': slug,
                'name': data.get('major', slug),
                'academic_year': data.get('academic_year', json_file.parent.name),
                'row_count': _count_rows(data),
            })
        return Response(majors)


class ArticulationDetailView(APIView):
    def get(self, request, cc_code, uc_code, major_slug):
        json_file = _agreement_files(cc_code, uc_code).get(major_slug)
        if json_file is None:
            return Response({'error': 'Not found'}, status=404)
        return Response(json.loads(json_file.read_text()))


class ArticulationFailedView(APIView):
    """Majors the scraper failed to fetch for a cc -> uc pair and that still have no agreement file."""

    def get(self, request, cc_code, uc_code):
        if not FAILED_SCRAPES_FILE.exists():
            return Response([])
        try:
            entries = json.loads(FAILED_SCRAPES_FILE.read_text())
        except json.JSONDecodeError:
            return Response([])

        cc = cc_code.upper()
        uc = uc_code.upper()
        scraped = set(_agreement_files(cc_code, uc_code))

        seen = set()
        failed = []
        for entry in entries:
            if entry.get('sending_code') != cc or entry.get('receiving_code') != uc:
                continue
            major = entry.get('major') or ''
            key = (major, entry.get('academic_year'))
            if key in seen or _slugify(major) in scraped:
                continue
            seen.add(key)
            failed.append({'major': major, 'academic_year': entry.get('academic_year')})

        failed.sort(key=lambda e: e['major'].lower())
        return Response(failed)
