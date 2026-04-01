"""
migrate_to_groups.py — Patch existing flat-row JSON files to the new grouped format.

WHY THIS EXISTS:
  The parser rewrite (parser.py) correctly captures ASSIST.org's RequirementGroup
  structure from the API. But 7000+ already-scraped JSON files use the old flat
  sections[].rows[] format. Those files need to be re-scraped to get the proper
  group structure from the API's templateAssets.

  Until the full re-scrape can be done, this script provides a TEMPORARY FIX by
  reading each file's "Important Information" notes text to identify which courses
  are optional (SELECT_ONE sequences) and which are mandatory (COMPLETE_ALL).

THE APPROACH:
  ASSIST.org advisors write notes like:
    "Students must choose one of the following Math sequences:
     Math 10ABC and 18 or Math 20AB and 18."
  or:
    "Students must choose one of the following two-course sequences:
     Business Analytics: ECON 1 and ECON 3
     Machine Learning: COGS 14A-B
     Science: BILD 1 and BILD 3"

  We parse these to:
  1. Identify SELECT_ONE course groups (courses that are alternatives of each other)
  2. Find their intersection (courses in ALL options → standalone COMPLETE_ALL)
  3. Map the flat rows to groups accordingly
  4. Convert the file to new sections[].groups[] format

LIMITATIONS (why re-scraping is still needed):
  - Note parsing is heuristic and may miss some patterns
  - Missing courses (courses that had no CC articulation) are still missing
    — the API's templateAssets shows ALL UC courses even with no CC equiv;
    the old parser only stored courses that had articulation entries
  - The template structure is authoritative; notes are just advisories

USAGE:
  # Dry run — show what changes would be made (no files written)
  python -m scraper.migrate_to_groups --dry-run

  # Migrate all files
  python -m scraper.migrate_to_groups

  # Migrate a single CC→UC pair
  python -m scraper.migrate_to_groups --from sbcc --to ucsd

  # Verbose output
  python -m scraper.migrate_to_groups --verbose
"""

import argparse
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)

ARTICULATION_DIR = Path(__file__).resolve().parent.parent / 'data' / 'articulation'


# ─────────────────────────────────────────────────────────────────────────────
# Course key normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize_key(prefix: str, number: str) -> str:
    return f"{prefix.strip().upper()} {str(number).strip().upper()}"


def course_key_from_row(row: dict) -> Optional[str]:
    courses = row.get('receiving_courses', {}).get('courses', [])
    if not courses:
        return None
    return normalize_key(courses[0].get('prefix', ''), courses[0].get('number', ''))


# ─────────────────────────────────────────────────────────────────────────────
# Course code expansion: "10ABC" → ["10A","10B","10C"]
# ─────────────────────────────────────────────────────────────────────────────

def expand_course_number(number_str: str) -> list[str]:
    """
    Expand a multi-letter course number suffix into individual numbers.

    Examples:
      "10ABC"  → ["10A", "10B", "10C"]
      "20AB"   → ["20A", "20B"]
      "14A-B"  → ["14A", "14B"]
      "14AB"   → ["14A", "14B"]
      "3A"     → ["3A"]          (single letter — no expansion needed)
      "61A"    → ["61A"]
    """
    # Range form: "14A-B" → base=14, range A..B
    range_match = re.match(r'^(\d+)([A-Z])-([A-Z])$', number_str.strip())
    if range_match:
        base = range_match.group(1)
        start_ch = ord(range_match.group(2))
        end_ch = ord(range_match.group(3))
        return [f"{base}{chr(c)}" for c in range(start_ch, end_ch + 1)]

    # Multi-letter suffix: "10ABC" → base=10, suffix=ABC (2+ letters)
    multi_match = re.match(r'^(\d+)([A-Z]{2,})$', number_str.strip())
    if multi_match:
        base = multi_match.group(1)
        letters = multi_match.group(2)
        # Only expand if letters are consecutive (A,B,C or similar)
        codes = [ord(l) for l in letters]
        is_consecutive = all(codes[i + 1] == codes[i] + 1 for i in range(len(codes) - 1))
        if is_consecutive:
            return [f"{base}{l}" for l in letters]
        # Non-consecutive multi-letter (e.g. "1AC") — return as-is
        return [number_str.strip()]

    # Single letter or plain number — return as-is
    return [number_str.strip()]


