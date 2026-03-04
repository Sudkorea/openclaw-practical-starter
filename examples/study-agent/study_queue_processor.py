#!/usr/bin/env python3
"""
study_queue_processor.py — Study Queue Curation and Review

Core processing script for the study-agent. Reads Airlock daily records,
extracts study candidates, applies spaced repetition scheduling, and
maintains the study queue JSON files.

Usage:
    # Nightly curation (called by cron-agent)
    python study_queue_processor.py --mode curate --date today

    # Review session (called manually or by operator)
    python study_queue_processor.py --mode review --date today

    # Show pending reviews
    python study_queue_processor.py --mode pending

    # Mark item as known/failed/skip
    python study_queue_processor.py --mode mark --item-id ID --result known|failed|skip

Key design decisions:
- The queue is stored as a flat list of JSON items per day; items persist
  indefinitely (state transitions rather than deletion).
- State machine: unknown -> learning -> known (or reset to learning on failure)
- Extraction logic is intentionally simple: keyword/pattern matching + LLM
  classification. The LLM call is optional and falls back to heuristics.
- All state changes are logged to Airlock for auditability.
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

STUDY_QUEUE_DIR = Path(
    os.environ.get(
        "STUDY_QUEUE_DIR",
        "~/.openclaw/repos/obsidian-vault/airlock/study_queue/",
    )
)

CONFIG_DIR = Path(__file__).parent / "config"

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_study_profile() -> dict:
    """Load user study preferences from config/study_profile.json."""
    path = CONFIG_DIR / "study_profile.json"
    if not path.exists():
        # Return safe defaults if config is missing
        return {
            "max_items_per_day": 10,
            "language": "English",
            "skip_topics": [],
            "priority_topics": [],
            "output_format": "json",
        }
    return json.loads(path.read_text())


def load_review_schedule() -> dict:
    """Load spaced repetition intervals from config/review_schedule.json."""
    path = CONFIG_DIR / "review_schedule.json"
    if not path.exists():
        # Standard spaced repetition intervals in days
        return {
            "intervals": [3, 7, 21, 60],
            "failure_reset_to": 0,  # Reset to first interval on failure
        }
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Queue persistence
# ---------------------------------------------------------------------------

def load_queue(queue_date: Optional[date] = None) -> list[dict]:
    """
    Load all queue items from the study_queue directory.
    Merges all queue files to get the complete active queue.
    Items are identified by their 'id' field; duplicates take the latest version.
    """
    items_by_id: dict[str, dict] = {}

    if not STUDY_QUEUE_DIR.exists():
        return []

    # Load all queue files, sorted by date (oldest first so newer overrides)
    for path in sorted(STUDY_QUEUE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            if isinstance(data, list):
                for item in data:
                    if "id" in item:
                        items_by_id[item["id"]] = item
        except Exception as e:
            print(f"WARNING: Could not load queue file {path.name}: {e}")

    return list(items_by_id.values())


def save_queue_for_date(items: list[dict], target_date: date) -> Path:
    """
    Save items to the queue file for the given date.
    Only saves items that were created on or modified on that date.
    """
    STUDY_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    date_str = target_date.strftime("%Y-%m-%d")
    output_path = STUDY_QUEUE_DIR / f"{date_str}.json"

    with open(output_path, "w") as f:
        json.dump(items, f, indent=2)

    return output_path


def find_existing_item(queue: list[dict], topic: str, days: int = 7) -> Optional[dict]:
    """
    Find an existing queue item by topic similarity.
    Returns the item if a match is found within the last `days` days.
    """
    cutoff = date.today() - timedelta(days=days)
    topic_lower = topic.lower()

    for item in queue:
        # Simple substring match — replace with semantic similarity if needed
        if topic_lower in item.get("topic", "").lower():
            first_seen = date.fromisoformat(item.get("first_seen", "2000-01-01"))
            if first_seen >= cutoff:
                return item

    return None


# ---------------------------------------------------------------------------
# Study candidate extraction
# ---------------------------------------------------------------------------

# Keywords that suggest a study candidate in an Airlock record
CANDIDATE_SIGNALS = [
    "error", "failed", "exception", "timeout", "retry", "traceback",
    "first time", "new pattern", "didn't know", "study_candidate: yes",
    "study candidate: yes", "learning opportunity",
]


def is_study_candidate(content: str) -> bool:
    """
    Heuristic check: does this Airlock record content suggest a study candidate?
    Returns True if any signal keyword is found.
    """
    content_lower = content.lower()
    return any(signal in content_lower for signal in CANDIDATE_SIGNALS)


def extract_topic_from_record(path: Path, content: str) -> Optional[str]:
    """
    Extract a topic name from an Airlock record.
    Tries: explicit 'Tags:' line, then filename slug, then TL;DR first noun phrase.
    Returns None if no topic can be extracted.
    """
    # 1. Check for explicit 'Tags:' or 'Topic:' line
    for line in content.splitlines():
        line = line.strip()
        if line.lower().startswith("**tags**:") or line.lower().startswith("tags:"):
            tags = re.split(r"[,;]", line.split(":", 1)[1])
            if tags:
                return tags[0].strip().strip("*")
        if line.lower().startswith("**topic**:") or line.lower().startswith("topic:"):
            return line.split(":", 1)[1].strip().strip("*")

    # 2. Fall back to filename slug (e.g., "2026-02-18-api-agent-vertex-error" -> "vertex error")
    slug = path.stem
    parts = slug.split("-")
    # Skip the date prefix (4 parts) and agent name (1 part)
    if len(parts) > 5:
        topic_parts = parts[5:]
        return " ".join(topic_parts).replace("-", " ")

    return None


def extract_tldr(content: str) -> str:
    """Extract the TL;DR from an Airlock record."""
    match = re.search(r"##\s+TL;DR\s*\n(.+)", content)
    if match:
        return match.group(1).strip()
    return ""


def generate_concept_summary(topic: str, tldr: str, content: str) -> str:
    """
    Generate a concept summary for a study item.

    In a real agent context, this would be an LLM call. Here we produce a
    structured stub that shows the expected format. Replace with your
    actual LLM API call.

    The summary should be 1-3 sentences:
    - What the concept is
    - Why it matters in practice
    - The key thing to remember
    """
    # Real implementation: call your LLM with a focused prompt like:
    #   prompt = f"""
    #   Based on this Airlock record about "{topic}", write a 1-3 sentence
    #   concept summary that explains:
    #   1. What the concept is
    #   2. Why it matters in practice
    #   3. The key thing to remember
    #
    #   TL;DR: {tldr}
    #   [Optional context from content]
    #
    #   Summary (concise, no filler):
    #   """
    #   return llm.complete(prompt).strip()

    # Stub: return a template-filled placeholder
    return (
        f"{topic}: {tldr}. "
        f"(Replace this with a generated concept summary by integrating an LLM call "
        f"in the generate_concept_summary function.)"
    )


