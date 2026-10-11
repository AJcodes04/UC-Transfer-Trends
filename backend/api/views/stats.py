from django.db.models import (
    Sum, Max, Min, Case, When, Value, CharField, FloatField, ExpressionWrapper,
)
from django.db.models.functions import NullIf
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from api.constants.majors import ALIAS_TO_CANONICAL, MAJOR_ALIASES
from api.models import CampusStats, TransferData
from api.serializers import (
    CampusMajorStatsRowSerializer, CampusStatsRowSerializer,
    MajorStatsRowSerializer, SchoolStatsRowSerializer,
)


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

# SQL CASE mapping every alias to its canonical major; built once, reused per request.
CANONICAL_MAJOR_NAME = Case(
    *(When(major_name=alias, then=Value(canonical)) for alias, canonical in ALIAS_TO_CANONICAL.items()),
    default='major_name',
    output_field=CharField(),
)


class GeneralStatsView(APIView):
    @extend_schema(responses=CampusStatsRowSerializer(many=True))
    def get(self, request):
        rows = (
            CampusStats.objects
            .values(
                'year', 'campus', 'applicants', 'admits', 'enrolls',
                'admit_rate', 'yield_rate', 'admit_gpa_min', 'admit_gpa_max',
            )
            .order_by('year', 'campus')
        )
        return Response(CampusStatsRowSerializer(rows, many=True).data)


class SchoolStatsView(APIView):
    @extend_schema(responses=SchoolStatsRowSerializer(many=True))
    def get(self, request, school):
        rows = (
            TransferData.objects
            .filter(university=school)
            .values('year', 'college_school')
            .annotate(**STAT_AGGREGATES)
            .order_by('year', 'college_school')
        )
        return Response(SchoolStatsRowSerializer(rows, many=True).data)


class CampusMajorStatsView(APIView):
    @extend_schema(responses=CampusMajorStatsRowSerializer(many=True))
    def get(self, request, campus):
        rows = list(
            TransferData.objects
            .filter(university=campus)
            .annotate(display_name=CANONICAL_MAJOR_NAME)
            .values('year', 'display_name')
            .annotate(**STAT_AGGREGATES)
            .order_by('year', 'display_name')
        )
        for row in rows:
            row['major_name'] = row.pop('display_name')
        return Response(CampusMajorStatsRowSerializer(rows, many=True).data)


class MajorStatsView(APIView):
    @extend_schema(responses=MajorStatsRowSerializer(many=True))
    def get(self, request, major):
        rows = (
            TransferData.objects
            .filter(major_name__in=[major, *MAJOR_ALIASES.get(major, [])])
            .values('year', 'university')
            .annotate(**STAT_AGGREGATES)
            .order_by('year', 'university')
        )
        return Response(MajorStatsRowSerializer(rows, many=True).data)
