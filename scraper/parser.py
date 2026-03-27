"""
Converts assist.org API responses into structured Pydantic models.

HOW assist.org's API structures articulation data:
  The endpoint /api/articulation/Agreements?Key={key} returns:
  {
    "result": {
      "name": "Computer Science, B.A.",
      "templateAssets": "<JSON string>",     // HTML notes, double-encoded
      "articulations": "<JSON string>",      // course data, double-encoded
      ...
    }
  }

  IMPORTANT: "articulations" and "templateAssets" are JSON strings within JSON.
  They must be json.loads()'d a second time to get the actual data.

  The "articulations" field parses to a list of entries, each mapping one UC
  (receiving) course to CC (sending) course(s):

  [
    {
      "articulation": {
        "course": {                              // UC course
          "prefix": "COMPSCI", "courseNumber": "61B",
          "courseTitle": "Data Structures",
          "minUnits": 4.0, "maxUnits": 4.0
        },
        "sendingArticulation": {
          "noArticulationReason": null,           // non-null = no CC equivalent
          "items": [                              // CC course groups
            {
              "courseConjunction": "And" | "Or",
              "items": [                          // individual CC courses
                {"prefix": "CS", "courseNumber": "106", ...}
              ]
            }
          ],
          "courseGroupConjunctions": [...]         // OR between groups
        }
      }
    }
  ]
"""

import json
import logging
import re
from typing import Optional

from scraper.models import (
    Agreement,
    AgreementSection,
    ArticulationRow,
    Course,
    CourseGroup,
    CourseLogic,
)

logger = logging.getLogger(__name__)


def parse_agreement_from_api(
    api_response: dict,
    sending_name: str,
    receiving_name: str,
    major: str,
    academic_year: str,
) -> Agreement:
    """
    Parse the /api/articulation/Agreements response into an Agreement model.

    This is the main entry point. It handles the double-encoded JSON fields
    and delegates to helper functions for course parsing.
    """
    agreement = Agreement(
        sending_institution=sending_name,
        receiving_institution=receiving_name,
        major=major,
        academic_year=academic_year,
        url=f"https://assist.org/transfer/results?year=&institution=&agreement=&agreementType=from&view=agreement&viewBy=major",
    )

    result = api_response.get("result")
    if not result:
        logger.warning(f"No 'result' key in API response for {major}")
        return agreement

    # Parse the double-encoded articulations field
    arts_raw = result.get("articulations", "")
    if not arts_raw:
        logger.warning(f"No articulations field for {major}")
        return agreement

    try:
        articulations = json.loads(arts_raw) if isinstance(arts_raw, str) else arts_raw
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse articulations for {major}: {e}")
        return agreement

    # Convert each articulation entry into a row
    rows = []
    for entry in articulations:
        row = _parse_articulation_entry(entry)
        if row:
            rows.append(row)

    if rows:
        agreement.sections = [
            AgreementSection(
                section_title="Lower Division Major Requirements",
                rows=rows,
            )
        ]

    # Extract notes from templateAssets
    notes = _extract_notes(result)
    if notes:
        agreement.notes = notes

    logger.info(f"Parsed {major}: {len(rows)} articulation rows")
    return agreement


def _parse_articulation_entry(entry: dict) -> Optional[ArticulationRow]:
    """
    Parse one entry from the articulations array.

    Each entry maps one UC (receiving) course to zero or more CC (sending) courses.
    """
    art = entry.get("articulation", {})
    if not art:
        return None

    # --- Receiving (UC) course ---
    course_data = art.get("course", {})
    if not course_data:
        return None

    receiving_course = Course(
        prefix=course_data.get("prefix", ""),
        number=course_data.get("courseNumber", ""),
        title=course_data.get("courseTitle", ""),
        units=course_data.get("minUnits"),
    )
    receiving = CourseGroup(courses=[receiving_course], logic=CourseLogic.SINGLE)

    # --- Sending (CC) courses ---
    sending_art = art.get("sendingArticulation", {})
    if not sending_art:
        return ArticulationRow(
            receiving_courses=receiving,
            sending_courses=CourseGroup(courses=[], logic=CourseLogic.NO_ARTICULATION),
        )

    # "No Course Articulated" — no CC course satisfies this UC requirement
    no_artic_reason = sending_art.get("noArticulationReason")
    if no_artic_reason:
        return ArticulationRow(
            receiving_courses=receiving,
            sending_courses=CourseGroup(courses=[], logic=CourseLogic.NO_ARTICULATION),
        )

    # Parse sending course groups
    # Structure: items = [ {courseConjunction, items: [course, course, ...]}, ... ]
    sending_groups = sending_art.get("items", [])
    all_sending_courses = []
    group_logic = CourseLogic.SINGLE

    for group in sending_groups:
        conjunction = group.get("courseConjunction", "And").lower()
        courses_in_group = group.get("items", [])

        for course_data in courses_in_group:
            course = _parse_course(course_data)
            if course:
                all_sending_courses.append(course)

        # Conjunction within a group tells how courses relate
        if len(courses_in_group) > 1:
            group_logic = CourseLogic.OR if "or" in conjunction else CourseLogic.AND

    # Check for OR between groups (courseGroupConjunctions)
    group_conjunctions = sending_art.get("courseGroupConjunctions", [])
    if group_conjunctions:
        for gc in group_conjunctions:
            if gc.get("courseConjunction", "").lower() == "or":
                group_logic = CourseLogic.OR

    # Final logic based on course count
    if len(all_sending_courses) == 0:
        sending = CourseGroup(courses=[], logic=CourseLogic.NO_ARTICULATION)
    elif len(all_sending_courses) == 1:
        sending = CourseGroup(courses=all_sending_courses, logic=CourseLogic.SINGLE)
    else:
        sending = CourseGroup(courses=all_sending_courses, logic=group_logic)

    return ArticulationRow(receiving_courses=receiving, sending_courses=sending)


def _parse_course(data: dict) -> Optional[Course]:
    """Parse a single course from the API response."""
    prefix = data.get("prefix", "")
    number = data.get("courseNumber", "")
    title = data.get("courseTitle", "")
    units = data.get("minUnits")

    if not prefix and not number:
        return None

    return Course(
        prefix=prefix.strip(),
        number=str(number).strip(),
        title=title.strip(),
        units=float(units) if units is not None else None,
    )


def _extract_notes(result: dict) -> list[str]:
    """
    Extract admission notes from templateAssets.

    templateAssets is a double-encoded JSON string containing a list of objects.
    Objects with type "GeneralText" have HTML content with admission info.
    """
    template_raw = result.get("templateAssets", "")
    if not template_raw:
        return []

    try:
        templates = json.loads(template_raw) if isinstance(template_raw, str) else template_raw
    except (json.JSONDecodeError, ValueError):
        return []

    notes = []
    for item in templates:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "GeneralText":
            html = item.get("content", "")
            text = _strip_html(html)
            if text and len(text) > 10:
                notes.append(text)

    return notes


def _strip_html(html: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
