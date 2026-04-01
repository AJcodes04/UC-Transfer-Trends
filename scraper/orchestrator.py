"""
Orchestrator — coordinates the full scrape pipeline using pure HTTP.

KEY INSIGHT: All of assist.org's API endpoints are public. We discovered this
during the initial Playwright-based discovery: the /api/articulation/Agreements
endpoint returns full course-level data without authentication. This means we
can replace the entire Playwright browser flow with simple httpx HTTP requests.

FLOW:
  1. Resolve "2024-25" → numeric year ID via /api/academicyears
  2. For each target UC campus:
     a. GET /api/agreements?... → list of majors with articulation agreements
     b. For each major:
        - Check manifest (skip if already scraped)
        - GET /api/articulation/Agreements?Key=... → full course data
        - Parse the JSON response into an Agreement model
        - Save as JSON file
        - Update manifest

WHY no Playwright needed:
  The original plan assumed course-level data was auth-gated behind the Angular
  SPA's XHR calls. Discovery proved this wrong — the API is fully public.
  Plain HTTP is faster, more reliable, and has zero browser overhead.
"""

import asyncio
import logging
import re
from typing import Optional

from scraper.api_client import AssistAPIClient
from scraper.config import (
    CC_INSTITUTIONS,
    UC_INSTITUTIONS,
    OUTPUT_DIR,
    KNOWN_YEAR_IDS,
)
from scraper.manifest import ManifestTracker
from scraper.models import Agreement
from scraper.parser import parse_agreement_from_api

logger = logging.getLogger(__name__)


def _agreement_has_content(agreement) -> bool:
    """
    Return True if the agreement has at least one articulation row.
    Handles both the new grouped format (sections[].groups[].options[].rows[])
    and the legacy flat format (sections[].rows[]).
    """
    if not agreement.sections:
        return False
    for section in agreement.sections:
        # New format: rows nested inside groups → options
        for group in section.groups:
            for option in group.options:
                if option.rows:
                    return True
        # Legacy format: flat rows directly on section
        if section.rows:
            return True
    return False


def _slugify(text: str) -> str:
    """
    Convert a major name to a filesystem-safe filename.
    e.g., "Computer Science, B.A." → "computer_science_b_a"
    """
    text = text.lower().strip()
    text = re.sub(r'[&/]+', '_', text)
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = text.strip('_')
    return text


def _save_agreement(agreement: Agreement, sending_code: str, receiving_code: str) -> str:
    """
    Save an Agreement to a JSON file.
    Path: data/articulation/{cc_code}/{uc_code}/{year}/{major_slug}.json
    """
    major_slug = _slugify(agreement.major)
    out_dir = OUTPUT_DIR / sending_code.lower() / receiving_code.lower() / agreement.academic_year
    out_dir.mkdir(parents=True, exist_ok=True)

    file_path = out_dir / f"{major_slug}.json"
    file_path.write_text(agreement.model_dump_json(indent=2))
    logger.info(f"Saved: {file_path}")
    return str(file_path)


async def resolve_year_id(target_year: str) -> Optional[int]:
    """
    Look up the numeric year ID for a year string like "2024-25".

    assist.org URLs use numeric IDs (e.g., 74), not year strings.
    Tries the /api/academicyears endpoint first; falls back to the
    hard-coded KNOWN_YEAR_IDS table if the API returns 400.
    """
    # Normalise "2024-25" → also try "2024-2025" variants in fallback
    # Build a set of candidate keys to check in KNOWN_YEAR_IDS
    candidates = {target_year}
    parts = target_year.split("-")
    if len(parts) == 2 and len(parts[1]) == 2:
        # "2024-25" → also store as "2024-25" (already there)
        pass

    # Check hard-coded table first (avoids one round-trip if key matches)
    if target_year in KNOWN_YEAR_IDS:
        cached_id = KNOWN_YEAR_IDS[target_year]
        logger.info(f"Resolved year '{target_year}' to ID {cached_id} (from known table)")
        return cached_id

    # Try the live API
    try:
        async with AssistAPIClient() as client:
            years = await client.get_academic_years()
            for year in years:
                year_id = year.get("Id", year.get("id"))
                fall_year = year.get("FallYear", year.get("fallYear"))
                if fall_year is None or year_id is None:
                    continue
                try:
                    target_start = int(target_year.split("-")[0])
                except (ValueError, IndexError):
                    continue
                if fall_year == target_start:
                    logger.info(f"Resolved year '{target_year}' to ID {year_id} (FallYear={fall_year})")
                    return year_id
    except Exception as e:
        logger.warning(f"Could not fetch academic years from API ({e}); checking fallback table")

    logger.error(f"Could not find year ID for '{target_year}' (not in API or known table)")
    return None


