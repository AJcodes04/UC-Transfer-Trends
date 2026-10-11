from django.db.models import Max, Min, Sum
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import TransferData
from api.services.major_grouping import group_majors


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
