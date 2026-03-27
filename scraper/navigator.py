"""
SPA navigation logic for assist.org.

WHY this is separate from browser.py:
  browser.py handles low-level browser lifecycle (launch, intercept, capture).
  This module handles assist.org-specific navigation: building URLs, finding
  the major list, clicking into agreements, and handling Angular's loading states.

  Keeping them separate means browser.py can be reused if assist.org changes
  their frontend, and navigator.py can be updated without touching browser plumbing.

HOW assist.org navigation works:
  1. You land on a "results" page showing all majors with agreements
  2. Each major is a clickable link/row
  3. Clicking a major loads the agreement detail (course-level articulation)
  4. The detail page fetches data via XHR, then Angular renders it

  We need to handle Angular's loading states: there are spinners and lazy-loaded
  content. We wait for specific selectors + networkidle to ensure data has arrived.
"""

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import quote

from playwright.async_api import Page

from scraper.browser import AssistBrowser, PageCapture
from scraper.config import (
    ASSIST_BASE_URL,
    RESULTS_URL_TEMPLATE,
    PAGE_DELAY,
    SELECTOR_TIMEOUT,
)

logger = logging.getLogger(__name__)


class AssistNavigator:
    """
    Navigates assist.org's Angular SPA to find and load agreement pages.

    Usage:
        async with AssistBrowser() as browser:
            nav = AssistNavigator(browser)
            majors = await nav.get_major_list(sending_id=92, receiving_id=79, year_id=74)
            for major in majors:
                capture = await nav.load_agreement(major["key"])
    """

    def __init__(self, browser: AssistBrowser) -> None:
        self._browser = browser
        self._page: Optional[Page] = None

    async def _get_page(self) -> Page:
        """Get or create a reusable page (tab). Reusing avoids the overhead of
        creating a new tab + context for every agreement."""
        if self._page is None or self._page.is_closed():
            self._page = await self._browser.new_page()
        return self._page

    def build_results_url(
        self, sending_id: int, receiving_id: int, year_id: int
    ) -> str:
        """
        Build the URL for the major list / results page.

        This page shows all majors that have articulation agreements between
        the two institutions for the given year.
        """
        return RESULTS_URL_TEMPLATE.format(
            base=ASSIST_BASE_URL,
            year_id=year_id,
            receiving_id=receiving_id,
            sending_id=sending_id,
        )

    async def get_major_list(
        self,
        sending_id: int,
        receiving_id: int,
        year_id: int,
    ) -> list[dict]:
        """
        Navigate to the results page and extract the list of available majors.

        Returns a list of dicts with major info. We try two strategies:

        1. XHR interception: Look for the API response that contains the major list.
           This is preferred because we get clean JSON with major names and IDs.

        2. DOM fallback: If XHR doesn't give us what we need, parse the rendered
           page for major links/rows.

        Each dict has at minimum:
          {"name": "Computer Science", "key": "...", "url": "..."}
        """
        url = self.build_results_url(sending_id, receiving_id, year_id)
        logger.info(f"Loading major list: {url}")

        page = await self._get_page()
        capture = await self._browser.navigate_and_capture(
            url,
            page=page,
            wait_for_selector=".viewByMajorResults, .results-content, .agreement-list",
        )

        majors = []

        # Strategy 1: Extract from XHR responses
        # Look for the response that contains agreement/major data
        for resp in capture.xhr_responses:
            if "/agreements" in resp.url or "/reports" in resp.url:
                try:
                    import json
                    data = json.loads(resp.body)
                    # The response structure varies — it might be a dict with a "reports" key
                    # or a flat list. Handle both.
                    reports = data if isinstance(data, list) else data.get("reports", [])
                    for report in reports:
                        major_name = report.get("label", report.get("name", ""))
                        major_key = report.get("key", "")
                        if major_name:
                            majors.append({
                                "name": major_name,
                                "key": major_key,
                                "report": report,  # Keep full data for URL building
                            })
                    if majors:
                        logger.info(f"Found {len(majors)} majors via XHR")
                        return majors
                except Exception as e:
                    logger.debug(f"Failed to parse XHR response: {e}")

        # Strategy 2: DOM fallback — find major links in the rendered page
        logger.info("XHR extraction failed for major list, falling back to DOM")
        major_links = await page.query_selector_all("a[href*='agreement']")
        if not major_links:
            # Try broader selectors
            major_links = await page.query_selector_all(".results-content a, .viewByMajorResults a")

        for link in major_links:
            text = (await link.text_content() or "").strip()
            href = await link.get_attribute("href") or ""
            if text and href:
                majors.append({
                    "name": text,
                    "key": href,
                    "url": f"{ASSIST_BASE_URL}{href}" if href.startswith("/") else href,
                })

        logger.info(f"Found {len(majors)} majors via DOM")
        return majors

    async def load_agreement(
        self,
        major_key: str,
        sending_id: int,
        receiving_id: int,
        year_id: int,
    ) -> PageCapture:
        """
        Navigate to a specific major's agreement page and capture all data.

        Parameters:
          major_key: The major identifier from get_major_list() — either a URL
                    path fragment or a key used to construct the URL
          sending_id, receiving_id, year_id: Institution/year IDs for URL building

        Returns a PageCapture with the XHR responses (containing articulation JSON)
        and the rendered HTML (for DOM fallback parsing).
        """
        # Be polite — wait between page loads
        await asyncio.sleep(PAGE_DELAY)

        # Build the agreement URL
        # assist.org agreement URLs look like:
        # /transfer/results?year=74&institution=79&agreement=92&agreementType=from&view=agreement&viewBy=major&viewByKey=...
        if major_key.startswith("http"):
            url = major_key
        elif major_key.startswith("/"):
            url = f"{ASSIST_BASE_URL}{major_key}"
        else:
            # Construct from components
            base_url = self.build_results_url(sending_id, receiving_id, year_id)
            url = f"{base_url}&viewByKey={quote(major_key)}"

        logger.info(f"Loading agreement: {url}")

        page = await self._get_page()
        capture = await self._browser.navigate_and_capture(
            url,
            page=page,
            # Wait for the agreement content to render
            wait_for_selector=".articulation-content, .agreement-content, .courseRow, .resultBody",
        )

        return capture

    async def close(self) -> None:
        """Close the reusable page."""
        if self._page and not self._page.is_closed():
            await self._page.close()
            self._page = None
