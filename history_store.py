"""
History Store — in-memory per-user ring buffer of recent notification decisions.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from config import HISTORY_BUFFER_SIZE


class HistoryStore:
    """Thread-safe in-memory history of notification decisions per user."""

    def __init__(self, buffer_size: int = HISTORY_BUFFER_SIZE):
        self.buffer_size = buffer_size
        self._store: dict[str, deque] = defaultdict(lambda: deque(maxlen=self.buffer_size))

    def add(self, user_id: str, record: dict):
        """Add a decision record for a user."""
        self._store[user_id].append(record)

    def get_recent(self, user_id: str, window_minutes: int = None) -> list[dict]:
        """Get recent decision records for a user, optionally within a time window."""
        records = list(self._store.get(user_id, []))
        if window_minutes is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
            records = [
                r for r in records
                if r.get("parsed_timestamp", datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
            ]
        return records

    def count_in_window(self, user_id: str, window_minutes: int) -> int:
        """Count how many decisions exist for a user in the last N minutes."""
        return len(self.get_recent(user_id, window_minutes))

    def count_decisions_by_type(
        self, user_id: str, event_type: str, decision: str, window_minutes: int
    ) -> int:
        """Count decisions of a specific type+decision combo in a window."""
        recent = self.get_recent(user_id, window_minutes)
        return sum(
            1 for r in recent
            if r.get("event_type") == event_type and r.get("decision") == decision
        )

    def count_by_event_type(self, user_id: str, event_type: str, window_minutes: int) -> int:
        """Count events of a specific type within a window."""
        recent = self.get_recent(user_id, window_minutes)
        return sum(1 for r in recent if r.get("event_type") == event_type)

    def count_urgent_by_source_or_type(
        self, user_id: str, event_type: str, source: str, window_minutes: int
    ) -> int:
        """Count NOW decisions from the same event_type or source in a window."""
        recent = self.get_recent(user_id, window_minutes)
        return sum(
            1 for r in recent
            if r.get("decision") == "NOW"
            and (r.get("event_type") == event_type or r.get("source") == source)
        )

    def get_dedupe_key_entries(self, user_id: str, dedupe_key: str, window_minutes: int) -> list[dict]:
        """Find entries with a matching dedupe_key within a window."""
        recent = self.get_recent(user_id, window_minutes)
        return [r for r in recent if r.get("dedupe_key") == dedupe_key]

    def get_text_entries(self, user_id: str, window_minutes: int) -> list[dict]:
        """Get entries with their text content for near-duplicate checking."""
        recent = self.get_recent(user_id, window_minutes)
        return [r for r in recent if r.get("normalized_text")]

    def count_event_type_today(self, user_id: str, event_type: str) -> int:
        """Count events of a specific type today (UTC)."""
        today = datetime.now(timezone.utc).date()
        records = list(self._store.get(user_id, []))
        return sum(
            1 for r in records
            if r.get("event_type") == event_type
            and r.get("parsed_timestamp", datetime.min.replace(tzinfo=timezone.utc)).date() == today
        )

    def clear(self):
        """Clear all history."""
        self._store.clear()

    def clear_user(self, user_id: str):
        """Clear history for a specific user."""
        if user_id in self._store:
            del self._store[user_id]
