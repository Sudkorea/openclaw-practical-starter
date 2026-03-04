#!/usr/bin/env python3
"""
nightly_summary.py — Nightly / Morning Ops Summary

Reads the day's Airlock records and health check status, then produces a
structured summary suitable for posting to the #ops Discord channel.

Called by: cron-agent
  - Nightly mode (22:30): summarize today
  - Morning mode (09:00): summarize yesterday

Usage:
    python nightly_summary.py [--date today|yesterday|YYYY-MM-DD]
                               [--mode nightly|morning-briefing]
                               [--post-to-channel ops]
                               [--dry-run]

Key design decisions:
- Reads only from the Airlock daily directory — does not re-query agents.
- "morning-briefing" mode is shorter (failed jobs + today's schedule only).
- "nightly" mode is full (all jobs, health status, study queue count, tomorrow's schedule).
- --dry-run prints the message without posting it to Discord.
- Posting to Discord uses a simple webhook env var; swap for your actual channel integration.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AIRLOCK_DAILY_DIR = Path(
    os.environ.get(
        "AIRLOCK_DAILY_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/daily/",
    )
)

AIRLOCK_STUDY_QUEUE_DIR = Path(
    os.environ.get(
        "AIRLOCK_STUDY_QUEUE_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/study_queue/",
    )
)

HEALTH_STATUS_PATH = Path(
    os.environ.get(
        "HEALTH_STATUS_PATH",
        "~/.openclaw/repos/obsidian-vault/airlock/logs/health_status_latest.json",
    )
)

CRON_JOBS_PATH = Path(
    os.environ.get(
        "CRON_JOBS_PATH",
        "~/.openclaw/repos/openclaw-practical-starter/examples/cron-agent/cron_jobs.json",
    )
)

# Discord webhook URL for posting to the ops channel.
# Set DISCORD_OPS_WEBHOOK in your environment.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_OPS_WEBHOOK", "")


# ---------------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------------

def resolve_date(date_arg: str) -> date:
    """Convert 'today', 'yesterday', or 'YYYY-MM-DD' to a date object."""
    today = date.today()
    if date_arg == "today":
        return today
    elif date_arg == "yesterday":
        return today - timedelta(days=1)
    else:
        return date.fromisoformat(date_arg)


def collect_airlock_records(target_date: date) -> list[dict]:
    """
    Read all Airlock daily records for the given date.
    Extracts TL;DR, agent name, and status from each markdown file.
    """
    date_prefix = target_date.strftime("%Y-%m-%d")
    records = []

    if not AIRLOCK_DAILY_DIR.exists():
        return records

    for path in sorted(AIRLOCK_DAILY_DIR.glob(f"{date_prefix}-*.md")):
        record = parse_airlock_record(path)
        records.append(record)

    return records


def parse_airlock_record(path: Path) -> dict:
    """
    Parse a minimal set of fields from an Airlock markdown record.
    We only need the TL;DR and a rough status (success/failure/escalated).
    """
    filename = path.stem  # e.g., 2026-02-18-cron-health-check
    parts = filename.split("-", 3)
    agent_name = parts[2] if len(parts) > 2 else "unknown"
    slug = parts[3] if len(parts) > 3 else filename

    tldr = ""
    status = "unknown"

    try:
        content = path.read_text()
        # Extract TL;DR line (first non-empty line after "## TL;DR")
        match = re.search(r"##\s+TL;DR\s*\n(.+)", content)
        if match:
            tldr = match.group(1).strip()

        # Infer status from content keywords
        lower = content.lower()
        if any(word in lower for word in ["failed", "error", "unresponsive", "failure"]):
            status = "failure"
        elif any(word in lower for word in ["escalat"]):
            status = "escalated"
        else:
            status = "success"
    except Exception as e:
        tldr = f"(could not parse: {e})"
        status = "parse_error"

    return {
        "filename": path.name,
        "agent": agent_name,
        "slug": slug,
        "tldr": tldr,
        "status": status,
        "path": str(path),
    }


def get_health_status() -> Optional[dict]:
    """Load the latest health check status JSON."""
    if not HEALTH_STATUS_PATH.exists():
        return None
    try:
        return json.loads(HEALTH_STATUS_PATH.read_text())
    except Exception:
        return None


def count_study_queue(target_date: date) -> int:
    """Count the number of study queue entries for the given date."""
    date_str = target_date.strftime("%Y-%m-%d")
    queue_file = AIRLOCK_STUDY_QUEUE_DIR / f"{date_str}.json"
    if not queue_file.exists():
        return 0
    try:
        data = json.loads(queue_file.read_text())
        return len(data) if isinstance(data, list) else 0
    except Exception:
        return 0


def load_cron_jobs() -> list[dict]:
    """Load the enabled cron jobs from the schedule file."""
    if not CRON_JOBS_PATH.exists():
        return []
    try:
        data = json.loads(CRON_JOBS_PATH.read_text())
        return [j for j in data.get("jobs", []) if j.get("enabled", True)]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def build_nightly_summary(target_date: date) -> str:
    """Full nightly summary: all jobs, health, study queue, tomorrow schedule."""
    records = collect_airlock_records(target_date)
    health = get_health_status()
    study_count = count_study_queue(target_date)
    date_str = target_date.strftime("%Y-%m-%d")

    successes = [r for r in records if r["status"] == "success"]
    failures = [r for r in records if r["status"] in ("failure", "escalated", "parse_error")]

    lines = [
        f"**[Nightly Summary] {date_str}**",
        "",
        f"Jobs recorded: {len(records)} | OK: {len(successes)} | Issues: {len(failures)}",
    ]

    if failures:
        lines.append("\n**Failed / escalated jobs:**")
        for r in failures:
            lines.append(f"  - [{r['agent']}] {r['slug']}: {r['tldr']}")

    if health:
        ok = health.get("ok", 0)
        total = health.get("total", 0)
        unresponsive = health.get("unresponsive", [])
        lines.append(f"\nAgent health: {ok}/{total} OK")
        if unresponsive:
            lines.append(f"  Unresponsive: {', '.join(unresponsive)}")

    lines.append(f"\nStudy queue candidates today: {study_count}")
    lines.append("\nTomorrow's first 3 scheduled jobs:")

    jobs = load_cron_jobs()
    for j in jobs[:3]:
        lines.append(f"  - {j['id']} [{j['schedule']}]")

    return "\n".join(lines)


def build_morning_briefing(target_date: date) -> str:
    """Short morning briefing: overnight failures and today's first jobs."""
    records = collect_airlock_records(target_date)
    date_str = target_date.strftime("%Y-%m-%d")

    failures = [r for r in records if r["status"] in ("failure", "escalated")]

    lines = [
        f"**[Morning Briefing] {date_str}**",
        "",
    ]

    if not failures:
        lines.append("Overnight: no failures.")
    else:
        lines.append(f"Overnight issues ({len(failures)}):")
        for r in failures:
            lines.append(f"  - [{r['agent']}] {r['slug']}: {r['tldr']}")

    jobs = load_cron_jobs()
    lines.append("\nFirst 3 jobs today:")
    for j in jobs[:3]:
        lines.append(f"  - {j['id']} [{j['schedule']}] → {j['target']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Channel posting
# ---------------------------------------------------------------------------

def post_to_discord(message: str, channel: str) -> bool:
    """
    Post a message to a Discord channel via webhook.

    Real implementation: use requests.post with the Discord webhook URL.
    Replace this stub with your actual posting logic.
    """
    webhook_url = DISCORD_WEBHOOK_URL

    if not webhook_url:
        print(
            f"WARNING: DISCORD_OPS_WEBHOOK not set. "
            f"Cannot post to #{channel}. Message:\n{message}"
        )
        return False

    # Stub: in production, use:
    #   import requests
    #   response = requests.post(webhook_url, json={"content": message})
    #   return response.status_code == 204
    print(f"[STUB] Would post to #{channel} via webhook.")
    print(f"Message:\n{message}")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OpenClaw nightly/morning ops summary")
    parser.add_argument(
        "--date",
        default="today",
        help="Date to summarize: 'today', 'yesterday', or 'YYYY-MM-DD'",
    )
    parser.add_argument(
        "--mode",
        choices=["nightly", "morning-briefing"],
        default="nightly",
        help="Summary mode (default: nightly)",
    )
    parser.add_argument(
        "--post-to-channel",
        default="",
        help="Discord channel name to post to (e.g., 'ops')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the message without posting it",
    )
    args = parser.parse_args()

    target_date = resolve_date(args.date)

    if args.mode == "nightly":
        message = build_nightly_summary(target_date)
    else:
        message = build_morning_briefing(target_date)

    print(message)

    if args.post_to_channel and not args.dry_run:
        success = post_to_discord(message, args.post_to_channel)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
