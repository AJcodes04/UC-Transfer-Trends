"""Applies the alias and grouping rules in api.constants.majors onto Major rows."""

from api.constants.majors import _SUB_MAJOR_RE, MAJOR_ABSORPTIONS, MAJOR_ALIASES


def sync_major_groups(Major=None):
    """Recompute canonical/parent for every Major; idempotent. Returns (aliases, grouped) counts."""
    if Major is None:
        from api.models import Major
    for name in MAJOR_ALIASES:
        Major.objects.get_or_create(name=name)

    majors = {m.name: m for m in Major.objects.order_by().all()}
    for m in majors.values():
        m.canonical_id = None
        m.parent_id = None

    for canonical_name, aliases in MAJOR_ALIASES.items():
        canonical = majors[canonical_name]
        for alias in aliases:
            if alias in majors:
                majors[alias].canonical_id = canonical.id

    primary = {name: m for name, m in majors.items() if m.canonical_id is None}

    for name, m in primary.items():
        match = _SUB_MAJOR_RE.match(name)
        base = match.group(1).strip() if match else None
        if base and base != name and base in primary:
            m.parent_id = primary[base].id

    for parent_name, children in MAJOR_ABSORPTIONS.items():
        parent = primary.get(parent_name)
        if parent is None:
            continue
        for child_name in children:
            child = primary.get(child_name)
            if child is None or child is parent:
                continue
            for other in primary.values():
                if other.parent_id == child.id:
                    other.parent_id = parent.id
            child.parent_id = parent.id

    Major.objects.bulk_update(majors.values(), ['canonical', 'parent'], batch_size=500)
    aliases = sum(1 for m in majors.values() if m.canonical_id)
    grouped = sum(1 for m in majors.values() if m.parent_id)
    return aliases, grouped