def parse_course_list_from_text(segment: str, default_dept: str = '') -> list[str]:
    """
    Extract UC course keys from a text segment.

    Handles patterns like:
      "MATH 10A, 10B, 10C"      → [MATH 10A, MATH 10B, MATH 10C]
      "Math 10ABC"               → [MATH 10A, MATH 10B, MATH 10C]
      "COGS 14A-B"               → [COGS 14A, COGS 14B]
      "ECON 1 and ECON 3"        → [ECON 1, ECON 3]
      "POLI 5 and 30"            → [POLI 5, POLI 30]
    """
    keys = []
    current_dept = default_dept

    # Find all (dept, number) or (standalone_number) tokens
    # We look for optional dept prefix + course number patterns
    pattern = re.compile(
        r'\b'
        r'(?:([A-Z]{2,6})\s+)?'      # optional dept code (2-6 uppercase letters)
        r'(\d+[A-Z]{0,4}(?:-[A-Z])?)'  # course number with optional letter suffix
        r'\b',
        re.IGNORECASE
    )

    for m in pattern.finditer(segment):
        dept = (m.group(1) or current_dept).upper().strip()
        raw_num = m.group(2).upper().strip()

        if dept:
            current_dept = dept

        for expanded in expand_course_number(raw_num):
            key = normalize_key(dept, expanded)
            if key.strip() and dept:
                keys.append(key)

    return keys


# ─────────────────────────────────────────────────────────────────────────────
# Note text → SELECT_ONE sequence detection
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SelectOneSpec:
    """Specification for a SELECT_ONE group discovered from notes text."""
    label: str                          # Human-readable group label
    options: list[list[str]]            # Each option is a list of course keys
    standalone: list[str] = field(default_factory=list)  # Courses in ALL options → standalone


def _extract_math_sequence(note_text: str) -> Optional[SelectOneSpec]:
    """
    Parse the classic UCSD Cog Sci / Psychology pattern:
      "Students must choose one of the following Math sequences:
       Math 10ABC and 18 or Math 20AB and 18"
    or:
      "Math 10ABC or Math 20AB and 18"

    Returns a SelectOneSpec with the two sequences, or None if not found.
    """
    # Pattern: "... Math sequences: <seq1> or <seq2>"
    # or: "... Math sequence: <seq1> or <seq2>"
    m = re.search(
        r'(?:choose one of the following|following)\s+math\s+sequence[s]?\s*[:\.]?\s*'
        r'([^.]{5,200})',
        note_text,
        re.IGNORECASE
    )
    if not m:
        return None

    segment = m.group(1).strip()

    # Split on ' or ' (case insensitive) to get the two sequence options
    # Must be a word-boundary ' or ' not 'and' or embedded in a word
    parts = re.split(r'\s+or\s+', segment, flags=re.IGNORECASE)
    if len(parts) < 2:
        return None

    # Parse each part's course list, defaulting prefix to MATH if none given
    options = []
    for part in parts:
        # Trim trailing punctuation / URLs
        part = re.split(r'https?://', part)[0].strip(' .,;')
        if not part:
            continue
        courses = parse_course_list_from_text(part, default_dept='MATH')
        if courses:
            options.append(courses)

    if len(options) < 2:
        return None

    # Courses that appear in ALL options are standalone requirements
    all_sets = [set(opt) for opt in options]
    intersection = all_sets[0].intersection(*all_sets[1:])

    # Remove intersection from each option
    clean_options = [
        [c for c in opt if c not in intersection]
        for opt in options
    ]
    # Drop options that became empty after removing intersection
    clean_options = [o for o in clean_options if o]

    if len(clean_options) < 2:
        return None

    return SelectOneSpec(
        label="Select A or B",
        options=clean_options,
        standalone=list(intersection),
    )


