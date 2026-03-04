#!/usr/bin/env python3
"""
airlock_orchestrator.py

Nightly/daily orchestration script for Airlock records.

Responsibilities:
- Process daily Airlock records from the daily/ directory
- Build/update index files in the index/ directory (airlock_index.schema.json)
- Enforce configurable retention (default 30 days)
- Validate each record against the Airlock index schema
- Optionally invoke a sanitizer script before indexing
- Emit a JSON status report to stdout (and optionally a log file)

Environment variables (all overridable via CLI args):
    AIRLOCK_BASE_DIR  - root of the airlock folder tree
                        (e.g. ~/.openclaw/repos/obsidian-vault/airlock)
    AIRLOCK_SANITIZER - path to sanitizer script (optional)
    AIRLOCK_RETENTION - retention in days (default 30)
    AIRLOCK_SCHEMA    - path to airlock_index.schema.json (optional; enables validation)

Exit codes:
    0  - success (all records processed, no fatal errors)
    1  - partial failure (some records failed schema validation)
    2  - fatal error (base dir missing, unrecoverable I/O error, etc.)
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stderr)
logger = logging.getLogger("airlock_orchestrator")


# ---------------------------------------------------------------------------
# Schema validation (lightweight, no external deps required)
# ---------------------------------------------------------------------------

REQUIRED_RECORD_FIELDS = {"date", "generated_at_utc", "record_count", "records"}


def validate_record_against_schema(record: Dict[str, Any], schema_path: Optional[Path]) -> Tuple[bool, List[str]]:
    """
    Validate a single record dict.

    If jsonschema is available and schema_path is provided, use it for full
    validation.  Otherwise fall back to a lightweight field-presence check
    based on the required fields declared in airlock_index.schema.json.

    Returns (is_valid, list_of_error_messages).
    """
    errors: List[str] = []

    # Lightweight built-in check
    missing = REQUIRED_RECORD_FIELDS - set(record.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")

    if "date" in record:
        date_val = record["date"]
        if not isinstance(date_val, str) or len(date_val) < 8:
            errors.append(f"'date' must be a non-empty string, got: {type(date_val).__name__!r}")

    if "record_count" in record:
        if not isinstance(record["record_count"], int):
            errors.append(f"'record_count' must be int, got: {type(record['record_count']).__name__!r}")

    if "records" in record:
        if not isinstance(record["records"], list):
            errors.append(f"'records' must be a list, got: {type(record['records']).__name__!r}")

    # Full jsonschema validation (optional, gracefully skipped if not installed)
    if schema_path and schema_path.exists() and not errors:
        try:
            import jsonschema  # type: ignore
            with schema_path.open() as f:
                schema = json.load(f)
            try:
                jsonschema.validate(instance=record, schema=schema)
            except jsonschema.ValidationError as exc:
                errors.append(f"jsonschema: {exc.message}")
        except ImportError:
            logger.debug("jsonschema not installed; skipping full schema validation")

    return (len(errors) == 0), errors


# ---------------------------------------------------------------------------
# Sanitizer integration
# ---------------------------------------------------------------------------

def run_sanitizer(sanitizer_path: Path, target_dir: Path) -> Dict[str, Any]:
    """
    Invoke an external sanitizer script and return its JSON report.

    The sanitizer is called as:
        python <sanitizer_path> --target <target_dir> --json

    If the script does not support --json or returns non-JSON output,
    we treat stdout as a plain message and return a minimal report.
    """
    cmd = [sys.executable, str(sanitizer_path), "--target", str(target_dir), "--json"]
    logger.info("Running sanitizer: %s", " ".join(cmd))
    result = {"invoked": True, "command": cmd, "returncode": None, "report": None, "error": None}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        result["returncode"] = proc.returncode
        if proc.returncode != 0:
            result["error"] = proc.stderr.strip() or "sanitizer returned non-zero exit code"
            logger.warning("Sanitizer exited %d: %s", proc.returncode, result["error"])
        else:
            try:
                result["report"] = json.loads(proc.stdout)
            except json.JSONDecodeError:
                result["report"] = {"raw_output": proc.stdout.strip()}
    except subprocess.TimeoutExpired:
        result["error"] = "sanitizer timed out after 120 s"
        logger.error(result["error"])
    except FileNotFoundError as exc:
        result["error"] = str(exc)
        logger.error("Sanitizer not found: %s", exc)
    return result


# ---------------------------------------------------------------------------
# Core orchestration logic
# ---------------------------------------------------------------------------

def discover_daily_files(daily_dir: Path) -> List[Path]:
    """Return all .json files under daily/ sorted by name (date order)."""
    if not daily_dir.exists():
        return []
    return sorted(daily_dir.glob("*.json"))


def load_record(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Load a JSON record file.  Returns (record, error_message)."""
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"
    except OSError as exc:
        return None, f"I/O error: {exc}"


def build_index(records: List[Dict[str, Any]], date_str: str) -> Dict[str, Any]:
    """Build an Airlock index document from a list of validated records."""
    return {
        "date": date_str,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "records": records,
    }


def write_index(index_dir: Path, date_str: str, index_doc: Dict[str, Any]) -> Path:
    """Persist an index document; returns the written path."""
    index_dir.mkdir(parents=True, exist_ok=True)
    out_path = index_dir / f"{date_str}_index.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(index_doc, f, ensure_ascii=False, indent=2)
    logger.info("Index written: %s", out_path)
    return out_path


