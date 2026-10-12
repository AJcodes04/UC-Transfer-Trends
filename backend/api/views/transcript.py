"""
Transcript PDF parsing endpoint. Extracts text from uploaded PDFs
with pdfplumber and sends it to the Claude API for structured course
extraction; scanned PDFs with no text layer are sent as the PDF itself.
Rate-limited per IP per day (see DAILY_LIMIT).
"""

import base64
import io
import json
import logging

import anthropic
import pdfplumber

from django.conf import settings
from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.errors import error_response
from api.serializers import ErrorSerializer, TranscriptParseSerializer, TranscriptUploadSerializer
from api.services.transcript import match_college

logger = logging.getLogger(__name__)

DAILY_LIMIT = 5
WINDOW_SECONDS = 86400
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PAGES = 30
MAX_TEXT_CHARS = 150_000
MODEL = 'claude-haiku-4-5'
REQUEST_TIMEOUT_SECONDS = 90.0

_client = None

SYSTEM_PROMPT = """You are a transcript parser. Given a community college transcript, either as extracted text or as the PDF itself, report the institution and extract every course.

"institution" is the name of the community college printed in the transcript header (e.g. "De Anza College"), or an empty string if none is shown.

Each course has exactly these fields:
- "prefix": the department/subject code in uppercase (e.g. "CIS", "MATH", "PE"). If the prefix has a space like "P E", collapse it to "PE".
- "number": the course number including any letter suffix, in uppercase (e.g. "022A", "001B", "21JA"). Strip any trailing periods.
- "title": the course title as shown, in title case.
- "units": the number of units/credits as a number (e.g. 4.5, 5.0).
- "grade": the letter grade (e.g. "A", "A-", "B+", "W", "P", "NP"). For in-progress courses use "IP".
- "needs_review": true if any field for this course was unclear or had to be guessed (garbled text, a watermark through the line, an ambiguous grade or unit count); otherwise false.

Rules:
- Include ALL courses: completed, in-progress, withdrawn, passed, etc.
- Do NOT include summary lines (GPA, total units, etc.), institution headers, or non-course text.
- The transcript text may have watermark artifacts (random single letters scattered in the text). Ignore them.
- If the same course appears multiple times (retakes), include all instances — deduplication is handled downstream."""

COURSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'prefix': {'type': 'string'},
        'number': {'type': 'string'},
        'title': {'type': 'string'},
        'units': {'type': 'number'},
        'grade': {'type': 'string'},
        'needs_review': {'type': 'boolean'},
    },
    'required': ['prefix', 'number', 'title', 'units', 'grade', 'needs_review'],
    'additionalProperties': False,
}

OUTPUT_SCHEMA = {
    'type': 'object',
    'properties': {
        'institution': {'type': 'string'},
        'courses': {'type': 'array', 'items': COURSE_SCHEMA},
    },
    'required': ['institution', 'courses'],
    'additionalProperties': False,
}

GRADE_RANK = {
    'F': 0, 'D-': 1, 'D': 2, 'D+': 3,
    'C-': 4, 'C': 5, 'C+': 6,
    'B-': 7, 'B': 8, 'B+': 9,
    'A-': 10, 'A': 11, 'A+': 12,
    'NP': -2, 'P': 13,
    'W': -3, 'FW': -3, 'I': -4, 'IP': -5, 'NC': -2, 'CR': 13,
}


def _user_content(pages_text, pdf_bytes):
    """Extracted text when the PDF has a text layer; otherwise the PDF itself so scans can be read."""
    if pages_text:
        return 'Parse this transcript:\n\n' + '\n\n--- PAGE BREAK ---\n\n'.join(pages_text)
    return [
        {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf',
                                        'data': base64.b64encode(pdf_bytes).decode()}},
        {'type': 'text', 'text': 'Parse this transcript.'},
    ]


def _anthropic_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=1,
        )
    return _client


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _check_rate_limit(ip):
    """Returns (allowed, remaining). The window starts at the IP's first request and expires with the cache key."""
    key = f'transcript_ratelimit:{ip}'
    cache.add(key, 0, timeout=WINDOW_SECONDS)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=WINDOW_SECONDS)
        count = 1
    return count <= DAILY_LIMIT, max(DAILY_LIMIT - count, 0)


