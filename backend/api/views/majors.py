from django.db.models import F, Max, Min, Sum
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Major, TransferData
from api.serializers import GroupedMajorSerializer
from api.services.major_grouping import group_majors


class GroupedMajorListView(APIView):
    @extend_schema(responses=GroupedMajorSerializer(many=True))
    def get(self, request):
        major_rows = (
            TransferData.objects
            .order_by()
            .values('major_id')
            .annotate(
                total_apps=Sum('applicants'),
                latest_year=Max('year'),
                earliest_year=Min('year'),
            )
        )
        campus_rows = (
            TransferData.objects
            .order_by()
            .values('major_id', university=F('campus__code'))
            .distinct()
        )
        majors = {m.id: m for m in Major.objects.all()}
        groups = group_majors(major_rows, campus_rows, majors)
        return Response(GroupedMajorSerializer(groups, many=True).data)
