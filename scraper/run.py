"""
CLI entrypoint for the assist.org scraper.

USAGE:
  # Run discovery on one agreement page (inspect XHR + DOM output)
  python -m scraper.run discover --from SBCC --to UCB

  # Scrape a single major for testing
  python -m scraper.run scrape --from SBCC --to UCB --major "Computer Science" --debug

  # Scrape all majors for one UC
  python -m scraper.run scrape --from SBCC --to UCB

  # Scrape all UCs for one CC
  python -m scraper.run scrape --from SBCC --to ALL

  # Scrape ALL community colleges → ALL UCs
  python -m scraper.run scrape --from ALL --to ALL

  # Override academic year
  python -m scraper.run scrape --from SBCC --to UCB --year 2023-24

  # Run with visible browser for debugging
  python -m scraper.run scrape --from SBCC --to UCB --headful --debug

  # List available institutions (from assist.org API)
  python -m scraper.run list-institutions

  # List available academic years
  python -m scraper.run list-years

WHY argparse instead of click/typer:
  Zero extra dependencies. The CLI is simple enough that argparse handles it fine.
  We already have enough dependencies (playwright, httpx, pydantic, tenacity).
"""

import argparse
import asyncio
import json
import logging
import sys

from scraper.config import (
    ASSIST_BASE_URL,
    CC_INSTITUTIONS,
    UC_INSTITUTIONS,
    DISCOVERY_DIR,
)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging format and level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_discover(args: argparse.Namespace) -> None:
    """
    Navigate to one agreement page and dump all captured data for inspection.

    WHY: Before building/refining the parser, you need to see what data
    assist.org actually sends. This captures every XHR response and the
    rendered DOM so you can examine the exact JSON structure.
    """
    from scraper.api_client import AssistAPIClient
    from scraper.browser import AssistBrowser
    from scraper.orchestrator import resolve_year_id

    sending_code = args.sending.upper()
    receiving_code = args.to[0].upper() if args.to else "UCB"

    if sending_code not in CC_INSTITUTIONS:
        print(f"Error: Unknown CC code '{sending_code}'")
        sys.exit(1)
    if receiving_code not in UC_INSTITUTIONS:
        print(f"Error: Unknown UC code '{receiving_code}'")
        sys.exit(1)

    cc = CC_INSTITUTIONS[sending_code]
    uc = UC_INSTITUTIONS[receiving_code]

    # Resolve the year
    year_id = await resolve_year_id(args.year)
    if year_id is None:
        print(f"Error: Could not resolve year '{args.year}'")
        sys.exit(1)

    # Build the URL for the results/agreement page
    url = (
        f"{ASSIST_BASE_URL}/transfer/results?year={year_id}"
        f"&institution={uc['id']}&agreement={cc['id']}"
        f"&agreementType=from&view=agreement&viewBy=major"
    )

    print(f"\nDiscovery target:")
    print(f"  From: {cc['name']} (ID: {cc['id']})")
    print(f"  To:   {uc['name']} (ID: {uc['id']})")
    print(f"  Year: {args.year} (ID: {year_id})")
    print(f"  URL:  {url}")
    print(f"\nLaunching browser...")

    async with AssistBrowser(headless=not args.headful, debug=True) as browser:
        output_dir = await browser.dump_discovery(url)

    print(f"\nDiscovery output saved to: {output_dir}")
    print(f"Inspect the files to understand assist.org's data format:")
    print(f"  - xhr_*/body.json  — intercepted API responses (primary data source)")
    print(f"  - xhr_*/meta.json  — URL and status for each XHR")
    print(f"  - page.html        — fully rendered DOM (fallback data source)")
    print(f"  - screenshot.png   — visual snapshot of the page")


