from django.db.models import Max, Min, Sum
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import TransferData
from api.serializers import GroupedMajorSerializer
from api.services.major_grouping import group_majors


class GroupedMajorListView(APIView):
    @extend_schema(responses=GroupedMajorSerializer(many=True))
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
        groups = group_majors(major_rows, campus_rows)
        return Response(GroupedMajorSerializer(groups, many=True).data)
