from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.tests.factories import make_campus_stats


class HttpCacheHeaderTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        make_campus_stats(campus='UCB', year=2023)

    def test_successful_api_gets_are_publicly_cacheable_with_an_etag(self):
        response = self.client.get('/api/stats/general/')
        self.assertEqual(set(response['Cache-Control'].split(', ')), {'public', 'max-age=3600'})
        self.assertTrue(response.has_header('ETag'))

    def test_matching_etag_yields_304_with_empty_body(self):
        etag = self.client.get('/api/stats/general/')['ETag']
        response = self.client.get('/api/stats/general/', HTTP_IF_NONE_MATCH=etag)
        self.assertEqual((response.status_code, response.content), (304, b''))

    def test_health_errors_and_posts_are_not_cached(self):
        self.assertFalse(self.client.get('/api/health/').has_header('Cache-Control'))
        self.assertFalse(self.client.get('/api/articulation/none/x/y/').has_header('Cache-Control'))
        with override_settings(ANTHROPIC_API_KEY='k'):
            self.assertFalse(self.client.post('/api/transcript/upload/', {}, format='multipart').has_header('Cache-Control'))

    @override_settings(API_CACHE_MAX_AGE=60)
    def test_max_age_is_configurable(self):
        response = self.client.get('/api/stats/general/')
        self.assertIn('max-age=60', response['Cache-Control'])