async def cmd_scrape(args: argparse.Namespace) -> None:
    """Run the full scrape pipeline."""
    from scraper.orchestrator import scrape_agreements

    sending_code = args.sending.upper()
    receiving_codes = [code.upper() for code in args.to] if args.to else ["ALL"]

    summary = await scrape_agreements(
        sending_code=sending_code,
        receiving_codes=receiving_codes,
        target_year=args.year,
        major_filter=args.major,
        headless=not args.headful,
        debug=args.debug,
    )

    print(f"\nResults: {summary}")


async def cmd_list_institutions(args: argparse.Namespace) -> None:
    """Fetch and display all institutions from assist.org."""
    from scraper.api_client import AssistAPIClient

    async with AssistAPIClient() as client:
        institutions = await client.get_institutions()

    print(f"\nFound {len(institutions)} institutions:\n")
    for inst in sorted(institutions, key=lambda x: x.get("id", 0)):
        inst_id = inst.get("id", "?")
        # Institution names are nested in a "names" array
        names = inst.get("names", [])
        name = names[0].get("name", "Unknown") if names else inst.get("name", "Unknown")
        print(f"  {inst_id:>4}  {name}")


async def cmd_list_years(args: argparse.Namespace) -> None:
    """Fetch and display available academic years from assist.org."""
    from scraper.api_client import AssistAPIClient

    async with AssistAPIClient() as client:
        years = await client.get_academic_years()

    print(f"\nAvailable academic years:\n")
    for year in years:
        # API returns PascalCase: {"Id": 74, "FallYear": 2024}
        year_id = year.get("Id", year.get("id", "?"))
        fall_year = year.get("FallYear", year.get("fallYear", "?"))
        # Construct the academic year label: FallYear 2024 → "2024-25"
        if isinstance(fall_year, int):
            label = f"{fall_year}-{(fall_year + 1) % 100:02d}"
        else:
            label = str(fall_year)
        print(f"  ID: {year_id:>3}  Year: {label}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scraper",
        description="Scrape articulation agreements from assist.org",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- discover ---
    discover_parser = subparsers.add_parser(
        "discover",
        help="Inspect one agreement page (dump XHR + DOM for development)",
    )
    discover_parser.add_argument(
        "--from", dest="sending", default="SBCC",
        help="Sending CC code (default: SBCC)",
    )
    discover_parser.add_argument(
        "--to", nargs="+", default=["UCB"],
        help="Receiving UC code (default: UCB)",
    )
    discover_parser.add_argument(
        "--year", default="2024-25",
        help="Academic year (default: 2024-25)",
    )
    discover_parser.add_argument(
        "--headful", action="store_true",
        help="Show the browser window",
    )

    # --- scrape ---
    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Scrape articulation agreements",
    )
    scrape_parser.add_argument(
        "--from", dest="sending", default="SBCC",
        help="Sending CC code, or ALL for every community college (default: SBCC)",
    )
    scrape_parser.add_argument(
        "--to", nargs="+", default=None,
        help="Receiving UC code(s), or ALL (default: ALL)",
    )
    scrape_parser.add_argument(
        "--year", default="2024-25",
        help="Academic year (default: 2024-25)",
    )
    scrape_parser.add_argument(
        "--major", default=None,
        help="Filter to majors containing this string (case-insensitive)",
    )
    scrape_parser.add_argument(
        "--headful", action="store_true",
        help="Show the browser window",
    )
    scrape_parser.add_argument(
        "--debug", action="store_true",
        help="Save screenshots and extra debug info",
    )

    # --- list-institutions ---
    subparsers.add_parser(
        "list-institutions",
        help="List all institutions from assist.org",
    )

    # --- list-years ---
    subparsers.add_parser(
        "list-years",
        help="List available academic years",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # Dispatch to the appropriate async command
    commands = {
        "discover": cmd_discover,
        "scrape": cmd_scrape,
        "list-institutions": cmd_list_institutions,
        "list-years": cmd_list_years,
    }

    cmd_func = commands.get(args.command)
    if cmd_func is None:
        parser.print_help()
        sys.exit(1)

    asyncio.run(cmd_func(args))


if __name__ == "__main__":
    main()
