import base64
import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import httpx

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from api.services.transcript import match_college
from api.views.transcript import (
    DAILY_LIMIT,
    MAX_PAGES,
    MAX_TEXT_CHARS,
    MODEL,
    OUTPUT_SCHEMA,
    SYSTEM_PROMPT,
    _check_rate_limit,
    _get_client_ip,
)

UPLOAD_URL = '/api/transcript/upload/'

COLLEGES = [
    {'code': 'dac', 'name': 'De Anza College'},
    {'code': 'foothill', 'name': 'Foothill College'},
    {'code': 'lacc', 'name': 'Los Angeles City College'},
    {'code': 'lavc', 'name': 'Los Angeles Valley College'},
    {'code': 'canada', 'name': 'Cañada College'},
    {'code': 'mtsjc', 'name': 'Mt. San Jacinto College'},
]


def pdf_file(name='t.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 fake', content_type='application/pdf')


def fake_pdf(page_texts):
    pdf = MagicMock()
    pdf.pages = [MagicMock(extract_text=MagicMock(return_value=t)) for t in page_texts]
    pdf.__enter__.return_value = pdf
    pdf.__exit__.return_value = False
    return pdf


def fake_message(text, stop_reason='end_turn'):
    message = MagicMock()
    message.stop_reason = stop_reason
    message.content = [MagicMock(text=text)]
    message.usage = SimpleNamespace(input_tokens=1200, output_tokens=340)
    return message


@patch('api.services.transcript.list_colleges', return_value=COLLEGES)
class CollegeMatchTests(TestCase):
    def test_exact_name_ignoring_case_and_filler_words(self, _):
        self.assertEqual(match_college('DE ANZA COMMUNITY COLLEGE')['code'], 'dac')

    def test_accents_and_abbreviations_are_normalized(self, _):
        self.assertEqual(match_college('Canada College')['code'], 'canada')
        self.assertEqual(match_college('Mount San Jacinto College')['code'], 'mtsjc')

    def test_name_embedded_in_longer_header(self, _):
        self.assertEqual(match_college('Los Angeles Valley College Official Transcript')['code'], 'lavc')

    def test_ambiguous_header_matches_nothing(self, _):
        self.assertIsNone(match_college('Foothill-De Anza Community College District'))

    def test_unknown_or_empty_matches_nothing(self, _):
        self.assertIsNone(match_college('Harvard University'))
        self.assertIsNone(match_college(''))
        self.assertIsNone(match_college('College'))


class ClientIpTests(TestCase):

    def test_prefers_first_forwarded_address(self):
        rf = RequestFactory()
        request = rf.get('/', HTTP_X_FORWARDED_FOR='203.0.113.9, 10.0.0.1', REMOTE_ADDR='10.0.0.2')
        self.assertEqual(_get_client_ip(request), '203.0.113.9')
        self.assertEqual(_get_client_ip(rf.get('/', REMOTE_ADDR='10.0.0.2')), '10.0.0.2')


class TranscriptRateLimitTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.settings_override = override_settings(ANTHROPIC_API_KEY='test-key')
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()

    def test_limiter_counts_to_limit_then_blocks(self):
        for i in range(DAILY_LIMIT):
            allowed, remaining = _check_rate_limit('1.2.3.4')
            self.assertTrue(allowed)
            self.assertEqual(remaining, DAILY_LIMIT - i - 1)
        allowed, remaining = _check_rate_limit('1.2.3.4')
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_limiter_is_per_ip(self):
        for _ in range(DAILY_LIMIT):
            _check_rate_limit('1.1.1.1')
        self.assertEqual(_check_rate_limit('2.2.2.2'), (True, DAILY_LIMIT - 1))

    def test_invalid_upload_does_not_consume_quota(self):
        no_file = self.client.post(UPLOAD_URL, {}, format='multipart')
        wrong_type = self.client.post(UPLOAD_URL, {'file': SimpleUploadedFile('t.txt', b'x')}, format='multipart')
        self.assertEqual((no_file.status_code, wrong_type.status_code), (400, 400))
        self.assertIn('error', no_file.data)
        self.assertEqual(wrong_type.data['error'], 'Only PDF files are accepted')
        self.assertIsNone(cache.get('transcript_ratelimit:127.0.0.1'))

    def test_oversized_upload_rejected(self):
        big = SimpleUploadedFile('big.pdf', b'0' * (10 * 1024 * 1024 + 1))
        response = self.client.post(UPLOAD_URL, {'file': big}, format='multipart')
        self.assertEqual((response.status_code, response.data['error']), (400, 'File too large (max 10MB)'))

    def test_over_limit_returns_429_with_header_and_limit_in_message(self):
        cache.set('transcript_ratelimit:127.0.0.1', DAILY_LIMIT, timeout=60)
        response = self.client.post(UPLOAD_URL, {'file': pdf_file()}, format='multipart')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['X-RateLimit-Remaining'], '0')
        self.assertIn(str(DAILY_LIMIT), response.data['error'])

    @override_settings(ANTHROPIC_API_KEY='')
    def test_missing_api_key_is_a_server_error(self):
        with self.assertLogs('django.request', level='ERROR'):
            response = self.client.post(UPLOAD_URL, {'file': pdf_file()}, format='multipart')
        self.assertEqual(response.status_code, 500)
        self.assertIn('ANTHROPIC_API_KEY', response.data['error'])


