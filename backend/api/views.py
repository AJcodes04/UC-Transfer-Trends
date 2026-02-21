import re

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Avg, Count
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
    def get(self, request):
        # Get all majors with their total applicants
        major_apps = {
            row['major_name']: row['total_apps']
            for row in (
                TransferData.objects
                .values('major_name')
                .annotate(total_apps=Sum('applicants'))
            )
        }
        all_names = set(major_apps.keys())

        # Build a mapping of major_name → list of campus codes that offer it.
        # Uses values() + distinct() so Django does one SQL query with
        # SELECT DISTINCT major_name, university — much faster than N queries.
        major_campuses = {}
        for row in (
            TransferData.objects
            .values('major_name', 'university')
            .distinct()
        ):
            major_campuses.setdefault(row['major_name'], set()).add(row['university'])

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

        # Build response sorted by total applicants (most popular first)
        result = []
        for base, related in groups.items():
            result.append({
                'name': base,
                'total_applicants': major_apps.get(base, 0),
                'related': sorted(related),
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


class MajorStatsView(APIView):
    def get(self, request, major):
        stats = (
            TransferData.objects
            .filter(major_name=major)
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
