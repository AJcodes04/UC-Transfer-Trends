"""Builds the grouped major list: alias merging, regex sub-major grouping, explicit absorptions."""

from api.constants.majors import (
    _SUB_MAJOR_RE, ALIAS_TO_CANONICAL, MAJOR_ABSORPTIONS, MAJOR_ALIASES,
)

DISCONTINUED_BEFORE = 2020
MIN_HISTORY_YEARS = 6


def group_majors(major_rows, campus_rows):
    """
    major_rows: dicts with major_name, total_apps, latest_year, earliest_year.
    campus_rows: dicts with major_name, university (distinct pairs).
    """
    major_agg = {row['major_name']: row for row in major_rows}
    active_majors = {
        name: row['total_apps']
        for name, row in major_agg.items()
        if row['latest_year'] >= DISCONTINUED_BEFORE
        or (row['latest_year'] - row['earliest_year'] + 1) >= MIN_HISTORY_YEARS
    }

    major_latest = {
        name: row['latest_year']
        for name, row in major_agg.items()
        if name in active_majors
    }

    for canonical, aliases in MAJOR_ALIASES.items():
        for alias in aliases:
            if alias in active_majors:
                active_majors.setdefault(canonical, 0)
                active_majors[canonical] += active_majors.pop(alias)
                if alias in major_latest:
                    major_latest.setdefault(canonical, 0)
                    major_latest[canonical] = max(
                        major_latest.get(canonical, 0),
                        major_latest.pop(alias),
                    )

    all_names = set(active_majors.keys())
    major_apps = active_majors

    major_campuses = {}
    for row in campus_rows:
        name = ALIAS_TO_CANONICAL.get(row['major_name'], row['major_name'])
        if name in all_names:
            major_campuses.setdefault(name, set()).add(row['university'])

    groups = {}
    assigned = set()

    for name in sorted(all_names):
        match = _SUB_MAJOR_RE.match(name)
        if match:
            candidate_base = match.group(1).strip()
            if candidate_base in all_names and candidate_base != name:
                if candidate_base not in groups:
                    groups[candidate_base] = []
                groups[candidate_base].append(name)
                assigned.add(name)
                continue
        if name not in groups:
            groups[name] = []

    for parent, children in MAJOR_ABSORPTIONS.items():
        if parent not in all_names:
            continue
        if parent not in groups:
            groups[parent] = []
        for child in children:
            if child not in all_names:
                continue
            if child in groups:
                groups[parent].extend(groups.pop(child))
            else:
                for other_base, other_related in groups.items():
                    if child in other_related:
                        other_related.remove(child)
                        break
            if child not in groups[parent]:
                groups[parent].append(child)
            assigned.add(child)

    result = []
    for base, related in groups.items():
        result.append({
            'name': base,
            'total_applicants': major_apps.get(base, 0),
            'latest_year': major_latest.get(base, 0),
            'related': sorted(
                [{'name': r, 'campuses': sorted(major_campuses.get(r, [])),
                  'latest_year': major_latest.get(r, 0)}
                 for r in related],
                key=lambda x: x['name'],
            ),
            'campuses': sorted(major_campuses.get(base, [])),
        })

    result.sort(key=lambda x: x['total_applicants'], reverse=True)
    return result