class TranscriptParseTests(TestCase):
    """Drives the full upload path with pdfplumber and the Anthropic client replaced by fakes."""

    COURSES = [
        {'prefix': 'math', 'number': '1a.', 'title': 'Calculus I', 'units': 5, 'grade': 'c', 'needs_review': False},
        {'prefix': 'MATH', 'number': '1A', 'title': 'Calculus I', 'units': 5.0, 'grade': 'A', 'needs_review': False},
        {'prefix': 'P E', 'number': '022a', 'title': 'Yoga', 'units': 0, 'grade': 'P', 'needs_review': True},
        {'prefix': 'ENGL', 'number': '1', 'title': 'Composition', 'units': 4, 'grade': 'W', 'needs_review': False},
        {'prefix': 'ENGL', 'number': '1', 'title': 'Composition', 'units': 4, 'grade': 'B+', 'needs_review': False},
    ]

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.settings_override = override_settings(ANTHROPIC_API_KEY='test-key')
        self.settings_override.enable()
        # Expected 5xx responses would otherwise print django.request errors into the test output.
        self._request_logger = logging.getLogger('django.request')
        self._request_level = self._request_logger.level
        self._request_logger.setLevel(logging.CRITICAL)
        self.pdf_open = patch('api.views.transcript.pdfplumber.open', return_value=fake_pdf(['MATH 1A  A\n', 'ENGL 1  B+'])).start()
        self.model = MagicMock()
        self.model.messages.create.return_value = fake_message(json.dumps({'institution': 'De Anza College', 'courses': self.COURSES}))
        patch('api.views.transcript._anthropic_client', return_value=self.model).start()
        patch('api.services.transcript.list_colleges', return_value=COLLEGES).start()

    def tearDown(self):
        patch.stopall()
        self.settings_override.disable()
        self._request_logger.setLevel(self._request_level)

    def _post(self):
        return self.client.post(UPLOAD_URL, {'file': pdf_file()}, format='multipart')

    def test_success_normalizes_and_keeps_best_grade_per_course(self):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        by_key = {f"{c['prefix']} {c['number']}": c for c in response.data['courses']}
        self.assertEqual(set(by_key), {'MATH 1A', 'PE 022A', 'ENGL 1'})
        self.assertEqual(by_key['MATH 1A']['grade'], 'A')
        self.assertEqual(by_key['ENGL 1']['grade'], 'B+')
        self.assertEqual(by_key['PE 022A']['units'], 0.0)
        self.assertEqual(by_key['MATH 1A']['units'], 5.0)
        self.assertEqual([k for k, c in by_key.items() if c['needs_review']], ['PE 022A'])
        self.assertEqual(response['X-RateLimit-Remaining'], str(DAILY_LIMIT - 1))

    def test_token_usage_is_logged_per_parse(self):
        with self.assertLogs('api.views.transcript', level='INFO') as logs:
            self._post()
        self.assertIn('mode=text input_tokens=1200 output_tokens=340 stop_reason=end_turn', logs.output[0])

    def test_detected_institution_is_returned_as_a_college(self):
        response = self._post()
        self.assertEqual(response.data['college'], {'code': 'dac', 'name': 'De Anza College'})

    def test_unknown_institution_gives_null_college(self):
        self.model.messages.create.return_value = fake_message('{"institution": "Some Other School", "courses": []}')
        response = self._post()
        self.assertEqual((response.status_code, response.data), (200, {'college': None, 'courses': []}))

    def test_sends_joined_pages_with_system_prompt_to_configured_model(self):
        self._post()
        kwargs = self.model.messages.create.call_args.kwargs
        self.assertEqual(kwargs['model'], MODEL)
        self.assertEqual(kwargs['system'], SYSTEM_PROMPT)
        self.assertEqual(kwargs['output_config'], {'format': {'type': 'json_schema', 'schema': OUTPUT_SCHEMA}})
        content = kwargs['messages'][0]['content']
        self.assertIn('MATH 1A', content)
        self.assertIn('--- PAGE BREAK ---', content)
        self.assertIn('ENGL 1', content)

    def test_quota_decrements_across_successful_parses(self):
        first = self._post()
        second = self._post()
        self.assertEqual((first['X-RateLimit-Remaining'], second['X-RateLimit-Remaining']),
                         (str(DAILY_LIMIT - 1), str(DAILY_LIMIT - 2)))

    def test_empty_transcript_returns_no_courses(self):
        self.model.messages.create.return_value = fake_message('{"institution": "", "courses": []}')
        response = self._post()
        self.assertEqual((response.status_code, response.data), (200, {'college': None, 'courses': []}))

    def test_invalid_json_is_logged_and_a_server_error(self):
        self.model.messages.create.return_value = fake_message('not json at all')
        with self.assertLogs('api.views.transcript', level='WARNING'):
            response = self._post()
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.data)

    def test_truncated_output_is_reported_not_parsed(self):
        self.model.messages.create.return_value = fake_message('[{"prefix": "MA', stop_reason='max_tokens')
        with self.assertLogs('api.views.transcript', level='WARNING'):
            response = self._post()
        self.assertEqual((response.status_code, response.data['error']), (500, 'Transcript is too long for the parser.'))

    def test_api_error_is_a_bad_gateway_without_leaking_details(self):
        self.model.messages.create.side_effect = anthropic.APIConnectionError(
            request=httpx.Request('POST', 'https://api.anthropic.com/v1/messages'))
        with self.assertLogs('api.views.transcript', level='ERROR'):
            response = self._post()
        self.assertEqual((response.status_code, response.data['error']), (502, 'AI service error. Please try again.'))

    def test_unexpected_exception_is_a_server_error(self):
        self.model.messages.create.side_effect = RuntimeError('boom with secrets')
        with self.assertLogs('api.views.transcript', level='ERROR'):
            response = self._post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('secrets', response.data['error'])

    def test_unreadable_pdf_is_a_client_error_and_model_not_called(self):
        self.pdf_open.side_effect = ValueError('bad pdf')
        with self.assertLogs('api.views.transcript', level='WARNING'):
            response = self._post()
        self.assertEqual((response.status_code, response.data['error']), (400, 'Could not read the PDF file.'))
        self.model.messages.create.assert_not_called()

    def test_pdf_without_text_is_sent_as_a_document(self):
        self.pdf_open.return_value = fake_pdf(['', '   ', None])
        response = self._post()
        self.assertEqual(response.status_code, 200)
        content = self.model.messages.create.call_args.kwargs['messages'][0]['content']
        self.assertEqual(content[0]['type'], 'document')
        self.assertEqual(content[0]['source']['media_type'], 'application/pdf')
        self.assertEqual(base64.b64decode(content[0]['source']['data']), b'%PDF-1.4 fake')
        self.assertEqual(content[1], {'type': 'text', 'text': 'Parse this transcript.'})

    def test_too_many_pages_rejected_before_model_call(self):
        self.pdf_open.return_value = fake_pdf(['x'] * (MAX_PAGES + 1))
        response = self._post()
        self.assertEqual(response.status_code, 400)
        self.assertIn(str(MAX_PAGES), response.data['error'])
        self.model.messages.create.assert_not_called()

    def test_too_much_text_rejected_before_model_call(self):
        self.pdf_open.return_value = fake_pdf(['x' * (MAX_TEXT_CHARS + 1)])
        response = self._post()
        self.assertEqual((response.status_code, response.data['error']), (400, 'Transcript text is too long to parse.'))
        self.model.messages.create.assert_not_called()


class AnthropicClientTests(TestCase):

    def test_client_is_built_once_from_settings(self):
        from api.views import transcript
        with patch.object(transcript, '_client', None), \
             patch('api.views.transcript.anthropic.Anthropic') as ctor, \
             override_settings(ANTHROPIC_API_KEY='k-123'):
            first = transcript._anthropic_client()
            second = transcript._anthropic_client()
        ctor.assert_called_once_with(api_key='k-123', timeout=transcript.REQUEST_TIMEOUT_SECONDS, max_retries=1)
        self.assertIs(first, second)

    def test_rate_limit_recovers_if_key_expires_between_add_and_incr(self):
        cache.clear()
        with patch('api.views.transcript.cache.incr', side_effect=ValueError):
            self.assertEqual(_check_rate_limit('9.9.9.9'), (True, DAILY_LIMIT - 1))
        self.assertEqual(cache.get('transcript_ratelimit:9.9.9.9'), 1)