async def _scrape_one_cc(
    client: AssistAPIClient,
    tracker: ManifestTracker,
    sending_code: str,
    cc: dict,
    targets: list[tuple[str, dict]],
    target_year: str,
    year_id: int,
    major_filter: Optional[str] = None,
    semaphore: Optional[asyncio.Semaphore] = None,
) -> dict:
    """Scrape all UC targets for a single community college.
    Returns a dict with success/failed/skipped counts for this CC."""
    counts = {"success": 0, "failed": 0, "skipped": 0}

    for uc_code, uc_info in targets:
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraping: {cc['name']} → {uc_info['name']} ({target_year})")
        logger.info(f"{'='*60}")

        try:
            # Step 1: Get list of majors with agreements
            if semaphore:
                async with semaphore:
                    data = await client.get_agreements_for_institution(
                        receiving_id=uc_info["id"],
                        sending_id=cc["id"],
                        year_id=year_id,
                    )
            else:
                data = await client.get_agreements_for_institution(
                    receiving_id=uc_info["id"],
                    sending_id=cc["id"],
                    year_id=year_id,
                )
            reports = data.get("reports", []) if isinstance(data, dict) else data

            if not reports:
                logger.warning(f"No majors found for {sending_code} → {uc_code}")
                continue

            logger.info(f"Found {len(reports)} majors for {uc_code}")

            # Step 2: Fetch each major's full agreement
            for i, report in enumerate(reports):
                major_name = report.get("label", "Unknown")
                major_key = report.get("key", "")

                # Apply major filter if specified
                if major_filter and major_filter.lower() not in major_name.lower():
                    continue

                # Skip if already scraped (resume support)
                if tracker.is_already_scraped(sending_code, uc_code, target_year, major_name):
                    logger.info(f"  [{i+1}/{len(reports)}] Skipping (already scraped): {major_name}")
                    counts["skipped"] += 1
                    continue

                logger.info(f"  [{i+1}/{len(reports)}] Scraping: {major_name}")

                try:
                    # Fetch full agreement via HTTP (rate-limited by semaphore)
                    if semaphore:
                        async with semaphore:
                            detail = await client.get_agreement_detail(major_key)
                    else:
                        detail = await client.get_agreement_detail(major_key)

                    # Parse API response into Agreement model
                    agreement = parse_agreement_from_api(
                        api_response=detail,
                        sending_name=cc["name"],
                        receiving_name=uc_info["name"],
                        major=major_name,
                        academic_year=target_year,
                    )

                    # Check if agreement has actual content
                    if not _agreement_has_content(agreement):
                        logger.warning(f"    Empty agreement for {major_name}")
                        tracker.mark_skipped(
                            sending_code, uc_code, target_year, major_name,
                            reason="No articulation data found"
                        )
                        counts["skipped"] += 1
                        continue

                    # Save as JSON
                    file_path = _save_agreement(agreement, sending_code, uc_code)
                    tracker.mark_complete(
                        sending_code, uc_code, target_year, major_name, file_path
                    )
                    counts["success"] += 1

                except Exception as e:
                    logger.error(f"    Failed to scrape {major_name}: {e}", exc_info=True)
                    tracker.mark_failed(
                        sending_code, uc_code, target_year, major_name, str(e)
                    )
                    counts["failed"] += 1

        except Exception as e:
            logger.error(f"Failed to process {uc_code}: {e}", exc_info=True)

    return counts


