"""
Transcript PDF parsing endpoint. Extracts text from uploaded PDFs
with pdfplumber and sends it to the Claude API for structured course
extraction. Rate-limited to 3 parses per IP per day.
"""

import io
import json
import os
import time

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

# Rate limit: max parses per IP per day
DAILY_LIMIT = 5

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


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _check_rate_limit(ip):
    """Returns (allowed, remaining, reset_seconds)."""
    cache_key = f'transcript_ratelimit:{ip}'
    data = cache.get(cache_key)

    now = time.time()
    if data is None:
        # First request today
        data = {'count': 1, 'first_request': now}
        cache.set(cache_key, data, timeout=86400)
        return True, DAILY_LIMIT - 1

    # Check if 24h window has passed
    elapsed = now - data['first_request']
    if elapsed >= 86400:
        data = {'count': 1, 'first_request': now}
        cache.set(cache_key, data, timeout=86400)
        return True, DAILY_LIMIT - 1

    if data['count'] >= DAILY_LIMIT:
        return False, 0

    data['count'] += 1
    remaining_ttl = int(86400 - elapsed)
    cache.set(cache_key, data, timeout=remaining_ttl)
    return True, DAILY_LIMIT - data['count']


class TranscriptUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        if not HAS_PDFPLUMBER:
            return Response(
                {'error': 'pdfplumber is not installed.'},
                status=500,
            )

        if not HAS_ANTHROPIC:
            return Response(
                {'error': 'anthropic package is not installed.'},
                status=500,
            )

        api_key = os.getenv('ANTHROPIC_API_KEY', '')
        if not api_key:
            return Response(
                {'error': 'ANTHROPIC_API_KEY is not configured.'},
                status=500,
            )

        # Rate limit check
        client_ip = _get_client_ip(request)
        allowed, remaining = _check_rate_limit(client_ip)
        if not allowed:
            return Response(
                {'error': 'Daily limit reached. You can parse up to 3 transcripts per day. Please try again tomorrow.'},
                status=429,
            )

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'No file uploaded'}, status=400)

        if not uploaded.name.lower().endswith('.pdf'):
            return Response({'error': 'Only PDF files are accepted'}, status=400)

        if uploaded.size > 10 * 1024 * 1024:
            return Response({'error': 'File too large (max 10MB)'}, status=400)

        try:
            # Extract text from PDF
            pdf_bytes = uploaded.read()
            pages_text = []

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ''
                    if text.strip():
                        pages_text.append(text)

            if not pages_text:
                return Response(
                    {'error': 'Could not extract any text from the PDF.'},
                    status=400,
                )

            full_text = '\n\n--- PAGE BREAK ---\n\n'.join(pages_text)

            # Send to Claude for parsing
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

            # Strip markdown code fences if present
            if response_text.startswith('```'):
                response_text = response_text.split('\n', 1)[1]
                if response_text.endswith('```'):
                    response_text = response_text[:-3]
                response_text = response_text.strip()

            courses = json.loads(response_text)

            if not isinstance(courses, list):
                return Response(
                    {'error': 'Unexpected response format from parser.'},
                    status=500,
                )

            # Normalize fields
            for course in courses:
                course['prefix'] = str(course.get('prefix', '')).upper().replace(' ', '')
                course['number'] = str(course.get('number', '')).upper().rstrip('.')
                course['title'] = str(course.get('title', ''))
                course['grade'] = str(course.get('grade', '')).upper()
                try:
                    course['units'] = float(course.get('units', 0))
                except (ValueError, TypeError):
                    course['units'] = 0.0

            # Deduplicate: keep best grade per course
            grade_rank = {
                'F': 0, 'D-': 1, 'D': 2, 'D+': 3,
                'C-': 4, 'C': 5, 'C+': 6,
                'B-': 7, 'B': 8, 'B+': 9,
                'A-': 10, 'A': 11, 'A+': 12,
                'NP': -2, 'P': 13,
                'W': -3, 'FW': -3, 'I': -4, 'IP': -5, 'NC': -2, 'CR': 13,
            }

            best = {}
            for entry in courses:
                key = f"{entry['prefix']} {entry['number']}"
                rank = grade_rank.get(entry['grade'], -1)
                if key not in best or rank > grade_rank.get(best[key]['grade'], -1):
                    best[key] = entry

            result = list(best.values())

            response = Response(result)
            response['X-RateLimit-Remaining'] = str(remaining)
            return response

        except json.JSONDecodeError:
            return Response(
                {'error': 'Failed to parse response. Please try again.'},
                status=500,
            )
        except anthropic.APIError as e:
            return Response(
                {'error': f'AI service error: {str(e)}'},
                status=502,
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to parse PDF: {str(e)}'},
                status=400,
            )
