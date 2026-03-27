"""
Pydantic models defining the output JSON schema for articulation agreements.

WHY Pydantic:
  We're converting messy web data into structured JSON. Pydantic validates types,
  enforces required fields, and serializes to JSON automatically. If assist.org
  returns unexpected data (missing units, weird course codes), Pydantic catches it
  at parse time rather than producing silently broken output files.

HOW course grouping works on assist.org:
  An articulation "row" maps UC courses to CC courses. But it's not always 1:1.

  - SINGLE: One course satisfies the requirement (most common)
  - AND: Student must take ALL listed courses together (e.g., CS 130A AND CS 130B)
  - OR: Student can take ANY ONE of the listed courses
  - NO_ARTICULATION: No CC course exists that satisfies this UC requirement
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CourseLogic(str, Enum):
    """How multiple courses in a group relate to each other."""
    SINGLE = "SINGLE"           # Exactly one course
    AND = "AND"                 # Must take all courses in the group
    OR = "OR"                   # Can take any one course in the group
    NO_ARTICULATION = "NO_ARTICULATION"  # No equivalent course exists


class Course(BaseModel):
    """A single course (either UC or CC side)."""
    prefix: str = Field(description="Department code, e.g. 'COMPSCI' or 'CS'")
    number: str = Field(description="Course number, e.g. '61A' or '130A'")
    title: str = Field(default="", description="Course title, e.g. 'Structure and Interpretation of Computer Programs'")
    units: Optional[float] = Field(default=None, description="Unit count, e.g. 4.0")


class CourseGroup(BaseModel):
    """
    A group of courses connected by AND/OR logic, or a single course.

    Examples:
      SINGLE: [CS 61A]
      AND:    [CS 130A, CS 130B] — must take both
      OR:     [MATH 4A, MATH 4B] — take either one
    """
    courses: list[Course] = Field(default_factory=list)
    logic: CourseLogic = Field(default=CourseLogic.SINGLE)


class ArticulationRow(BaseModel):
    """
    One row in an articulation agreement — maps UC requirement(s) to CC course(s).

    The receiving side is what the UC requires; the sending side is what the CC offers
    to satisfy that requirement.
    """
    receiving_courses: CourseGroup = Field(
        description="UC courses (the requirement to satisfy)"
    )
    sending_courses: CourseGroup = Field(
        description="CC courses that fulfill the UC requirement"
    )


class AgreementSection(BaseModel):
    """
    A named section within an agreement, grouping related articulation rows.

    Example section titles:
      - "Lower Division Major Requirements"
      - "Preparation for the Major"
      - "General Education Requirements"
    """
    section_title: str = Field(default="", description="Section heading from assist.org")
    rows: list[ArticulationRow] = Field(default_factory=list)


class Agreement(BaseModel):
    """
    Complete articulation agreement for one major between two institutions.

    This is what gets saved as a JSON file — one file per major per UC per year.
    The schema mirrors assist.org's agreement page structure: metadata at the top,
    then sections containing rows of course mappings.
    """
    sending_institution: str = Field(description="CC name, e.g. 'Santa Barbara City College'")
    receiving_institution: str = Field(description="UC name, e.g. 'University of California, Berkeley'")
    major: str = Field(description="Major name as listed on assist.org")
    academic_year: str = Field(description="Academic year string, e.g. '2024-25'")
    url: str = Field(default="", description="Direct URL to this agreement on assist.org")
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    sections: list[AgreementSection] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, description="Footer notes / caveats from the agreement page")


# ---------------------------------------------------------------------------
# Manifest models — track scraping progress for resume capability
# ---------------------------------------------------------------------------

class ScrapeStatus(str, Enum):
    """Status of a single agreement scrape attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # e.g., empty agreement or no articulation exists


class ManifestEntry(BaseModel):
    """
    One entry in the scrape manifest, representing a single (CC, UC, year, major) combo.

    WHY a manifest:
      Scraping all UCs takes time. If the process crashes mid-run, the manifest lets us
      resume where we left off — already-scraped agreements are skipped on the next run.
    """
    sending_code: str
    receiving_code: str
    academic_year: str
    major: str
    status: ScrapeStatus
    file_path: Optional[str] = None
    error: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class Manifest(BaseModel):
    """Top-level manifest tracking all scrape progress."""
    entries: list[ManifestEntry] = Field(default_factory=list)
