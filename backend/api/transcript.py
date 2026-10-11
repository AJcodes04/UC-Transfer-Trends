"""
Transcript PDF parsing endpoint. Extracts text from uploaded PDFs
with pdfplumber and sends it to the Claude API for structured course
extraction. Rate-limited per IP per day (see DAILY_LIMIT).
"""

import io
import json
import logging
import os

from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

logger = logging.getLogger(__name__)

DAILY_LIMIT = 5
WINDOW_SECONDS = 86400
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

SYSTEM_PROMPT = """You are a transcript parser. Given the raw text extracted from a community college transcript PDF, extract every course into a JSON array.

Each course object must have exactly these fields:
- "prefix": the department/subject code in uppercase (e.g. "CIS", "MATH", "PE"). If the prefix has a space like "P E", collapse it to "PE".
- "number": the course number including any letter suffix, in uppercase (e.g. "022A", "001B", "21JA"). Strip any trailing periods.
- "title": the course title as shown, in title case.
- "units": the number of units/credits as a number (e.g. 4.5, 5.0).
- "grade": the letter grade (e.g. "A", "A-", "B+", "W", "P", "NP"). For in-progress courses use "IP".

Rules:
- Include ALL courses: completed, in-progress, withdrawn, passed, etc.
- Do NOT include summary lines (GPA, total units, etc.), institution headers, or non-course text.
- The transcript text may have watermark artifacts (random single letters scattered in the text). Ignore them.
- If the same course appears multiple times (retakes), include all instances — deduplication is handled downstream.
- Return ONLY the JSON array, no other text or markdown formatting."""

GRADE_RANK = {
    'F': 0, 'D-': 1, 'D': 2, 'D+': 3,
    'C-': 4, 'C': 5, 'C+': 6,
    'B-': 7, 'B': 8, 'B+': 9,
    'A-': 10, 'A': 11, 'A+': 12,
    'NP': -2, 'P': 13,
    'W': -3, 'FW': -3, 'I': -4, 'IP': -5, 'NC': -2, 'CR': 13,
}


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


def _validate_upload(uploaded):
    if not uploaded:
        return 'No file uploaded'
    if not uploaded.name.lower().endswith('.pdf'):
        return 'Only PDF files are accepted'
    if uploaded.size > MAX_UPLOAD_BYTES:
        return 'File too large (max 10MB)'
    return None


class TranscriptUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        if not HAS_PDFPLUMBER:
            return Response({'error': 'pdfplumber is not installed.'}, status=500)
        if not HAS_ANTHROPIC:
            return Response({'error': 'anthropic package is not installed.'}, status=500)

        api_key = os.getenv('ANTHROPIC_API_KEY', '')
        if not api_key:
            return Response({'error': 'ANTHROPIC_API_KEY is not configured.'}, status=500)

        uploaded = request.FILES.get('file')
        problem = _validate_upload(uploaded)
        if problem:
            return Response({'error': problem}, status=400)

        allowed, remaining = _check_rate_limit(_get_client_ip(request))
        if not allowed:
            response = Response(
                {'error': f'Daily limit reached. You can parse up to {DAILY_LIMIT} transcripts per day. Please try again tomorrow.'},
                status=429,
            )
        else:
            response = self._parse(uploaded, api_key)
        response['X-RateLimit-Remaining'] = str(remaining)
        return response

    def _parse(self, uploaded, api_key):
        try:
            pages_text = []
            try:
                with pdfplumber.open(io.BytesIO(uploaded.read())) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text() or ''
                        if text.strip():
                            pages_text.append(text)
            except Exception:
                logger.warning('Unreadable transcript PDF %r', uploaded.name, exc_info=True)
                return Response({'error': 'Could not read the PDF file.'}, status=400)

            if not pages_text:
                return Response({'error': 'Could not extract any text from the PDF.'}, status=400)

            full_text = '\n\n--- PAGE BREAK ---\n\n'.join(pages_text)

            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[
                    {'role': 'user', 'content': f'Parse this transcript:\n\n{full_text}'}
                ],
            )

            response_text = message.content[0].text.strip()
            if response_text.startswith('```'):
                response_text = response_text.split('\n', 1)[1]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

            courses = json.loads(response_text)
            if not isinstance(courses, list):
                return Response({'error': 'Unexpected response format from parser.'}, status=500)

            for course in courses:
                course['prefix'] = str(course.get('prefix', '')).upper().replace(' ', '')
                course['number'] = str(course.get('number', '')).upper().rstrip('.')
                course['title'] = str(course.get('title', ''))
                course['grade'] = str(course.get('grade', '')).upper()
                try:
                    course['units'] = float(course.get('units', 0))
                except (ValueError, TypeError):
                    course['units'] = 0.0

            # Retakes: keep the best grade per course.
            best = {}
            for entry in courses:
                key = f"{entry['prefix']} {entry['number']}"
                rank = GRADE_RANK.get(entry['grade'], -1)
                if key not in best or rank > GRADE_RANK.get(best[key]['grade'], -1):
                    best[key] = entry

            return Response(list(best.values()))

        except json.JSONDecodeError:
            logger.warning('Transcript parser returned non-JSON output (stop_reason=%s)', message.stop_reason)
            return Response({'error': 'Failed to parse response. Please try again.'}, status=500)
        except anthropic.APIError:
            logger.exception('Anthropic API error while parsing transcript')
            return Response({'error': 'AI service error. Please try again.'}, status=502)
        except Exception:
            logger.exception('Unexpected error while parsing transcript')
            return Response({'error': 'Transcript parsing failed.'}, status=500)
