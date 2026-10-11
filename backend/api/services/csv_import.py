"""Helpers shared by the CSV import commands: file sniffing, value parsing, keyed upserts."""

import csv
from decimal import Decimal, InvalidOperation


def read_rows(filepath):
    """Yield stripped dict rows from a UC export, handling UTF-8 or UTF-16 and comma or tab delimiters."""
    try:
        with open(filepath, newline='', encoding='utf-8') as f:
            f.read(1)
        encoding = 'utf-8'
    except UnicodeDecodeError:
        encoding = 'utf-16'

    with open(filepath, newline='', encoding=encoding) as f:
        sample = f.read(1024)
        f.seek(0)
        reader = csv.DictReader(f, delimiter='\t' if '\t' in sample else ',')
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        for row in reader:
            yield {k: v.strip() if v else '' for k, v in row.items() if k}


def first_present(row, *keys):
    """First non-empty value among alternative column names (exports renamed columns in 2025)."""
    for key in keys:
        if row.get(key):
            return row[key]
    return ''


def parse_gpa_range(value):
    """'3.64 - 3.93' -> (Decimal('3.64'), Decimal('3.93')); masked or malformed -> (None, None)."""
    if not value or value.lower() == 'masked':
        return None, None
    parts = value.split('-')
    if len(parts) != 2:
        return None, None
    try:
        return Decimal(parts[0].strip()), Decimal(parts[1].strip())
    except (InvalidOperation, ValueError):
        return None, None


def parse_rate(value):
    """'52%' -> 52; blank or malformed -> None."""
    value = (value or '').replace('%', '').strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_int(value):
    """'1,234' -> 1234; blank or malformed -> 0."""
    if not value:
        return 0
    try:
        return int(value.replace(',', ''))
    except ValueError:
        return 0


def upsert(model, rows, unique_fields, update_fields):
    """Insert-or-update rows on the unique key; returns (inserted, updated). Last duplicate key in a file wins."""
    deduped = list({tuple(getattr(r, f) for f in unique_fields): r for r in rows}.values())
    before = model.objects.count()
    model.objects.bulk_create(
        deduped, update_conflicts=True,
        unique_fields=unique_fields, update_fields=update_fields,
    )
    inserted = model.objects.count() - before
    return inserted, len(deduped) - inserted
