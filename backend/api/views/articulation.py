from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from api.services import articulation


class ArticulationCollegesView(APIView):
    def get(self, request):
        return Response(articulation.list_colleges())


class ArticulationUCsView(APIView):
    def get(self, request, cc_code):
        return Response(articulation.list_campuses(cc_code))


class ArticulationMajorsView(APIView):
    def get(self, request, cc_code, uc_code):
        return Response(articulation.list_majors(cc_code, uc_code))


class ArticulationDetailView(APIView):
    def get(self, request, cc_code, uc_code, major_slug):
        data = articulation.load_agreement(cc_code, uc_code, major_slug)
        if data is None:
            raise NotFound('No agreement found for this major.')
        return Response(data)


class ArticulationFailedView(APIView):
    def get(self, request, cc_code, uc_code):
        return Response(articulation.list_failed(cc_code, uc_code))
