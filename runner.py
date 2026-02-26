"""
Runner — CLI script to process test events, stress tests, and LLM failure simulation.
"""

import json
import sys
import os

# Ensure the project directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decision_engine import DecisionEngine


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_test_dataset(engine: DecisionEngine, events: list, label: str = "TEST DATASET"):
    """Run a batch of events and display results."""
    print(f"\n{'━' * 80}")
    print(f"  ▶  {label}")
    print(f"{'━' * 80}")

    results = engine.process_batch(events)

    # Print detailed results
    for i, result in enumerate(results, 1):
        ev = result["input_event"]
        d = result["decision"]

        # Color-code decisions
        if d == "NOW":
            badge = "🟢 NOW   "
        elif d == "LATER":
            badge = "🟡 LATER "
        elif d == "NEVER":
            badge = "🔴 NEVER "
        else:
            badge = f"   {d:<6}"

        msg = ev.get("message", "")[:45]
        print(f"  {i:>2}. [{ev.get('user_id', '?'):<3}] {ev.get('event_type', '?'):<10} "
              f"│ {badge} │ {result['explanation_code']:<25} │ {msg}")

        if result.get("scheduled_time"):
            print(f"      ↳ scheduled: {result['scheduled_time']}")
        if result.get("matched_rule_id"):
            print(f"      ↳ rule: {result['matched_rule_id']}")

    return results


def main():
    # Determine paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    rules_path = os.path.join(base_dir, "rules.json")
    events_path = os.path.join(base_dir, "test_events.json")
    output_path = os.path.join(base_dir, "output.json")

    # Load test data
    test_data = load_json(events_path)
    test_events = test_data.get("test_events", [])
    stress_events = test_data.get("stress_test_events", [])

    simulate_failure = "--simulate-failure" in sys.argv

    # ── Scenario 1: Main test dataset ─────────────────────────────────
    print("\n" + "=" * 80)
    print("  NOTIFICATION PRIORITIZATION ENGINE — NOW / LATER / NEVER")
    print("=" * 80)

    engine = DecisionEngine(rules_path=rules_path, simulate_llm_failure=False)
    results_main = run_test_dataset(engine, test_events, "SCENARIO 1: Main Test Dataset (8 events)")

    # Print formatted table
    engine.logger.print_table()

    # ── Scenario 2: Stress test ───────────────────────────────────────
    engine2 = DecisionEngine(rules_path=rules_path, simulate_llm_failure=False)
    results_stress = run_test_dataset(engine2, stress_events,
                                       "SCENARIO 2: Stress Test — 6 alerts to same user in 5 min")
    engine2.logger.print_table()

    # ── Scenario 3: LLM failure simulation ────────────────────────────
    engine3 = DecisionEngine(rules_path=rules_path, simulate_llm_failure=True)
    results_fallback = run_test_dataset(engine3, test_events,
                                         "SCENARIO 3: LLM Failure — Fallback decisions")
    engine3.logger.print_table()

    # ── Export combined output ────────────────────────────────────────
    all_output = {
        "scenario_1_main_test": results_main,
        "scenario_2_stress_test": results_stress,
        "scenario_3_llm_failure": results_fallback,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_output, f, indent=2, default=str)

    print(f"\n✅ All decisions exported to: {output_path}")
    print(f"   Total decisions: {len(results_main) + len(results_stress) + len(results_fallback)}")


if __name__ == "__main__":
    main()