def _extract_named_sequence(note_text: str) -> Optional[SelectOneSpec]:
    """
    Parse the UCSD Data Science pattern:
      "Students must choose one of the following two-course sequences:
       Business Analytics: ECON 1 and ECON 3
       Machine Learning: COGS 14A-B
       Science: BILD 1 and BILD 3
       Social Sciences: (POLI 5 and POLI 30) or (SOCI 60 and USP 4)"

    Each named sequence is one option. If a sequence itself has a sub-OR
    (like "(POLI 5 and POLI 30) or (SOCI 60 and USP 4)"), we split it into
    two sub-options.

    Notes are stored as a single long string (no newlines), so we locate
    "Name:" boundaries by finding title-case words containing lowercase
    letters followed by a colon — distinguishing them from all-caps course
    codes like "ECON 1".
    """
    # Find the starting segment — use DOTALL since notes are a single line string
    m = re.search(
        r'(?:students must choose|choose one of the following)[^.]{0,80}'
        r'(?:two-course\s+)?sequences?\s*[(:]\s*'
        r'(.+)',
        note_text,
        re.IGNORECASE | re.DOTALL
    )
    if not m:
        return None

    block = m.group(1)

    # Truncate at AP/IB credit section or other major markers
    block = re.split(r'(?:UC\s+San\s+Diego\s+Advanced|Advanced\s+Placement|upper.division)', block, flags=re.I)[0]
    block = block.strip()

    if not block:
        return None

    # Find "Name:" boundaries. A valid name contains at least one lowercase letter
    # (distinguishing "Business Analytics:" from "ECON 1" course codes) and must
    # start after whitespace (not after a hyphen like "14A-B Science:").
    name_starts = [
        ms for ms in re.finditer(r'(?:^|(?<=\s))([A-Z][A-Za-z\s,&/()]+?)\s*:\s*', block)
        if re.search(r'[a-z]', ms.group(1))
        and len(ms.group(1).strip()) >= 3
        and len(ms.group(1).strip()) <= 60
    ]

    if not name_starts:
        return None

    # Extract text for each entry (from after "Name:" to before the next "Name:")
    options = []
    for i, nm in enumerate(name_starts):
        end = name_starts[i + 1].start() if i + 1 < len(name_starts) else len(block)
        course_str = block[nm.end():end].strip()

        if not course_str:
            continue

        # Handle sub-OR: "(POLI 5 and POLI 30) or (SOCI 60 and USP 4)"
        if re.search(r'\bor\b', course_str, re.I):
            sub_parts = re.split(r'\bor\b', course_str, flags=re.I)
            for sp in sub_parts:
                sp = sp.strip('() ')
                courses = parse_course_list_from_text(sp)
                if courses:
                    options.append(courses)
        else:
            courses = parse_course_list_from_text(course_str)
            if courses:
                options.append(courses)

    if len(options) < 2:
        return None

    # Compute intersection → standalone
    all_sets = [set(opt) for opt in options]
    intersection = all_sets[0].intersection(*all_sets[1:])
    clean_options = [[c for c in opt if c not in intersection] for opt in options]
    clean_options = [o for o in clean_options if o]

    if len(clean_options) < 2:
        return None

    n = len(clean_options)
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:n])
    if n == 2:
        label = "Select A or B"
    else:
        label = "Select " + ", ".join(letters[:-1]) + f", or {letters[-1]}"

    return SelectOneSpec(
        label=label,
        options=clean_options,
        standalone=list(intersection),
    )


def parse_select_one_specs(notes: list[str]) -> list[SelectOneSpec]:
    """
    Parse all notes and return a list of SELECT_ONE specs found.
    Tries each extraction strategy in order, stopping when one succeeds.
    """
    if not notes:
        return []

    full_text = ' '.join(notes)
    specs = []

    # Try math sequence first (most common pattern)
    math_spec = _extract_math_sequence(full_text)
    if math_spec:
        specs.append(math_spec)

    # Try named sequences (Data Science pattern)
    named_spec = _extract_named_sequence(full_text)
    if named_spec:
        # Avoid duplicating if math_spec already found some of the same courses
        existing_keys = {k for s in specs for opt in s.options for k in opt}
        named_keys = {k for opt in named_spec.options for k in opt}
        if not named_keys.issubset(existing_keys):
            specs.append(named_spec)

    return specs


# ─────────────────────────────────────────────────────────────────────────────
# Convert flat rows to grouped structure
# ─────────────────────────────────────────────────────────────────────────────

