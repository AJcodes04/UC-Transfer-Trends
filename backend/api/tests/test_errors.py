
from django.test import TestCase
from rest_framework.test import APIClient


class ErrorShapeTests(TestCase):

    def test_drf_exceptions_render_as_error_key(self):
        from rest_framework.exceptions import NotFound, Throttled

        from api.errors import api_exception_handler
        self.assertEqual(api_exception_handler(NotFound('gone'), {}).data, {'error': 'gone'})
        response = api_exception_handler(Throttled(wait=7), {})
        self.assertEqual(response.status_code, 429)
        self.assertIn('error', response.data)
        self.assertEqual(response['Retry-After'], '7')

    def test_unknown_route_method_uses_error_key(self):
        response = APIClient().post('/api/health/')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(list(response.data), ['error'])