def generate_self_check_question(topic: str, summary: str) -> str:
    """
    Generate a self-check question for spaced repetition review.

    Real implementation: LLM call.
    Stub: template-based question.
    """
    return f"Explain {topic} and describe the most important thing to remember when you encounter it."


# ---------------------------------------------------------------------------
# Queue item construction
# ---------------------------------------------------------------------------

def build_queue_item(
    topic: str,
    source_path: Path,
    content: str,
    tldr: str,
    schedule: dict,
    priority: str = "medium",
) -> dict:
    """Build a complete study queue item from extracted data."""
    today = date.today()
    item_id = f"{today.strftime('%Y-%m-%d')}-{topic.lower().replace(' ', '-')[:40]}"

    intervals = schedule.get("intervals", [3, 7, 21, 60])
    first_review = today + timedelta(days=intervals[0])

    summary = generate_concept_summary(topic, tldr, content)
    question = generate_self_check_question(topic, summary)

    return {
        "id": item_id,
        "topic": topic,
        "source_file": str(source_path),
        "first_seen": today.isoformat(),
        "next_review": first_review.isoformat(),
        "review_count": 0,
        "state": "learning",
        "priority": priority,
        "concept_summary": summary,
        "self_check_question": question,
        "rag_indexed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Review session
# ---------------------------------------------------------------------------

def get_pending_reviews(queue: list[dict]) -> list[dict]:
    """Return all queue items due for review today or earlier."""
    today = date.today()
    return [
        item for item in queue
        if item.get("state") == "learning"
        and date.fromisoformat(item.get("next_review", "2099-01-01")) <= today
    ]


def advance_review(item: dict, schedule: dict) -> dict:
    """
    Mark an item as successfully reviewed and schedule the next review.
    Returns the updated item.
    """
    intervals = schedule.get("intervals", [3, 7, 21, 60])
    review_count = item.get("review_count", 0) + 1
    item["review_count"] = review_count

    if review_count >= len(intervals):
        # Completed all review intervals — mark as known
        item["state"] = "known"
        item["next_review"] = None
        print(f"  KNOWN: {item['topic']} — completed all review intervals.")
    else:
        next_interval = intervals[review_count]
        next_date = date.today() + timedelta(days=next_interval)
        item["next_review"] = next_date.isoformat()
        print(f"  OK: {item['topic']} — next review in {next_interval} days ({next_date}).")

    return item


def reset_review(item: dict, schedule: dict) -> dict:
    """
    Reset an item after a failed review back to the first interval.
    Returns the updated item.
    """
    intervals = schedule.get("intervals", [3, 7, 21, 60])
    reset_to = schedule.get("failure_reset_to", 0)
    next_date = date.today() + timedelta(days=intervals[reset_to])
    item["review_count"] = reset_to
    item["next_review"] = next_date.isoformat()
    item["state"] = "learning"
    print(f"  RESET: {item['topic']} — back to {intervals[reset_to]}-day review ({next_date}).")
    return item


def mark_item(queue: list[dict], item_id: str, result: str, schedule: dict) -> list[dict]:
    """Update a specific item in the queue by ID."""
    for i, item in enumerate(queue):
        if item["id"] == item_id:
            if result == "known":
                queue[i] = advance_review(item, schedule)
            elif result == "failed":
                queue[i] = reset_review(item, schedule)
            elif result == "skip":
                queue[i]["state"] = "skipped"
                print(f"  SKIPPED: {item['topic']}")
            break
    else:
        print(f"ERROR: Item {item_id} not found in queue.")
    return queue


# ---------------------------------------------------------------------------
# Airlock record
# ---------------------------------------------------------------------------

def write_curation_record(
    date_str: str,
    added: list[dict],
    skipped: list[tuple[str, str]],
    files_read: int,
) -> Path:
    """Write an Airlock record of the curation run."""
    AIRLOCK_DAILY_DIR.mkdir(parents=True, exist_ok=True)
    record_path = AIRLOCK_DAILY_DIR / f"{date_str}-study-agent-curation.md"

    added_list = "\n".join(
        f"- [{item['priority']}] {item['topic']}: next review {item['next_review']}"
        for item in added
    ) or "None"

    skipped_list = "\n".join(
        f"- {topic}: {reason}"
        for topic, reason in skipped
    ) or "None"

    record = f"""## TL;DR
Curation for {date_str}: {len(added)} items added to study queue, {len(skipped)} skipped.

## Sources read
- {files_read} airlock daily files processed

## New items added
{added_list}

## Skipped
{skipped_list}

## RAG indexing
Pending — run knowledge_extractor.py to index new items.

## Next action
DONE — review session due in 3 days.
"""

    with open(record_path, "w") as f:
        f.write(record)

    return record_path


# ---------------------------------------------------------------------------
# Main modes
# ---------------------------------------------------------------------------

def mode_curate(target_date: date, profile: dict, schedule: dict) -> None:
    """Run the nightly curation: read airlock records, extract candidates, update queue."""
    date_str = target_date.strftime("%Y-%m-%d")
    print(f"Curating study candidates for {date_str}")

    existing_queue = load_queue()
    max_items = profile.get("max_items_per_day", 10)
    skip_topics = [t.lower() for t in profile.get("skip_topics", [])]

    new_items = []
    skipped = []
    files_read = 0

    if not AIRLOCK_DAILY_DIR.exists():
        print(f"WARNING: Airlock daily dir not found: {AIRLOCK_DAILY_DIR}")
    else:
        for path in sorted(AIRLOCK_DAILY_DIR.glob(f"{date_str}-*.md")):
            # Skip records written by the study-agent itself
            if "study-agent" in path.stem:
                continue

            files_read += 1
            try:
                content = path.read_text()
            except Exception as e:
                print(f"  WARNING: Could not read {path.name}: {e}")
                continue

            if not is_study_candidate(content):
                continue

            topic = extract_topic_from_record(path, content)
            if not topic:
                skipped.append((path.stem, "could not extract topic"))
                continue

            if any(skip in topic.lower() for skip in skip_topics):
                skipped.append((topic, "in skip_topics list"))
                continue

            existing = find_existing_item(existing_queue, topic, days=7)
            if existing:
                skipped.append((topic, f"duplicate of {existing['id']}"))
                continue

            # Check if already marked as known
            known = next((i for i in existing_queue if topic.lower() in i.get("topic", "").lower() and i.get("state") == "known"), None)
            if known:
                skipped.append((topic, "already in 'known' state"))
                continue

            if len(new_items) >= max_items:
                skipped.append((topic, f"daily limit reached ({max_items})"))
                continue

            tldr = extract_tldr(content)
            item = build_queue_item(topic, path, content, tldr, schedule)
            new_items.append(item)
            print(f"  + Added: {topic}")

    # Save new items
    if new_items:
        save_queue_for_date(new_items, target_date)
        print(f"\nSaved {len(new_items)} items to {STUDY_QUEUE_DIR}/{date_str}.json")
    else:
        print("\nNo new items to add today.")

    record_path = write_curation_record(date_str, new_items, skipped, files_read)
    print(f"Airlock record: {record_path}")

    # Summary line for cron-agent
    total_queue = len(existing_queue) + len(new_items)
    print(
        f"\n[study-agent] {date_str}: {len(new_items)} added, "
        f"{len(skipped)} skipped, {total_queue} total in queue"
    )


def mode_pending(queue: list[dict]) -> None:
    """Show all items due for review."""
    pending = get_pending_reviews(queue)
    if not pending:
        print("No items due for review.")
        return

    print(f"{len(pending)} item(s) due for review:\n")
    for item in sorted(pending, key=lambda x: x.get("priority", "medium"), reverse=True):
        print(f"[{item['id']}] ({item['priority']}) {item['topic']}")
        print(f"  {item['concept_summary']}")
        print(f"  Q: {item['self_check_question']}")
        print()


def mode_review(queue: list[dict], schedule: dict) -> None:
    """Interactive review session: work through pending items."""
    pending = get_pending_reviews(queue)
    if not pending:
        print("No items due for review today.")
        return

    print(f"{len(pending)} item(s) to review. Type 'y' (knew it), 'n' (didn't), 's' (skip).\n")

    updated_items = []
    for item in pending:
        print(f"[{item['topic']}]")
        print(f"Summary: {item['concept_summary']}")
        print(f"Q: {item['self_check_question']}")
        answer = input("Result (y/n/s): ").strip().lower()

        if answer == "y":
            item = advance_review(item, schedule)
        elif answer == "n":
            item = reset_review(item, schedule)
        else:
            item["state"] = "skipped"
            print(f"  Skipped.")

        updated_items.append(item)

    # Save updated items
    save_queue_for_date(updated_items, date.today())
    print(f"\nReview complete. {len(updated_items)} items updated.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Study queue processor")
    parser.add_argument(
        "--mode",
        choices=["curate", "review", "pending", "mark"],
        default="curate",
    )
    parser.add_argument(
        "--date",
        default="today",
        help="Date for curation: 'today', 'yesterday', or 'YYYY-MM-DD'",
    )
    parser.add_argument("--item-id", help="Item ID for --mode mark")
    parser.add_argument(
        "--result",
        choices=["known", "failed", "skip"],
        help="Result for --mode mark",
    )
    args = parser.parse_args()

    profile = load_study_profile()
    schedule = load_review_schedule()

    if args.date == "today":
        target_date = date.today()
    elif args.date == "yesterday":
        target_date = date.today() - timedelta(days=1)
    else:
        target_date = date.fromisoformat(args.date)

    if args.mode == "curate":
        mode_curate(target_date, profile, schedule)

    elif args.mode == "pending":
        queue = load_queue()
        mode_pending(queue)

    elif args.mode == "review":
        queue = load_queue()
        mode_review(queue, schedule)

    elif args.mode == "mark":
        if not args.item_id or not args.result:
            print("ERROR: --mode mark requires --item-id and --result")
            sys.exit(1)
        queue = load_queue()
        queue = mark_item(queue, args.item_id, args.result, schedule)
        save_queue_for_date(queue, date.today())
        print(f"Updated item {args.item_id}: {args.result}")


if __name__ == "__main__":
    main()
