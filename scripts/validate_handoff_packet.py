#!/usr/bin/env python3
"""
validate_handoff_packet.py

Validates a handoff packet JSON document against the OpenClaw handoff packet
schema (schemas/handoff_packet.schema.json).

The handoff packet is the inter-agent communication contract used throughout
the multi-agent architecture.  Required fields (from the schema):
    - objective   : string
    - scope       : object
    - constraints : object
    - acceptance  : object
    - risk        : "low" | "medium" | "high"

Usage examples:
    # Validate a file and print results as JSON
    python validate_handoff_packet.py --packet /path/to/packet.json

    # Validate from stdin
    cat packet.json | python validate_handoff_packet.py --stdin

    # Validate an inline JSON string
    python validate_handoff_packet.py --json '{"objective":"...",...}'

    # Use a custom schema path
    python validate_handoff_packet.py --packet packet.json \
        --schema /path/to/handoff_packet.schema.json

    # Exit 0 on valid, non-zero on invalid (useful in CI/cron pipelines)
    python validate_handoff_packet.py --packet packet.json --strict

Environment variables:
    HANDOFF_SCHEMA_PATH  - path to handoff_packet.schema.json (optional)

Output:
    A single JSON document to stdout with the following structure:
    {
        "valid": true|false,
        "errors": [],
        "warnings": [],
        "packet_summary": { ... }
    }

Exit codes:
    0  - packet is valid
    1  - packet is invalid (structural/type errors)
    2  - fatal error (file not found, not JSON, etc.)
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stderr)
logger = logging.getLogger("validate_handoff_packet")


# ---------------------------------------------------------------------------
# Schema definition (kept in sync with schemas/handoff_packet.schema.json)
# ---------------------------------------------------------------------------

# Fields required at the top level
REQUIRED_FIELDS: Dict[str, type] = {
    "objective": str,
    "scope": dict,
    "constraints": dict,
    "acceptance": dict,
    "risk": str,
}

VALID_RISK_VALUES = {"low", "medium", "high"}

# Recommended (non-mandatory) sub-keys that signal a well-formed packet
SCOPE_RECOMMENDED_KEYS = {"files", "commands"}
CONSTRAINTS_RECOMMENDED_KEYS = {"runtime", "security", "style", "budget"}
ACCEPTANCE_RECOMMENDED_KEYS = {"tests", "lint", "manual"}


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------

def validate_packet(packet: Any) -> Tuple[bool, List[str], List[str]]:
    """
    Validate a handoff packet dict.

    Returns:
        (is_valid, errors, warnings)
        - errors:   list of strings that make the packet invalid
        - warnings: list of strings for best-practice issues (non-blocking)
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Top-level must be an object
    if not isinstance(packet, dict):
        errors.append(
            f"Packet must be a JSON object (dict), got {type(packet).__name__!r}"
        )
        return False, errors, warnings

    # 2. Required fields — presence and type
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in packet:
            errors.append(f"Missing required field: '{field}'")
            continue
        value = packet[field]
        if not isinstance(value, expected_type):
            errors.append(
                f"Field '{field}' must be {expected_type.__name__!r}, "
                f"got {type(value).__name__!r}"
            )

    # 3. 'risk' enum check
    if "risk" in packet and isinstance(packet["risk"], str):
        if packet["risk"] not in VALID_RISK_VALUES:
            errors.append(
                f"Field 'risk' must be one of {sorted(VALID_RISK_VALUES)}, "
                f"got {packet['risk']!r}"
            )

    # 4. 'objective' must be non-empty
    if "objective" in packet and isinstance(packet["objective"], str):
        if not packet["objective"].strip():
            errors.append("Field 'objective' must not be an empty string")

    # 5. Object fields must not be empty (soft check → warnings only)
    for field in ("scope", "constraints", "acceptance"):
        if field in packet and isinstance(packet[field], dict):
            if not packet[field]:
                warnings.append(f"Field '{field}' is an empty object; consider adding sub-keys")

    # 6. Recommended sub-keys (warnings)
    if "scope" in packet and isinstance(packet["scope"], dict):
        missing_rec = SCOPE_RECOMMENDED_KEYS - set(packet["scope"].keys())
        if missing_rec:
            warnings.append(
                f"'scope' is missing recommended keys: {sorted(missing_rec)}. "
                "Consider adding 'files' and 'commands'."
            )

    if "constraints" in packet and isinstance(packet["constraints"], dict):
        missing_rec = CONSTRAINTS_RECOMMENDED_KEYS - set(packet["constraints"].keys())
        if missing_rec:
            warnings.append(
                f"'constraints' is missing recommended keys: {sorted(missing_rec)}."
            )

    if "acceptance" in packet and isinstance(packet["acceptance"], dict):
        missing_rec = ACCEPTANCE_RECOMMENDED_KEYS - set(packet["acceptance"].keys())
        if missing_rec:
            warnings.append(
                f"'acceptance' is missing recommended keys: {sorted(missing_rec)}."
            )

    # 7. Unknown top-level keys (informational warning)
    known_fields = set(REQUIRED_FIELDS.keys())
    extra_fields = set(packet.keys()) - known_fields
    if extra_fields:
        warnings.append(
            f"Packet contains extra (non-schema) top-level fields: {sorted(extra_fields)}. "
            "These are allowed but may be ignored by receiving agents."
        )

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def validate_with_jsonschema(packet: Any, schema_path: Path) -> Tuple[List[str], bool]:
    """
    Run full jsonschema validation if the library is available.
    Returns (additional_errors, ran_successfully).
    """
    try:
        import jsonschema  # type: ignore
    except ImportError:
        logger.debug("jsonschema not installed; skipping full schema validation")
        return [], False

    try:
        with schema_path.open(encoding="utf-8") as f:
            schema = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load schema from %s: %s", schema_path, exc)
        return [f"Schema load error: {exc}"], False

    schema_errors: List[str] = []
    try:
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(packet), key=lambda e: list(e.path)):
            path = " -> ".join(str(p) for p in err.path) if err.path else "<root>"
            schema_errors.append(f"[jsonschema] {path}: {err.message}")
    except Exception as exc:
        schema_errors.append(f"[jsonschema] Unexpected validation error: {exc}")

    return schema_errors, True


