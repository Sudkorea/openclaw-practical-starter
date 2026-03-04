#!/usr/bin/env python3
"""
kpi_snapshot.py

KPI snapshot collector for OpenClaw multi-agent operations.

Responsibilities:
- Collect agent performance metrics (response times, task counts)
- Measure cron job success rates from log files or a SQLite state DB
- Track response latency distribution (p50, p90, p99)
- Emit a structured JSON report to stdout
- Optionally append the report to a historical JSONL file

Environment variables (all overridable via CLI args):
    KPI_BASE_DIR     - workspace base dir containing agents/ and logs/
    KPI_HISTORY_FILE - path to the JSONL history file (default: <base_dir>/kpi_history.jsonl)
    KPI_CRON_LOG     - path to cron-agent log file (optional)
    KPI_AGENT_LOG    - path to agent execution log file (optional)

Output:
    A single JSON document on stdout.  If --history-file is set (or
    KPI_HISTORY_FILE is set), the snapshot is also appended there as one
    JSONL line so long-term trends can be analysed.

Exit codes:
    0  - report generated successfully
    1  - one or more metrics could not be collected (partial report)
    2  - fatal error (base dir not found, unreadable config, etc.)
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stderr)
logger = logging.getLogger("kpi_snapshot")


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def percentile(values: List[float], pct: float) -> Optional[float]:
    """Return the p<pct> value of a sorted list.  Returns None if empty."""
    if not values:
        return None
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (pct / 100.0)
    lo = int(k)
    hi = lo + 1
    if hi >= len(sorted_v):
        return round(sorted_v[lo], 4)
    frac = k - lo
    return round(sorted_v[lo] + frac * (sorted_v[hi] - sorted_v[lo]), 4)


def safe_ratio(numerator: int, denominator: int) -> Optional[float]:
    """Return numerator/denominator as %, or None if denominator is 0."""
    if denominator == 0:
        return None
    return round(100.0 * numerator / denominator, 2)


# ---------------------------------------------------------------------------
# Log parsers
# ---------------------------------------------------------------------------

# Patterns tuned for Python logging output:
#   2025-01-15 03:00:01,234 [INFO] cron_agent: job=nightly_backup status=success duration_ms=1234
CRON_LINE_RE = re.compile(
    r"job=(?P<job>\S+)\s+status=(?P<status>success|failure|error)\s+(?:duration_ms=(?P<dur>\d+))?"
)

# Agent execution lines:
#   2025-01-15 03:00:05,678 [INFO] agent: task=summarise agent=study response_ms=890
AGENT_LINE_RE = re.compile(
    r"task=(?P<task>\S+)\s+agent=(?P<agent>\S+)\s+(?:response_ms=(?P<rms>\d+))?"
)


def parse_cron_log(log_path: Path) -> Dict[str, Any]:
    """
    Parse a cron-agent log file and return success/failure counts per job.
    """
    job_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"success": 0, "failure": 0, "total": 0})
    durations: List[float] = []
    lines_read = 0

    try:
        with log_path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                lines_read += 1
                m = CRON_LINE_RE.search(line)
                if not m:
                    continue
                job = m.group("job")
                status = m.group("status")
                dur = m.group("dur")
                job_stats[job]["total"] += 1
                if status == "success":
                    job_stats[job]["success"] += 1
                else:
                    job_stats[job]["failure"] += 1
                if dur:
                    durations.append(float(dur))
    except OSError as exc:
        logger.warning("Cannot read cron log %s: %s", log_path, exc)
        return {"error": str(exc), "lines_read": 0, "jobs": {}}

    total_runs = sum(v["total"] for v in job_stats.values())
    total_success = sum(v["success"] for v in job_stats.values())

    return {
        "log_path": str(log_path),
        "lines_read": lines_read,
        "total_runs": total_runs,
        "total_success": total_success,
        "total_failure": total_runs - total_success,
        "overall_success_rate_pct": safe_ratio(total_success, total_runs),
        "duration_ms": {
            "p50": percentile(durations, 50),
            "p90": percentile(durations, 90),
            "p99": percentile(durations, 99),
            "count": len(durations),
        },
        "jobs": {
            job: {
                "success": v["success"],
                "failure": v["failure"],
                "total": v["total"],
                "success_rate_pct": safe_ratio(v["success"], v["total"]),
            }
            for job, v in sorted(job_stats.items())
        },
    }


def parse_agent_log(log_path: Path) -> Dict[str, Any]:
    """
    Parse an agent execution log and return per-agent response time stats.
    """
    agent_times: Dict[str, List[float]] = defaultdict(list)
    task_counts: Dict[str, int] = defaultdict(int)
    lines_read = 0

    try:
        with log_path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                lines_read += 1
                m = AGENT_LINE_RE.search(line)
                if not m:
                    continue
                agent = m.group("agent")
                task = m.group("task")
                rms = m.group("rms")
                task_counts[f"{agent}/{task}"] += 1
                if rms:
                    agent_times[agent].append(float(rms))
    except OSError as exc:
        logger.warning("Cannot read agent log %s: %s", log_path, exc)
        return {"error": str(exc), "lines_read": 0, "agents": {}}

    agents_report: Dict[str, Any] = {}
    for agent, times in sorted(agent_times.items()):
        agents_report[agent] = {
            "sample_count": len(times),
            "response_ms": {
                "p50": percentile(times, 50),
                "p90": percentile(times, 90),
                "p99": percentile(times, 99),
                "min": round(min(times), 4) if times else None,
                "max": round(max(times), 4) if times else None,
                "mean": round(sum(times) / len(times), 4) if times else None,
            },
        }

    return {
        "log_path": str(log_path),
        "lines_read": lines_read,
        "task_counts": dict(sorted(task_counts.items())),
        "agents": agents_report,
    }


# ---------------------------------------------------------------------------
# Airlock record count (proxy for agent productivity)
# ---------------------------------------------------------------------------

def count_airlock_records(base_dir: Path) -> Dict[str, Any]:
    """
    Count today's and total Airlock records as a productivity proxy.
    """
    airlock_dir = base_dir / "airlock" / "daily"
    if not airlock_dir.exists():
        return {"error": f"airlock/daily not found under {base_dir}", "total_files": 0}

    all_files = list(airlock_dir.glob("*.json"))
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_files = [f for f in all_files if today_str in f.name]

    return {
        "airlock_daily_dir": str(airlock_dir),
        "total_files": len(all_files),
        "today_files": len(today_files),
        "today_date_utc": today_str,
    }


# ---------------------------------------------------------------------------
# History persistence
# ---------------------------------------------------------------------------

def append_to_history(history_file: Path, snapshot: Dict[str, Any]) -> None:
    """Append snapshot as a single JSONL line to the history file."""
    try:
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
        logger.info("Snapshot appended to history: %s", history_file)
    except OSError as exc:
        logger.warning("Could not append to history file %s: %s", history_file, exc)


def load_history_summary(history_file: Path, last_n: int = 7) -> Optional[Dict[str, Any]]:
    """Return a brief summary of the last N snapshots (trend data)."""
    if not history_file.exists():
        return None
    snapshots: List[Dict[str, Any]] = []
    try:
        with history_file.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        snapshots.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except OSError:
        return None

    recent = snapshots[-last_n:]
    return {
        "total_snapshots": len(snapshots),
        "last_n": last_n,
        "recent_timestamps": [s.get("snapshot_at_utc") for s in recent],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="KPI Snapshot — collect agent and cron performance metrics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--base-dir",
        default=os.environ.get("KPI_BASE_DIR", ""),
        help="Workspace base directory (env: KPI_BASE_DIR)",
    )
    p.add_argument(
        "--cron-log",
        default=os.environ.get("KPI_CRON_LOG", ""),
        help="Path to cron-agent log file (env: KPI_CRON_LOG)",
    )
    p.add_argument(
        "--agent-log",
        default=os.environ.get("KPI_AGENT_LOG", ""),
        help="Path to agent execution log file (env: KPI_AGENT_LOG)",
    )
    p.add_argument(
        "--history-file",
        default=os.environ.get("KPI_HISTORY_FILE", ""),
        help="JSONL file to append snapshots to (env: KPI_HISTORY_FILE)",
    )
    p.add_argument(
        "--history-last-n",
        type=int,
        default=7,
        help="Number of recent snapshots to summarise in output",
    )
    p.add_argument(
        "--no-history",
        action="store_true",
        help="Skip writing to history file even if configured",
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

    exit_code = 0

    snapshot: Dict[str, Any] = {
        "snapshot_at_utc": datetime.now(timezone.utc).isoformat(),
        "collector": "kpi_snapshot",
        "base_dir": args.base_dir or None,
        "cron_metrics": None,
        "agent_metrics": None,
        "airlock_metrics": None,
        "history_summary": None,
        "warnings": [],
    }

    # ---- Cron job metrics ----
    if args.cron_log:
        cron_log_path = Path(args.cron_log).expanduser().resolve()
        logger.info("Parsing cron log: %s", cron_log_path)
        cron_result = parse_cron_log(cron_log_path)
        snapshot["cron_metrics"] = cron_result
        if "error" in cron_result:
            snapshot["warnings"].append(f"cron_metrics: {cron_result['error']}")
            exit_code = max(exit_code, 1)
    else:
        logger.info("No cron log specified; skipping cron metrics")
        snapshot["warnings"].append("cron_metrics: no --cron-log provided")

    # ---- Agent response time metrics ----
    if args.agent_log:
        agent_log_path = Path(args.agent_log).expanduser().resolve()
        logger.info("Parsing agent log: %s", agent_log_path)
        agent_result = parse_agent_log(agent_log_path)
        snapshot["agent_metrics"] = agent_result
        if "error" in agent_result:
            snapshot["warnings"].append(f"agent_metrics: {agent_result['error']}")
            exit_code = max(exit_code, 1)
    else:
        logger.info("No agent log specified; skipping agent metrics")
        snapshot["warnings"].append("agent_metrics: no --agent-log provided")

    # ---- Airlock productivity proxy ----
    if args.base_dir:
        base_dir = Path(args.base_dir).expanduser().resolve()
        if base_dir.exists():
            snapshot["airlock_metrics"] = count_airlock_records(base_dir)
        else:
            msg = f"base_dir does not exist: {base_dir}"
            logger.warning(msg)
            snapshot["warnings"].append(msg)
            exit_code = max(exit_code, 1)
    else:
        snapshot["warnings"].append("airlock_metrics: no --base-dir provided")

    # ---- History ----
    history_file_path: Optional[Path] = None
    if args.history_file:
        history_file_path = Path(args.history_file).expanduser().resolve()
    elif args.base_dir:
        history_file_path = Path(args.base_dir).expanduser().resolve() / "kpi_history.jsonl"

    if history_file_path and not args.no_history:
        append_to_history(history_file_path, snapshot)
        snapshot["history_summary"] = load_history_summary(history_file_path, args.history_last_n)
        snapshot["history_file"] = str(history_file_path)

    # ---- Output ----
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
