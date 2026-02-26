"""
Email Listener — IMAP-based Gmail listener that fetches unread emails
and converts them into notification events.

Upgraded to extract Message-ID for dedup, use sender as source,
apply keyword-based priority mapping, and extract meeting details
(time, location, topic) from email content.
"""

import imaplib
import email
import email.header
import email.utils
import re
import html
import uuid
from datetime import datetime, timezone


# Explicit Keyword Lists for Classification Hints
VERY_IMPORTANT_KEYWORDS = [
    r'\botp\b', r'\burgent\b', r'\bimmediately\b',
    r'\bpassword\s+reset\b', r'\bsecurity\s+alert\b', r'\bserver\s+down\b'
]

IMPORTANT_KEYWORDS = [
    r'\bmeeting\b', r'\breminder\b', r'\bschedule\b',
    r'\bassignment\b', r'\bdeadline\b'
]

IGNORE_KEYWORDS = [
    r'\bsale\b', r'\boffer\b', r'\bpromotion\b',
    r'\bnewsletter\b', r'\bdiscount\b'
]

VERY_IMPORTANT_REGEX = re.compile(r'(' + '|'.join(VERY_IMPORTANT_KEYWORDS) + r')', re.IGNORECASE)
IMPORTANT_REGEX = re.compile(r'(' + '|'.join(IMPORTANT_KEYWORDS) + r')', re.IGNORECASE)
IGNORE_REGEX = re.compile(r'(' + '|'.join(IGNORE_KEYWORDS) + r')', re.IGNORECASE)

# ── Meeting detail extraction patterns ────────────────────────────
# Time: matches "at 3pm", "at 15:30", "3:00 PM", "3pm", "3 PM", "at 3 PM IST"
_TIME_PATTERN = re.compile(
    r'(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?(?:\s*[A-Z]{2,4})?)'
    r'(?=\s|,|\.|$)',
    re.IGNORECASE
)
# Date: matches "on Monday", "on 27th Feb", "tomorrow", "25 Feb", etc.
_DATE_PATTERN = re.compile(
    r'(?:on\s+)?'
    r'(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday'
    r'|\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)'
    r'|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?'
    r'|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{2,4})?)',
    re.IGNORECASE
)
# Location: matches "at Office", "in Room 4B", "via Zoom", "on Google Meet", "Link:"
_LOCATION_PATTERN = re.compile(
    r'(?:(?:at|in|via|on|location[:\s]+|venue[:\s]+|place[:\s]+|room[:\s]+|link[:\s]+)\s*)'
    r'([\w][\w\s\-\.@/#:]{2,60})',
    re.IGNORECASE
)
# Topic / Agenda: matches "agenda:", "about:", "topic:", "re:", "regarding"
_AGENDA_PATTERN = re.compile(
    r'(?:agenda|topic|about|re|regarding|subject|purpose)[:\s]+([^\n\.]{5,120})',
    re.IGNORECASE
)


