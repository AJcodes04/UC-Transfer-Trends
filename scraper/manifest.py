"""
Manifest tracking for scrape progress — enables crash-safe resume.

WHY this exists:
  A full scrape across all 9 UC campuses can take hours. If the process crashes
  mid-run (network drop, laptop sleep, ctrl+C), we don't want to re-scrape
  everything from scratch. The manifest records each agreement's status as it
  completes, so the next run can skip already-scraped agreements.

HOW it works:
  - The manifest is a JSON file at data/articulation/manifest.json
  - Each entry tracks one (CC, UC, year, major) combination
  - After scraping each agreement, the orchestrator calls mark_complete() or
    mark_failed(), which immediately writes to disk (crash-safe)
  - On the next run, is_already_scraped() checks the manifest and skips
    completed entries
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from scraper.config import OUTPUT_DIR
from scraper.models import Manifest, ManifestEntry, ScrapeStatus

logger = logging.getLogger(__name__)

MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

# A curated, human-readable list of "real" scrape failures worth retrying or
# investigating. We deliberately EXCLUDE transient rate-limit (429) errors here,
# because those are noise: re-running the scraper retries them automatically and
# they usually succeed on a calmer pass. This file is the targeted re-scrape
# worklist — see _is_transient_error() for what we filter out.
FAILURES_PATH = OUTPUT_DIR / "failed_scrapes.json"


def _is_transient_error(error: str) -> bool:
    """
    Return True for errors that are transient and self-healing on retry.

    WHY: 429 ("Too Many Requests") means assist.org rate-limited us, not that
    the agreement is missing or broken. These resolve on a slower re-run, so we
    keep them out of failed_scrapes.json to avoid drowning the real failures.
    """
    err = (error or "").lower()
    return "429" in err or "too many requests" in err


class ManifestTracker:
    """
    Tracks scraping progress to enable resume capability.

    Usage:
        tracker = ManifestTracker()
        tracker.load()

        if not tracker.is_already_scraped("SBCC", "UCB", "2024-25", "Computer Science"):
            # ... scrape the agreement ...
            tracker.mark_complete("SBCC", "UCB", "2024-25", "Computer Science", "path/to/file.json")

        tracker.save()  # Also called automatically by mark_complete/mark_failed
    """

    def __init__(self, path: Path = MANIFEST_PATH) -> None:
        self._path = path
        self._manifest = Manifest()

    def load(self) -> None:
        """Load manifest from disk if it exists."""
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                self._manifest = Manifest(**data)
                logger.info(f"Loaded manifest with {len(self._manifest.entries)} entries")
            except Exception as e:
                logger.warning(f"Failed to load manifest, starting fresh: {e}")
                self._manifest = Manifest()
        else:
            logger.info("No existing manifest found, starting fresh")

    def save(self) -> None:
        """Write manifest to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            self._manifest.model_dump_json(indent=2)
        )

    # ------------------------------------------------------------------
    # Curated failures file (non-429 failures only)
    #
    # This is kept SEPARATE from the manifest on purpose. The manifest is the
    # full source of truth (every success/skip/failure, including 429s). This
    # file is a small, always-current worklist of real failures you'd actually
    # want to re-scrape or investigate. We rewrite it on every relevant event so
    # a major that later succeeds drops off the list automatically.
    # ------------------------------------------------------------------

    def _load_failures(self) -> list[dict]:
        """Read the curated failures file, returning [] if it doesn't exist yet."""
        if not FAILURES_PATH.exists():
            return []
        try:
            return json.loads(FAILURES_PATH.read_text())
        except Exception as e:
            logger.warning(f"Failed to read {FAILURES_PATH.name}, starting fresh: {e}")
            return []

    def _save_failures(self, failures: list[dict]) -> None:
        FAILURES_PATH.parent.mkdir(parents=True, exist_ok=True)
        FAILURES_PATH.write_text(json.dumps(failures, indent=2))

    def _same_combo(self, f: dict, sending_code: str, receiving_code: str,
                    year: str, major: str) -> bool:
        return (
            f.get("sending_code") == sending_code
            and f.get("receiving_code") == receiving_code
            and f.get("academic_year") == year
            and f.get("major") == major
        )

    def _record_failure(self, sending_code: str, receiving_code: str,
                        year: str, major: str, error: str) -> None:
        """Add/replace this combo in failed_scrapes.json (skips transient 429s)."""
        if _is_transient_error(error):
            return  # 429 noise — manifest still records it, but not here
        failures = self._load_failures()
        # Upsert: drop any prior entry for this combo so we don't accumulate dupes
        failures = [
            f for f in failures
            if not self._same_combo(f, sending_code, receiving_code, year, major)
        ]
        failures.append({
            "sending_code": sending_code,
            "receiving_code": receiving_code,
            "academic_year": year,
            "major": major,
            "error": error,
            "failed_at": datetime.utcnow().isoformat(),
        })
        self._save_failures(failures)

    def _clear_failure(self, sending_code: str, receiving_code: str,
                       year: str, major: str) -> None:
        """Remove this combo from failed_scrapes.json once it's resolved."""
        failures = self._load_failures()
        kept = [
            f for f in failures
            if not self._same_combo(f, sending_code, receiving_code, year, major)
        ]
        if len(kept) != len(failures):
            self._save_failures(kept)

    def is_already_scraped(
        self, sending_code: str, receiving_code: str, year: str, major: str
    ) -> bool:
        """
        Check if an agreement has already been successfully scraped.

        Only returns True for SUCCESS status — failed/skipped entries will be retried.
        """
        for entry in self._manifest.entries:
            if (
                entry.sending_code == sending_code
                and entry.receiving_code == receiving_code
                and entry.academic_year == year
                and entry.major == major
                and entry.status == ScrapeStatus.SUCCESS
            ):
                return True
        return False

    def mark_complete(
        self,
        sending_code: str,
        receiving_code: str,
        year: str,
        major: str,
        file_path: str,
    ) -> None:
        """Record a successful scrape and save to disk immediately."""
        self._upsert_entry(ManifestEntry(
            sending_code=sending_code,
            receiving_code=receiving_code,
            academic_year=year,
            major=major,
            status=ScrapeStatus.SUCCESS,
            file_path=file_path,
            scraped_at=datetime.utcnow(),
        ))
        self.save()
        # If this combo previously failed, it's now resolved — drop it.
        self._clear_failure(sending_code, receiving_code, year, major)

    def mark_failed(
        self,
        sending_code: str,
        receiving_code: str,
        year: str,
        major: str,
        error: str,
    ) -> None:
        """Record a failed scrape attempt and save to disk immediately."""
        self._upsert_entry(ManifestEntry(
            sending_code=sending_code,
            receiving_code=receiving_code,
            academic_year=year,
            major=major,
            status=ScrapeStatus.FAILED,
            error=error,
            scraped_at=datetime.utcnow(),
        ))
        self.save()
        # Record real (non-429) failures in the curated worklist.
        self._record_failure(sending_code, receiving_code, year, major, error)

    def mark_skipped(
        self,
        sending_code: str,
        receiving_code: str,
        year: str,
        major: str,
        reason: str = "",
    ) -> None:
        """Record a skipped agreement (e.g., empty/no articulation)."""
        self._upsert_entry(ManifestEntry(
            sending_code=sending_code,
            receiving_code=receiving_code,
            academic_year=year,
            major=major,
            status=ScrapeStatus.SKIPPED,
            error=reason,
            scraped_at=datetime.utcnow(),
        ))
        self.save()
        # A skipped (empty/no-articulation) result also resolves any prior failure.
        self._clear_failure(sending_code, receiving_code, year, major)

    def _upsert_entry(self, new_entry: ManifestEntry) -> None:
        """
        Add or update a manifest entry.

        If an entry for the same (CC, UC, year, major) already exists,
        replace it. This ensures retries overwrite previous failures.
        """
        # Remove existing entry for the same combo if present
        self._manifest.entries = [
            e for e in self._manifest.entries
            if not (
                e.sending_code == new_entry.sending_code
                and e.receiving_code == new_entry.receiving_code
                and e.academic_year == new_entry.academic_year
                and e.major == new_entry.major
            )
        ]
        self._manifest.entries.append(new_entry)

    def rebuild_failures_from_manifest(self) -> int:
        """
        Regenerate failed_scrapes.json from the loaded manifest's current state.

        WHY: the manifest already keeps exactly one entry per (CC, UC, year, major)
        — retries overwrite prior attempts — so a combo whose final status is
        FAILED is genuinely unresolved. We collect those (minus transient 429s)
        into the curated worklist. Use this to bootstrap the file from history
        without re-running the scraper. Returns the number of failures written.
        """
        failures = []
        for e in self._manifest.entries:
            if e.status != ScrapeStatus.FAILED:
                continue
            if _is_transient_error(e.error or ""):
                continue
            failures.append({
                "sending_code": e.sending_code,
                "receiving_code": e.receiving_code,
                "academic_year": e.academic_year,
                "major": e.major,
                "error": e.error or "",
                "failed_at": e.scraped_at.isoformat() if e.scraped_at else None,
            })
        self._save_failures(failures)
        logger.info(f"Wrote {len(failures)} non-429 failures to {FAILURES_PATH.name}")
        return len(failures)

    def summary(self) -> dict[str, int]:
        """Return a count of entries by status."""
        counts: dict[str, int] = {"success": 0, "failed": 0, "skipped": 0}
        for entry in self._manifest.entries:
            counts[entry.status.value] = counts.get(entry.status.value, 0) + 1
        return counts
