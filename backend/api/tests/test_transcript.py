
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


class TranscriptRateLimitTests(TestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        self.settings_override = override_settings(ANTHROPIC_API_KEY='test-key')
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()

    def _pdf(self):
        return SimpleUploadedFile('t.pdf', b'%PDF-1.4 fake', content_type='application/pdf')

    def test_limiter_counts_to_limit_then_blocks(self):
        from api.views.transcript import DAILY_LIMIT, _check_rate_limit
        for i in range(DAILY_LIMIT):
            allowed, remaining = _check_rate_limit('1.2.3.4')
            self.assertTrue(allowed)
            self.assertEqual(remaining, DAILY_LIMIT - i - 1)
        allowed, remaining = _check_rate_limit('1.2.3.4')
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_invalid_upload_does_not_consume_quota(self):
        from django.core.cache import cache
        self.client.post('/api/transcript/upload/', {}, format='multipart')
        self.client.post('/api/transcript/upload/', {'file': SimpleUploadedFile('t.txt', b'x')}, format='multipart')
        self.assertIsNone(cache.get('transcript_ratelimit:127.0.0.1'))

    def test_over_limit_returns_429_with_header_and_limit_in_message(self):
        from django.core.cache import cache

        from api.views.transcript import DAILY_LIMIT
        cache.set('transcript_ratelimit:127.0.0.1', DAILY_LIMIT, timeout=60)
        response = self.client.post('/api/transcript/upload/', {'file': self._pdf()}, format='multipart')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['X-RateLimit-Remaining'], '0')
        self.assertIn(str(DAILY_LIMIT), response.data['error'])
