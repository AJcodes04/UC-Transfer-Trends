"""
Pydantic models defining the output JSON schema for articulation agreements.

WHY Pydantic:
  We're converting messy web data into structured JSON. Pydantic validates types,
  enforces required fields, and serializes to JSON automatically. If assist.org
  returns unexpected data (missing units, weird course codes), Pydantic catches it
  at parse time rather than producing silently broken output files.

SCHEMA OVERVIEW (new grouped format):
  Agreement
    └── sections[]          (e.g. "Lower Division Major Requirements")
          └── groups[]      (one numbered requirement group from ASSIST.org)
                └── options[]   (one or more pathway options within the group)
                      └── rows[]  (ArticulationRow: one UC course ↔ CC course mapping)

HOW GROUPS WORK:
  ASSIST.org organizes requirements into numbered groups. A group can be:

  COMPLETE_ALL  — The student must complete every row in the group.
                  Example: MATH 18 (standalone), COMPSCI 61A + 61B + 61C (all required)

  SELECT_ONE    — The student picks any ONE complete pathway option.
                  Example: "Select A or B"
                    Option A: MATH 10A AND 10B AND 10C
                    Option B: MATH 20A AND 20B

  SELECT_N      — The student picks N individual courses from a pool.
                  Example: "Complete 1 course from the following: COGS 10 OR DSGN 1"

HOW COURSE LOGIC WORKS (within a row):
  Each ArticulationRow maps one UC requirement to CC courses. The CC side uses:
  - SINGLE: One CC course satisfies the UC requirement
  - AND: Student must take ALL listed CC courses together
  - OR: Student can take ANY ONE of the listed CC courses
  - NO_ARTICULATION: No CC course exists that satisfies this UC requirement

BACKWARDS COMPATIBILITY:
  Old JSON files (scraped before this rewrite) use sections[].rows[] (flat list).
  New files use sections[].groups[].options[].rows[].
  Both the backend (views.py) and frontend (courseMatch.js, TransferRequirements.jsx)
  handle both formats so the app keeps working while files are re-scraped.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Course-level models (unchanged from original)
# ---------------------------------------------------------------------------

class CourseLogic(str, Enum):
    """How multiple courses in a group relate to each other (CC side of a row)."""
    SINGLE = "SINGLE"           # Exactly one course
    AND = "AND"                 # Must take all courses in the group
    OR = "OR"                   # Can take any one course in the group
    NO_ARTICULATION = "NO_ARTICULATION"  # No equivalent course exists


class Course(BaseModel):
    """A single course (either UC or CC side)."""
    prefix: str = Field(description="Department code, e.g. 'COMPSCI' or 'CS'")
    number: str = Field(description="Course number, e.g. '61A' or '130A'")
    title: str = Field(default="", description="Course title")
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


# ---------------------------------------------------------------------------
# NEW: Requirement group models — capture ASSIST.org's grouped structure
# ---------------------------------------------------------------------------

class GroupLogic(str, Enum):
    """
    How a requirement group is satisfied.

    COMPLETE_ALL — Must complete every row in the group.
                   e.g., standalone course, or "take all of these"

    SELECT_ONE   — Pick any ONE complete pathway option.
                   e.g., "Select A or B" — complete all rows in option A,
                   OR complete all rows in option B.

    SELECT_N     — Pick exactly N individual courses from a pool.
                   e.g., "Complete 1 course from the following"
                   The pool is all rows in the single option.
    """
    COMPLETE_ALL = "COMPLETE_ALL"
    SELECT_ONE   = "SELECT_ONE"
    SELECT_N     = "SELECT_N"


class RequirementOption(BaseModel):
    """
    One pathway option within a requirement group.

    For COMPLETE_ALL: a single option containing all required rows.
    For SELECT_ONE:   each option is a complete independent pathway.
    For SELECT_N:     a single option listing all the alternate rows to pick from.
    """
    option_label: Optional[str] = Field(
        default=None,
        description="Letter label shown by ASSIST.org, e.g. 'A', 'B'. Null for unlabeled options."
    )
    rows: list[ArticulationRow] = Field(default_factory=list)


class RequirementGroup(BaseModel):
    """
    A numbered requirement group from ASSIST.org's template.

    Each group counts as ONE requirement for completion tracking purposes.
    A group is satisfied when its group_logic condition is met:
      - COMPLETE_ALL: every row's sending_courses is satisfied
      - SELECT_ONE:   any single option's rows are all satisfied
      - SELECT_N:     at least select_n individual rows are satisfied

    HOW THIS MAPS TO ASSIST.org'S API STRUCTURE:
      The templateAssets field has RequirementGroup items, each containing
      sections[]. Each section has rows[], each row has cells[] with id (UUID).
      The articulations field has entries with templateCellId = cell.id.
      This links each articulation to its group/section/row in the template.
    """
    group_id: str = Field(
        description="UUID from templateAssets groupId — links to the raw API structure"
    )
    group_number: int = Field(
        description="1-based sequential position within the section (for display)"
    )
    group_label: Optional[str] = Field(
        default=None,
        description=(
            "Human-readable group instruction, e.g. 'Select A or B' or "
            "'Complete 1 course from the following'. Null for standalone requirements."
        )
    )
    group_logic: GroupLogic = Field(
        default=GroupLogic.COMPLETE_ALL,
        description="How this group is satisfied — COMPLETE_ALL, SELECT_ONE, or SELECT_N"
    )
    select_n: Optional[int] = Field(
        default=None,
        description="For SELECT_N groups: how many courses the student must pick"
    )
    options: list[RequirementOption] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Section and Agreement models (updated to use groups)
# ---------------------------------------------------------------------------

class AgreementSection(BaseModel):
    """
    A named section within an agreement, grouping related requirement groups.

    Example section titles:
      - "Lower Division Major Requirements"
      - "Preparation for the Major"

    BACKWARDS COMPATIBILITY NOTE:
      Old scraped files have `rows` (flat list). New files have `groups`.
      Both fields are kept here so Pydantic can deserialize both formats.
      Code that reads agreements should prefer `groups` when present and
      fall back to building a synthetic single-group from `rows` when not.
    """
    section_title: str = Field(default="", description="Section heading from assist.org")
    groups: list[RequirementGroup] = Field(
        default_factory=list,
        description="Structured requirement groups (new format)"
    )
    rows: list[ArticulationRow] = Field(
        default_factory=list,
        description="[DEPRECATED] Flat row list from old-format scraped files. "
                    "New files populate groups[] instead."
    )


class Agreement(BaseModel):
    """
    Complete articulation agreement for one major between two institutions.

    Saved as a JSON file — one file per major per UC per year.
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