# ---------------------------------------------------------------------------
# Packet summary (non-sensitive excerpt for the report)
# ---------------------------------------------------------------------------

def summarise_packet(packet: Any) -> Dict[str, Any]:
    """Return a brief, non-sensitive summary of the packet fields."""
    if not isinstance(packet, dict):
        return {}
    summary: Dict[str, Any] = {}
    if "objective" in packet:
        obj = packet["objective"]
        summary["objective_preview"] = (obj[:120] + "...") if len(obj) > 120 else obj
    if "risk" in packet:
        summary["risk"] = packet["risk"]
    if "scope" in packet and isinstance(packet["scope"], dict):
        summary["scope_keys"] = sorted(packet["scope"].keys())
        files = packet["scope"].get("files", [])
        summary["scope_file_count"] = len(files) if isinstance(files, list) else "n/a"
    if "constraints" in packet and isinstance(packet["constraints"], dict):
        summary["constraint_keys"] = sorted(packet["constraints"].keys())
    if "acceptance" in packet and isinstance(packet["acceptance"], dict):
        summary["acceptance_keys"] = sorted(packet["acceptance"].keys())
    return summary


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def load_packet_from_file(path: Path) -> Tuple[Any, Optional[str]]:
    """Load and parse a JSON file.  Returns (packet, error_message)."""
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, f"File not found: {path}"
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error in {path}: {exc}"
    except OSError as exc:
        return None, f"I/O error reading {path}: {exc}"


def load_packet_from_stdin() -> Tuple[Any, Optional[str]]:
    """Read JSON from stdin.  Returns (packet, error_message)."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error from stdin: {exc}"


def load_packet_from_string(json_str: str) -> Tuple[Any, Optional[str]]:
    """Parse a JSON string provided inline.  Returns (packet, error_message)."""
    try:
        return json.loads(json_str), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error in --json argument: {exc}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate a handoff packet against the OpenClaw handoff packet schema",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    source_group = p.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--packet",
        metavar="FILE",
        help="Path to the handoff packet JSON file",
    )
    source_group.add_argument(
        "--stdin",
        action="store_true",
        help="Read the handoff packet JSON from stdin",
    )
    source_group.add_argument(
        "--json",
        metavar="JSON_STRING",
        dest="json_string",
        help="Inline JSON string to validate",
    )

    p.add_argument(
        "--schema",
        default=os.environ.get("HANDOFF_SCHEMA_PATH", ""),
        metavar="SCHEMA_FILE",
        help=(
            "Path to handoff_packet.schema.json for full jsonschema validation "
            "(env: HANDOFF_SCHEMA_PATH). If not provided, built-in checks are used."
        ),
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if there are any warnings (in addition to errors)",
    )
    p.add_argument(
        "--no-summary",
        action="store_true",
        help="Omit packet_summary from the output",
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

    # ---- Load packet ----
    packet: Any = None
    load_error: Optional[str] = None

    if args.packet:
        packet_path = Path(args.packet).expanduser().resolve()
        packet, load_error = load_packet_from_file(packet_path)
    elif args.stdin:
        packet, load_error = load_packet_from_stdin()
    elif args.json_string:
        packet, load_error = load_packet_from_string(args.json_string)

    if load_error:
        result = {
            "valid": False,
            "errors": [load_error],
            "warnings": [],
            "packet_summary": {},
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    # ---- Built-in validation ----
    is_valid, errors, warnings = validate_packet(packet)

    # ---- jsonschema validation (optional) ----
    schema_path: Optional[Path] = None
    if args.schema:
        schema_path = Path(args.schema).expanduser().resolve()
    else:
        # Auto-discover relative to this script's location
        candidate = Path(__file__).resolve().parent.parent / "schemas" / "handoff_packet.schema.json"
        if candidate.exists():
            schema_path = candidate
            logger.debug("Auto-discovered schema at %s", schema_path)

    if schema_path:
        extra_errors, ran = validate_with_jsonschema(packet, schema_path)
        if ran:
            errors.extend(extra_errors)
            if extra_errors:
                is_valid = False

    # ---- Build output ----
    result: Dict[str, Any] = {
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings,
    }

    if not args.no_summary:
        result["packet_summary"] = summarise_packet(packet)

    if schema_path:
        result["schema_used"] = str(schema_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # ---- Exit code ----
    if not is_valid:
        return 1
    if args.strict and warnings:
        logger.info("--strict: exiting 1 due to %d warning(s)", len(warnings))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
