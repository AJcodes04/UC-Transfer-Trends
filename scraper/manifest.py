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

    def summary(self) -> dict[str, int]:
        """Return a count of entries by status."""
        counts: dict[str, int] = {"success": 0, "failed": 0, "skipped": 0}
        for entry in self._manifest.entries:
            counts[entry.status.value] = counts.get(entry.status.value, 0) + 1
        return counts
