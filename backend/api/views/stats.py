from django.db.models import (
    Sum, Max, Min, Case, When, Value, CharField, FloatField, ExpressionWrapper,
)
from django.db.models.functions import NullIf
from rest_framework.response import Response
from rest_framework.views import APIView

from api.constants.majors import MAJOR_ALIASES
from api.models import CampusStats, TransferData


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
