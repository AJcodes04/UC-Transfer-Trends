import logging

from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import HealthSerializer

logger = logging.getLogger(__name__)


class HealthView(APIView):
    throttle_classes = []

    @extend_schema(responses={200: HealthSerializer, 503: HealthSerializer})
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception:
            logger.exception('Health check: database unreachable')
            return Response({'status': 'error', 'database': 'unreachable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'status': 'ok'})
