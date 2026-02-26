# Notification Prioritization Engine

> **Round 1 AI-Native Solution — Cyepro Solutions**  
> Candidate: Madhav 

A production-grade Notification Prioritization Engine that decides — for every incoming notification — whether it should be delivered **Now**, deferred for **Later**, or suppressed (**Never**). Built with a multi-stage AI decision pipeline, configurable rule engine, alert-fatigue management, and a live interactive web dashboard.

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Decision Logic — Now / Later / Never](#2-decision-logic--now--later--never)
3. [Data Model](#3-data-model)
4. [API Contracts](#4-api-contracts)
5. [Duplicate Prevention](#5-duplicate-prevention)
6. [Alert Fatigue Strategy](#6-alert-fatigue-strategy)
7. [Fallback Strategy](#7-fallback-strategy)
8. [Human-Configurable Rules](#8-human-configurable-rules)
9. [Metrics & Monitoring Plan](#9-metrics--monitoring-plan)
10. [Project Structure](#10-project-structure)
11. [Setup & Running](#11-setup--running)
12. [Testing](#12-testing)
13. [Tools Used](#13-tools-used)

---

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    NOTIFICATION EVENT SOURCES                         │
│   Messages · Reminders · Alerts · Promotions · System Events · Email │
└───────────────────────────┬──────────────────────────────────────────┘
                            │  Raw event JSON
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      INPUT VALIDATOR                                  │
│  • Required field check  • Type/channel enumeration validation        │
│  • Timestamp parsing     • expires_at normalization                   │
└───────────────────────────┬──────────────────────────────────────────┘
                            │  Normalized event
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    DUPLICATE DETECTOR                                 │
│  • Exact dedupe_key match (10-min window)                            │
│  • Near-duplicate text similarity (Levenshtein ≥ 0.90)              │
└──────────┬────────────────┬─────────────────────────────────────────┘
           │ duplicate      │ unique
           │ → NEVER        ▼
           │   ┌────────────────────────────────┐
           │   │        LLM CLASSIFIER           │
           │   │  Keyword scoring (urgent/promo/ │
           │   │  later) + priority_hint boost   │
           │   │  → label: NOW / LATER / NEVER   │
           │   └────────────┬───────────────────┘
           │                │ label + confidence + reason
           │                ▼
           │   ┌────────────────────────────────┐
           │   │       RULE ENGINE               │
           │   │  JSON rules (no re-deploy)      │
           │   │  force_decision / downgrade /   │
           │   │  limit_per_day / time_window    │
           │   └────────────┬───────────────────┘
           │                │ adjusted decision
           │                ▼
           │   ┌────────────────────────────────┐
           │   │    ALERT FATIGUE CHECK          │
           │   │  Frequency window counter       │
           │   │  NOW → LATER if ≥ 5 in 10 min  │
           │   │  LATER → NEVER if ≥ 7 in 10 min│
           │   └────────────┬───────────────────┘
           │                │ final decision
           │                ▼
           │   ┌────────────────────────────────┐
           │   │   CONFLICT / NOISE RESOLVER     │
           │   │  Max 2 urgent events of same    │
           │   │  type/source in 15 min → LATER  │
           │   └────────────┬───────────────────┘
           │                │
           │                ▼
           │   ┌────────────────────────────────┐
           │   │        SCHEDULER                │
           │   │  LATER → compute scheduled_time │
           │   │  Quiet hours / backoff / expiry │
           │   └────────────┬───────────────────┘
           │                │
           └────────────────┤
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    DECISION LOGGER                                    │
│  Structured JSON log: decision · explanation_code · reason           │
│  · matched_rule · confidence · raw_model_output · scheduled_time     │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   HISTORY STORE         │
              │   (per-user ring buffer) │
              └─────────────────────────┘
```

### Components Summary

| Component | File | Responsibility |
|---|---|---|
| **Decision Engine** | `decision_engine.py` | Central orchestrator; runs the full pipeline |
| **Input Validator** | `input_validator.py` | Schema & type validation; normalization |
| **Duplicate Detector** | `duplicate_detector.py` | Exact key + near-duplicate (Levenshtein) |
| **LLM Classifier** | `llm_classifier.py` | AI urgency scoring with keyword heuristics + fallback |
| **Rule Engine** | `rule_engine.py` | JSON-driven human-configurable rules |
| **Alert Fatigue** | `decision_engine.py` | Frequency window + noise limit logic |
| **Scheduler** | `scheduler.py` | Computes deferred delivery time |
| **History Store** | `history_store.py` | In-memory per-user ring buffer |
| **Logger** | `logger.py` | Structured explanation logging |
| **Web App / API** | `app.py` | Flask REST API + interactive dashboard |
| **Email Integration** | `web_app.py`, `email_listener.py` | Live Gmail IMAP + real-time dashboard |

---

## 2. Decision Logic — Now / Later / Never

Each event flows through a deterministic, ordered 8-step pipeline:

```
Step 1: VALIDATE         → reject malformed events (NEVER + VALIDATION_ERROR)
Step 2: DEDUPLICATE      → suppress exact/near-duplicate (NEVER)
Step 3: LLM CLASSIFY     → score urgency → NOW / LATER / NEVER
Step 4: RULE ENGINE      → override/downgrade/cap with human rules
Step 5: FATIGUE CHECK    → downgrade if user is overloaded
Step 6: NOISE RESOLVER   → downgrade if too many urgents of same type
Step 7: SCHEDULER        → compute scheduled_time for LATER; expire if past
Step 8: LOG              → write structured audit record
```

### Classification Criteria

| Signal | NOW | LATER | NEVER |
|---|---|---|---|
| `priority_hint` | `urgent`, `high` | `medium` | `low` |
| `event_type` | `alert`, `system` | `message`, `reminder`, `update`, `email` | `promotion` |
| Keywords | otp, outage, breach, failure, 95%, crash, security | reminder, submit, weekly, digest, report | sale, discount, promo, coupon, free, offer |
| Channel | `sms` (+1 urgency) | — | — |
| Duplicate | — | — | exact / near-dup |
| Quiet hours (10PM–6AM) | → downgraded to LATER | — | — |
| Frequency ≥ 5 in 10 min | → NOW demoted to LATER | ≥7 → NEVER | — |
| Expired | — | → NEVER | — |

### Explanation Codes

Every decision carries a machine-readable `explanation_code`:

| Code | Meaning |
|---|---|
| `URGENT_KEYWORD` | High-urgency keywords detected in message |
| `LLM_DECISION` | Standard LLM/heuristic classification |
| `FALLBACK` | LLM unavailable; deterministic fallback used |
| `RULE_OVERRIDE` | A human-configured rule changed the decision |
| `DUPLICATE_DEDUPE_KEY` | Exact dedupe_key seen within window |
| `DUPLICATE_TEXT_SIMILAR` | Near-duplicate text (≥ 90% similarity) |
| `FREQUENCY_LIMIT` | User received too many notifications recently |
| `FREQUENCY_SUPPRESSION` | User in overload — fully suppressed |
| `CONFLICT_NOISE_LIMIT` | Too many urgent events from same source |
| `EXPIRED` | Scheduled time exceeds `expires_at` |
| `VALIDATION_ERROR` | Event failed schema validation |

---

## 3. Data Model

### Notification Event (Input)

```json
{
  "user_id":       "u1",
  "event_type":    "alert",
  "title":         "Server Alert",
  "message":       "Server is down in zone A",
  "source":        "monitoring-service",
  "priority_hint": "urgent",
  "timestamp":     "2026-02-26T10:00:00Z",
  "channel":       "push",
  "metadata":      { "zone": "A", "server_id": "srv-42" },
  "dedupe_key":    "srvdown-42",
  "expires_at":    "2026-02-26T10:30:00Z"
}
```

**Valid Enumerations:**

| Field | Valid Values |
|---|---|
| `event_type` | `message`, `reminder`, `alert`, `promotion`, `system`, `update`, `email` |
| `channel` | `push`, `email`, `sms`, `in_app` |
| `priority_hint` | `low`, `medium`, `high`, `urgent` (optional) |

### Decision Output Record

```json
{
  "input_event": { "...": "...original normalized event..." },
  "decision":          "NOW",
  "scheduled_time":    null,
  "explanation_code":  "URGENT_KEYWORD",
  "reason":            "Urgent: service outage detected, priority=urgent",
  "matched_rule_id":   null
}
```

### Audit Log Entry (Logger)

```json
{
  "user_id":          "u1",
  "event_id":         "a3f1-...",
  "event_type":       "alert",
  "decision":         "NOW",
  "scheduled_time":   null,
  "timestamp":        "2026-02-26T10:00:00+00:00",
  "explanation_code": "URGENT_KEYWORD",
  "reason":           "Urgent: service outage detected",
  "matched_rule_id":  null,
  "confidence":       0.92,
  "raw_model_output": "LABEL:NOW; SHORT_REASON:Urgent: service outage detected; CONFIDENCE:0.92"
}
```

### History Store Record (per-user ring buffer)

```json
{
  "event_id":        "a3f1-...",
  "event_type":      "alert",
  "source":          "monitoring-service",
  "decision":        "NOW",
  "explanation_code":"URGENT_KEYWORD",
  "dedupe_key":      "srvdown-42",
  "normalized_text": "server alert server is down in zone a",
  "parsed_timestamp": "2026-02-26T10:00:00+00:00",
  "timestamp":        "2026-02-26T10:00:00+00:00"
}
```

### Rule Schema (`rules.json`)

```json
{
  "rules": [
    {
      "id": "R02",
      "description": "Always send urgent system alerts immediately",
      "priority": 200,
      "match": {
        "event_type":    ["system"],
        "priority_hint": ["urgent"]
      },
      "action": {
        "force_decision": "NOW"
      }
    }
  ]
}
```

**Rule Action Types:**

| Action Key | Behavior |
|---|---|
| `force_decision` | Override LLM output unconditionally |
| `downgrade` | Map `NOW → LATER` or `LATER → NEVER` |
| `limit_per_day` | Suppress after N events of this type per user per day |

---

## 4. API Contracts

The engine exposes a clean REST API via Flask (`app.py`):

### `POST /api/process` — Process Notification Events

Submit one or more notification events for prioritization.

**Request:**
```json
{
  "events": [
    {
      "user_id": "u1",
      "event_type": "alert",
      "title": "Server Down",
      "message": "Server is down in zone A",
      "priority_hint": "urgent",
      "timestamp": "2026-02-26T10:00:00Z",
      "channel": "push",
      "dedupe_key": "srvdown-42"
    }
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "input_event":      { "...": "..." },
      "decision":         "NOW",
      "scheduled_time":   null,
      "explanation_code": "URGENT_KEYWORD",
      "reason":           "Urgent: service outage detected, priority=urgent",
      "matched_rule_id":  null
    }
  ],
  "logs": [ { "...": "full audit log entry..." } ],
  "summary": { "total": 1, "now": 1, "later": 0, "never": 0 }
}
```

---

### `GET /api/rules` — Get Current Rules

Returns the active JSON rule set.

**Response:** Current `rules.json` contents.

---

### `POST /api/rules` — Update Rules (Hot Reload)

Updates rules **at runtime** without restarting the server.

**Request:**
```json
{
  "rules": [
    {
      "id": "R05",
      "description": "Suppress all promotions on SMS",
      "priority": 150,
      "match": { "event_type": ["promotion"], "channel": ["sms"] },
      "action": { "force_decision": "NEVER" }
    }
  ]
}
```

**Response:**
```json
{ "status": "ok", "message": "Rules updated (1 rules)" }
```

---

### `POST /api/simulate-failure` — Toggle LLM Failure Mode

Enables or disables LLM failure simulation to test the fallback path.

**Request:** `{ "enabled": true }`  
**Response:** `{ "status": "ok", "llm_failure_mode": true, "message": "LLM failure simulation enabled" }`

---

### `GET /api/health` — Health Check

**Response:** `{ "status": "ok", "engine": "Notification Prioritization Engine v1.0" }`

---

### `GET /api/test-events` — Get Test Events

Returns the pre-built test event suite for the interactive dashboard.

---

## 5. Duplicate Prevention

Two-stage deduplication with configurable 10-minute window:

### Stage 1 — Exact Dedupe Key Match

If the event has a `dedupe_key`, the system looks for any historical entry with the same key for that user within the dedupe window. If found → **NEVER** (`DUPLICATE_DEDUPE_KEY`).

> **Handles unreliable keys:** If `dedupe_key` is missing or `null`, Stage 1 is skipped transparently.

### Stage 2 — Near-Duplicate Text Similarity

For events that pass Stage 1, the normalized title + message text is compared against all recent entries using **Levenshtein distance**:

```
normalized_text = lowercase(strip_punctuation(collapse_whitespace(title + " " + message)))
similarity_ratio = 1 - (levenshtein_distance(a, b) / max(len(a), len(b)))
```

If `similarity_ratio ≥ 0.90` → **NEVER** (`DUPLICATE_TEXT_SIMILAR`).

**Quick-reject optimization:** If the lengths differ by more than `(1 - threshold) * max_len`, the pair is rejected without computing the full matrix — keeping latency low even at high event volumes.

---

## 6. Alert Fatigue Strategy

Three independent layers prevent notification overload:

### Layer 1 — Per-User Frequency Window

A sliding 10-minute window counts all decisions per user:

| Condition | Action |
|---|---|
| `count ≥ 5` | Downgrade `NOW → LATER` (`FREQUENCY_LIMIT`) |
| `count ≥ 7` | Suppress `LATER → NEVER` (`FREQUENCY_SUPPRESSION`) |

### Layer 2 — Source/Type Noise Limit

Within a 15-minute window, a maximum of 2 urgent (`NOW`) events from the same `event_type` or `source` are allowed:

- If `urgent_count ≥ 2` → downgrade `NOW → LATER` (`CONFLICT_NOISE_LIMIT`)
- This handles monitoring systems that fire many simultaneous alerts for a single incident.

### Layer 3 — Human Rule Caps

Rules can enforce per-day limits per event type per user:

```json
{ "action": { "limit_per_day": 3 } }
```

When the daily count reaches the limit, further events are suppressed (`RULE_OVERRIDE` → `NEVER`).

### Quiet Hours

Between 10 PM and 6 AM, `NOW` decisions are downgraded to `LATER` and scheduled for 8 AM the next day.

---

## 7. Fallback Strategy

The system is designed to **never silently lose important notifications** when the AI layer is unavailable.

```
LLM Classifier
      │
      ├── Normal path ──→ keyword scoring → label
      │
      └── Failure path (exception or simulate_failure=True)
                │
                ▼
          DETERMINISTIC FALLBACK
          ┌────────────────────────────────────────┐
          │  priority_hint → decision:             │
          │    urgent / high  → NOW                │
          │    medium         → LATER              │
          │    low            → NEVER              │
          │                                        │
          │  event_type fallback (no priority):    │
          │    alert / system → NOW                │
          │    message / reminder / update → LATER │
          │    promotion → NEVER                   │
          │                                        │
          │  Unknown → LATER (safe default)        │
          └────────────────────────────────────────┘
          explanation_code = "FALLBACK"
          confidence = 0.4
```

- **All remaining pipeline steps run normally** (Rule Engine, Fatigue Check, Scheduler, Logger) — only the LLM step is bypassed.
- The `FALLBACK` explanation code is always logged so operators can detect degradation.
- A `simulate_failure` toggle (`POST /api/simulate-failure`) allows live testing of this path.

---

## 8. Human-Configurable Rules

Rules are stored in `rules.json` and **reloaded at runtime** via `POST /api/rules` — no server restart required.

### Pre-built Rules

| Rule ID | Priority | Condition | Action |
|---|---|---|---|
| `R02` | 200 | `event_type=system` + `priority_hint=urgent` | `force_decision=NOW` |
| `R01` | 100 | `event_type=promotion` | `force_decision=NEVER` |
| `R04` | 80 | `event_type=reminder` | `limit_per_day=3` |
| `R03` | 50 | `time_window=22–6` | `downgrade: NOW → LATER` |

### Supported Match Conditions

| Condition | Type | Description |
|---|---|---|
| `event_type` | array | Match against one of the listed types |
| `priority_hint` | array | Match one of: `urgent`, `high`, `medium`, `low` |
| `channel` | array | Match one of: `push`, `email`, `sms`, `in_app` |
| `source` | array | Match by originating service name |
| `time_window` | object | `{ "start_hour": 22, "end_hour": 6 }` — wraps midnight |

Rules are **priority-sorted** (higher = matched first). The first matching `force_decision` wins and exits early.

---

## 9. Metrics & Monitoring Plan

### Key Metrics to Track

| Category | Metric | Why |
|---|---|---|
| **Throughput** | Events processed / second | Capacity planning |
| **Latency** | p50 / p95 / p99 decision latency | SLA compliance |
| **Decision Distribution** | `%NOW` / `%LATER` / `%NEVER` per time period | Detect anomalies (e.g. sudden suppression spike) |
| **Deduplication Rate** | `%DUPLICATE_DEDUPE_KEY` / `%DUPLICATE_TEXT_SIMILAR` | Key quality signal |
| **Fatigue Rate** | `%FREQUENCY_LIMIT` + `%FREQUENCY_SUPPRESSION` | User overload indicator |
| **LLM Health** | `%FALLBACK` decisions | Model reliability |
| **Rule Hit Rate** | `matched_rule_id` breakdown | Rule effectiveness |
| **Expiry Rate** | `%EXPIRED` decisions | Stale event detection |
| **Validation Error Rate** | `%VALIDATION_ERROR` | Upstream data quality |

### Monitoring Stack (Recommended)

```
Application → Structured JSON logs → log aggregator (ELK / Loki)
                                  → metrics pipeline (Prometheus)
                                  → dashboards (Grafana)
                                  → alerts (PagerDuty / Alertmanager)
```

### Critical Alerts to Set Up

| Alert | Threshold | Action |
|---|---|---|
| Fallback rate spike | `%FALLBACK > 5%` in 5 min | Page on-call — LLM degradation |
| NOW suppression spike | `%NEVER for NOW-hint > 10%` | Audit fatigue settings |
| Decision latency | `p99 > 200ms` | Scale horizontally |
| Validation error burst | `%VALIDATION_ERROR > 1%` | Alert upstream services |

### Auditability

Every single decision has a full audit trail in `output.json` containing:
- The original input event
- Final decision + `explanation_code` + human-readable `reason`
- Matched rule ID (if any)
- LLM confidence score + raw model output
- Scheduled delivery time (for LATER)

This makes every decision **reconstructable and explainable** post-hoc.

---

## 10. Project Structure

```
notification-prioritization-engine/
│
├── decision_engine.py      # Central orchestrator — 8-step pipeline
├── input_validator.py      # Schema validation & normalization
├── duplicate_detector.py   # Exact + near-duplicate detection (Levenshtein)
├── llm_classifier.py       # AI urgency classifier with fallback
├── rule_engine.py          # JSON rule loader, matcher, and executor
├── history_store.py        # In-memory per-user ring buffer
├── scheduler.py            # Deferred delivery time calculator
├── logger.py               # Structured audit log writer
├── config.py               # All tunable constants (no hard-coded values)
│
├── app.py                  # Flask REST API server (5 endpoints)
├── web_app.py              # Live Gmail dashboard (IMAP integration)
├── email_listener.py       # Gmail IMAP connector and email→event mapper
├── email_agent_runner.py   # CLI test runner for email mode
├── runner.py               # CLI test runner for core engine
│
├── rules.json              # Human-configurable rule set (hot-reloaded)
├── test_events.json        # Pre-built test scenarios
├── email_config.json       # Gmail credentials template
├── requirements.txt        # Python dependencies
│
├── templates/
│   └── index.html          # Web dashboard HTML
└── static/
    └── script.js           # Dashboard auto-refresh & simulation logic
```

---

## 11. Setup & Running (Connect Your Gmail)

To make this a **Real Agent** that monitors your actual Gmail inbox, follow these steps:

### Step 1: Gmail Security Setup
1. **Enable 2-Step Verification**: Go to [Google Security](https://myaccount.google.com/security) and turn it ON.
2. **Create an App Password**: Go to [App Passwords](https://myaccount.google.com/apppasswords), name it "Notification Agent", and copy the **16-character code**.
3. **Enable IMAP**: In Gmail Settings -> Forwarding and POP/IMAP -> Select **Enable IMAP** -> Save.

### Step 2: Configure Credentials
Edit the `email_config.json` file in the root directory:
```json
{
  "email": "your_email@gmail.com",
  "app_password": "xxxx xxxx xxxx xxxx",
  "imap_server": "imap.gmail.com",
  "imap_port": 993,
  "poll_interval_seconds": 15
}
```

### Step 3: Launch the Agent
```bash
# Install dependencies
pip install -r requirements.txt

# Start the Live Agent & Dashboard
python web_app.py
```
Open **http://localhost:5000** in your browser.

---

## 12. Testing & Simulation

### Real Results
Once the server is running with your credentials, simply **send yourself an email** (or wait for one to arrive). The dashboard will refresh every 15 seconds and categorize it automatically.

### What is the "Simulator"?
The **Simulate Incoming Email** panel at the top of the dashboard allows you to test the engine's logic without sending real emails. 
- **Dummy Data**: Any data entered there is processed by the same AI logic but doesn't touch your actual Gmail.
- **Why use it?** It's perfect for testing "Very Important" scenarios (like a server crash) to ensure the rules work exactly as expected before a real event happens.


---

## 13. Tools Used

| Tool | Usage |
|---|---|
| **Python 3.11** | Core engine language |
| **Flask** | REST API and web dashboard server |
| **Antigravity (Google DeepMind)** | AI coding assistant — used to scaffold initial module structure, debug pipeline ordering, and review edge-case logic |

### What was manually designed and written:

- The full 8-step pipeline architecture and ordering decisions
- Dual-stage dedup strategy (exact key + Levenshtein near-dup)
- Three-layer alert fatigue model (frequency + noise + rule cap)
- All rule schema design and action types
- Deterministic fallback hierarchy (priority_hint → event_type → LATER)
- Scheduler logic (quiet hours, exponential backoff, expiry check)
- All explanation codes and audit log schema
- The `conflict/noise resolution` step (unusual in standard designs)
- All tradeoff decisions (in-memory vs. persistent, LLM simulation rationale)
- This README

---

## Design Tradeoffs & Notes

| Decision | Rationale |
|---|---|
| In-memory `HistoryStore` (ring buffer) | Zero-latency lookups; acceptable for prototype. Production would use Redis with TTL. |
| Keyword heuristics instead of real LLM | Deterministic, testable, zero API cost. Real deployment would call GPT-4 / Gemini with the same interface; fallback is already wired. |
| Levenshtein over cosine/embedding | No external model dependency; fast for short strings; easily tunable threshold. |
| Rules in JSON (not DB) | Human-readable, git-trackable, hot-reloadable via API. No SQL dependency for config changes. |
| LATER does not queue to a message broker | This prototype decides timing; the delivery mechanism (SQS, Celery beat, etc.) is left to the consuming service. |
| Single process, single engine instance | Sufficient for demo volume; production would shard by user_id across stateless workers with shared Redis state. |

---

*Built for the Cyepro Solutions Round 1 AI-Native Solution Crafting Test.*
