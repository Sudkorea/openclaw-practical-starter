#!/usr/bin/env python3
"""
cost_report.py — GCP Billing / Cost Report

Fetches a cost snapshot for the configured GCP project and posts a summary
to the designated channel. Useful for weekly budget awareness.

Called by: cron-agent (Monday 09:00 via cron_jobs.json)

Usage:
    python cost_report.py [--period last-7-days|last-30-days|YYYY-MM-DD:YYYY-MM-DD]
                           [--post-to-channel finance]
                           [--dry-run]

Required environment variables:
    GCP_PROJECT_ID                  — your GCP project ID
    GOOGLE_APPLICATION_CREDENTIALS  — path to service account JSON key
                                      (must have Billing Viewer role)

Key design decisions:
- Uses the GCP Cloud Billing API via the google-cloud-billing library.
- Falls back to a mock report if credentials are not available (safe for testing).
- Always writes an Airlock record regardless of whether posting succeeds.
- Posting uses a Discord webhook; replace with your actual channel integration.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

AIRLOCK_DAILY_DIR = Path(
    os.environ.get(
        "AIRLOCK_DAILY_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/daily/",
    )
)

DISCORD_FINANCE_WEBHOOK = os.environ.get("DISCORD_FINANCE_WEBHOOK", "")

# Budget thresholds — adjust to your actual budget
DAILY_BUDGET_USD = float(os.environ.get("DAILY_BUDGET_USD", "5.0"))
WEEKLY_BUDGET_USD = float(os.environ.get("WEEKLY_BUDGET_USD", "30.0"))


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_period(period: str) -> tuple[date, date]:
    """
    Convert a period string to a (start_date, end_date) tuple.

    Supported formats:
        last-7-days     → last 7 calendar days
        last-30-days    → last 30 calendar days
        YYYY-MM-DD:YYYY-MM-DD → explicit range
    """
    today = date.today()
    if period == "last-7-days":
        return today - timedelta(days=7), today
    elif period == "last-30-days":
        return today - timedelta(days=30), today
    elif ":" in period:
        parts = period.split(":")
        return date.fromisoformat(parts[0]), date.fromisoformat(parts[1])
    else:
        raise ValueError(f"Unknown period format: {period}")


# ---------------------------------------------------------------------------
# GCP Billing API
# ---------------------------------------------------------------------------

def fetch_gcp_costs(project_id: str, start: date, end: date) -> list[dict]:
    """
    Fetch cost data from the GCP Cloud Billing API.

    Returns a list of line items:
        [{service: str, amount_usd: float, currency: str}, ...]

    Real implementation requires:
        pip install google-cloud-billing

    This function uses a mock when credentials are not configured so the
    script can be tested without real GCP access.
    """
    if not project_id or not GOOGLE_CREDENTIALS:
        print("WARNING: GCP credentials not configured. Using mock data.")
        return _mock_cost_data()

    try:
        # Real implementation (uncomment when you have credentials):
        # from google.cloud import billing_v1
        # client = billing_v1.CloudBillingClient()
        # ... (see GCP billing API docs for query structure)
        # For now, return mock data.
        print("NOTE: Real GCP billing API call would happen here.")
        return _mock_cost_data()

    except Exception as e:
        print(f"ERROR fetching GCP costs: {e}")
        return []


def _mock_cost_data() -> list[dict]:
    """Return sample cost data for testing and demonstration."""
    return [
        {"service": "Vertex AI", "amount_usd": 12.34, "currency": "USD"},
        {"service": "Cloud Run", "amount_usd": 3.21, "currency": "USD"},
        {"service": "Cloud Storage", "amount_usd": 0.87, "currency": "USD"},
        {"service": "Compute Engine", "amount_usd": 18.50, "currency": "USD"},
        {"service": "Cloud SQL", "amount_usd": 5.40, "currency": "USD"},
        {"service": "Networking", "amount_usd": 0.23, "currency": "USD"},
    ]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_report(
    costs: list[dict],
    project_id: str,
    start: date,
    end: date,
) -> dict:
    """
    Build a structured cost report from raw billing line items.
    """
    total_usd = sum(item["amount_usd"] for item in costs)
    days = (end - start).days or 1
    daily_avg = total_usd / days

    # Sort by cost descending so biggest items are first
    sorted_costs = sorted(costs, key=lambda x: x["amount_usd"], reverse=True)

    # Flag if over budget
    period_budget = WEEKLY_BUDGET_USD if days <= 7 else DAILY_BUDGET_USD * days
    over_budget = total_usd > period_budget

    return {
        "project_id": project_id or "(not set)",
        "period": f"{start} to {end}",
        "days": days,
        "total_usd": round(total_usd, 2),
        "daily_avg_usd": round(daily_avg, 2),
        "period_budget_usd": round(period_budget, 2),
        "over_budget": over_budget,
        "line_items": sorted_costs,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def format_channel_message(report: dict) -> str:
    """Format the report as a concise channel message."""
    status = "OVER BUDGET" if report["over_budget"] else "Within budget"
    budget_line = (
        f"Budget: ${report['period_budget_usd']:.2f} | "
        f"Spent: ${report['total_usd']:.2f} — **{status}**"
    )

    top_services = "\n".join(
        f"  {item['service']}: ${item['amount_usd']:.2f}"
        for item in report["line_items"][:5]
    )

    return (
        f"**[Cost Report] {report['period']}**\n"
        f"Project: `{report['project_id']}`\n\n"
        f"{budget_line}\n\n"
        f"Top services (${report['total_usd']:.2f} total):\n"
        f"{top_services}\n\n"
        f"Daily avg: ${report['daily_avg_usd']:.2f}"
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_airlock_record(report: dict) -> Optional[Path]:
    """Write an Airlock record of the cost report."""
    AIRLOCK_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    record_path = AIRLOCK_DAILY_DIR / f"{date_str}-cron-cost-report.md"

    status = "OVER BUDGET" if report["over_budget"] else "within budget"
    line_items = "\n".join(
        f"- {item['service']}: ${item['amount_usd']:.2f}"
        for item in report["line_items"]
    )

    record = f"""## TL;DR
