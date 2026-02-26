"""
Duplicate Detector — exact dedupe_key matching and near-duplicate text similarity.
"""

import re
import unicodedata
from config import DEDUPE_WINDOW_MINUTES, TEXT_SIMILARITY_THRESHOLD


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def levenshtein_ratio(s1: str, s2: str) -> float:
    """Compute normalized Levenshtein similarity ratio (0..1)."""
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)

    # Quick length-based rejection
    if abs(len1 - len2) / max(len1, len2) > (1 - TEXT_SIMILARITY_THRESHOLD):
        return 0.0

    # Dynamic programming Levenshtein
    matrix = list(range(len2 + 1))
    for i in range(1, len1 + 1):
        prev = matrix[0]
        matrix[0] = i
        for j in range(1, len2 + 1):
            temp = matrix[j]
            if s1[i - 1] == s2[j - 1]:
                matrix[j] = prev
            else:
                matrix[j] = 1 + min(prev, matrix[j], matrix[j - 1])
            prev = temp

    distance = matrix[len2]
    max_len = max(len1, len2)
    return 1.0 - (distance / max_len)


class DuplicateDetector:
    """Detects exact and near-duplicate notifications."""

    def __init__(self, history_store, dedupe_window: int = DEDUPE_WINDOW_MINUTES,
                 similarity_threshold: float = TEXT_SIMILARITY_THRESHOLD):
        self.history = history_store
        self.dedupe_window = dedupe_window
        self.similarity_threshold = similarity_threshold

    def check(self, event: dict) -> dict:
        """
        Check if event is a duplicate.
        Returns:
          {
            "is_duplicate": bool,
            "duplicate_type": "DUPLICATE_DEDUPE_KEY"|"DUPLICATE_TEXT_SIMILAR"|None,
            "matched_event_id": str|None
          }
        """
        user_id = event["user_id"]

        # 1. Exact dedupe_key check
        if event.get("dedupe_key"):
            matches = self.history.get_dedupe_key_entries(
                user_id, event["dedupe_key"], self.dedupe_window
            )
            if matches:
                return {
                    "is_duplicate": True,
                    "duplicate_type": "DUPLICATE_DEDUPE_KEY",
                    "matched_event_id": matches[-1].get("event_id"),
                }

        # 2. Near-duplicate text similarity
        event_text = normalize_text(
            (event.get("title", "") + " " + event.get("message", "")).strip()
        )
        if event_text:
            past_entries = self.history.get_text_entries(user_id, self.dedupe_window)
            for entry in past_entries:
                ratio = levenshtein_ratio(event_text, entry["normalized_text"])
                if ratio >= self.similarity_threshold:
                    return {
                        "is_duplicate": True,
                        "duplicate_type": "DUPLICATE_TEXT_SIMILAR",
                        "matched_event_id": entry.get("event_id"),
                    }

        return {
            "is_duplicate": False,
            "duplicate_type": None,
            "matched_event_id": None,
        }
