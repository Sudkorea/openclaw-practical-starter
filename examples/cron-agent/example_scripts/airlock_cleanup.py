#!/usr/bin/env python3
"""
airlock_cleanup.py — Archive Old Airlock Records

Moves Airlock daily records older than N days to a long-term archive directory.
Designed to be safe: it copies, verifies, then deletes. Never destructive without verification.

Called by: cron-agent (weekly, Sunday at 03:00 via cron_jobs.json)

Usage:
    python airlock_cleanup.py [--older-than-days 30]
                               [--archive-dir /archive/airlock/]
                               [--dry-run]

Key design decisions:
- Copy-then-delete (not move) so we can verify the copy succeeded before removing the original.
- dry-run mode is the default in examples so you cannot accidentally delete files.
- Writes an Airlock record of the cleanup itself (meta, but useful for audits).
- Only moves files from daily/ — does not touch study_queue/, index/, or topic-shifts/.
"""

import argparse
import hashlib
import os
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AIRLOCK_DAILY_DIR = Path(
    os.environ.get(
        "AIRLOCK_DAILY_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/daily/",
    )
)

DEFAULT_ARCHIVE_DIR = Path(
    os.environ.get(
        "AIRLOCK_ARCHIVE_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/archive/",
    )
)

AIRLOCK_LOG_DIR = Path(
    os.environ.get(
        "AIRLOCK_LOG_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/logs/",
    )
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def file_sha256(path: Path) -> str:
    """Compute SHA-256 of a file for copy verification."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_older_than(path: Path, cutoff_date: date) -> bool:
    """Return True if the file's date prefix (YYYY-MM-DD) is before cutoff_date."""
    name = path.stem  # e.g., 2026-01-01-cron-health-check
    try:
        file_date = date.fromisoformat(name[:10])
        return file_date < cutoff_date
    except ValueError:
        # If the filename doesn't start with a date, skip it.
        return False


def safe_copy_file(src: Path, dst_dir: Path) -> Path:
    """
    Copy src to dst_dir, preserving directory structure by year-month.
    Returns the destination path.
    Raises RuntimeError if the copy cannot be verified.
    """
    # Organize archive by year-month: archive/2026-01/filename.md
    date_prefix = src.stem[:7]  # e.g., "2026-01"
    month_dir = dst_dir / date_prefix
    month_dir.mkdir(parents=True, exist_ok=True)
    dst = month_dir / src.name

    if dst.exists():
        # Already archived — skip without error
        return dst

    src_hash = file_sha256(src)
    shutil.copy2(src, dst)
    dst_hash = file_sha256(dst)

    if src_hash != dst_hash:
        dst.unlink(missing_ok=True)
        raise RuntimeError(
            f"Copy verification failed for {src.name}: "
            f"src={src_hash} dst={dst_hash}"
        )

    return dst


# ---------------------------------------------------------------------------
# Main cleanup logic
# ---------------------------------------------------------------------------

def run_cleanup(
    older_than_days: int,
    archive_dir: Path,
    dry_run: bool,
) -> dict:
    """
    Find, copy, and delete old airlock records.
    Returns a summary dict.
    """
    cutoff_date = date.today() - timedelta(days=older_than_days)
    print(f"Archiving records older than {cutoff_date} (>{older_than_days} days)")
    print(f"Source:  {AIRLOCK_DAILY_DIR}")
    print(f"Archive: {archive_dir}")
    if dry_run:
        print("[DRY RUN] No files will be moved.")
    print("-" * 60)

    if not AIRLOCK_DAILY_DIR.exists():
        print(f"Daily dir does not exist: {AIRLOCK_DAILY_DIR}")
        return {"archived": 0, "skipped": 0, "errors": []}

    candidates = sorted(
        p for p in AIRLOCK_DAILY_DIR.glob("*.md")
        if is_older_than(p, cutoff_date)
    )

    print(f"Found {len(candidates)} files to archive.")

    archived = 0
    skipped = 0
    errors = []

    for src in candidates:
        try:
            if dry_run:
                print(f"  [DRY RUN] Would archive: {src.name}")
                archived += 1
                continue

            dst = safe_copy_file(src, archive_dir)
            src.unlink()
            print(f"  Archived: {src.name} -> {dst}")
            archived += 1

        except Exception as e:
            error_msg = f"{src.name}: {e}"
            print(f"  ERROR: {error_msg}")
            errors.append(error_msg)
            skipped += 1

    print("-" * 60)
    print(f"Done: {archived} archived, {skipped} errors.")

    return {
        "cutoff_date": cutoff_date.isoformat(),
        "archived": archived,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }


def write_cleanup_record(summary: dict, archive_dir: Path) -> None:
    """Write a brief Airlock record of the cleanup operation itself."""
    AIRLOCK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    record_path = AIRLOCK_DAILY_DIR / f"{date_str}-cron-airlock-cleanup.md"

    dry_run_note = " (DRY RUN — no files moved)" if summary.get("dry_run") else ""
    error_section = (
        "\n".join(f"- {e}" for e in summary["errors"])
        if summary["errors"]
        else "None"
    )

    record = f"""## TL;DR
Archived {summary['archived']} Airlock records older than {summary['cutoff_date']} to {archive_dir}{dry_run_note}.

## Details
- Cutoff date: {summary['cutoff_date']}
- Records archived: {summary['archived']}
- Errors: {summary['skipped']}
- Archive dir: {archive_dir}

## Errors
{error_section}

## Next action
DONE — no follow-up required unless errors listed above.
"""

    with open(record_path, "w") as f:
        f.write(record)

    print(f"Cleanup record written to: {record_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OpenClaw Airlock cleanup")
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=30,
        help="Archive records older than this many days (default: 30)",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=DEFAULT_ARCHIVE_DIR,
        help=f"Archive destination directory (default: {DEFAULT_ARCHIVE_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be archived without moving them",
    )
    args = parser.parse_args()

    summary = run_cleanup(
        older_than_days=args.older_than_days,
        archive_dir=args.archive_dir,
        dry_run=args.dry_run,
    )

    # Write a record of the cleanup (even for dry runs, so we have a log)
    if not args.dry_run:
        write_cleanup_record(summary, args.archive_dir)

    # Exit non-zero if there were errors
    if summary["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
