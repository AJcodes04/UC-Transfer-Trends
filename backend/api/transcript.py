"""
Transcript PDF parsing endpoint.

This is a stateless endpoint: it accepts a PDF file, extracts text using
pdfplumber, runs regex patterns to find course rows, and returns the
parsed courses as JSON. Nothing is stored on the server.

Community college transcripts typically list courses in a tabular format:
  PREFIX NUMBER   Title                    Units  Grade
  MATH   101      Calculus I                5.0    A
  ENGL   1A       English Composition       3.0    B+

The regex is intentionally broad to handle variations in spacing and
formatting across different community colleges.
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


# Matches lines like: "MATH 101  Calculus I  5.0  A"
# Groups: prefix, number, title (optional), units, grade
# The pattern is flexible about whitespace and handles various title formats.
COURSE_LINE_RE = re.compile(
    r'(?P<prefix>[A-Z]{2,6})\s+'          # Course prefix: 2-6 uppercase letters
    r'(?P<number>\d{1,4}[A-Z]?)\s+'       # Course number: digits, optional letter suffix
    r'(?P<title>.+?)\s+'                   # Title: non-greedy match
    r'(?P<units>\d+\.?\d*)\s+'             # Units: number with optional decimal
    r'(?P<grade>[A-F][+-]?|P|NP|W|CR|NC|I|IP)',  # Grade
    re.IGNORECASE,
)


class TranscriptUploadView(APIView):
    """
    POST /api/transcript/upload/
    Accepts a PDF file via multipart form data, extracts course information
    using text parsing, and returns the courses as a JSON array.

    This is completely stateless — the PDF is parsed in memory and nothing
    is saved. The user reviews the results on the frontend before adding
    courses to their localStorage-backed course list.
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        # Check that pdfplumber is installed
        if not HAS_PDFPLUMBER:
            return Response(
                {'error': 'pdfplumber is not installed. Run: pip install pdfplumber'},
                status=500,
            )

        # Validate that a file was uploaded
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'No file uploaded'}, status=400)

        # Validate file type
        if not uploaded.name.lower().endswith('.pdf'):
            return Response({'error': 'Only PDF files are accepted'}, status=400)

        # Limit file size to 10MB to prevent abuse
        if uploaded.size > 10 * 1024 * 1024:
            return Response({'error': 'File too large (max 10MB)'}, status=400)

        try:
            # Read the PDF and extract text from all pages
            pdf_bytes = uploaded.read()
            courses = []
            seen = set()  # Deduplicate by prefix+number+grade

            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ''
                    for line in text.split('\n'):
                        match = COURSE_LINE_RE.search(line)
                        if not match:
                            continue

                        prefix = match.group('prefix').upper()
                        number = match.group('number').upper()
                        title = match.group('title').strip()
                        units = match.group('units')
                        grade = match.group('grade').upper()

                        # Deduplicate — same course+grade shouldn't appear twice
                        dedup_key = f'{prefix} {number} {grade}'
                        if dedup_key in seen:
                            continue
                        seen.add(dedup_key)

                        courses.append({
                            'prefix': prefix,
                            'number': number,
                            'title': title,
                            'units': float(units),
                            'grade': grade,
                        })

            return Response(courses)

        except Exception as e:
            return Response(
                {'error': f'Failed to parse PDF: {str(e)}'},
                status=400,
            )