def enforce_retention(index_dir: Path, retention_days: int) -> List[str]:
    """
    Delete index files older than retention_days.
    Returns list of deleted file names.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted: List[str] = []
    for f in index_dir.glob("*_index.json"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                f.unlink()
                deleted.append(f.name)
                logger.info("Retention: deleted %s (mtime %s)", f.name, mtime.date())
        except OSError as exc:
            logger.warning("Could not check/delete %s: %s", f.name, exc)
    return deleted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Airlock Orchestrator — nightly processing of daily Airlock records",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--base-dir",
        default=os.environ.get("AIRLOCK_BASE_DIR", ""),
        help="Root of the airlock folder (env: AIRLOCK_BASE_DIR)",
    )
    p.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Date to process in YYYY-MM-DD format (default: today UTC)",
    )
    p.add_argument(
        "--retention",
        type=int,
        default=int(os.environ.get("AIRLOCK_RETENTION", "30")),
        help="Number of days to keep index files (env: AIRLOCK_RETENTION)",
    )
    p.add_argument(
        "--schema",
        default=os.environ.get("AIRLOCK_SCHEMA", ""),
        help="Path to airlock_index.schema.json for validation (env: AIRLOCK_SCHEMA)",
    )
    p.add_argument(
        "--sanitizer",
        default=os.environ.get("AIRLOCK_SANITIZER", ""),
        help="Path to sanitizer script (env: AIRLOCK_SANITIZER). Skipped if not set.",
    )
    p.add_argument(
        "--log-file",
        default="",
        help="Optional path to write the JSON status report (in addition to stdout)",
    )
    p.add_argument(
        "--skip-retention",
        action="store_true",
        help="Skip retention enforcement (useful for dry-run testing)",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ---- Resolve paths ----
    if not args.base_dir:
        logger.error("--base-dir is required (or set AIRLOCK_BASE_DIR)")
        return 2

    base_dir = Path(args.base_dir).expanduser().resolve()
    if not base_dir.exists():
        logger.error("Base directory does not exist: %s", base_dir)
        return 2

    daily_dir = base_dir / "daily"
    index_dir = base_dir / "index"
    schema_path = Path(args.schema).expanduser().resolve() if args.schema else None
    sanitizer_path = Path(args.sanitizer).expanduser().resolve() if args.sanitizer else None

    date_str = args.date

    status: Dict[str, Any] = {
        "orchestrator": "airlock_orchestrator",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "date_processed": date_str,
        "base_dir": str(base_dir),
        "retention_days": args.retention,
        "sanitizer_result": None,
        "files_discovered": 0,
        "files_valid": 0,
        "files_invalid": 0,
        "validation_errors": [],
        "index_written": None,
        "retention_deleted": [],
        "success": False,
        "errors": [],
    }

    exit_code = 0

    # ---- Sanitizer (optional, runs before indexing) ----
    if sanitizer_path:
        sanitizer_result = run_sanitizer(sanitizer_path, daily_dir)
        status["sanitizer_result"] = sanitizer_result
        if sanitizer_result.get("error"):
            status["errors"].append(f"Sanitizer error: {sanitizer_result['error']}")
            # Non-fatal: continue with indexing

    # ---- Discover daily records ----
    daily_files = discover_daily_files(daily_dir)
    logger.info("Discovered %d file(s) in %s", len(daily_files), daily_dir)
    status["files_discovered"] = len(daily_files)

    valid_records: List[Dict[str, Any]] = []
    for file_path in daily_files:
        record, load_err = load_record(file_path)
        if load_err:
            msg = f"{file_path.name}: {load_err}"
            logger.warning(msg)
            status["validation_errors"].append(msg)
            status["files_invalid"] += 1
            exit_code = 1
            continue

        is_valid, schema_errors = validate_record_against_schema(record, schema_path)
        if not is_valid:
            for err in schema_errors:
                msg = f"{file_path.name}: {err}"
                logger.warning(msg)
                status["validation_errors"].append(msg)
            status["files_invalid"] += 1
            exit_code = 1
        else:
            valid_records.append(record)
            status["files_valid"] += 1
            logger.debug("Valid: %s", file_path.name)

    # ---- Build and write index ----
    if valid_records:
        index_doc = build_index(valid_records, date_str)
        try:
            index_path = write_index(index_dir, date_str, index_doc)
            status["index_written"] = str(index_path)
        except OSError as exc:
            msg = f"Failed to write index: {exc}"
            logger.error(msg)
            status["errors"].append(msg)
            exit_code = max(exit_code, 2)
    else:
        logger.info("No valid records found; no index written for %s", date_str)

    # ---- Retention enforcement ----
    if not args.skip_retention and index_dir.exists():
        deleted = enforce_retention(index_dir, args.retention)
        status["retention_deleted"] = deleted
        if deleted:
            logger.info("Retention removed %d index file(s)", len(deleted))

    # ---- Finalise status ----
    status["success"] = (exit_code == 0)

    report = json.dumps(status, ensure_ascii=False, indent=2)
    print(report)

    if args.log_file:
        log_path = Path(args.log_file).expanduser()
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("w", encoding="utf-8") as f:
                f.write(report + "\n")
            logger.info("JSON report written to %s", log_path)
        except OSError as exc:
            logger.warning("Could not write log file: %s", exc)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