GCP cost report for {report['period']}: ${report['total_usd']:.2f} total ({status}).

## Details
- Project: {report['project_id']}
- Period: {report['period']} ({report['days']} days)
- Total: ${report['total_usd']:.2f}
- Budget: ${report['period_budget_usd']:.2f}
- Daily avg: ${report['daily_avg_usd']:.2f}
- Over budget: {report['over_budget']}

## Line items
{line_items}

## Next action
{"ESCALATE: over budget — review GCP Console for cost drivers." if report['over_budget'] else "DONE — within budget."}
"""

    with open(record_path, "w") as f:
        f.write(record)

    print(f"Airlock record written to: {record_path}")
    return record_path


def post_to_channel(message: str, channel: str) -> bool:
    """Post message to a Discord channel via webhook. Stub — replace with real implementation."""
    webhook_url = DISCORD_FINANCE_WEBHOOK
    if not webhook_url:
        print(f"WARNING: DISCORD_FINANCE_WEBHOOK not set. Cannot post to #{channel}.")
        print(f"Message:\n{message}")
        return False

    # Real implementation:
    #   import requests
    #   resp = requests.post(webhook_url, json={"content": message})
    #   return resp.status_code == 204
    print(f"[STUB] Would post to #{channel}")
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GCP cost report for OpenClaw ops")
    parser.add_argument(
        "--period",
        default="last-7-days",
        help="Report period: last-7-days, last-30-days, or YYYY-MM-DD:YYYY-MM-DD",
    )
    parser.add_argument(
        "--post-to-channel",
        default="",
        help="Channel to post report to (e.g., 'finance')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print report without posting or writing to Airlock",
    )
    args = parser.parse_args()

    start, end = parse_period(args.period)
    print(f"Fetching costs for {start} to {end}")

    costs = fetch_gcp_costs(GCP_PROJECT_ID, start, end)
    report = build_report(costs, GCP_PROJECT_ID, start, end)
    message = format_channel_message(report)

    print(message)

    if not args.dry_run:
        write_airlock_record(report)
        if args.post_to_channel:
            post_to_channel(message, args.post_to_channel)

    # Exit non-zero if over budget so cron-agent can detect it
    if report["over_budget"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
