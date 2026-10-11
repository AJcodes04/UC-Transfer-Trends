from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle


class AnonThrottleTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()

    def test_requests_over_the_anon_rate_get_429_with_error_shape(self):
        with patch.object(SimpleRateThrottle, 'THROTTLE_RATES', {'anon': '2/min'}):
            codes = [self.client.get('/api/stats/general/').status_code for _ in range(3)]
            blocked = self.client.get('/api/stats/general/')
            health = self.client.get('/api/health/')
        self.assertEqual(codes, [200, 200, 429])
        self.assertEqual(list(blocked.data), ['error'])
        self.assertTrue(blocked.has_header('Retry-After'))
        self.assertEqual(health.status_code, 200)
