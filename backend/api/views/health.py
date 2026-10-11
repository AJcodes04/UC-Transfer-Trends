import logging

from django.db import connection
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthView(APIView):
    throttle_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception:
            logger.exception('Health check: database unreachable')
            return Response({'status': 'error', 'database': 'unreachable'}, status=503)
        return Response({'status': 'ok'})
