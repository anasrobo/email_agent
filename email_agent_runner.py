"""
Email Agent Runner — continuously monitors Gmail and classifies incoming
emails through the Notification Prioritization Engine.

Usage:
    Live mode  :  python email_agent_runner.py
    Test mode  :  python email_agent_runner.py --test
"""

import sys
import os
import time
import getpass
from datetime import datetime, timezone

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decision_engine import DecisionEngine
from email_listener import EmailListener


# ── Formatting helpers ────────────────────────────────────────────────

DECISION_ICONS = {
    "NOW":   "🟢",
    "LATER": "🟡",
    "NEVER": "🔴",
}


def _print_decision(subject: str, decision: str, reason: str):
    """Print a formatted decision block for one email."""
    icon = DECISION_ICONS.get(decision, "⚪")
    print(f"\n  📧 EMAIL RECEIVED: {subject}")
    print(f"     DECISION: {icon} {decision}")
    print(f"     REASON:   {reason}")


# ── Core processing ──────────────────────────────────────────────────

def process_email(engine: DecisionEngine, email_data: dict) -> dict:
    """
    Convert a parsed email into a notification event, run it through
    the DecisionEngine, and print the result.
    Returns the engine output record.
    """
    notification = EmailListener.email_to_notification(email_data)
    result = engine.process_event(notification)

    _print_decision(
        subject=email_data.get("subject", "(no subject)"),
        decision=result["decision"],
        reason=result["reason"],
    )
    return result


# ── Test mode ─────────────────────────────────────────────────────────

def simulate_email(subject: str, body: str = "") -> dict:
    """
    Build a fake parsed-email dict without connecting to any server.
    Useful for testing the pipeline end-to-end.
    """
    return {
        "sender": "test@example.com",
        "subject": subject,
        "body": body or subject,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_test():
    """Run several simulated emails through the engine."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    rules_path = os.path.join(base_dir, "rules.json")

    engine = DecisionEngine(rules_path=rules_path)

    test_subjects = [
        ("Meeting at 5 PM", "Don't forget your meeting with the design team at 5 PM today."),
        ("URGENT: Server is down!", "Production server web-03 is unresponsive. Immediate action required."),
        ("Weekly Newsletter — Feb 2026", "Here are the top stories this week from our blog."),
        ("Your OTP code is 482917", "Use this code to verify your login. Expires in 5 minutes."),
        ("50% OFF Summer Sale!", "Flat 50% discount on all items. Limited time offer."),
        ("Reminder: Submit timesheet", "Please submit your timesheet before end of day Friday."),
        ("Critical security alert", "Unauthorized login attempt detected on your account."),
        ("Team lunch tomorrow", "Hey, we're going to the new pizza place tomorrow at noon."),
    ]

    print("\n" + "=" * 70)
    print("  📬  EMAIL AGENT — TEST MODE")
    print("=" * 70)

    results = []
    for subject, body in test_subjects:
        fake_email = simulate_email(subject, body)
        result = process_email(engine, fake_email)
        results.append(result)

    # Summary table
    print("\n" + "─" * 70)
    print(f"  {'#':<3} {'Decision':<8} {'Subject'}")
    print("─" * 70)
    for i, (subj_body, res) in enumerate(zip(test_subjects, results), 1):
        icon = DECISION_ICONS.get(res["decision"], "⚪")
        print(f"  {i:<3} {icon} {res['decision']:<6} {subj_body[0]}")
    print("─" * 70)
    print(f"\n  ✅ Processed {len(results)} simulated emails.\n")


# ── Live mode ─────────────────────────────────────────────────────────

def run_live(email_address: str, password: str, poll_interval: int = 30):
    """
    Continuously poll Gmail for unread emails, classify each one,
    and log the decision.  Runs until interrupted with Ctrl+C.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    rules_path = os.path.join(base_dir, "rules.json")

    engine = DecisionEngine(rules_path=rules_path)
    listener = EmailListener(email_address, password)

    print("\n" + "=" * 70)
    print("  📬  EMAIL AGENT — LIVE MODE")
    print(f"  Polling every {poll_interval}s  •  Press Ctrl+C to stop")
    print("=" * 70)

    listener.connect()

    try:
        cycle = 0
        while True:
            cycle += 1
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n⏳ [{now}] Poll #{cycle} — checking for new emails ...")

            try:
                emails = listener.fetch_unread()
            except Exception as e:
                print(f"  ⚠️  Fetch error: {e}")
                # Try to reconnect on next cycle
                try:
                    listener.disconnect()
                    listener.connect()
                except Exception:
                    pass
                time.sleep(poll_interval)
                continue

            if not emails:
                print("  — No new emails.")
            else:
                print(f"  📩 Found {len(emails)} new email(s):")
                for eml in emails:
                    process_email(engine, eml)

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print("\n\n🛑 Agent stopped by user.")
    finally:
        listener.disconnect()
        print("👋 Goodbye.\n")


# ── Entry point ───────────────────────────────────────────────────────

def main():
    if "--test" in sys.argv:
        run_test()
        return

    # Live mode — prompt for credentials
    print("\n📬 Email Agent — Live Mode Setup")
    print("─" * 40)
    print("You need a Gmail address and an App Password.")
    print("Generate one at: https://myaccount.google.com/apppasswords\n")

    email_address = input("Gmail address : ").strip()
    password = getpass.getpass("App password  : ").strip()

    if not email_address or not password:
        print("❌ Email and password are required.")
        sys.exit(1)

    run_live(email_address, password)


if __name__ == "__main__":
    main()