def migrate_section(section: dict) -> dict:
    """
    Convert a section with flat rows[] into a section with groups[].

    Rows that belong to a SELECT_ONE sequence are grouped together.
    All other rows become individual COMPLETE_ALL groups.
    """
    rows = section.get('rows', [])
    if not rows:
        return section  # Empty section, nothing to do

    notes = section.get('_notes', [])  # Injected by caller
    specs = parse_select_one_specs(notes)

    # Build a row lookup: course_key → row
    key_to_row = {}
    for row in rows:
        k = course_key_from_row(row)
        if k:
            key_to_row[k] = row

    # Track which rows have been assigned to a SELECT_ONE group
    assigned_keys: set[str] = set()
    groups = []
    group_number = 1

    # ── Build SELECT_ONE groups from specs ────────────────────────────────
    for spec in specs:
        options_out = []
        option_labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:len(spec.options)])

        for i, option_courses in enumerate(spec.options):
            option_rows = []
            for key in option_courses:
                if key in key_to_row:
                    option_rows.append(key_to_row[key])
                    assigned_keys.add(key)
                # If key not in rows: the course had no CC articulation — skip it
                # (it would show as "No Course Articulated" if we had it)

            if option_rows:
                options_out.append({
                    'option_label': option_labels[i] if i < len(option_labels) else None,
                    'rows': option_rows,
                })

        if len(options_out) >= 2:
            # Only add SELECT_ONE group if at least 2 options have rows
            groups.append({
                'group_id': f'migrated-select1-{group_number}',
                'group_number': group_number,
                'group_label': spec.label,
                'group_logic': 'SELECT_ONE',
                'select_n': None,
                'options': options_out,
            })
            group_number += 1
        elif len(options_out) == 1:
            # Only one option had rows — treat as COMPLETE_ALL (can't pick between nothing)
            for row in options_out[0]['rows']:
                k = course_key_from_row(row)
                if k:
                    assigned_keys.discard(k)  # Unassign so it falls to COMPLETE_ALL below

    # ── Remaining rows → individual COMPLETE_ALL groups ───────────────────
    # Preserve original row order for unassigned rows
    for row in rows:
        k = course_key_from_row(row)
        if k and k in assigned_keys:
            continue  # Already in a SELECT_ONE group

        groups.append({
            'group_id': f'migrated-{group_number}',
            'group_number': group_number,
            'group_label': None,
            'group_logic': 'COMPLETE_ALL',
            'select_n': None,
            'options': [{'option_label': None, 'rows': [row]}],
        })
        group_number += 1

    new_section = dict(section)
    new_section['groups'] = groups
    # Keep rows field but empty it (preserved for reference if needed)
    new_section['rows'] = []
    new_section.pop('_notes', None)
    return new_section


def _flatten_groups_to_rows(section: dict) -> list[dict]:
    """
    Extract all rows from a section's groups back into a flat list.
    Used for force-re-migration of already-migrated files.
    """
    rows = []
    for group in section.get('groups', []):
        for option in group.get('options', []):
            rows.extend(option.get('rows', []))
    return rows


