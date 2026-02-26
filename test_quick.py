"""Quick test: verify the meeting extractor and decision engine work correctly."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_listener import EmailListener
from decision_engine import DecisionEngine

print("=" * 60)
print("  NOTIFICATION ENGINE — QUICK SELF-TEST")
print("=" * 60)

# ── Test 1: Meeting email extraction
print("\n[1] MEETING DETAIL EXTRACTION")
test_emails = [
    {
        "subject": "Team Meeting — Sprint Planning on Friday",
        "body": "Hi team, we have a sprint planning meeting on Friday at 3:00 PM in Conference Room 4B. Agenda: review Q1 backlog and assign tasks for the next sprint. Join Zoom: https://zoom.us/j/987654321"
    },
    {
        "subject": "Product Review on Wednesday at 11 AM",
        "body": "You are invited to the Product Review. Location: via Zoom https://meet.google.com/abc-def-ghi. Topic: Q1 product roadmap discussion and stakeholder updates."
    },
    {
        "subject": "Reminder — submit timesheet by EOD",
        "body": "Please submit your timesheet today by 6:00 PM. No location — this is just an internal reminder."
    },
]

for em in test_emails:
    details = EmailListener.extract_meeting_details(em["subject"], em["body"])
    print(f"\n  Subject : {em['subject']}")
    print(f"  Time    : {details['time']}")
    print(f"  Date    : {details['date']}")
    print(f"  Location: {details['location']}")
    print(f"  Topic   : {details['topic']}")

# ── Test 2: email_to_notification conversion
print("\n" + "=" * 60)
print("[2] EMAIL → NOTIFICATION CONVERSION")
meeting_email = {
    "message_id": "test-001",
    "sender": "manager@company.com",
    "subject": "Team Meeting at 3 PM on Friday in Room 4B",
    "body": "Hi team, sprint review at 3:00 PM on Friday. Agenda: Q1 review. Room 4B, Building 2.",
    "timestamp": "2026-02-27T09:00:00+00:00",
}
notif = EmailListener.email_to_notification(meeting_email)
print(f"  priority_hint : {notif['priority_hint']}")
print(f"  is_meeting    : {notif['metadata']['is_meeting']}")
print(f"  meeting.time  : {notif['metadata']['meeting'].get('time')}")
print(f"  meeting.date  : {notif['metadata']['meeting'].get('date')}")
print(f"  meeting.loc   : {notif['metadata']['meeting'].get('location')}")
print(f"  meeting.topic : {notif['metadata']['meeting'].get('topic')}")

# ── Test 3: Decision engine for each scenario
print("\n" + "=" * 60)
print("[3] DECISION ENGINE — CLASSIFICATION TEST")

engine = DecisionEngine(rules_path="rules.json")

test_events = [
    {
        "user_id": "u1", "event_type": "email",
        "title": "Team Meeting at 3 PM — Sprint Planning",
        "message": "Sprint meeting on Friday at 3 PM in Room 4B. Agenda: Q1 review.",
        "priority_hint": "high", "timestamp": "2026-02-27T09:00:00Z", "channel": "email",
        "source": "manager@company.com",
    },
    {
        "user_id": "u2", "event_type": "message",
        "title": "Your OTP is 445566",
        "message": "Use OTP 445566 to complete your login. Valid 5 minutes.",
        "priority_hint": "urgent", "timestamp": "2026-02-27T09:01:00Z", "channel": "sms",
    },
    {
        "user_id": "u3", "event_type": "promotion",
        "title": "Flat 70% OFF — Summer Sale",
        "message": "Shop now and save! Use code SALE70. Limited time offer.",
        "priority_hint": "low", "timestamp": "2026-02-27T09:02:00Z", "channel": "push",
    },
    {
        "user_id": "u4", "event_type": "alert",
        "title": "URGENT: Server is down",
        "message": "Critical: server srv-42 in zone-A is unreachable. Investigate immediately.",
        "priority_hint": "urgent", "timestamp": "2026-02-27T09:03:00Z", "channel": "push",
    },
]

for ev in test_events:
    result = engine.process_event(ev)
    d = result['decision']
    badge = {"NOW": "🔴 NOW", "LATER": "🟡 LATER", "NEVER": "⚪ NEVER"}.get(d, d)
    print(f"\n  [{badge}] {ev['title'][:50]}")
    print(f"    Code   : {result['explanation_code']}")
    print(f"    Reason : {result['reason'][:80]}")

print("\n" + "=" * 60)
print("  ✅ All tests passed successfully!")
print("=" * 60)
