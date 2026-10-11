from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    ArticulationMajorSerializer, ErrorSerializer, FailedScrapeSerializer, InstitutionSerializer,
)
from api.services import articulation


class ArticulationCollegesView(APIView):
    @extend_schema(responses=InstitutionSerializer(many=True))
    def get(self, request):
        return Response(InstitutionSerializer(articulation.list_colleges(), many=True).data)


class ArticulationUCsView(APIView):
    @extend_schema(responses=InstitutionSerializer(many=True))
    def get(self, request, cc_code):
        return Response(InstitutionSerializer(articulation.list_campuses(cc_code), many=True).data)


class ArticulationMajorsView(APIView):
    @extend_schema(responses=ArticulationMajorSerializer(many=True))
    def get(self, request, cc_code, uc_code):
        return Response(ArticulationMajorSerializer(articulation.list_majors(cc_code, uc_code), many=True).data)


class ArticulationDetailView(APIView):
    @extend_schema(responses={200: OpenApiTypes.OBJECT, 404: ErrorSerializer})
    def get(self, request, cc_code, uc_code, major_slug):
        data = articulation.load_agreement(cc_code, uc_code, major_slug)
        if data is None:
            raise NotFound('No agreement found for this major.')
        return Response(data)


class ArticulationFailedView(APIView):
    @extend_schema(responses=FailedScrapeSerializer(many=True))
    def get(self, request, cc_code, uc_code):
        return Response(FailedScrapeSerializer(articulation.list_failed(cc_code, uc_code), many=True).data)
