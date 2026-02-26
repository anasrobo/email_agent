"""
Input Validator — validates and normalizes incoming notification events.
"""

import uuid
from datetime import datetime, timezone


REQUIRED_FIELDS = ["user_id", "event_type", "message", "timestamp", "channel"]
VALID_EVENT_TYPES = {"message", "reminder", "alert", "promotion", "system", "update", "email"}
VALID_CHANNELS = {"push", "email", "sms", "in_app"}
VALID_PRIORITY_HINTS = {"low", "medium", "high", "urgent"}


class ValidationError(Exception):
    """Raised when an event fails validation."""
    pass


def validate_event(event: dict) -> dict:
    """
    Validate and normalize a notification event.
    Returns a cleaned copy with defaults filled in.
    Raises ValidationError for invalid events.
    """
    if not isinstance(event, dict):
        raise ValidationError("Event must be a JSON object (dict)")

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in event or not event[field]:
            raise ValidationError(f"Missing required field: {field}")

    # Validate event_type
    if event["event_type"] not in VALID_EVENT_TYPES:
        raise ValidationError(
            f"Invalid event_type '{event['event_type']}'. "
            f"Must be one of: {', '.join(VALID_EVENT_TYPES)}"
        )

    # Validate channel
    if event["channel"] not in VALID_CHANNELS:
        raise ValidationError(
            f"Invalid channel '{event['channel']}'. "
            f"Must be one of: {', '.join(VALID_CHANNELS)}"
        )

    # Parse timestamp
    try:
        ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValidationError(f"Invalid timestamp format: {event['timestamp']}")

    # Build normalized event
    normalized = {
        "event_id": event.get("event_id", str(uuid.uuid4())),
        "user_id": str(event["user_id"]),
        "event_type": event["event_type"],
        "title": event.get("title", ""),
        "message": event["message"],
        "source": event.get("source", "unknown"),
        "priority_hint": event.get("priority_hint", None),
        "timestamp": ts.isoformat(),
        "parsed_timestamp": ts,
        "channel": event["channel"],
        "metadata": event.get("metadata", {}),
        "dedupe_key": event.get("dedupe_key", None),
        "expires_at": None,
    }

    # Validate priority_hint if provided
    if normalized["priority_hint"] and normalized["priority_hint"] not in VALID_PRIORITY_HINTS:
        raise ValidationError(
            f"Invalid priority_hint '{normalized['priority_hint']}'. "
            f"Must be one of: {', '.join(VALID_PRIORITY_HINTS)}"
        )

    # Parse expires_at if provided
    if event.get("expires_at"):
        try:
            exp = datetime.fromisoformat(event["expires_at"].replace("Z", "+00:00"))
            normalized["expires_at"] = exp
        except (ValueError, AttributeError):
            raise ValidationError(f"Invalid expires_at format: {event['expires_at']}")

    return normalized
