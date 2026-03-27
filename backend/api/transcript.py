"""
Stateless transcript PDF parsing endpoint. Accepts a PDF, extracts
course rows via regex, and returns parsed courses as JSON.
"""

import re
import io

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


COURSE_LINE_RE = re.compile(
    r'(?P<prefix>[A-Z]{2,6})\s+'
    r'(?P<number>\d{1,4}[A-Z]?)\s+'
    r'(?P<title>.+?)\s+'
    r'(?P<units>\d+\.?\d*)\s+'
    r'(?P<grade>[A-F][+-]?|P|NP|W|CR|NC|I|IP)',
    re.IGNORECASE,
)


class TranscriptUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        if not HAS_PDFPLUMBER:
            return Response(
                {'error': 'pdfplumber is not installed. Run: pip install pdfplumber'},
                status=500,
            )

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'No file uploaded'}, status=400)

        if not uploaded.name.lower().endswith('.pdf'):
            return Response({'error': 'Only PDF files are accepted'}, status=400)

        if uploaded.size > 10 * 1024 * 1024:
            return Response({'error': 'File too large (max 10MB)'}, status=400)

        try:
            pdf_bytes = uploaded.read()
            raw_entries = []

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ''
                    for line in text.split('\n'):
                        match = COURSE_LINE_RE.search(line)
                        if not match:
                            continue

                        raw_entries.append({
                            'prefix': match.group('prefix').upper(),
                            'number': match.group('number').upper(),
                            'title': match.group('title').strip(),
                            'units': float(match.group('units')),
                            'grade': match.group('grade').upper(),
                        })

            grade_rank = {
                'F': 0, 'D-': 1, 'D': 2, 'D+': 3,
                'C-': 4, 'C': 5, 'C+': 6,
                'B-': 7, 'B': 8, 'B+': 9,
                'A-': 10, 'A': 11, 'A+': 12,
                'NP': -2, 'P': 13,
                'W': -3, 'I': -4, 'IP': -5, 'NC': -2, 'CR': 13,
            }

            best = {}
            for entry in raw_entries:
                key = f"{entry['prefix']} {entry['number']}"
                rank = grade_rank.get(entry['grade'], -1)
                if key not in best or rank > grade_rank.get(best[key]['grade'], -1):
                    best[key] = entry

            courses = list(best.values())
            return Response(courses)

        except Exception as e:
            return Response(
                {'error': f'Failed to parse PDF: {str(e)}'},
                status=400,
            )
