"""
HTTP client for assist.org's public API endpoints.

KEY DISCOVERY: All of assist.org's API endpoints are fully public — including the
course-level articulation data. No authentication, cookies, or browser required.
This means we can fetch everything with plain HTTP requests, which is:
  - Much faster than Playwright (no browser startup, no JS execution)
  - More reliable (no timing issues with Angular rendering)
  - Simpler to maintain

The three endpoints we use:
  1. /api/agreements?... → list of majors with agreements between two schools
  2. /api/articulation/Agreements?Key=... → full course-level data for one major
  3. /api/academicyears → maps year strings to numeric IDs

WHY httpx: async-native HTTP client, similar to requests.Session but non-blocking.
WHY tenacity: automatic retry with exponential backoff for transient failures.
"""

import asyncio
import gzip
import json
import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from scraper.config import (
    ASSIST_API_BASE,
    API_DELAY,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
)

logger = logging.getLogger(__name__)


def _decompress(data: bytes) -> bytes:
    """
    Decompress gzip data if present (identified by magic bytes \x1f\x8b).
    Returns data unchanged if it's not gzip.

    We only handle gzip here — brotli is excluded from Accept-Encoding so the
    server won't send it, and zlib/deflate fallbacks were causing garbage output
    on unrecognised encodings.
    """
    if data[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(data)
        except Exception:
            pass
    return data


def _safe_decode(data: bytes) -> str:
    """Decode bytes to str, decompressing first if needed."""
    return _decompress(data).decode("utf-8", errors="replace")


def _parse_response(data: bytes) -> Any:
    """
    Parse a JSON response body, handling any compression the server might add
    without a Content-Encoding header.

    Strategy: try json.loads on raw bytes first (httpx already decompresses
    when Content-Encoding is set). If that fails due to encoding/decode error,
    try decompressing manually then parsing.
    """
    try:
        return json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        decompressed = _decompress(data)
        if decompressed is not data:   # decompression changed something
            return json.loads(decompressed)
        raise


class AssistAPIClient:
    """
    Async client for assist.org's public (unauthenticated) API.

    Usage:
        async with AssistAPIClient() as client:
            institutions = await client.get_institutions()
            years = await client.get_academic_years()
    """

    def __init__(self) -> None:
        # httpx.AsyncClient is like requests.Session but async — it reuses
        # TCP connections across requests, which is faster for multiple calls.
        self._client: httpx.AsyncClient | None = None
        # Adaptive delay — starts at API_DELAY, increases on 429s
        self._current_delay: float = API_DELAY

    async def __aenter__(self) -> "AssistAPIClient":
        self._client = httpx.AsyncClient(
            base_url=ASSIST_API_BASE,
            timeout=httpx.Timeout(15.0),
            # follow_redirects so the warmup GET to assist.org/ works properly
            follow_redirects=True,
            # Mimic a real browser to pass Cloudflare / Azure ARRAffinity checks.
            # The ARRAffinity cookie is set by Azure App Service on the first
            # request to assist.org — subsequent API calls must carry it or the
            # server returns 400.  httpx stores cookies in the client's jar
            # automatically, so after the warmup GET below they'll be sent on
            # every API call without any extra work.
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Referer": "https://assist.org/",
                "Origin": "https://assist.org",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": '"macOS"',
                "Connection": "keep-alive",
            },
        )
        # Warmup: fetch the main page so Azure sets the ARRAffinity session
        # cookie in our client's cookie jar before we make any API calls.
        # Without this the API returns 400 on every request.
        #
        # ASP.NET anti-CSRF double-submit pattern:
        #   1. Server sets X-XSRF-TOKEN as a cookie on the warmup response.
        #   2. Client must echo that value back as a *request header* named
        #      X-XSRF-TOKEN on every subsequent API call.
        # The cookie alone is not enough — ASP.NET validates the header too.
        try:
            warmup = await self._client.get("https://assist.org/")
            logger.debug(f"Warmup GET assist.org/ → {warmup.status_code} "
                         f"(cookies: {list(self._client.cookies.keys())})")

            # Extract the XSRF token and inject it as a header.
            # httpx stores cookies in a CookieJar keyed by (domain, path, name).
            # We try both "X-XSRF-TOKEN" (set by ASP.NET) and "XSRF-TOKEN"
            # (set by some Angular apps) — whichever is present.
            xsrf = (
                self._client.cookies.get("X-XSRF-TOKEN")
                or self._client.cookies.get("XSRF-TOKEN")
            )
            if xsrf:
                self._client.headers["X-XSRF-TOKEN"] = xsrf
                logger.debug(f"Set X-XSRF-TOKEN header ({len(xsrf)} chars)")
            else:
                logger.warning("No XSRF token found in warmup cookies — API calls may return 400")
        except Exception as e:
            logger.warning(f"Warmup request failed (continuing anyway): {e}")
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    @retry(
        retry=retry_if_exception_type((httpx.TransportError,)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_BACKOFF_BASE, min=5, max=60),
    )
    async def _get(self, path: str) -> Any:
        """
        Make a GET request to the assist.org API with retry logic.

        On 429 (rate limit), increases the base delay for all future requests
        so we don't keep hammering the server.
        """
        assert self._client is not None, "Client not initialized — use 'async with'"

        # Polite delay between API calls
        await asyncio.sleep(self._current_delay)

        full_url = str(self._client.base_url).rstrip("/") + path
        logger.debug(f"GET {full_url}")
        response = await self._client.get(path)

        # On 429, wait extra and increase delay for future requests
        if response.status_code == 429:
            self._current_delay = min(self._current_delay + 2.0, 15.0)
            logger.warning(f"Rate limited (429). Increasing delay to {self._current_delay}s")
            await asyncio.sleep(10)  # Extra pause before tenacity retry
            response.raise_for_status()

        if response.status_code >= 400:
            body_preview = _safe_decode(response.content)
            logger.error(
                f"HTTP {response.status_code} from {full_url}\n"
                f"  Response body: {body_preview[:500]}"
            )

        response.raise_for_status()
        return _parse_response(response.content)

    async def get_institutions(self) -> list[dict]:
        """
        Fetch all institutions from assist.org.

        Returns a list of dicts like:
          [{"id": 92, "names": [{"name": "Santa Barbara City College", ...}], ...}, ...]

        WHY: Useful for validating that our hardcoded institution IDs in config.py
        are still correct, and for looking up IDs for new colleges.
        """
        logger.info("Fetching institutions from assist.org API...")
        data = await self._get("/institutions")
        logger.info(f"Found {len(data)} institutions")
        return data

    async def get_academic_years(self) -> list[dict]:
        """
        Fetch available academic years.

        Returns a list of dicts like:
          [{"id": 74, "defaultYear": true, "label": "2024-25"}, ...]

        The 'id' is what assist.org's URL parameters expect (not the year string).
        WHY: We need the numeric year ID to construct agreement URLs.
        """
        logger.info("Fetching academic years from assist.org API...")
        data = await self._get("/academicyears")
        logger.info(f"Found {len(data)} academic years")
        return data

    async def get_agreements_for_institution(
        self, receiving_id: int, sending_id: int, year_id: int
    ) -> dict:
        """
        Fetch the list of available major agreements between two institutions.

        Returns a dict like:
          {"reports": [{"label": "Computer Science, B.A.", "key": "75/92/to/79/Major/...", ...}, ...]}

        Each report's "key" can be passed to get_agreement_detail() to fetch
        the full course-level articulation data.
        """
        path = (
            f"/agreements?receivingInstitutionId={receiving_id}"
            f"&sendingInstitutionId={sending_id}"
            f"&academicYearId={year_id}&categoryCode=major"
        )
        logger.info(f"Fetching major list: receiving={receiving_id}, sending={sending_id}, year={year_id}")
        data = await self._get(path)
        reports = data.get("reports", []) if isinstance(data, dict) else data
        logger.info(f"Found {len(reports)} majors")
        return data

    async def get_agreement_detail(self, key: str) -> dict:
        """
        Fetch the full articulation agreement for one major.

        Parameters:
          key: The agreement key from get_agreements_for_institution(),
               e.g. "75/92/to/79/Major/fc50cced-05c2-43c7-7dd5-08dcb87d5deb"

        Returns the full API response containing:
          - result.name: major name
          - result.articulations: JSON string with course-level mappings
          - result.templateAssets: JSON string with notes/requirements HTML

        Both articulations and templateAssets are double-encoded (JSON strings
        within JSON), so the caller needs to json.loads() them again.
        """
        path = f"/articulation/Agreements?Key={key}"
        logger.info(f"Fetching agreement detail: {key[:60]}...")
        data = await self._get(path)
        return data
