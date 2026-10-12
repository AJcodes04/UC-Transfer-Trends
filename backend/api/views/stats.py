from django.db.models import ExpressionWrapper, F, FloatField, Max, Min, Q, Sum
from django.db.models.functions import Coalesce, NullIf
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import CampusStats, TransferData
from api.serializers import (
    CampusMajorStatsRowSerializer,
    CampusStatsRowSerializer,
    MajorStatsRowSerializer,
    SchoolStatsRowSerializer,
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

# An alias row reports under its canonical major's name.
CANONICAL_MAJOR_NAME = Coalesce(F('major__canonical__name'), F('major__name'))


class GeneralStatsView(APIView):
    @extend_schema(responses=CampusStatsRowSerializer(many=True))
    def get(self, request):
        rows = (
            CampusStats.objects
            .values(
                'year', 'applicants', 'admits', 'enrolls',
                'admit_rate', 'yield_rate', 'admit_gpa_min', 'admit_gpa_max',
                campus_code=F('campus__code'),
            )
            .order_by('year', 'campus__code')
        )
        return Response(CampusStatsRowSerializer(rows, many=True).data)


class SchoolStatsView(APIView):
    @extend_schema(responses=SchoolStatsRowSerializer(many=True))
    def get(self, request, school):
        rows = (
            TransferData.objects
            .filter(campus__code=school)
            .values('year', 'college_school')
            .annotate(**STAT_AGGREGATES)
            .order_by('year', 'college_school')
        )
        return Response(SchoolStatsRowSerializer(rows, many=True).data)


class CampusMajorStatsView(APIView):
    @extend_schema(responses=CampusMajorStatsRowSerializer(many=True))
    def get(self, request, campus):
        rows = (
            TransferData.objects
            .filter(campus__code=campus)
            .values('year', major_name=CANONICAL_MAJOR_NAME)
            .annotate(**STAT_AGGREGATES)
            .order_by('year', 'major_name')
        )
        return Response(CampusMajorStatsRowSerializer(rows, many=True).data)


class MajorStatsView(APIView):
    @extend_schema(responses=MajorStatsRowSerializer(many=True))
    def get(self, request, major):
        rows = (
            TransferData.objects
            .filter(Q(major__name=major) | Q(major__canonical__name=major))
            .values('year', university=F('campus__code'))
            .annotate(**STAT_AGGREGATES)
            .order_by('year', 'university')
        )
        return Response(MajorStatsRowSerializer(rows, many=True).data)
