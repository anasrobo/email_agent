"""
Flask Web Application — Interactive dashboard for the Notification Prioritization Engine.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify
from decision_engine import DecisionEngine

app = Flask(__name__)

# Global engine instance
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(BASE_DIR, "rules.json")
EVENTS_PATH = os.path.join(BASE_DIR, "test_events.json")

engine = DecisionEngine(rules_path=RULES_PATH)


def load_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/process", methods=["POST"])
def process_events():
    """Process a batch of notification events."""
    global engine
    data = request.get_json()
    events = data.get("events", [])

    if not events:
        return jsonify({"error": "No events provided"}), 400

    # Reset engine state for fresh processing
    engine.reset()

    results = engine.process_batch(events)
    logs = engine.logger.logs

    return jsonify({
        "results": results,
        "logs": logs,
        "summary": {
            "total": len(results),
            "now": sum(1 for r in results if r["decision"] == "NOW"),
            "later": sum(1 for r in results if r["decision"] == "LATER"),
            "never": sum(1 for r in results if r["decision"] == "NEVER"),
        }
    })


@app.route("/api/rules", methods=["GET"])
def get_rules():
    """Get current rules."""
    rules_data = load_json_file(RULES_PATH)
    return jsonify(rules_data)


@app.route("/api/rules", methods=["POST"])
def update_rules():
    """Update rules at runtime."""
    global engine
    data = request.get_json()

    try:
        # Validate structure
        rules = data.get("rules", data) if isinstance(data, dict) else data
        if not isinstance(rules, list) and not (isinstance(data, dict) and "rules" in data):
            return jsonify({"error": "Invalid rules format"}), 400

        # Save to file
        save_json_file(RULES_PATH, data)

        # Reload engine rules
        engine.reload_rules(rules_path=RULES_PATH)

        return jsonify({"status": "ok", "message": f"Rules updated ({len(rules if isinstance(rules, list) else data.get('rules', []))} rules)"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/test-events", methods=["GET"])
def get_test_events():
    """Get test events."""
    data = load_json_file(EVENTS_PATH)
    return jsonify(data)


@app.route("/api/simulate-failure", methods=["POST"])
def simulate_failure():
    """Toggle LLM failure simulation."""
    global engine
    data = request.get_json()
    enabled = data.get("enabled", False)
    engine.set_llm_failure(enabled)
    return jsonify({
        "status": "ok",
        "llm_failure_mode": enabled,
        "message": f"LLM failure simulation {'enabled' if enabled else 'disabled'}"
    })


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "engine": "Notification Prioritization Engine v1.0"})


if __name__ == "__main__":
    print("\n🚀 Notification Prioritization Engine — Web Dashboard")
    print("   http://localhost:5000\n")
    app.run(debug=True, port=5000, host="0.0.0.0")
