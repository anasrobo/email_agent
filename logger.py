"""
Logger — structured explanation logging and console output.
"""

import json
from datetime import datetime, timezone


class DecisionLogger:
    """Accumulates structured decision logs and prints formatted output."""

    def __init__(self):
        self.logs: list[dict] = []

    def log(self, event: dict, decision: str, scheduled_time: str | None,
            explanation_code: str, reason: str, matched_rule_id: str | None = None,
            confidence: float = 0.0, raw_model_output: str = "") -> dict:
        """Create and store a structured log entry."""
        entry = {
            "user_id": event.get("user_id"),
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "decision": decision,
            "scheduled_time": scheduled_time,
            "timestamp": event.get("timestamp"),
            "explanation_code": explanation_code,
            "reason": reason,
            "matched_rule_id": matched_rule_id,
            "confidence": round(confidence, 2),
            "raw_model_output": raw_model_output,
        }
        self.logs.append(entry)
        return entry

    def get_output_record(self, event: dict, log_entry: dict) -> dict:
        """Build the final output record combining input + decision."""
        # Build a clean input event (remove internal fields)
        clean_input = {k: v for k, v in event.items()
                       if k not in ("parsed_timestamp", "event_id")}

        return {
            "input_event": clean_input,
            "decision": log_entry["decision"],
            "scheduled_time": log_entry["scheduled_time"],
            "explanation_code": log_entry["explanation_code"],
            "reason": log_entry["reason"],
            "matched_rule_id": log_entry["matched_rule_id"],
        }

    def print_table(self):
        """Print a formatted table of all decisions."""
        if not self.logs:
            print("No decisions logged.")
            return

        # Header
        print("\n" + "=" * 120)
        print(f"{'#':<4} {'User':<6} {'Type':<12} {'Message (truncated)':<35} "
              f"{'Decision':<8} {'Code':<25} {'Rule':<6}")
        print("-" * 120)

        for i, log in enumerate(self.logs, 1):
            msg = log.get("reason", "")[:33]
            print(
                f"{i:<4} {log['user_id']:<6} {log['event_type']:<12} "
                f"{msg:<35} {log['decision']:<8} "
                f"{log['explanation_code']:<25} {log.get('matched_rule_id') or '-':<6}"
            )

        print("=" * 120 + "\n")

    def export_json(self, filepath: str = "output.json"):
        """Export all logs to a JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.logs, f, indent=2, default=str)
        print(f"[Logger] Exported {len(self.logs)} decisions to {filepath}")

    def clear(self):
        """Clear all logs."""
        self.logs.clear()
