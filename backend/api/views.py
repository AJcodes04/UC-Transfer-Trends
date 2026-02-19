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


class MajorListView(APIView):
    def get(self, request):
        majors = (
            TransferData.objects
            .values_list('major_name', flat=True)
            .distinct()
            .order_by('major_name')
        )
        return Response(list(majors))


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
