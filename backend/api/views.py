import json
import re
from pathlib import Path

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Avg, Count, Max, Min, Case, When, Value, CharField
from django_filters import rest_framework as filters

from .models import TransferData, CampusStats
from .serializers import TransferDataSerializer

ARTICULATION_DIR = Path(__file__).resolve().parent.parent.parent / 'data' / 'articulation'


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
        'Pre-Mathematics',
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
        'Pre-Applied Mathematics',
        'Applied Mathematics',
        'Applied and Computational Mathematics',
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
        'Engineering Mathematics',
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
        'Cell, Molecular, & Developmental Biology',
        'Genetics & Plant Biology',
        'Genetics and Genomics',
        'Global Disease Biology',
        'Human Biology',
        'Microbiology',
        'Molecular & Medical Microbiology',
        'Molecular Biology',
        'Molecular, Cell, & Developmental Biology',
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
        'East Asian Religion, Thought and Culture',
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
        'Pre-Economics',
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
            name = row['major_name']
            for canonical, aliases in MAJOR_ALIASES.items():
                if name in aliases:
                    name = canonical
                    break
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


class GeneralStatsView(APIView):
    def get(self, request):
        stats = (
            CampusStats.objects
            .values('year', 'campus')
            .annotate(
                applicants=Sum('applicants'),
                admits=Sum('admits'),
                enrolls=Sum('enrolls'),
                admit_rate=Avg('admit_rate'),
                yield_rate=Avg('yield_rate'),
                admit_gpa_min=Min('admit_gpa_min'),
                admit_gpa_max=Max('admit_gpa_max'),
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
            .annotate(
                total_applicants=Sum('applicants'),
                total_admits=Sum('admits'),
                total_enrolls=Sum('enrolls'),
                avg_admit_rate=Avg('admit_rate'),
                avg_yield_rate=Avg('yield_rate'),
                avg_admit_gpa_min=Min('admit_gpa_min'),
                avg_admit_gpa_max=Max('admit_gpa_max'),
            )
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
            .annotate(
                total_applicants=Sum('applicants'),
                total_admits=Sum('admits'),
                total_enrolls=Sum('enrolls'),
                avg_admit_rate=Avg('admit_rate'),
                avg_yield_rate=Avg('yield_rate'),
                avg_admit_gpa_min=Min('admit_gpa_min'),
                avg_admit_gpa_max=Max('admit_gpa_max'),
            )
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
            .annotate(
                total_applicants=Sum('applicants'),
                total_admits=Sum('admits'),
                total_enrolls=Sum('enrolls'),
                avg_admit_rate=Avg('admit_rate'),
                avg_yield_rate=Avg('yield_rate'),
                avg_admit_gpa_min=Min('admit_gpa_min'),
                avg_admit_gpa_max=Max('admit_gpa_max'),
            )
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
    'sbcc': 'Santa Barbara City College',
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
        colleges = []
        if ARTICULATION_DIR.is_dir():
            for cc_dir in sorted(ARTICULATION_DIR.iterdir()):
                if cc_dir.is_dir() and not cc_dir.name.startswith('_'):
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


class ArticulationMajorsView(APIView):
    def get(self, request, cc_code, uc_code):
        uc_dir = ARTICULATION_DIR / cc_code.lower() / uc_code.lower()
        if not uc_dir.is_dir():
            return Response([])

        year_dirs = sorted(
            [d for d in uc_dir.iterdir() if d.is_dir()],
            key=lambda d: d.name,
            reverse=True,
        )
        if not year_dirs:
            return Response([])

        year_dir = year_dirs[0]
        majors = []
        for json_file in sorted(year_dir.glob('*.json')):
            try:
                data = json.loads(json_file.read_text())
                row_count = sum(len(s.get('rows', [])) for s in data.get('sections', []))
                majors.append({
                    'slug': json_file.stem,
                    'name': data.get('major', json_file.stem),
                    'academic_year': data.get('academic_year', year_dir.name),
                    'row_count': row_count,
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return Response(majors)


class ArticulationDetailView(APIView):
    def get(self, request, cc_code, uc_code, major_slug):
        uc_dir = ARTICULATION_DIR / cc_code.lower() / uc_code.lower()
        if not uc_dir.is_dir():
            return Response({'error': 'Not found'}, status=404)

        year_dirs = sorted(
            [d for d in uc_dir.iterdir() if d.is_dir()],
            key=lambda d: d.name,
            reverse=True,
        )
        if not year_dirs:
            return Response({'error': 'Not found'}, status=404)

        json_file = year_dirs[0] / f'{major_slug}.json'
        if not json_file.exists():
            return Response({'error': 'Not found'}, status=404)

        data = json.loads(json_file.read_text())
        return Response(data)
