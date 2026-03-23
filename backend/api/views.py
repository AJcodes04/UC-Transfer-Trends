import re

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Avg, Count, Max, Min, Case, When, Value, CharField
from django_filters import rest_framework as filters

from .models import TransferData, CampusStats
from .serializers import TransferDataSerializer


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


# Regex to detect sub-major delimiters (e.g., " - ", " (", "/", " with ", " :")
_SUB_MAJOR_RE = re.compile(r'^(.+?)(\s*[-/(:]|\s+with\s|\s+w/)', re.IGNORECASE)

# Explicit absorption rules: parent major → list of child majors that should
# appear as specializations under the parent on the landing page.  These
# override the regex-based grouping.  If a child major doesn't exist in the
# database it is silently skipped.
# Aliases: majors that are the same program with different spelling.
# The alias's data gets merged into the canonical name and the alias
# is hidden everywhere (not shown as a specialization).
MAJOR_ALIASES = {
    'Communication': ['Communication Studies', 'Communication Arts'],
    'African American Studies': ['African-American Studies'],
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
    #! Might need to change later because Film is different at other schools
    'Film': [
        'Film & Television',
        'Film and Digital Media',
        'Film and Media Studies',
        'Film Studies',
    ],
    'Art': [
        'Art - Studio',
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
    """Returns majors grouped by base name with total applicants and campuses."""

    # Majors with no data since this year are considered discontinued.
    DISCONTINUED_BEFORE = 2020
    # Discontinued majors are still shown if they span at least this many years.
    MIN_HISTORY_YEARS = 6

    def get(self, request):
        # Get all majors with their total applicants and year range.
        # A major is kept if it is either:
        #   1. Active — has data in DISCONTINUED_BEFORE or later, OR
        #   2. Has significant history — spans MIN_HISTORY_YEARS+ years
        # This hides short-lived discontinued programs while preserving
        # ones with enough data to be useful.
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

        # Track latest_year per major so the frontend can flag discontinued ones.
        major_latest = {
            name: row['latest_year']
            for name, row in major_agg.items()
            if name in active_majors
        }

        # Merge aliases: fold each alias's applicants into the canonical name
        # and remove the alias from the active set entirely.
        for canonical, aliases in MAJOR_ALIASES.items():
            for alias in aliases:
                if alias in active_majors:
                    active_majors.setdefault(canonical, 0)
                    active_majors[canonical] += active_majors.pop(alias)
                    # Keep the most recent year across aliases
                    if alias in major_latest:
                        major_latest.setdefault(canonical, 0)
                        major_latest[canonical] = max(
                            major_latest.get(canonical, 0),
                            major_latest.pop(alias),
                        )

        all_names = set(active_majors.keys())
        major_apps = active_majors

        # Build a mapping of major_name  -> list of campus codes that offer it.
        # Uses values() + distinct() so Django does one SQL query with
        # SELECT DISTINCT major_name, university — much faster than N queries.
        major_campuses = {}
        for row in (
            TransferData.objects
            .values('major_name', 'university')
            .distinct()
        ):
            # Map alias campus data to the canonical name
            name = row['major_name']
            for canonical, aliases in MAJOR_ALIASES.items():
                if name in aliases:
                    name = canonical
                    break
            if name in all_names:
                major_campuses.setdefault(name, set()).add(row['university'])

        # Group sub-majors under their base if the base exists standalone
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

        # Apply explicit absorption rules — these override the regex grouping.
        # For each parent→children mapping, move children under the parent
        # and remove them as standalone top-level groups.
        for parent, children in MAJOR_ABSORPTIONS.items():
            # Ensure the parent exists as a group (it must exist in the DB)
            if parent not in all_names:
                continue
            if parent not in groups:
                groups[parent] = []
            for child in children:
                if child not in all_names:
                    continue  # skip majors that don't exist in the DB
                # Remove child from wherever it currently lives
                if child in groups:
                    # Child was a top-level group — move its own sub-majors
                    # under the parent too, then delete the child group
                    groups[parent].extend(groups.pop(child))
                else:
                    # Child might be a sub-major under a different parent
                    for other_base, other_related in groups.items():
                        if child in other_related:
                            other_related.remove(child)
                            break
                # Add the child under the parent (avoid duplicates)
                if child not in groups[parent]:
                    groups[parent].append(child)
                assigned.add(child)

        # Build response sorted by total applicants (most popular first)
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
                # Sorted list of campus codes that offer this base major
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
    """Returns pre-computed campus-level stats from official UC data."""
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
                avg_admit_gpa_min=Avg('admit_gpa_min'),
                avg_admit_gpa_max=Avg('admit_gpa_max'),
            )
            .order_by('year', 'college_school')
        )
        return Response(list(stats))


class CampusMajorStatsView(APIView):
    """Per-major stats for a single campus, aggregated by year + major_name.

    This is the mirror of MajorStatsView: instead of "one major across all
    campuses" it returns "one campus across all its majors".  The frontend
    uses it to draw a trend chart with one line per major.

    Before aggregating, we use Case/When to rename alias and absorption
    child majors to their canonical parent name.  This makes the DB-level
    GROUP BY merge their rows automatically — sums get added up and
    averages are computed across all contributing rows, which is more
    accurate than trying to re-average in Python afterwards.
    """
    def get(self, request, campus):
        # Build Case/When rules: child name → parent name.
        # The DB will rename matching rows before the GROUP BY, so
        # "Computer Science with Business Applications" becomes
        # "Computer Science" and their stats merge correctly.
        whens = []
        for canonical, aliases in MAJOR_ALIASES.items():
            for alias in aliases:
                whens.append(When(major_name=alias, then=Value(canonical)))
        for parent, children in MAJOR_ABSORPTIONS.items():
            for child in children:
                whens.append(When(major_name=child, then=Value(parent)))

        qs = TransferData.objects.filter(university=campus)

        # If there are rename rules, annotate a normalized name and
        # group by that instead of the raw major_name.
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
                avg_admit_gpa_min=Avg('admit_gpa_min'),
                avg_admit_gpa_max=Avg('admit_gpa_max'),
            )
            .order_by('year', group_field)
        )

        # Rename the group field back to major_name so the frontend
        # doesn't need to know about the normalization.
        if group_field != 'major_name':
            for row in stats:
                row['major_name'] = row.pop(group_field)

        return Response(stats)


class MajorStatsView(APIView):
    def get(self, request, major):
        # Collect all names that should be queried: the major itself plus
        # any aliases that map to it (e.g. "African-American Studies" →
        # "African American Studies").
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
                avg_admit_gpa_min=Avg('admit_gpa_min'),
                avg_admit_gpa_max=Avg('admit_gpa_max'),
            )
            .order_by('year', 'university')
        )
        return Response(list(stats))
