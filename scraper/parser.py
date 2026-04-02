"""
Converts assist.org API responses into structured Pydantic models.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW THE ASSIST.org API STRUCTURES ARTICULATION DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The endpoint /api/articulation/Agreements?Key={key} returns:
{
  "result": {
    "name": "Computer Science, B.A.",
    "templateAssets": "<JSON string>",     // double-encoded
    "articulations": "<JSON string>",      // double-encoded
    ...
  }
}

IMPORTANT: Both "articulations" and "templateAssets" are JSON-within-JSON.
They must be json.loads()'d a second time.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
UNDERSTANDING THE TEMPLATE STRUCTURE (the key to grouping)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
templateAssets is a list of items. Each item has a `type` field:

  GeneralText / GeneralTitle   — Admission notes and headings (general info)
  RequirementTitle             — Section heading, e.g. "REQUIRED FOR ADMISSION"
  RequirementGroup             — The key structure: defines one numbered requirement.

A RequirementGroup looks like:
{
  "type": "RequirementGroup",
  "groupId": "uuid",
  "instruction": {
    "conjunction": "And" | "Or",   // How sections within the group relate
    "selectionType": "Complete",   // "Complete" = follow conjunction rule
  },
  "hideSectionLetters": false,     // false = show "A", "B" labels
  "showConjunctionBetweenSections": false,
  "sections": [
    {
      "type": "Section",
      "advisements": [             // Tells how rows within THIS section relate
        {
          "type": "NFollowing",    // "Select N from the following rows"
          "amount": 1.0,           // N = 1 means "pick 1 course"
          "amountUnitType": "Course",
          "selectionType": "Complete"
        }
      ],
      "rows": [
        {
          "position": 0,
          "cells": [
            {
              "type": "Course",
              "id": "uuid",        // <-- THIS IS THE KEY
              "course": { "prefix": "MATH", "courseNumber": "18", ... }
            }
          ]
        }
      ]
    }
  ]
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW GROUPING LOGIC IS DETERMINED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
We determine how each group should be satisfied by combining two signals:

1. GROUP-LEVEL instruction.conjunction:
   - "Or"  → sections are ALTERNATIVES (select any one complete section)
             This gives us GroupLogic.SELECT_ONE, e.g. "Select A or B"
   - "And" → sections must ALL be satisfied

2. SECTION-LEVEL advisements (NFollowing):
   - Present → "Select N courses from the rows in this section"
               This gives us GroupLogic.SELECT_N, e.g. "Complete 1 from the following"
   - Absent  → "Complete ALL rows in this section" (COMPLETE_ALL)

When a group has multiple sections with "And" between them AND some sections
have NFollowing advisements, we split it into separate sub-groups — one per
section — so each sub-group has a single, clear logic.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW ARTICULATIONS LINK TO GROUPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The "articulations" field is a list of entries, each with:
  {
    "templateCellId": "uuid",   // matches cell.id in templateAssets
    "articulation": {
      "course": { ... },                   // UC (receiving) course
      "sendingArticulation": { ... }       // CC (sending) course options
    }
  }

By matching templateCellId → cell.id → section → RequirementGroup, we know
exactly which group each UC course belongs to. Courses not found in the
template (rare) are collected as ungrouped fallbacks.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from scraper.models import (
    Agreement,
    AgreementSection,
    ArticulationRow,
    Course,
    CourseGroup,
    CourseLogic,
    GroupLogic,
    RequirementGroup,
    RequirementOption,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal data structures used during parsing
# ---------------------------------------------------------------------------

@dataclass
class _CellLocation:
    """Where a template cell lives — which group, section, and row."""
    group_id: str          # RequirementGroup.groupId
    section_idx: int       # Index within group.sections[]
    row_position: int      # Row's position field (for ordering)


@dataclass
class _SectionSpec:
    """Parsed specification for one section within a RequirementGroup."""
    section_idx: int
    select_n: Optional[int]     # None = complete all; int = select N courses
    cell_ids_in_order: list     # Ordered list of cell UUIDs in this section


@dataclass
class _GroupSpec:
    """Parsed specification for one RequirementGroup from templateAssets."""
    group_id: str
    conjunction: str            # "And" or "Or" (between sections)
    hide_section_letters: bool
    section_specs: list         # List[_SectionSpec]
    position: int               # Position within the Requirements area (for ordering)
    section_title: str          # Nearest preceding RequirementTitle text


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_agreement_from_api(
    api_response: dict,
    sending_name: str,
    receiving_name: str,
    major: str,
    academic_year: str,
) -> Agreement:
    """
    Parse the /api/articulation/Agreements response into an Agreement model.

    This is the main entry point. It:
      1. Decodes the double-encoded JSON fields
      2. Parses templateAssets to understand the group structure
      3. Parses articulations and links each entry to its group via templateCellId
      4. Builds RequirementGroup objects with proper SELECT_ONE / SELECT_N / COMPLETE_ALL logic
      5. Falls back to a flat list for any articulations not found in the template
    """
    agreement = Agreement(
        sending_institution=sending_name,
        receiving_institution=receiving_name,
        major=major,
        academic_year=academic_year,
        url="https://assist.org/transfer/results?year=&institution=&agreement=&agreementType=from&view=agreement&viewBy=major",
    )

    result = api_response.get("result")
    if not result:
        logger.warning(f"No 'result' key in API response for {major}")
        return agreement

    # ── Step 1: Decode the double-encoded fields ──────────────────────────
    arts_raw = result.get("articulations", "")
    if not arts_raw:
        logger.warning(f"No articulations field for {major}")
        return agreement

    try:
        articulations = json.loads(arts_raw) if isinstance(arts_raw, str) else arts_raw
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse articulations for {major}: {e}")
        return agreement

    template_raw = result.get("templateAssets", "")
    template_assets = []
    if template_raw:
        try:
            template_assets = json.loads(template_raw) if isinstance(template_raw, str) else template_raw
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse templateAssets for {major}: {e}")

    # ── Step 2: Build cell→group map and ordered group specs from template ─
    cell_to_location, group_specs = _parse_template_structure(template_assets)

    # ── Step 3: Parse all articulation entries into a lookup dict ─────────
    # Maps cell UUID → ArticulationRow (so we can fill in groups by cell ID)
    cell_to_row: dict[str, ArticulationRow] = {}
    ungrouped_rows: list[ArticulationRow] = []

    for entry in articulations:
        row = _parse_articulation_entry(entry)
        if not row:
            continue

        cell_id = entry.get("templateCellId")
        if cell_id and cell_id in cell_to_location:
            cell_to_row[cell_id] = row
        else:
            # Articulation has no template entry — collect as fallback
            ungrouped_rows.append(row)
            if cell_id:
                logger.debug(f"  templateCellId {cell_id} not found in template for {major}")

    # ── Step 4: Assemble RequirementGroups from the template structure ─────
    #
    # We iterate group_specs IN POSITION ORDER (how ASSIST.org numbers them).
    # For each group spec, we build one or more RequirementGroup objects.
    #
    # We bucket groups by section_title so we can create AgreementSection objects.
    section_buckets: dict[str, list[RequirementGroup]] = {}  # title → groups list
    section_order: list[str] = []  # Track insertion order

    group_counter = 1  # Sequential 1-based group number for display

    for gs in group_specs:
        title = gs.section_title or "Lower Division Major Requirements"
        if title not in section_buckets:
            section_buckets[title] = []
            section_order.append(title)

        new_groups = _build_requirement_groups(
            group_spec=gs,
            cell_to_row=cell_to_row,
            group_counter_start=group_counter,
        )

        if new_groups:
            section_buckets[title].extend(new_groups)
            group_counter += len(new_groups)

    # ── Step 5: Build AgreementSection objects ─────────────────────────────
    sections = []

    for title in section_order:
        grps = section_buckets[title]
        # Only include sections that have at least one row somewhere
        non_empty = [
            g for g in grps
            if any(len(opt.rows) > 0 for opt in g.options)
        ]
        if non_empty:
            sections.append(AgreementSection(
                section_title=title,
                groups=non_empty,
            ))

    # ── Step 6: Handle ungrouped fallback rows ─────────────────────────────
    # If the template had no RequirementGroups, or some articulations couldn't
    # be mapped, put them in a fallback section. This ensures we never lose data.
    if ungrouped_rows:
        logger.info(f"  {len(ungrouped_rows)} ungrouped rows for {major} — using fallback section")
        fallback_groups = [
            RequirementGroup(
                group_id=f"ungrouped-{i}",
                group_number=group_counter + i,
                group_label=None,
                group_logic=GroupLogic.COMPLETE_ALL,
                options=[RequirementOption(rows=[row])],
            )
            for i, row in enumerate(ungrouped_rows)
        ]
        if sections:
            # Append to the first (and usually only) section
            sections[0].groups.extend(fallback_groups)
        else:
            sections.append(AgreementSection(
                section_title="Lower Division Major Requirements",
                groups=fallback_groups,
            ))

    # ── Step 7: Final fallback: no template structure at all ───────────────
    # If templateAssets had no RequirementGroups, we still got articulations
    # but couldn't build any groups. Use the flat list approach as a fallback.
    if not sections and articulations:
        logger.info(f"  No template groups found for {major} — falling back to flat list")
        flat_rows = []
        for entry in articulations:
            row = _parse_articulation_entry(entry)
            if row:
                flat_rows.append(row)
        if flat_rows:
            fallback_groups = [
                RequirementGroup(
                    group_id=f"flat-{i}",
                    group_number=i + 1,
                    group_label=None,
                    group_logic=GroupLogic.COMPLETE_ALL,
                    options=[RequirementOption(rows=[row])],
                )
                for i, row in enumerate(flat_rows)
            ]
            sections.append(AgreementSection(
                section_title="Lower Division Major Requirements",
                groups=fallback_groups,
            ))

    if sections:
        agreement.sections = sections

    # ── Step 8: Extract notes from GeneralText items in templateAssets ─────
    notes = _extract_notes(template_assets)
    if notes:
        agreement.notes = notes

    total_rows = sum(
        len(opt.rows)
        for sec in agreement.sections
        for grp in sec.groups
        for opt in grp.options
    )
    logger.info(f"Parsed {major}: {len(agreement.sections)} section(s), "
                f"{sum(len(s.groups) for s in agreement.sections)} group(s), "
                f"{total_rows} total rows")
    return agreement


# ---------------------------------------------------------------------------
# Template parsing helpers
# ---------------------------------------------------------------------------

def _parse_template_structure(
    template_assets: list,
) -> tuple[dict[str, _CellLocation], list[_GroupSpec]]:
    """
    Scan templateAssets and extract:
      1. cell_to_location: maps each cell UUID → _CellLocation
      2. group_specs: ordered list of _GroupSpec (sorted by Requirements area position)

    WHY we sort by position:
      The items list in templateAssets is not guaranteed to be in display order.
      The `position` field within a given `area` tells us the actual order.
      We sort by (area, position) to match ASSIST.org's displayed order.
    """
    cell_to_location: dict[str, _CellLocation] = {}
    group_specs: list[_GroupSpec] = []

    # Track the most recently seen RequirementTitle per area
    # so we can label each RequirementGroup with its preceding section title.
    # Items are sorted by position, so the nearest title before a group is its label.
    last_requirement_title: dict[str, str] = {}  # area → title text

    # Sort items by (area, position) to process in display order
    def sort_key(item):
        area = item.get("area", "ZZZ")  # Unknown area sorts last
        pos = item.get("position", 999)
        return (area, pos)

    sorted_items = sorted(template_assets, key=sort_key)

    for item in sorted_items:
        item_type = item.get("type")
        area = item.get("area", "")

        if item_type == "RequirementTitle":
            # Store this title; it will label the next RequirementGroup in this area
            last_requirement_title[area] = _strip_html(item.get("content", ""))

        elif item_type == "RequirementGroup":
            group_id = item.get("groupId", "")
            instruction = item.get("instruction") or {}
            conjunction = instruction.get("conjunction", "And")
            hide_letters = item.get("hideSectionLetters", False)
            position = item.get("position", 0)

            # Use the most recently seen title in this area as this group's section title
            section_title = last_requirement_title.get(area, "")

            # Parse each section within this group
            section_specs: list[_SectionSpec] = []
            sections = item.get("sections", [])

            for sec_idx, section in enumerate(sections):
                # Check for NFollowing advisement (tells us to "pick N from rows")
                select_n = _extract_select_n(section.get("advisements", []))

                # Collect cell IDs in row order
                # Sort rows by their position field to maintain correct ordering
                rows_sorted = sorted(
                    section.get("rows", []),
                    key=lambda r: r.get("position", 0)
                )
                cell_ids = []
                for row in rows_sorted:
                    for cell in row.get("cells", []):
                        cell_id = cell.get("id")
                        if cell_id:
                            cell_ids.append(cell_id)
                            # Also register the location for articulation lookup
                            cell_to_location[cell_id] = _CellLocation(
                                group_id=group_id,
                                section_idx=sec_idx,
                                row_position=row.get("position", 0),
                            )

                section_specs.append(_SectionSpec(
                    section_idx=sec_idx,
                    select_n=select_n,
                    cell_ids_in_order=cell_ids,
                ))

            group_specs.append(_GroupSpec(
                group_id=group_id,
                conjunction=conjunction,
                hide_section_letters=hide_letters,
                section_specs=section_specs,
                position=position,
                section_title=section_title,
            ))

    return cell_to_location, group_specs


def _extract_select_n(advisements: list) -> Optional[int]:
    """
    Check section advisements for an NFollowing instruction.

    NFollowing means "select N courses from the following rows".
    Returns N as an int, or None if no NFollowing advisement is present
    (meaning all rows in the section are required — COMPLETE_ALL).
    """
    for adv in advisements:
        if adv.get("type") == "NFollowing":
            amount = adv.get("amount")
            if amount is not None:
                return int(amount)
    return None


def _build_requirement_groups(
    group_spec: _GroupSpec,
    cell_to_row: dict[str, ArticulationRow],
    group_counter_start: int,
) -> list[RequirementGroup]:
    """
    Convert a _GroupSpec into one or more RequirementGroup model objects.

    WHY this may return multiple groups:
      When a RequirementGroup has conjunction=And (all sections required) AND
      the sections have different selection logic (some NFollowing, some not),
      we split them into separate RequirementGroup objects — one per section —
      because each represents a distinct logical requirement.

      Example: UCB CS has a group with:
        Section 0 (NFollowing=1): EECS 16A OR MATH 54 OR MATH 56  ← pick 1
        Section 1 (complete all): MATH 1A AND MATH 1B             ← take both
      These become two separate RequirementGroup objects:
        Group A (SELECT_N=1): {EECS 16A, MATH 54, MATH 56}
        Group B (COMPLETE_ALL): {MATH 1A, MATH 1B}

    When conjunction=Or (sections are alternatives), we return ONE group
    with SELECT_ONE logic and multiple RequirementOption objects.
    """
    conjunction = group_spec.conjunction.lower()
    section_specs = group_spec.section_specs

    # ── Case: SELECT_ONE — sections are alternative pathways ──────────────
    # conjunction=Or means "complete any one of the following sections"
    if conjunction == "or":
        options = []
        option_labels = _generate_option_labels(
            len(section_specs),
            hide_letters=group_spec.hide_section_letters,
        )
        for i, ss in enumerate(section_specs):
            rows = _collect_rows_from_cells(ss.cell_ids_in_order, cell_to_row)
            if rows:  # Only include options that have actual articulation data
                options.append(RequirementOption(
                    option_label=option_labels[i],
                    rows=rows,
                ))

        if not options:
            return []

        n_options = len(options)
        label = _make_select_one_label(n_options, group_spec.hide_section_letters)

        return [RequirementGroup(
            group_id=group_spec.group_id,
            group_number=group_counter_start,
            group_label=label,
            group_logic=GroupLogic.SELECT_ONE,
            options=options,
        )]

    # ── Case: AND between sections ─────────────────────────────────────────
    # Each section may have its own selection logic (NFollowing or complete-all).
    # If all sections are uniform, produce one group.
    # If they differ, produce one group per section.

    # Determine if all sections have the same logic
    all_select_n = [ss.select_n for ss in section_specs]
    are_uniform = (len(set(str(n) for n in all_select_n)) <= 1)

    # Also check: if there's only ONE section, always produce one group
    if len(section_specs) == 1 or are_uniform:
        ss0 = section_specs[0]

        if len(section_specs) == 1:
            # Single section — simple case
            all_cell_ids = ss0.cell_ids_in_order
            select_n_val = ss0.select_n
        else:
            # Multiple uniform sections — flatten all cells into one pool
            all_cell_ids = []
            for ss in section_specs:
                all_cell_ids.extend(ss.cell_ids_in_order)
            select_n_val = all_select_n[0]

        rows = _collect_rows_from_cells(all_cell_ids, cell_to_row)
        if not rows:
            return []

        if select_n_val is not None:
            logic = GroupLogic.SELECT_N
            label = _make_select_n_label(select_n_val)
        else:
            logic = GroupLogic.COMPLETE_ALL
            label = None  # No special label for "complete all"

        return [RequirementGroup(
            group_id=group_spec.group_id,
            group_number=group_counter_start,
            group_label=label,
            group_logic=logic,
            select_n=select_n_val,
            options=[RequirementOption(rows=rows)],
        )]

    else:
        # Non-uniform sections with And conjunction — split into sub-groups
        result_groups = []
        for i, ss in enumerate(section_specs):
            rows = _collect_rows_from_cells(ss.cell_ids_in_order, cell_to_row)
            if not rows:
                continue

            if ss.select_n is not None:
                logic = GroupLogic.SELECT_N
                label = _make_select_n_label(ss.select_n)
            else:
                logic = GroupLogic.COMPLETE_ALL
                label = None

            result_groups.append(RequirementGroup(
                group_id=f"{group_spec.group_id}__sec{i}",
                group_number=group_counter_start + len(result_groups),
                group_label=label,
                group_logic=logic,
                select_n=ss.select_n,
                options=[RequirementOption(rows=rows)],
            ))
        return result_groups


def _collect_rows_from_cells(
    cell_ids: list[str],
    cell_to_row: dict[str, ArticulationRow],
) -> list[ArticulationRow]:
    """
    Look up rows for each cell ID and return them in order.
    Cells with no articulation entry are skipped (no CC equivalent was found).
    """
    rows = []
    seen = set()
    for cell_id in cell_ids:
        if cell_id in cell_to_row and cell_id not in seen:
            rows.append(cell_to_row[cell_id])
            seen.add(cell_id)
    return rows


def _generate_option_labels(
    n_sections: int,
    hide_letters: bool,
) -> list[Optional[str]]:
    """
    Generate option labels (A, B, C, ...) for SELECT_ONE groups.

    If hideSectionLetters=True, ASSIST.org doesn't show A/B labels,
    which typically means "Complete 1 from the following" (unlabeled options).
    If False, labels are shown: Option A, Option B, etc.
    """
    if hide_letters:
        return [None] * n_sections
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [letters[i] if i < len(letters) else str(i + 1) for i in range(n_sections)]


def _make_select_one_label(n_options: int, hide_letters: bool) -> Optional[str]:
    """
    Generate a human-readable group label for SELECT_ONE groups.

    Examples:
      hide_letters=False, 2 options → "Select A or B"
      hide_letters=False, 3 options → "Select A, B, or C"
      hide_letters=True             → "Complete 1 option from the following"
    """
    if hide_letters:
        return "Complete 1 option from the following"
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:n_options])
    if len(letters) == 1:
        return None  # Single option = standalone
    if len(letters) == 2:
        return f"Select {letters[0]} or {letters[1]}"
    return "Select " + ", ".join(letters[:-1]) + f", or {letters[-1]}"


def _make_select_n_label(n: int) -> str:
    """Generate a human-readable label for SELECT_N groups."""
    unit = "course" if n == 1 else "courses"
    return f"Complete {n} {unit} from the following"


# ---------------------------------------------------------------------------
# Articulation entry parsing
# ---------------------------------------------------------------------------

def _parse_articulation_entry(entry: dict) -> Optional[ArticulationRow]:
    """
    Parse one entry from the articulations array.

    TWO formats exist depending on whether the UC side is a single course or a
    multi-course sequence:

    Single course (art.type != "Series"):
      {
        "templateCellId": "uuid",
        "articulation": {
          "course": { "prefix": "MATH", "courseNumber": "3A", ... },
          "sendingArticulation": { ... }
        }
      }

    Series / sequence (art.type == "Series"):
      {
        "templateCellId": "uuid",
        "articulation": {
          "type": "Series",
          "series": {
            "conjunction": "And",
            "courses": [
              { "prefix": "CHEM", "courseNumber": "1A", ... },
              { "prefix": "CHEM", "courseNumber": "1B", ... },
              ...
            ]
          },
          "sendingArticulation": { ... }
        }
      }

    Series entries appear for requirements like "CHEM 1A AND 1B AND 1C" where
    the entire sequence together satisfies a group.  Without handling this,
    the whole chemistry / physics group rows are silently dropped.
    """
    art = entry.get("articulation", {})
    if not art:
        return None

    art_type = art.get("type", "")

    # ── Series: multi-course UC sequence ──────────────────────────────────
    if art_type == "Series":
        series = art.get("series", {})
        series_courses_raw = series.get("courses", []) if isinstance(series, dict) else []
        receiving_courses = [c for c in (_parse_course(cd) for cd in series_courses_raw) if c]
        if not receiving_courses:
            return None
        logic = CourseLogic.AND if len(receiving_courses) > 1 else CourseLogic.SINGLE
        receiving = CourseGroup(courses=receiving_courses, logic=logic)

    # ── Single course ──────────────────────────────────────────────────────
    else:
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

    # ── Sending (CC) courses ───────────────────────────────────────────────
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
    # Structure:
    #   items = [
    #     { "courseConjunction": "And" | "Or", "items": [course, ...] },
    #     ...
    #   ]
    # Multiple item groups are separated by courseGroupConjunctions (And/Or between groups)
    sending_groups = sending_art.get("items", [])
    all_sending_courses = []
    within_group_logic = CourseLogic.SINGLE

    for group in sending_groups:
        conjunction = group.get("courseConjunction", "And").lower()
        courses_in_group = group.get("items", [])

        for course_data in courses_in_group:
            course = _parse_course(course_data)
            if course:
                all_sending_courses.append(course)

        # Conjunction within a group tells how courses in that group relate
        if len(courses_in_group) > 1:
            within_group_logic = CourseLogic.OR if "or" in conjunction else CourseLogic.AND

    # Conjunction BETWEEN groups (multiple item groups with "Or" = OR between them)
    group_conjunctions = sending_art.get("courseGroupConjunctions", [])
    if group_conjunctions:
        for gc in group_conjunctions:
            if gc.get("courseConjunction", "").lower() == "or":
                within_group_logic = CourseLogic.OR

    # Assign final logic based on course count
    if len(all_sending_courses) == 0:
        sending = CourseGroup(courses=[], logic=CourseLogic.NO_ARTICULATION)
    elif len(all_sending_courses) == 1:
        sending = CourseGroup(courses=all_sending_courses, logic=CourseLogic.SINGLE)
    else:
        sending = CourseGroup(courses=all_sending_courses, logic=within_group_logic)

    return ArticulationRow(receiving_courses=receiving, sending_courses=sending)


def _parse_course(data: dict) -> Optional[Course]:
    """Parse a single course object from the API response."""
    prefix = data.get("prefix", "")
    number = data.get("courseNumber", "")
    title = data.get("courseTitle", "")
    units = data.get("minUnits")

    if not prefix and not number:
        return None

    return Course(
        prefix=prefix.strip(),
        number=str(number).strip(),
        title=title.strip() if title else "",
        units=float(units) if units is not None else None,
    )


# ---------------------------------------------------------------------------
# Notes extraction
# ---------------------------------------------------------------------------

def _extract_notes(template_assets: list) -> list[str]:
    """
    Extract admission notes from GeneralText items in templateAssets.

    GeneralText items contain HTML with general information about the major —
    admission requirements, advising notes, AP/IB credit policies, etc.
    We strip HTML tags and return the plain text.
    """
    notes = []
    for item in template_assets:
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
