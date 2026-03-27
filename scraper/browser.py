"""
Playwright browser lifecycle and XHR interception.

WHY Playwright instead of just HTTP requests:
  assist.org is an Angular SPA (Single Page Application). The actual articulation
  data is loaded via authenticated XHR (XMLHttpRequest) calls that happen after
  the page's JavaScript runs. You can't get this data with plain HTTP requests
  because:
    1. The auth tokens are generated client-side during page load
    2. The data endpoints require these tokens in request headers
    3. The page content is rendered by JavaScript, not served as static HTML

  Playwright automates a real Chromium browser, so all the JavaScript runs naturally
  and we can intercept the XHR responses as they happen.

WHY XHR interception is the primary strategy:
  Instead of parsing the rendered DOM (which is fragile — CSS classes change),
  we capture the raw JSON responses from assist.org's internal API calls. This
  gives us structured data directly, which is far more reliable than scraping HTML.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Response,
    Playwright,
)

from scraper.config import (
    NAVIGATION_TIMEOUT,
    SELECTOR_TIMEOUT,
    DISCOVERY_DIR,
    DEBUG_DIR,
)

logger = logging.getLogger(__name__)


@dataclass
class InterceptedResponse:
    """
    A captured XHR response from the browser.

    We store these as the page loads so the parser can extract articulation
    data from the raw JSON without touching the DOM.
    """
    url: str
    status: int
    body: str  # Raw response body (usually JSON)
    content_type: str = ""


@dataclass
class PageCapture:
    """
    Everything captured from loading a single agreement page:
    both the XHR responses and the final rendered HTML.
    """
    url: str
    xhr_responses: list[InterceptedResponse] = field(default_factory=list)
    html: str = ""
    screenshot_path: Optional[str] = None


class AssistBrowser:
    """
    Manages a Playwright browser instance with XHR interception.

    Usage:
        async with AssistBrowser(headless=True) as browser:
            capture = await browser.navigate_and_capture("https://assist.org/...")

    HOW interception works:
      When we navigate to a page, Playwright fires a "response" event for every
      network request the page makes. We attach a handler that filters for
      assist.org API calls (URLs containing '/api/') and saves their response
      bodies. By the time the page finishes loading, we have all the JSON data
      the Angular app received.
    """

    def __init__(self, headless: bool = True, debug: bool = False) -> None:
        self._headless = headless
        self._debug = debug
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self) -> "AssistBrowser":
        self._playwright = await async_playwright().start()

        # Launch Chromium with reasonable settings
        # - headless=True for production, False for debugging (see the browser)
        # - slow_mo adds a small delay between actions when debugging
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            slow_mo=100 if not self._headless else 0,
        )

        # A browser context is like an incognito window — isolated cookies/storage.
        # We set a realistic viewport and user agent so assist.org serves us the
        # full desktop experience (not a mobile layout).
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        # Set default timeouts for all pages in this context
        self._context.set_default_timeout(SELECTOR_TIMEOUT)
        self._context.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

        return self

    async def __aexit__(self, *args) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        """Create a new browser tab within our context."""
        assert self._context is not None
        return await self._context.new_page()

    async def navigate_and_capture(
        self,
        url: str,
        page: Optional[Page] = None,
        wait_for_selector: Optional[str] = None,
    ) -> PageCapture:
        """
        Navigate to a URL and capture all XHR responses + final HTML.

        Parameters:
          url: The page to navigate to
          page: Reuse an existing page (tab), or create a new one
          wait_for_selector: CSS selector to wait for after navigation, indicating
                            the content we care about has loaded

        Returns a PageCapture with all intercepted API responses and the page HTML.
        """
        if page is None:
            page = await self.new_page()

        capture = PageCapture(url=url)

        # --- Set up XHR interception ---
        # This handler fires for EVERY network response on the page.
        # We filter for assist.org API calls and save their bodies.
        async def on_response(response: Response) -> None:
            try:
                # Only capture assist.org API responses
                if "/api/" not in response.url:
                    return
                # Only capture successful responses with content
                if response.status < 200 or response.status >= 400:
                    return

                content_type = response.headers.get("content-type", "")
                body = await response.text()

                capture.xhr_responses.append(InterceptedResponse(
                    url=response.url,
                    status=response.status,
                    body=body,
                    content_type=content_type,
                ))
                logger.debug(f"Intercepted: {response.url} ({response.status}, {len(body)} bytes)")

            except Exception as e:
                # Don't let a single failed interception kill the whole page load
                logger.warning(f"Failed to capture response {response.url}: {e}")

        page.on("response", on_response)

        try:
            # Navigate and wait for the page to be mostly done loading.
            # "networkidle" means no network requests for 500ms — a good signal
            # that the Angular app has finished its initial data fetching.
            await page.goto(url, wait_until="networkidle")

            # If caller specified a selector, wait for it to appear in the DOM.
            # This handles cases where Angular renders content slightly after networkidle.
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=SELECTOR_TIMEOUT)
                except Exception:
                    logger.warning(f"Selector '{wait_for_selector}' not found within timeout")

            # Give Angular a moment to finish rendering after data arrives
            await asyncio.sleep(1)

            # Capture the fully rendered HTML (for DOM fallback parsing)
            capture.html = await page.content()

            # Save a screenshot if we're in debug mode
            if self._debug:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                screenshot_path = DEBUG_DIR / f"screenshot_{hash(url) & 0xFFFFFFFF:08x}.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)
                capture.screenshot_path = str(screenshot_path)
                logger.debug(f"Screenshot saved: {screenshot_path}")

        except Exception as e:
            logger.error(f"Navigation failed for {url}: {e}")
            raise

        finally:
            # Remove the handler to avoid memory leaks if the page is reused
            page.remove_listener("response", on_response)

        logger.info(
            f"Captured {len(capture.xhr_responses)} XHR responses from {url}"
        )
        return capture

    async def dump_discovery(self, url: str) -> Path:
        """
        Navigate to a URL and dump ALL captured data for manual inspection.

        WHY: Before building the parser, we need to see what data assist.org
        actually sends. This saves everything to _discovery/ so we can examine
        the exact JSON structure and figure out what to parse.

        Returns the path to the discovery output directory.
        """
        DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)

        capture = await self.navigate_and_capture(url)

        # Save each intercepted XHR response as a separate file
        for i, resp in enumerate(capture.xhr_responses):
            resp_dir = DISCOVERY_DIR / f"xhr_{i:03d}"
            resp_dir.mkdir(exist_ok=True)

            # Save metadata
            (resp_dir / "meta.json").write_text(json.dumps({
                "url": resp.url,
                "status": resp.status,
                "content_type": resp.content_type,
                "body_length": len(resp.body),
            }, indent=2))

            # Save the response body — try to pretty-print if it's JSON
            try:
                parsed = json.loads(resp.body)
                (resp_dir / "body.json").write_text(json.dumps(parsed, indent=2))
            except (json.JSONDecodeError, ValueError):
                (resp_dir / "body.txt").write_text(resp.body)

        # Save the rendered HTML
        (DISCOVERY_DIR / "page.html").write_text(capture.html)

        # Save a screenshot
        page = await self.new_page()
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(2)
        await page.screenshot(
            path=str(DISCOVERY_DIR / "screenshot.png"),
            full_page=True,
        )
        await page.close()

        logger.info(f"Discovery dump saved to {DISCOVERY_DIR}")
        logger.info(f"  - {len(capture.xhr_responses)} XHR responses")
        logger.info(f"  - page.html ({len(capture.html)} bytes)")
        logger.info(f"  - screenshot.png")

        return DISCOVERY_DIR
