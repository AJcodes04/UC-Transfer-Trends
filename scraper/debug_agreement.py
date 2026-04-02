"""
Debug script: fetch the raw API response for a single agreement and dump it.

Usage:
    python -m scraper.debug_agreement SBCC UCSB "Chemistry, B.S."

Saves raw JSON to debug_<cc>_<uc>_<major>.json so you can inspect what
the ASSIST.org API actually returns for this major.
"""

import asyncio
import json
import re
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from scraper.api_client import AssistAPIClient
from scraper.config import CC_INSTITUTIONS, UC_INSTITUTIONS, KNOWN_YEAR_IDS


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


async def main(cc_code: str, uc_code: str, major_filter: str):
    cc = CC_INSTITUTIONS.get(cc_code.upper())
    uc = UC_INSTITUTIONS.get(uc_code.upper())
    if not cc or not uc:
        print(f"Unknown CC or UC code. Available CCs: {list(CC_INSTITUTIONS)}")
        print(f"Available UCs: {list(UC_INSTITUTIONS)}")
        sys.exit(1)

    year_id = KNOWN_YEAR_IDS.get("2025-26", 76)

    async with AssistAPIClient() as client:
        data = await client.get_agreements_for_institution(
            receiving_id=uc["id"],
            sending_id=cc["id"],
            year_id=year_id,
        )
        reports = data.get("reports", [])
        matches = [r for r in reports if major_filter.lower() in r.get("label", "").lower()]

        if not matches:
            print(f"No major matching '{major_filter}' found. Available majors:")
            for r in reports:
                print(f"  {r.get('label')}")
            sys.exit(1)

        report = matches[0]
        print(f"Found: {report['label']} (key={report['key'][:40]}...)")

        detail = await client.get_agreement_detail(report["key"])

        # Parse the double-encoded fields
        result = detail.get("result", {})
        arts_raw = result.get("articulations", "")
        tmpl_raw = result.get("templateAssets", "")

        articulations = json.loads(arts_raw) if isinstance(arts_raw, str) else arts_raw
        template_assets = json.loads(tmpl_raw) if isinstance(tmpl_raw, str) else tmpl_raw

        # Print summary of template structure
        print(f"\n--- TEMPLATE ASSETS ({len(template_assets)} items) ---")
        for item in template_assets:
            t = item.get("type", "?")
            area = item.get("area", "")
            pos = item.get("position", "")
            if t == "RequirementGroup":
                sections = item.get("sections", [])
                conjunction = (item.get("instruction") or {}).get("conjunction", "?")
                total_cells = sum(
                    len(cell.get("cells", []))
                    for s in sections
                    for row in s.get("rows", [])
                    for cell in [row]
                )
                # Actually count cells correctly
                cell_count = sum(
                    1
                    for s in sections
                    for row in s.get("rows", [])
                    for cell in row.get("cells", [])
                )
                print(f"  RequirementGroup  area={area} pos={pos}  conjunction={conjunction}  sections={len(sections)}  cells={cell_count}")
            elif t == "RequirementTitle":
                print(f"  RequirementTitle  area={area} pos={pos}: {item.get('content','')[:60]}")
            else:
                print(f"  {t}  area={area} pos={pos}")

        print(f"\n--- ARTICULATIONS ({len(articulations)} entries) ---")
        no_cell_id = 0
        no_course = 0
        matched = 0
        for entry in articulations:
            cell_id = entry.get("templateCellId")
            art = entry.get("articulation", {})
            course = art.get("course", {}) if art else {}
            if not cell_id:
                no_cell_id += 1
            if not course:
                no_course += 1
            else:
                matched += 1
                prefix = course.get("prefix", "?")
                num = course.get("courseNumber", "?")
                print(f"  cell={str(cell_id)[:8] if cell_id else 'NULL':8}  UC={prefix} {num}")

        print(f"\nSummary: {matched} with UC course, {no_course} missing UC course, {no_cell_id} missing cell ID")

        # Save full raw data to file
        out = {
            "major": report["label"],
            "key": report["key"],
            "template_assets": template_assets,
            "articulations": articulations,
        }
        slug = _slugify(report["label"])
        fname = f"debug_{cc_code.lower()}_{uc_code.lower()}_{slug}.json"
        with open(fname, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nFull data saved to: {fname}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python -m scraper.debug_agreement <CC_CODE> <UC_CODE> <major_name>")
        print("Example: python -m scraper.debug_agreement SBCC UCSB 'Chemistry, B.S.'")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
