from django.db.models import Max, Min, Sum
from django_filters import rest_framework as filters
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import TransferData
from api.serializers import TransferDataSerializer
from api.services.major_grouping import group_majors


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


class GroupedMajorListView(APIView):
    def get(self, request):
        major_rows = (
            TransferData.objects
            .values('major_name')
            .annotate(
                total_apps=Sum('applicants'),
                latest_year=Max('year'),
                earliest_year=Min('year'),
            )
        )
        campus_rows = TransferData.objects.values('major_name', 'university').distinct()
        return Response(group_majors(major_rows, campus_rows))
