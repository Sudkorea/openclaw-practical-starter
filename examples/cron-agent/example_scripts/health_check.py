#!/usr/bin/env python3
"""
health_check.py — Agent Health Check Script

Pings all registered sub-agents via the OpenClaw sessions API, records their
status, and writes a summary to the Airlock.

Called by: cron-agent (every 30 minutes via cron_jobs.json)
Output:    Console summary + optional Airlock record

Usage:
    python health_check.py [--output-airlock] [--agents agent1,agent2]

Key design decisions:
- Each agent gets a lightweight "ping" message, not a real task, to minimize cost.
- A session that does not respond within PING_TIMEOUT_SECONDS is marked "unresponsive".
- Results are written to a structured JSON file so the nightly_summary.py can consume them.
- This script does NOT restart agents — it only reports status. Restarts require human approval.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration — adapt these to match your actual agent names and paths
# ---------------------------------------------------------------------------

# Names of agents to check. Must match the registered agent names in OpenClaw.
DEFAULT_AGENTS = [
    "study-agent",
    "voice-agent",
    "caine-agent",
    "finance-agent",
]

# How long to wait for a ping response before marking the agent unresponsive.
PING_TIMEOUT_SECONDS = 30

# Where to write the health status JSON for downstream consumption.
HEALTH_STATUS_DIR = Path(
    os.environ.get(
        "HEALTH_STATUS_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/logs/",
    )
)

# Where to write the Airlock record (only when --output-airlock is set).
AIRLOCK_DAILY_DIR = Path(
    os.environ.get(
        "AIRLOCK_DAILY_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/daily/",
    )
)


# ---------------------------------------------------------------------------
# Health check logic
# ---------------------------------------------------------------------------

def ping_agent(agent_name: str) -> dict:
    """
    Send a minimal ping to an agent and return its status.

    In a real OpenClaw integration, you would use the sessions_send tool or
    call the OpenClaw API here. This example shows the pattern using a stub.

    Returns a dict with:
        name:       agent name
        status:     "ok" | "unresponsive" | "error"
        latency_ms: response time in milliseconds (None if unresponsive)
        message:    agent's response or error text
        checked_at: ISO 8601 UTC timestamp
    """
    import time

    start = time.monotonic()
    checked_at = datetime.now(timezone.utc).isoformat()

    # --- STUB: Replace this block with your actual OpenClaw API call ---
    # Example real call (pseudocode):
    #   response = openclaw.sessions_send(
    #       target=agent_name,
    #       message="ping",
    #       timeout=PING_TIMEOUT_SECONDS,
    #   )
    #   if response.status == "ok":
    #       return {"status": "ok", "latency_ms": ..., ...}
    # -------------------------------------------------------------------

    # Simulate: in a real script, this would be the API call result
    print(f"  Pinging {agent_name}...", end=" ", flush=True)
    latency_ms = None
    status = "ok"
    message = "pong"

    # The stub just marks all agents as ok; replace with real logic.
    elapsed = (time.monotonic() - start) * 1000
    latency_ms = round(elapsed, 1)
    print(f"{status} ({latency_ms}ms)")

    return {
        "name": agent_name,
        "status": status,
        "latency_ms": latency_ms,
        "message": message,
        "checked_at": checked_at,
    }


def run_health_check(agent_names: list[str]) -> dict:
    """
    Run health checks for all given agents and return a consolidated report.
    """
    now = datetime.now(timezone.utc)
    results = []

    print(f"Health check at {now.isoformat()}")
    print(f"Checking {len(agent_names)} agents: {', '.join(agent_names)}")
    print("-" * 60)

    for name in agent_names:
        result = ping_agent(name)
        results.append(result)

    # Build summary counts
    ok_count = sum(1 for r in results if r["status"] == "ok")
    unresponsive = [r["name"] for r in results if r["status"] == "unresponsive"]
    error = [r["name"] for r in results if r["status"] == "error"]

    report = {
        "checked_at": now.isoformat(),
        "total": len(results),
        "ok": ok_count,
        "unresponsive": unresponsive,
        "error_agents": error,
        "results": results,
    }

    print("-" * 60)
    print(f"Summary: {ok_count}/{len(results)} OK")
    if unresponsive:
        print(f"  UNRESPONSIVE: {', '.join(unresponsive)}")
    if error:
        print(f"  ERROR: {', '.join(error)}")

    return report


def write_status_json(report: dict) -> Path:
    """
    Write the health report as a JSON file for downstream consumption.
    Always overwrites the same file so the nightly_summary.py can read the latest.
    """
    HEALTH_STATUS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = HEALTH_STATUS_DIR / "health_status_latest.json"

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Status JSON written to: {output_path}")
    return output_path


def write_airlock_record(report: dict, status_path: Path) -> Optional[Path]:
    """
    Write an Airlock record only if there are failures worth noting.
    We do NOT write records for all-ok runs to avoid log noise.
    """
    has_issues = report["unresponsive"] or report["error_agents"]
    if not has_issues:
        print("All agents OK — skipping Airlock record (no issues to log).")
        return None

    AIRLOCK_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{date_str}-cron-health-check.md"
    record_path = AIRLOCK_DAILY_DIR / filename

    unresponsive_list = "\n".join(f"- {n}" for n in report["unresponsive"]) or "None"
    error_list = "\n".join(f"- {n}" for n in report["error_agents"]) or "None"

    record = f"""## TL;DR
Health check at {report['checked_at']}: {report['ok']}/{report['total']} agents OK.
Issues detected: {len(report['unresponsive'])} unresponsive, {len(report['error_agents'])} error.

## Unresponsive agents
{unresponsive_list}

## Error agents
{error_list}

## Full status
See: {status_path}

## Next action
- If unresponsive: check agent logs, restart manually if needed.
- If error: review error message in {status_path} for details.
- If this is the 3rd failure today: escalate to main channel.
"""

    # Append to the daily record (multiple health checks may run per day)
    with open(record_path, "a") as f:
        f.write(record + "\n---\n")

    print(f"Airlock record written to: {record_path}")
    return record_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OpenClaw agent health check")
    parser.add_argument(
        "--output-airlock",
        action="store_true",
        help="Write an Airlock record if any agent is unhealthy",
    )
    parser.add_argument(
        "--agents",
        type=str,
        default=",".join(DEFAULT_AGENTS),
        help=f"Comma-separated agent names (default: {','.join(DEFAULT_AGENTS)})",
    )
    args = parser.parse_args()

    agent_names = [a.strip() for a in args.agents.split(",") if a.strip()]

    report = run_health_check(agent_names)
    status_path = write_status_json(report)

    if args.output_airlock:
        write_airlock_record(report, status_path)

    # Exit with non-zero code if any agent is unhealthy
    # This lets the cron-agent detect failure via exit code.
    if report["unresponsive"] or report["error_agents"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