class TranscriptUploadView(APIView):
    parser_classes = [MultiPartParser]

    @extend_schema(
        request=TranscriptUploadSerializer,
        responses={200: TranscriptParseSerializer, 400: ErrorSerializer, 429: ErrorSerializer},
    )
    def post(self, request):
        if not settings.ANTHROPIC_API_KEY:
            return error_response('ANTHROPIC_API_KEY is not configured.', status.HTTP_500_INTERNAL_SERVER_ERROR)

        upload = TranscriptUploadSerializer(data=request.data)
        if not upload.is_valid():
            return error_response(str(upload.errors['file'][0]), status.HTTP_400_BAD_REQUEST)
        uploaded = upload.validated_data['file']

        allowed, remaining = _check_rate_limit(_get_client_ip(request))
        if not allowed:
            response = error_response(
                f'Daily limit reached. You can parse up to {DAILY_LIMIT} transcripts per day. Please try again tomorrow.',
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
        else:
            response = self._parse(uploaded)
        response['X-RateLimit-Remaining'] = str(remaining)
        return response

    def _parse(self, uploaded):
        try:
            pages_text = []
            pdf_bytes = uploaded.read()
            try:
                with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    if len(pdf.pages) > MAX_PAGES:
                        return error_response(f'PDF has too many pages (max {MAX_PAGES}).', status.HTTP_400_BAD_REQUEST)
                    for page in pdf.pages:
                        text = page.extract_text() or ''
                        if text.strip():
                            pages_text.append(text)
            except Exception:
                logger.warning('Unreadable transcript PDF %r', uploaded.name, exc_info=True)
                return error_response('Could not read the PDF file.', status.HTTP_400_BAD_REQUEST)

            if sum(len(t) for t in pages_text) > MAX_TEXT_CHARS:
                return error_response('Transcript text is too long to parse.', status.HTTP_400_BAD_REQUEST)

            message = _anthropic_client().messages.create(
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': _user_content(pages_text, pdf_bytes)}],
                output_config={'format': {'type': 'json_schema', 'schema': OUTPUT_SCHEMA}},
            )

            logger.info(
                'Transcript parse: mode=%s input_tokens=%s output_tokens=%s stop_reason=%s',
                'text' if pages_text else 'pdf', message.usage.input_tokens, message.usage.output_tokens, message.stop_reason,
            )
            if message.stop_reason == 'max_tokens':
                logger.warning('Transcript parse hit max_tokens for %r', uploaded.name)
                return error_response('Transcript is too long for the parser.', status.HTTP_500_INTERNAL_SERVER_ERROR)

            parsed = json.loads(message.content[0].text)
            courses = parsed['courses']

            for course in courses:
                course['prefix'] = course['prefix'].upper().replace(' ', '')
                course['number'] = course['number'].upper().rstrip('.')
                course['grade'] = course['grade'].upper()
                course['units'] = float(course['units'])

            # Retakes: keep the best grade per course.
            best = {}
            for entry in courses:
                key = f"{entry['prefix']} {entry['number']}"
                rank = GRADE_RANK.get(entry['grade'], -1)
                if key not in best or rank > GRADE_RANK.get(best[key]['grade'], -1):
                    best[key] = entry

            result = {'college': match_college(parsed['institution']), 'courses': list(best.values())}
            return Response(TranscriptParseSerializer(result).data)

        except json.JSONDecodeError:
            logger.warning('Transcript parser returned non-JSON output (stop_reason=%s)', message.stop_reason)
            return error_response('Failed to parse response. Please try again.', status.HTTP_500_INTERNAL_SERVER_ERROR)
        except anthropic.APIError:
            logger.exception('Anthropic API error while parsing transcript')
            return error_response('AI service error. Please try again.', status.HTTP_502_BAD_GATEWAY)
        except Exception:
            logger.exception('Unexpected error while parsing transcript')
            return error_response('Transcript parsing failed.', status.HTTP_500_INTERNAL_SERVER_ERROR)
