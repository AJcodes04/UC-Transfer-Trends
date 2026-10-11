"""Builds the grouped major list: alias merging, regex sub-major grouping, explicit absorptions."""

from collections import defaultdict

from api.constants.majors import _SUB_MAJOR_RE, ALIAS_TO_CANONICAL, MAJOR_ABSORPTIONS

# A major is discontinued when its last data year is more than this many years before the newest data year.
DISCONTINUED_WINDOW_YEARS = 5
MIN_HISTORY_YEARS = 6


def group_majors(major_rows, campus_rows):
    """
    major_rows: dicts with major_name, total_apps, latest_year, earliest_year.
    campus_rows: dicts with major_name, university (distinct pairs).
    """
    active = _active_majors(major_rows)
    names = set(active)

    campuses = defaultdict(set)
    for row in campus_rows:
        name = ALIAS_TO_CANONICAL.get(row['major_name'], row['major_name'])
        if name in names:
            campuses[name].add(row['university'])

    groups = _group_by_sub_major(names)
    _apply_absorptions(groups, names)

    result = [
        {
            'name': base,
            'total_applicants': active[base]['apps'],
            'latest_year': active[base]['latest'],
            'campuses': sorted(campuses[base]),
            'related': sorted(
                ({'name': r, 'campuses': sorted(campuses[r]), 'latest_year': active[r]['latest']}
                 for r in related),
                key=lambda x: x['name'],
            ),
        }
        for base, related in groups.items()
    ]
    result.sort(key=lambda x: x['total_applicants'], reverse=True)
    return result


def _active_majors(major_rows):
    """Drop discontinued short-lived majors, then fold aliases into their canonical name."""
    rows = list(major_rows)
    if not rows:
        return {}
    cutoff = max(r['latest_year'] for r in rows) - DISCONTINUED_WINDOW_YEARS

    active = {}
    for row in rows:
        span = row['latest_year'] - row['earliest_year'] + 1
        if row['latest_year'] < cutoff and span < MIN_HISTORY_YEARS:
            continue
        name = ALIAS_TO_CANONICAL.get(row['major_name'], row['major_name'])
        entry = active.setdefault(name, {'apps': 0, 'latest': 0})
        entry['apps'] += row['total_apps']
        entry['latest'] = max(entry['latest'], row['latest_year'])
    return active


def _group_by_sub_major(names):
    """'Chemistry - Organic' nests under 'Chemistry' when the base name is itself a major."""
    groups = {}
    for name in sorted(names):
        match = _SUB_MAJOR_RE.match(name)
        base = match.group(1).strip() if match else None
        if base and base != name and base in names:
            groups.setdefault(base, []).append(name)
        else:
            groups.setdefault(name, [])
    return groups


def _apply_absorptions(groups, names):
    for parent, children in MAJOR_ABSORPTIONS.items():
        if parent not in names:
            continue
        related = groups.setdefault(parent, [])
        for child in children:
            if child not in names:
                continue
            if child in groups:
                related.extend(groups.pop(child))
            else:
                for other in groups.values():
                    if child in other:
                        other.remove(child)
                        break
            if child not in related:
                related.append(child)
