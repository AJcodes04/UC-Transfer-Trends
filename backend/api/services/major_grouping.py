"""Builds the grouped major list from Major relationships (canonical = alias of, parent = listed under)."""

from collections import defaultdict

# A major is discontinued when its last data year is more than this many years before the newest data year.
DISCONTINUED_WINDOW_YEARS = 5
MIN_HISTORY_YEARS = 6


def group_majors(major_rows, campus_rows, majors):
    """
    major_rows: dicts with major_id, total_apps, latest_year, earliest_year (one per Major with data).
    campus_rows: dicts with major_id, university (distinct pairs).
    majors: {id: Major} covering every id referenced above.
    """
    active = _active_majors(major_rows, majors)

    campuses = defaultdict(set)
    for row in campus_rows:
        canonical_id = majors[row['major_id']].canonical_id_or_self
        if canonical_id in active:
            campuses[canonical_id].add(row['university'])

    groups = {}
    for major_id in sorted(active, key=lambda i: majors[i].name):
        parent_id = majors[major_id].parent_id
        if parent_id in active and parent_id != major_id:
            groups.setdefault(parent_id, []).append(major_id)
        else:
            groups.setdefault(major_id, [])

    def entry(major_id):
        return {
            'name': majors[major_id].name,
            'campuses': sorted(campuses[major_id]),
            'latest_year': active[major_id]['latest'],
        }

    result = [
        {
            **entry(base_id),
            'total_applicants': active[base_id]['apps'],
            'related': sorted((entry(r) for r in related), key=lambda x: x['name']),
        }
        for base_id, related in groups.items()
    ]
    result.sort(key=lambda x: x['total_applicants'], reverse=True)
    return result


def _active_majors(major_rows, majors):
    """Drop discontinued short-lived majors, then fold aliases into their canonical major."""
    rows = list(major_rows)
    if not rows:
        return {}
    cutoff = max(r['latest_year'] for r in rows) - DISCONTINUED_WINDOW_YEARS

    active = {}
    for row in rows:
        span = row['latest_year'] - row['earliest_year'] + 1
        if row['latest_year'] < cutoff and span < MIN_HISTORY_YEARS:
            continue
        canonical_id = majors[row['major_id']].canonical_id_or_self
        entry = active.setdefault(canonical_id, {'apps': 0, 'latest': 0})
        entry['apps'] += row['total_apps']
        entry['latest'] = max(entry['latest'], row['latest_year'])
    return active
