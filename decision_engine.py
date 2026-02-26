"""
Decision Engine — the central orchestrator that combines all signals into final decisions.

Pipeline per event:
1. Validate → 2. Check duplicate → 3. Match rules → 4. LLM classify (or fallback)
→ 5. Frequency/fatigue check → 6. Conflict resolution → 7. Schedule → 8. Log
"""

from datetime import datetime, timezone
from input_validator import validate_event, ValidationError
from duplicate_detector import DuplicateDetector, normalize_text
from history_store import HistoryStore
from rule_engine import RuleEngine
from llm_classifier import LLMClassifier
from scheduler import compute_scheduled_time
from logger import DecisionLogger
from config import (
    FREQUENCY_WINDOW_MINUTES, FREQUENCY_LIMIT,
    NOISE_LIMIT_MAX_URGENT, NOISE_LIMIT_WINDOW_MINUTES,
)


class DecisionEngine:
    """Processes notification events and produces prioritized decisions."""

    def __init__(self, rules_path: str = None, rules_data: list = None,
                 simulate_llm_failure: bool = False):
        self.history = HistoryStore()
        self.dedup = DuplicateDetector(self.history)
        self.rules = RuleEngine(rules_path=rules_path, rules_data=rules_data)
        self.llm = LLMClassifier(simulate_failure=simulate_llm_failure)
        self.logger = DecisionLogger()

    def process_event(self, raw_event: dict) -> dict:
        """
        Process a single notification event through the full pipeline.
        Returns the output record dict.
        """
        # ── Step 1: Validate ──────────────────────────────────────────
        try:
            event = validate_event(raw_event)
        except ValidationError as e:
            error_record = {
                "input_event": raw_event,
                "decision": "NEVER",
                "scheduled_time": None,
                "explanation_code": "VALIDATION_ERROR",
                "reason": f"Invalid event: {e}",
                "matched_rule_id": None,
            }
            return error_record

        # ── Step 2: Check duplicates ──────────────────────────────────
        dup_result = self.dedup.check(event)
        if dup_result["is_duplicate"]:
            decision = "NEVER"
            explanation_code = dup_result["duplicate_type"]
            reason = (
                f"Duplicate suppressed: {dup_result['duplicate_type']} "
                f"(matched {dup_result['matched_event_id'][:8] if dup_result['matched_event_id'] else 'unknown'})"
            )
            log_entry = self.logger.log(
                event, decision, None, explanation_code, reason
            )
            self._record_history(event, decision, explanation_code)
            return self.logger.get_output_record(event, log_entry)

        # ── Step 3: LLM classification ────────────────────────────────
        llm_result = self.llm.classify(event)
        current_decision = llm_result["label"]
        explanation_code = llm_result["explanation_code"]
        confidence = llm_result["confidence"]
        raw_output = llm_result["raw_output"]
        reason = raw_output

        # ── Step 4: Apply human rules ─────────────────────────────────
        matched_rules = self.rules.match(event)
        matched_rule_id = None

        if matched_rules:
            rule_result = self.rules.apply_actions(
                event, matched_rules, current_decision, self.history
            )
            if rule_result["explanation_code"]:
                current_decision = rule_result["decision"]
                explanation_code = rule_result["explanation_code"]
                matched_rule_id = rule_result["matched_rule_id"]
                reason = rule_result["reason"]

        # ── Step 5: Frequency / alert fatigue ─────────────────────────
        freq_count = self.history.count_in_window(
            event["user_id"], FREQUENCY_WINDOW_MINUTES
        )

        if freq_count >= FREQUENCY_LIMIT:
            if current_decision == "NOW":
                current_decision = "LATER"
                explanation_code = "FREQUENCY_LIMIT"
                reason = (
                    f"Downgraded NOW→LATER: user {event['user_id']} received "
                    f"{freq_count} notifications in last {FREQUENCY_WINDOW_MINUTES} min"
                )
            elif current_decision == "LATER" and freq_count >= FREQUENCY_LIMIT + 2:
                current_decision = "NEVER"
                explanation_code = "FREQUENCY_SUPPRESSION"
                reason = (
                    f"Suppressed: user {event['user_id']} received "
                    f"{freq_count} notifications (fatigue threshold)"
                )

        # ── Step 6: Conflict / noise resolution ──────────────────────
        if current_decision == "NOW":
            urgent_count = self.history.count_urgent_by_source_or_type(
                event["user_id"], event["event_type"],
                event.get("source", ""), NOISE_LIMIT_WINDOW_MINUTES
            )
            if urgent_count >= NOISE_LIMIT_MAX_URGENT:
                current_decision = "LATER"
                explanation_code = "CONFLICT_NOISE_LIMIT"
                reason = (
                    f"Noise limit: {urgent_count} urgent {event['event_type']} events "
                    f"from {event.get('source', 'unknown')} in last "
                    f"{NOISE_LIMIT_WINDOW_MINUTES} min (limit={NOISE_LIMIT_MAX_URGENT})"
                )

        # ── Step 7: Schedule ──────────────────────────────────────────
        scheduled_time = None
        if current_decision == "LATER":
            sched = compute_scheduled_time(event, explanation_code, freq_count)
            if sched == "EXPIRED":
                current_decision = "NEVER"
                explanation_code = "EXPIRED"
                reason = "Scheduled time exceeds expires_at — notification expired"
                scheduled_time = None
            else:
                scheduled_time = sched

        # ── Step 8: Log ───────────────────────────────────────────────
        log_entry = self.logger.log(
            event, current_decision, scheduled_time,
            explanation_code, reason,
            matched_rule_id=matched_rule_id,
            confidence=confidence,
            raw_model_output=raw_output,
        )
        self._record_history(event, current_decision, explanation_code)

        return self.logger.get_output_record(event, log_entry)

    def process_batch(self, events: list[dict]) -> list[dict]:
        """Process a batch of events and return all output records."""
        return [self.process_event(e) for e in events]

    def _record_history(self, event: dict, decision: str, explanation_code: str):
        """Add event to history store for future dedup/frequency checks."""
        self.history.add(event["user_id"], {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "source": event.get("source", "unknown"),
            "decision": decision,
            "explanation_code": explanation_code,
            "dedupe_key": event.get("dedupe_key"),
            "normalized_text": normalize_text(
                (event.get("title", "") + " " + event.get("message", "")).strip()
            ),
            "parsed_timestamp": event.get("parsed_timestamp"),
            "timestamp": event.get("timestamp"),
        })

    def set_llm_failure(self, enabled: bool):
        """Toggle LLM failure simulation."""
        self.llm.set_failure_mode(enabled)

    def reload_rules(self, rules_path: str = None, rules_data: list = None):
        """Reload rules without restarting."""
        self.rules.reload(rules_path=rules_path, rules_data=rules_data)

    def reset(self):
        """Reset all state (history + logs)."""
        self.history.clear()
        self.logger.clear()
