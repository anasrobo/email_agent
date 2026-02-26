"""
LLM Classifier — simulated LLM for urgency classification with fallback.

Uses keyword heuristics to mimic LLM behavior without requiring an API.
Includes a simulate_failure flag to demonstrate fail-safe behavior.
"""

import re
import time
import random
from config import LLM_TIMEOUT_SECONDS, FALLBACK_MAP, FALLBACK_EVENT_TYPE_MAP


# Urgency keywords that indicate NOW
URGENT_KEYWORDS = [
    r'\botp\b', r'\bpassword\b', r'\b2fa\b', r'\bverif',
    r'\bdown\b', r'\boutage\b', r'\bcritical\b', r'\bemergency\b',
    r'\bsecurity\b', r'\bbreach\b', r'\bfailure\b', r'\bfailed\b',
    r'\bexpir', r'\bblocked\b', r'\bunauthorized\b',
    r'\b95%\b', r'\b100%\b', r'\b99%\b', r'\boverload\b',
    r'\bcrash', r'\berror\b', r'\balert\b',
]

# Promotional / low-priority keywords that indicate NEVER
PROMO_KEYWORDS = [
    r'\bsale\b', r'\bdiscount\b', r'\b\d+%\s*off\b', r'\bflat\b',
    r'\bpromo', r'\bcoupon\b', r'\bdeal\b', r'\boffer\b',
    r'\bfree\b', r'\bclearance\b', r'\blimited.?time\b',
]

# Medium/deferred keywords that indicate LATER
LATER_KEYWORDS = [
    r'\breminder\b', r'\bsubmit\b', r'\bupdate\b', r'\bweekly\b',
    r'\bmonthly\b', r'\bsummary\b', r'\bdigest\b', r'\bnewsletter\b',
    r'\breport\b', r'\bschedul',
]


class LLMClassifier:
    """Simulated LLM classifier with keyword heuristics and fail-safe fallback."""

    def __init__(self, simulate_failure: bool = False):
        self.simulate_failure = simulate_failure
        self._call_count = 0

    def classify(self, event: dict) -> dict:
        """
        Classify an event using simulated LLM reasoning.
        Returns:
          {
            "label": "NOW"|"LATER"|"NEVER",
            "confidence": float 0-1,
            "raw_output": str,
            "used_fallback": bool,
            "explanation_code": "LLM_DECISION"|"URGENT_KEYWORD"|"FALLBACK"
          }
        """
        self._call_count += 1

        # Simulate LLM failure
        if self.simulate_failure:
            return self._fallback(event, reason="LLM service simulated failure")

        try:
            return self._llm_classify(event)
        except Exception as e:
            return self._fallback(event, reason=f"LLM error: {e}")

    def _llm_classify(self, event: dict) -> dict:
        """Keyword-based classification mimicking LLM reasoning."""
        text = f"{event.get('title', '')} {event.get('message', '')}".lower()
        event_type = event.get("event_type", "")
        priority = event.get("priority_hint", "")
        channel = event.get("channel", "")

        # Score urgent keywords
        urgent_score = sum(1 for kw in URGENT_KEYWORDS if re.search(kw, text))
        promo_score = sum(1 for kw in PROMO_KEYWORDS if re.search(kw, text))
        later_score = sum(1 for kw in LATER_KEYWORDS if re.search(kw, text))

        # Boost based on structured fields
        if priority == "urgent":
            urgent_score += 3
        elif priority == "high":
            urgent_score += 2
        elif priority == "low":
            promo_score += 2

        if event_type in ("alert", "system"):
            urgent_score += 2
        elif event_type == "promotion":
            promo_score += 3
        elif event_type == "reminder":
            later_score += 2

        if channel == "sms":
            urgent_score += 1  # SMS usually implies urgency

        # Determine label + confidence
        total = max(urgent_score + promo_score + later_score, 1)

        if urgent_score > promo_score and urgent_score > later_score:
            label = "NOW"
            confidence = min(0.5 + (urgent_score / total) * 0.5, 0.99)
            explanation_code = "URGENT_KEYWORD" if urgent_score >= 2 else "LLM_DECISION"
            reason = self._build_reason(label, text, urgent_score, event_type, priority)
        elif promo_score > urgent_score and promo_score > later_score:
            label = "NEVER"
            confidence = min(0.5 + (promo_score / total) * 0.5, 0.99)
            explanation_code = "LLM_DECISION"
            reason = f"Promotional content detected (score={promo_score})"
        elif later_score > 0:
            label = "LATER"
            confidence = min(0.5 + (later_score / total) * 0.4, 0.95)
            explanation_code = "LLM_DECISION"
            reason = f"Non-urgent, schedulable content (score={later_score})"
        else:
            # Default based on event_type
            label = FALLBACK_EVENT_TYPE_MAP.get(event_type, "LATER")
            confidence = 0.5
            explanation_code = "LLM_DECISION"
            reason = f"Default classification for {event_type}"

        raw = f"LABEL:{label}; SHORT_REASON:{reason}; CONFIDENCE:{confidence:.2f}"

        return {
            "label": label,
            "confidence": round(confidence, 2),
            "raw_output": raw,
            "used_fallback": False,
            "explanation_code": explanation_code,
        }

    def _build_reason(self, label, text, score, event_type, priority):
        """Build a human-readable reason string."""
        parts = []
        if "otp" in text:
            parts.append("contains OTP")
        if "down" in text:
            parts.append("service outage detected")
        if any(re.search(kw, text) for kw in [r'\b95%\b', r'\b100%\b', r'\b99%\b']):
            parts.append("resource threshold critical")
        if priority == "urgent":
            parts.append("priority=urgent")
        if event_type in ("alert", "system"):
            parts.append(f"event_type={event_type}")
        if not parts:
            parts.append(f"urgency score={score}")
        return f"Urgent: {', '.join(parts)}"

    def _fallback(self, event: dict, reason: str = "LLM unavailable") -> dict:
        """Deterministic fallback when LLM is unavailable."""
        priority = event.get("priority_hint", "")
        event_type = event.get("event_type", "")

        # Fallback mapping
        if priority in FALLBACK_MAP:
            label = FALLBACK_MAP[priority]
        elif event_type in FALLBACK_EVENT_TYPE_MAP:
            label = FALLBACK_EVENT_TYPE_MAP[event_type]
        else:
            label = "LATER"

        return {
            "label": label,
            "confidence": 0.4,
            "raw_output": f"FALLBACK: {reason} → {label}",
            "used_fallback": True,
            "explanation_code": "FALLBACK",
        }

    def set_failure_mode(self, enabled: bool):
        """Toggle simulated failure mode."""
        self.simulate_failure = enabled
