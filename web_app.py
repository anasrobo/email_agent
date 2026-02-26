import os
import json
import time
import threading
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request

# Import existing notification engine components
from decision_engine import DecisionEngine
from email_listener import EmailListener

app = Flask(__name__)

# ── Global State ──────────────────────────────────────────────────────
NOTIFICATIONS_FILE = "notifications.json"
memory_notifications = []

# Initialize Decision Engine
base_dir = os.path.dirname(os.path.abspath(__file__))
rules_path = os.path.join(base_dir, "rules.json")
engine = DecisionEngine(rules_path=rules_path)


# ── Initialization ────────────────────────────────────────────────────
def load_notifications():
    """Load notifications from disk into memory."""
    global memory_notifications
    if os.path.exists(NOTIFICATIONS_FILE):
        try:
            with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
                memory_notifications = json.load(f)
        except Exception as e:
            print(f"Error loading notifications: {e}")
            memory_notifications = []


def save_notifications():
    """Save the memory list to disk."""
    try:
        with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(memory_notifications, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving notifications: {e}")


load_notifications()


# ── Core Processing ───────────────────────────────────────────────────
def process_classification(engine_result: dict) -> dict:
    """
    Format the DecisionEngine result into the 3-tier structure
    for the web dashboard. Includes meeting details if present.
    """
    decision = engine_result.get("decision", "LATER")

    # Map decision to 3-tier classification
    if decision == "NOW":
        classification = "VERY IMPORTANT"
    elif decision == "NEVER":
        classification = "IGNORE"
    else:
        classification = "IMPORTANT"

    event = engine_result.get("input_event", {})
    metadata = event.get("metadata", {})
    meeting = metadata.get("meeting", {})

    formatted_record = {
        "time": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "sender": event.get("source", "unknown"),
        "subject": event.get("title", "(no subject)"),
        "body_preview": metadata.get("body_preview", event.get("message", ""))[:300],
        "classification": classification,
        "decision": decision,
        "reason": engine_result.get("reason", "No reason provided"),
        "is_meeting": metadata.get("is_meeting", False),
        # Structured meeting fields — None if not detected
        "meeting_time":     meeting.get("time"),
        "meeting_date":     meeting.get("date"),
        "meeting_location": meeting.get("location"),
        "meeting_topic":    meeting.get("topic"),
    }
    return formatted_record


def process_and_store_email(email_data: dict):
    """Run an email through the engine and store the result."""
    notification = EmailListener.email_to_notification(email_data)
    result = engine.process_event(notification)
    formatted = process_classification(result)
    
    # Store at the beginning of the list (newest first)
    memory_notifications.insert(0, formatted)
    
    # Keep only the latest 100 for memory safety
    if len(memory_notifications) > 100:
        memory_notifications.pop()
        
    save_notifications()
    return formatted


# ── Background IMAP Thread ────────────────────────────────────────────
def load_config():
    config_path = os.path.join(base_dir, "email_config.json")
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading config: {e}")
        return None


def background_email_listener():
    """Continuously poll Gmail based on configuration."""
    print("[Background Thread] Starting email monitor...")
    
    while True:
        config = load_config()
        if not config:
            print("[Background Thread] email_config.json missing or invalid. Retrying in 15s...")
            time.sleep(15)
            continue
            
        poll_interval = config.get("poll_interval_seconds", 15)
        email_addr = config.get("email")
        password = config.get("app_password")
        
        if not email_addr or not password or password == "your_app_password":
            print("[Background Thread] Please configure email_config.json with real credentials.")
            time.sleep(15)
            continue
            
        listener = EmailListener(
            email_address=email_addr,
            password=password,
            imap_host=config.get("imap_server", "imap.gmail.com"),
            imap_port=config.get("imap_port", 993)
        )
        
        try:
            listener.connect()
            
            # On first connect, fetch last 24 hours of emails to build history
            print("[Background Thread] Fetching recent emails from last 24 hours...")
            try:
                recent_emails = listener.fetch_recent_emails(hours=24, limit=50)
                print(f"[Background Thread] Found {len(recent_emails)} recent emails to process")
                for eml in recent_emails:
                    print(f"[IMAP] Processing recent email: {eml.get('subject')}")
                    process_and_store_email(eml)
            except Exception as e:
                print(f"[Background Thread] Error fetching recent emails: {e}")
            
            # Now start polling for new unread emails
            while True:
                # Reload config inside loop to catch interval changes
                config = load_config()
                if config:
                   poll_interval = config.get("poll_interval_seconds", 15)
                   
                try:
                    emails = listener.fetch_unread()
                    for eml in emails:
                        print(f"[IMAP] New email received: {eml.get('subject')}")
                        process_and_store_email(eml)
                except Exception as loop_e:
                    print(f"[IMAP] Fetch error: {loop_e}. Will reconnect.")
                    break # Break inner loop to trigger reconnect
                    
                time.sleep(poll_interval)
                
        except Exception as e:
            print(f"[Background Thread] Connection error: {e}. Retrying in {poll_interval}s...")
            time.sleep(poll_interval)
        finally:
            listener.disconnect()


# Start background thread
imapd_thread = threading.Thread(target=background_email_listener, daemon=True)
imapd_thread.start()


# ── Flask Routes ──────────────────────────────────────────────────────
@app.route("/")
def index():
    """Serve the main dashboard UI."""
    return render_template("index.html")


@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    """Return the list of processed notifications."""
    return jsonify(memory_notifications)


@app.route("/api/simulate", methods=["POST"])
def simulate():
    """API endpoint to simulate an incoming email."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    subject = data.get("subject", "Test Subject")
    body = data.get("body", "Test Body")
    sender = data.get("sender", "simulator@example.com")
    
    simulated_email = {
        "message_id": f"sim-{datetime.now().timestamp()}",
        "sender": sender,
        "subject": subject,
        "body": body,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    result = process_and_store_email(simulated_email)
    return jsonify({"success": True, "result": result})


if __name__ == "__main__":
    print("\n" + "="*50)
    print("  📧 Live Email Prioritization Dashboard")
    print("  Running on http://127.0.0.1:5000")
    print("="*50 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