class EmailListener:
    """Connects to Gmail via IMAP and fetches unread emails."""

    def __init__(self, email_address: str, password: str,
                 imap_host: str = "imap.gmail.com", imap_port: int = 993):
        self.email_address = email_address
        self.password = password
        self.imap_host = imap_host
        self.imap_port = imap_port
        self._connection: imaplib.IMAP4_SSL | None = None

    def connect(self):
        """Establish an IMAP SSL connection and authenticate."""
        print(f"[EmailListener] Connecting to {self.imap_host}:{self.imap_port} ...")
        self._connection = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        self._connection.login(self.email_address, self.password)
        print(f"[EmailListener] Authenticated as {self.email_address}")

    def disconnect(self):
        """Close the IMAP connection gracefully."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None
            print("[EmailListener] Disconnected.")

    def fetch_unread(self) -> list[dict]:
        """
        Search INBOX for UNSEEN messages, parse each one, and return
        a list of parsed email dicts. Messages are marked as SEEN.
        """
        if not self._connection:
            raise RuntimeError("Not connected — call connect() first")

        self._connection.select("INBOX")
        status, data = self._connection.search(None, "UNSEEN")

        if status != "OK" or not data[0]:
            return []

        message_ids = data[0].split()
        emails = []

        for mid in message_ids:
            status, msg_data = self._connection.fetch(mid, "(RFC822)")
            if status != "OK":
                continue

            raw_bytes = msg_data[0][1]
            parsed = self._parse_email(raw_bytes)
            if parsed:
                emails.append(parsed)

            # Mark as SEEN so we don't re-process
            self._connection.store(mid, "+FLAGS", "\\Seen")

        return emails

    @staticmethod
    def _decode_header(raw_header: str) -> str:
        """Decode a potentially encoded email header value."""
        if not raw_header:
            return ""
        parts = email.header.decode_header(raw_header)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags and decode entities."""
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        return html.unescape(text).strip()

    def _parse_email(self, raw_bytes: bytes) -> dict | None:
        """Parse raw RFC-822 bytes into a structured dict."""
        try:
            msg = email.message_from_bytes(raw_bytes)
        except Exception:
            return None

        subject = self._decode_header(msg.get("Subject", ""))
        sender = self._decode_header(msg.get("From", ""))
        message_id = msg.get("Message-ID", "").strip("<>")

        if not message_id:
            message_id = f"generated-{uuid.uuid4()}"

        # Parse date
        date_str = msg.get("Date", "")
        try:
            parsed_dt = email.utils.parsedate_to_datetime(date_str)
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            timestamp = parsed_dt.isoformat()
        except Exception:
            timestamp = datetime.now(timezone.utc).isoformat()

        # Extract body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(
                            part.get_content_charset() or "utf-8",
                            errors="replace",
                        )
                    break
                elif content_type == "text/html" and not body:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = self._strip_html(
                            payload.decode(
                                part.get_content_charset() or "utf-8",
                                errors="replace",
                            )
                        )
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                raw_text = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    body = self._strip_html(raw_text)
                else:
                    body = raw_text

        return {
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "body": body.strip(),
            "timestamp": timestamp,
        }

    @staticmethod
    def extract_meeting_details(subject: str, body: str) -> dict:
        """
        Extract structured meeting information from email subject + body.
        Returns a dict with keys: time, date, location, topic.
        Any field that could not be found is None.
        """
        full_text = f"{subject}\n{body}"
        details = {"time": None, "date": None, "location": None, "topic": None}

        # Time
        time_match = _TIME_PATTERN.search(full_text)
        if time_match:
            candidate = time_match.group(1).strip()
            # Filter out pure numbers with no AM/PM (likely not a time)
            if re.search(r'[APap][Mm]|:', candidate):
                details["time"] = candidate

        # Date
        date_match = _DATE_PATTERN.search(full_text)
        if date_match:
            details["date"] = date_match.group(1).strip().title()

        # Location — try known patterns
        # First, look for Zoom/Meet/Teams links or explicit location words
        zoom_match = re.search(
            r'(zoom\.us/[^\s]+|meet\.google\.com/[^\s]+|teams\.microsoft\.com/[^\s]+'
            r'|https?://[^\s]+(?:zoom|meet|webex|teams)[^\s]*)',
            full_text, re.IGNORECASE
        )
        if zoom_match:
            details["location"] = zoom_match.group(0)[:80]
        else:
            loc_match = _LOCATION_PATTERN.search(full_text)
            if loc_match:
                candidate = loc_match.group(1).strip()
                # Drop time-like matches that bled into location
                if not re.fullmatch(r'\d{1,2}(?::\d{2})?\s*(?:AM|PM)', candidate, re.IGNORECASE):
                    details["location"] = candidate[:80]

        # Topic / Agenda
        agenda_match = _AGENDA_PATTERN.search(full_text)
        if agenda_match:
            details["topic"] = agenda_match.group(1).strip()[:120]
        else:
            # Fall back: use subject as topic if it has meeting keywords
            if IMPORTANT_REGEX.search(subject):
                details["topic"] = subject[:120]

        return details

    @staticmethod
    def email_to_notification(email_data: dict) -> dict:
        """
        Convert a parsed email dict into the notification JSON format.
        Applies keyword-based priority hints and extracts meeting details.
        """
        subject = email_data.get("subject", "(no subject)")
        body = email_data.get("body", "")
        sender = email_data.get("sender", "unknown_sender")
        message_id = email_data.get("message_id")

        full_text = f"{subject} {body}"

        # Determine priority hint based on explicit keyword rules
        priority = "medium"  # default to IMPORTANT/LATER
        if VERY_IMPORTANT_REGEX.search(full_text):
            priority = "urgent"  # maps to NOW
        elif IGNORE_REGEX.search(full_text):
            priority = "low"     # maps to NEVER
        elif IMPORTANT_REGEX.search(full_text):
            priority = "high"    # maps to LATER/NOW (LLM will push to LATER per assignment)

        # Extract meeting details if this looks like a meeting email
        meeting_details = {}
        is_meeting = bool(IMPORTANT_REGEX.search(full_text))
        if is_meeting:
            meeting_details = EmailListener.extract_meeting_details(subject, body)

        return {
            "user_id": "gmail_user",
            "event_type": "email",
            "title": subject,
            "message": body[:500] if body else subject,
            "source": sender,
            "priority_hint": priority,
            "timestamp": email_data.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            "channel": "email",
            "dedupe_key": message_id,
            "metadata": {
                "is_meeting": is_meeting,
                "meeting": meeting_details if is_meeting else {},
                "body_preview": body[:300] if body else "",
            },
        }
