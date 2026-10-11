from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient


class HealthViewTests(TestCase):

    def test_health_ok(self):
        response = APIClient().get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'status': 'ok'})

    def test_database_failure_is_503_and_logged(self):
        with patch('api.views.health.connection') as connection:
            connection.cursor.side_effect = RuntimeError('db down')
            with self.assertLogs('api.views.health', level='ERROR'), self.assertLogs('django.request', level='ERROR'):
                response = APIClient().get('/api/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {'status': 'error', 'database': 'unreachable'})