async def scrape_agreements(
    sending_code: str = "SBCC",
    receiving_codes: Optional[list[str]] = None,
    target_year: str = "2024-25",
    major_filter: Optional[str] = None,
    headless: bool = True,
    debug: bool = False,
    workers: int = 1,
) -> dict:
    """
    Main scraping orchestrator — fetches articulation data via pure HTTP.

    Parameters:
      sending_code: CC institution code (e.g., "SBCC"), or "ALL" for every CC
      receiving_codes: List of UC codes (e.g., ["UCB", "UCLA"]), or None/["ALL"] for all
      target_year: Academic year string (e.g., "2024-25")
      major_filter: If set, only scrape majors containing this string (case-insensitive)
      headless/debug: Kept for CLI compatibility but unused (no browser needed)
      workers: Number of CCs to scrape concurrently (default: 1)

    Returns a summary dict with counts of success/failed/skipped.
    """
    # Determine which CCs to scrape
    if sending_code.upper() == "ALL":
        senders = list(CC_INSTITUTIONS.items())
    else:
        if sending_code not in CC_INSTITUTIONS:
            raise ValueError(
                f"Unknown CC code '{sending_code}'. "
                f"Available: ALL, {', '.join(sorted(CC_INSTITUTIONS.keys()))}"
            )
        senders = [(sending_code, CC_INSTITUTIONS[sending_code])]

    # Determine which UCs to scrape
    if not receiving_codes or receiving_codes == ["ALL"]:
        targets = list(UC_INSTITUTIONS.items())
    else:
        targets = []
        for code in receiving_codes:
            code = code.upper()
            if code not in UC_INSTITUTIONS:
                logger.warning(f"Unknown UC code '{code}', skipping")
                continue
            targets.append((code, UC_INSTITUTIONS[code]))

    if not targets:
        raise ValueError("No valid UC targets specified")

    # Resolve year string → numeric ID
    year_id = await resolve_year_id(target_year)
    if year_id is None:
        raise ValueError(f"Could not resolve year '{target_year}' — check assist.org")

    # Load manifest for resume support
    tracker = ManifestTracker()
    tracker.load()

    logger.info(f"Scraping {len(senders)} CC(s) → {len(targets)} UC(s) for {target_year} with {workers} worker(s)")

    # Semaphore limits concurrent API requests across all workers.
    # Each worker processes a different CC but they share the rate limit.
    # workers=4 means up to 4 API calls can be in-flight at once.
    semaphore = asyncio.Semaphore(workers) if workers > 1 else None

    # Single HTTP client for all requests (connection reuse = faster)
    async with AssistAPIClient() as client:
        if workers <= 1:
            # Sequential mode — same as before
            for cc_code, cc_info in senders:
                logger.info(f"\n{'#'*60}")
                logger.info(f"Community College: {cc_info['name']} ({cc_code})")
                logger.info(f"{'#'*60}")

                await _scrape_one_cc(
                    client, tracker, cc_code, cc_info,
                    targets, target_year, year_id, major_filter,
                )
        else:
            # Parallel mode — process multiple CCs concurrently
            async def _worker(cc_code, cc_info):
                logger.info(f"\n{'#'*60}")
                logger.info(f"[WORKER] Community College: {cc_info['name']} ({cc_code})")
                logger.info(f"{'#'*60}")
                return await _scrape_one_cc(
                    client, tracker, cc_code, cc_info,
                    targets, target_year, year_id, major_filter,
                    semaphore=semaphore,
                )

            # Process in batches of `workers` size to avoid spawning
            # 116 coroutines at once
            batch_size = workers
            for i in range(0, len(senders), batch_size):
                batch = senders[i:i + batch_size]
                tasks = [_worker(code, info) for code, info in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

    # Print summary
    summary = tracker.summary()
    logger.info(f"\n{'='*60}")
    logger.info(f"Scrape complete!")
    logger.info(f"  Success: {summary['success']}")
    logger.info(f"  Failed:  {summary['failed']}")
    logger.info(f"  Skipped: {summary['skipped']}")
    logger.info(f"{'='*60}")

    return summary