def migrate_agreement(data: dict, force: bool = False) -> tuple[dict, dict]:
    """
    Migrate one agreement JSON from old format to new grouped format.

    Returns (new_data, stats) where stats is a dict with info about what changed.

    If force=True, re-migrates files that are already in the new format by
    flattening their groups back to rows and re-applying SELECT_ONE detection.
    """
    sections = data.get('sections', [])
    if not sections:
        return data, {'skipped': True, 'reason': 'no sections'}

    # Check if already in new format
    first_section = sections[0]
    already_new = first_section.get('groups') and not first_section.get('rows')
    if already_new and not force:
        return data, {'skipped': True, 'reason': 'already new format'}

    if already_new and force:
        # Re-inflate rows from existing groups so migrate_section can re-process
        for section in sections:
            if not section.get('rows'):
                section['rows'] = _flatten_groups_to_rows(section)
                section['groups'] = []

    notes = data.get('notes', [])
    specs = parse_select_one_specs(notes)

    total_rows_before = sum(len(s.get('rows', [])) for s in sections)
    select_one_count = 0

    new_sections = []
    for section in sections:
        section_copy = dict(section)
        section_copy['_notes'] = notes  # Inject notes for migration
        new_sec = migrate_section(section_copy)
        new_sections.append(new_sec)

        for grp in new_sec.get('groups', []):
            if grp.get('group_logic') == 'SELECT_ONE':
                select_one_count += 1

    total_groups_after = sum(len(s.get('groups', [])) for s in new_sections)

    new_data = dict(data)
    new_data['sections'] = new_sections

    return new_data, {
        'skipped': False,
        'rows_before': total_rows_before,
        'groups_after': total_groups_after,
        'select_one_groups': select_one_count,
        'specs_found': len(specs),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main migration runner
# ─────────────────────────────────────────────────────────────────────────────

def run_migration(
    cc_filter: Optional[str] = None,
    uc_filter: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False,
    force: bool = False,
) -> dict:
    """
    Run the migration over all matching JSON files.

    Returns summary statistics.
    """
    json_files = sorted(ARTICULATION_DIR.rglob('*.json'))
    json_files = [f for f in json_files if '_discovery' not in str(f)]

    if cc_filter:
        json_files = [f for f in json_files if f.parts[-4] == cc_filter.lower()]
    if uc_filter:
        json_files = [f for f in json_files if f.parts[-3] == uc_filter.lower()]

    stats = {
        'total': len(json_files),
        'already_new_format': 0,
        'migrated': 0,
        'with_select_one': 0,
        'errors': 0,
        'skipped_no_sections': 0,
    }

    for fpath in json_files:
        try:
            data = json.loads(fpath.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read {fpath}: {e}")
            stats['errors'] += 1
            continue

        new_data, info = migrate_agreement(data, force=force)

        if info.get('skipped'):
            reason = info.get('reason', '')
            if 'already new' in reason:
                stats['already_new_format'] += 1
            else:
                stats['skipped_no_sections'] += 1
            continue

        stats['migrated'] += 1
        if info.get('select_one_groups', 0) > 0:
            stats['with_select_one'] += 1

        if verbose:
            rows = info.get('rows_before', 0)
            groups = info.get('groups_after', 0)
            sel1 = info.get('select_one_groups', 0)
            major = data.get('major', fpath.stem)
            cc = fpath.parts[-4]
            uc = fpath.parts[-3]
            if sel1 > 0:
                logger.info(f"  [{cc}→{uc}] {major}: {rows} rows → {groups} groups ({sel1} SELECT_ONE)")

        if not dry_run:
            fpath.write_text(json.dumps(new_data, indent=2, default=str))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Migrate articulation JSON files from flat rows to grouped format'
    )
    parser.add_argument('--from', dest='cc', default=None,
                        help='Filter by community college code (e.g. sbcc)')
    parser.add_argument('--to', dest='uc', default=None,
                        help='Filter by UC code (e.g. ucsd)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would change without writing files')
    parser.add_argument('--verbose', action='store_true',
                        help='Log details for every file changed')
    parser.add_argument('--force', action='store_true',
                        help='Re-migrate files already in the new format (re-applies SELECT_ONE detection)')
    args = parser.parse_args()

    scope = f"{'all CCs' if not args.cc else args.cc} → {'all UCs' if not args.uc else args.uc}"
    mode = 'DRY RUN — ' if args.dry_run else ''
    logger.info(f"{mode}Migrating articulation data for {scope}...")

    result = run_migration(
        cc_filter=args.cc,
        uc_filter=args.uc,
        dry_run=args.dry_run,
        verbose=args.verbose,
        force=getattr(args, 'force', False),
    )

    logger.info(f"\nMigration complete ({mode.strip(':')})")
    logger.info(f"  Total files processed: {result['total']}")
    logger.info(f"  Already new format:    {result['already_new_format']}")
    logger.info(f"  Migrated:              {result['migrated']}")
    logger.info(f"  With SELECT_ONE groups:{result['with_select_one']}")
    logger.info(f"  Skipped (no sections): {result['skipped_no_sections']}")
    logger.info(f"  Errors:                {result['errors']}")


if __name__ == '__main__':
    main()
