"""
Configuration constants for the Notification Prioritization Engine.
"""

# ── Dedupe Window ──────────────────────────────────────────────────────
DEDUPE_WINDOW_MINUTES = 10

# ── Near-Duplicate Threshold ───────────────────────────────────────────
TEXT_SIMILARITY_THRESHOLD = 0.9  # normalized Levenshtein ratio

# ── Alert Fatigue / Frequency ──────────────────────────────────────────
FREQUENCY_WINDOW_MINUTES = 10
FREQUENCY_LIMIT = 5              # ≥ this many in window → downgrade
HISTORY_BUFFER_SIZE = 30         # ring buffer size per user

# ── Conflict / Noise Limits ───────────────────────────────────────────
NOISE_LIMIT_MAX_URGENT = 2       # M urgent of same type/source allowed
NOISE_LIMIT_WINDOW_MINUTES = 15  # within this window

# ── Quiet Hours ────────────────────────────────────────────────────────
QUIET_HOUR_START = 22  # 10 PM
QUIET_HOUR_END = 6     # 6 AM
QUIET_RESUME_HOUR = 8  # schedule LATER at 8 AM

# ── Scheduler ──────────────────────────────────────────────────────────
BASE_BACKOFF_MINUTES = 5
DEFAULT_WORKING_HOUR = 9  # for reminders

# ── LLM ────────────────────────────────────────────────────────────────
LLM_TIMEOUT_SECONDS = 2

# ── Fallback Mapping ──────────────────────────────────────────────────
FALLBACK_MAP = {
    "urgent":  "NOW",
    "high":    "NOW",
    "medium":  "LATER",
    "low":     "NEVER",
}

FALLBACK_EVENT_TYPE_MAP = {
    "alert":     "NOW",
    "system":    "NOW",
    "message":   "LATER",
    "reminder":  "LATER",
    "update":    "LATER",
    "email":     "LATER",
    "promotion": "NEVER",
}
