"""
Rule Engine — loads, matches, and applies human-configurable JSON rules.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


class RuleEngine:
    """Loads JSON rule sets and matches events against them."""

    def __init__(self, rules_path: str = None, rules_data: list = None):
        if rules_data is not None:
            self.rules = sorted(rules_data, key=lambda r: r.get("priority", 0), reverse=True)
        elif rules_path:
            self.rules = self._load_rules(rules_path)
        else:
            self.rules = []

    def _load_rules(self, path: str) -> list:
        """Load rules from JSON file, sorted by priority descending."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rules = data.get("rules", data) if isinstance(data, dict) else data
            return sorted(rules, key=lambda r: r.get("priority", 0), reverse=True)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[RuleEngine] Warning: Could not load rules from {path}: {e}")
            return []

    def reload(self, rules_path: str = None, rules_data: list = None):
        """Reload rules from file or data."""
        if rules_data is not None:
            self.rules = sorted(rules_data, key=lambda r: r.get("priority", 0), reverse=True)
        elif rules_path:
            self.rules = self._load_rules(rules_path)

    def match(self, event: dict) -> list[dict]:
        """
        Find all matching rules for an event, sorted by priority (highest first).
        Returns list of { "rule_id", "rule", "action" }.
        """
        matches = []
        for rule in self.rules:
            if self._matches_rule(event, rule):
                matches.append({
                    "rule_id": rule.get("id", "unknown"),
                    "rule": rule,
                    "action": rule.get("action", {}),
                })
        return matches

    def _matches_rule(self, event: dict, rule: dict) -> bool:
        """Check if an event matches a rule's conditions."""
        match_cond = rule.get("match", {})

        # Match event_type
        if "event_type" in match_cond:
            if event.get("event_type") not in match_cond["event_type"]:
                return False

        # Match priority_hint
        if "priority_hint" in match_cond:
            if event.get("priority_hint") not in match_cond["priority_hint"]:
                return False

        # Match channel
        if "channel" in match_cond:
            if event.get("channel") not in match_cond["channel"]:
                return False

        # Match source
        if "source" in match_cond:
            if event.get("source") not in match_cond["source"]:
                return False

        # Match time_window (hour-based)
        if "time_window" in match_cond:
            tw = match_cond["time_window"]
            ts = event.get("parsed_timestamp", datetime.now(timezone.utc))
            hour = ts.hour
            start = tw.get("start_hour", 0)
            end = tw.get("end_hour", 24)

            if start > end:
                # Wraps midnight, e.g., 22-6
                if not (hour >= start or hour < end):
                    return False
            else:
                if not (start <= hour < end):
                    return False

        return True

    def apply_actions(self, event: dict, matched_rules: list, current_decision: str,
                      history_store=None) -> dict:
        """
        Apply rule actions to modify the decision.
        Returns {
            "decision": str,
            "explanation_code": str,
            "matched_rule_id": str|None,
            "reason": str
        }
        """
        result = {
            "decision": current_decision,
            "explanation_code": None,
            "matched_rule_id": None,
            "reason": None,
        }

        for match in matched_rules:
            action = match["action"]
            rule_id = match["rule_id"]
            rule_desc = match["rule"].get("description", "")

            # force_decision overrides everything
            if "force_decision" in action:
                result["decision"] = action["force_decision"]
                result["explanation_code"] = "RULE_OVERRIDE"
                result["matched_rule_id"] = rule_id
                result["reason"] = f"Rule {rule_id}: {rule_desc}"
                return result  # highest priority match wins

            # downgrade mapping
            if "downgrade" in action:
                dg = action["downgrade"]
                if current_decision in dg:
                    result["decision"] = dg[current_decision]
                    result["explanation_code"] = "RULE_OVERRIDE"
                    result["matched_rule_id"] = rule_id
                    result["reason"] = f"Rule {rule_id}: {rule_desc} (downgraded {current_decision} → {dg[current_decision]})"
                    current_decision = result["decision"]

            # limit_per_day
            if "limit_per_day" in action and history_store:
                limit = action["limit_per_day"]
                count = history_store.count_event_type_today(
                    event["user_id"], event["event_type"]
                )
                if count >= limit:
                    result["decision"] = "NEVER"
                    result["explanation_code"] = "RULE_OVERRIDE"
                    result["matched_rule_id"] = rule_id
                    result["reason"] = (
                        f"Rule {rule_id}: {rule_desc} — "
                        f"daily limit {limit} reached ({count} today)"
                    )
                    return result

        return result
