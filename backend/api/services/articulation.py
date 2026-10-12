"""Read access to the scraper's articulation JSON files under data/articulation."""

import json
import logging
import re
from pathlib import Path

from django.core.cache import cache

from api.constants.institutions import CC_NAMES, UC_NAMES

logger = logging.getLogger(__name__)

ARTICULATION_DIR = Path(__file__).resolve().parents[3] / 'data' / 'articulation'
FAILED_SCRAPES_FILE = ARTICULATION_DIR / 'failed_scrapes.json'

_CODE_RE = re.compile(r'^[a-z0-9_-]+$')
CACHE_SECONDS = 3600


def _stamp(*paths):
    """Key fragment that changes when any listed directory gains or loses an entry, or a file is rewritten."""
    return '-'.join(str(p.stat().st_mtime_ns) for p in paths if p.exists())


def _year_dirs(uc_dir):
    return sorted((d for d in uc_dir.iterdir() if d.is_dir()), key=lambda d: d.name)


def slugify(text):
    """Mirror of the scraper's filename slug so failure-log major names can be matched to files."""
    text = re.sub(r'[&/]+', '_', text.lower().strip())
    return re.sub(r'[^a-z0-9]+', '_', text).strip('_')


def articulation_dir(*codes):
    """Join URL codes under ARTICULATION_DIR, or None if any code is not a plain slug or the dir is missing."""
    codes = [c.lower() for c in codes]
    if not all(_CODE_RE.match(c) for c in codes):
        return None
    path = ARTICULATION_DIR.joinpath(*codes)
    return path if path.is_dir() else None


def agreement_files(cc_code, uc_code):
    """Map major slug -> newest agreement file across every academic year folder."""
    uc_dir = articulation_dir(cc_code, uc_code)
    if uc_dir is None:
        return {}
    files = {}
    for year_dir in _year_dirs(uc_dir):
        for json_file in year_dir.glob('*.json'):
            files[json_file.stem] = json_file
    return files


def count_rows(agreement_data):
    """Number of UC requirements a student must satisfy; alternatives in a choice group count once."""
    count = 0
    for section in agreement_data.get('sections', []):
        groups = section.get('groups', [])
        if not groups:
            count += len(section.get('rows', []))
            continue
        for group in groups:
            option_sizes = [len(o.get('rows', [])) for o in group.get('options', [])]
            logic = group.get('group_logic')
            if logic == 'SELECT_ONE':
                count += max(option_sizes, default=0)
            elif logic == 'SELECT_N' and group.get('select_n'):
                count += min(group['select_n'], sum(option_sizes))
            else:
                count += sum(option_sizes)
    return count


def list_colleges():
    """Community colleges whose folder holds every UC campus, i.e. fully scraped."""
    if not ARTICULATION_DIR.is_dir():
        return []
    cc_dirs = [d for d in ARTICULATION_DIR.iterdir() if d.is_dir()]
    key = f'art:colleges:{_stamp(ARTICULATION_DIR, *cc_dirs)}'
    return cache.get_or_set(key, _build_colleges, CACHE_SECONDS)


def _build_colleges():
    all_ucs = set(UC_NAMES)
    colleges = []
    for cc_dir in sorted(ARTICULATION_DIR.iterdir()):
        if not cc_dir.is_dir() or cc_dir.name.startswith('_'):
            continue
        uc_dirs = {d.name for d in cc_dir.iterdir() if d.is_dir()}
        if all_ucs.issubset(uc_dirs):
            colleges.append({'code': cc_dir.name, 'name': CC_NAMES.get(cc_dir.name, cc_dir.name.upper())})
    return colleges


def list_campuses(cc_code):
    cc_dir = articulation_dir(cc_code)
    if cc_dir is None:
        return []
    key = f'art:campuses:{cc_dir.name}:{_stamp(cc_dir)}'
    return cache.get_or_set(key, lambda: [
        {'code': d.name, 'name': UC_NAMES.get(d.name, d.name.upper())}
        for d in sorted(cc_dir.iterdir()) if d.is_dir()
    ], CACHE_SECONDS)


def list_majors(cc_code, uc_code):
    uc_dir = articulation_dir(cc_code, uc_code)
    if uc_dir is None:
        return []
    key = f'art:majors:{uc_dir.parent.name}:{uc_dir.name}:{_stamp(uc_dir, *_year_dirs(uc_dir))}'
    return cache.get_or_set(key, lambda: _build_majors(cc_code, uc_code), CACHE_SECONDS)


def _build_majors(cc_code, uc_code):
    majors = []
    for slug, json_file in sorted(agreement_files(cc_code, uc_code).items()):
        try:
            data = json.loads(json_file.read_text())
        except json.JSONDecodeError:
            logger.warning('Skipping malformed agreement file %s', json_file)
            continue
        majors.append({
            'slug': slug,
            'name': data.get('major', slug),
            'academic_year': data.get('academic_year', json_file.parent.name),
            'row_count': count_rows(data),
        })
    return majors


def agreement_path(cc_code, uc_code, major_slug):
    """Path of the newest agreement file for the slug, or None."""
    return agreement_files(cc_code, uc_code).get(major_slug)


def load_agreement(cc_code, uc_code, major_slug):
    """Parsed agreement JSON, or None when no file exists for the slug."""
    json_file = agreement_path(cc_code, uc_code, major_slug)
    if json_file is None:
        return None
    return json.loads(json_file.read_text())


def list_failed(cc_code, uc_code):
    """Majors the scraper failed to fetch for a cc -> uc pair and that still have no agreement file."""
    if not FAILED_SCRAPES_FILE.exists():
        return []
    uc_dir = articulation_dir(cc_code, uc_code)
    year_dirs = _year_dirs(uc_dir) if uc_dir else []
    key = f'art:failed:{cc_code.lower()}:{uc_code.lower()}:{_stamp(FAILED_SCRAPES_FILE, *year_dirs)}'
    return cache.get_or_set(key, lambda: _build_failed(cc_code, uc_code), CACHE_SECONDS)


def _build_failed(cc_code, uc_code):
    try:
        entries = json.loads(FAILED_SCRAPES_FILE.read_text())
    except json.JSONDecodeError:
        logger.warning('Malformed failed-scrapes log %s', FAILED_SCRAPES_FILE)
        return []

    cc = cc_code.upper()
    uc = uc_code.upper()
    scraped = set(agreement_files(cc_code, uc_code))

    seen = set()
    failed = []
    for entry in entries:
        if entry.get('sending_code') != cc or entry.get('receiving_code') != uc:
            continue
        major = entry.get('major') or ''
        key = (major, entry.get('academic_year'))
        if key in seen or slugify(major) in scraped:
            continue
        seen.add(key)
        failed.append({'major': major, 'academic_year': entry.get('academic_year')})

    failed.sort(key=lambda e: e['major'].lower())
    return failed
