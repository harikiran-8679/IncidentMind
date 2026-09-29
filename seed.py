"""
seed.py — Idempotent seeder that retains all 15 demo incidents into Hindsight.

Run once before the demo:
    source venv/bin/activate
    python seed.py

Idempotency: we use document_id = "incident-{id}" and "outcome-{id}".
Hindsight will update-or-insert based on document_id.

For incidents where a first fix attempt FAILED (INC-003, INC-008, INC-012,
INC-015) we also retain a separate "outcome-{id}-failed" memory entry so the
agent can recall and explicitly warn against that approach.
"""

import json
import sys
import time
from pathlib import Path

from memory import retain_incident, retain_outcome
from config import HINDSIGHT_BANK_ID

INCIDENTS_FILE = Path(__file__).parent / "data" / "incidents.json"


def seed_all() -> None:
    """Retain all incidents and their outcomes into Hindsight Cloud."""
    print(f"🧠 IncidentMind Seeder — bank: {HINDSIGHT_BANK_ID}")
    print("=" * 60)

    incidents = json.loads(INCIDENTS_FILE.read_text())
    print(f"📋 Found {len(incidents)} incidents to seed\n")

    retained_ok = 0
    retained_err = 0

    for inc in incidents:
        inc_id = inc["id"]
        service = inc["service"]
        outcome = inc.get("outcome", "pending")

        print(f"  ⏳ Seeding {inc_id} ({service}) ...", end=" ", flush=True)

        # ── Retain the full incident ─────────────────────────────────────────
        result = retain_incident(
            incident_id=inc_id,
            service=service,
            symptoms=inc["symptoms"],
            error_log=inc["error_log"],
            root_cause=inc["root_cause"],
            fix_applied=inc["fix_applied"],
            time_to_resolve_min=inc["time_to_resolve_min"],
            outcome=outcome,
        )

        if result["success"]:
            print(f"incident ✓", end=" ", flush=True)
        else:
            print(f"incident ✗ ({result['message'][:60]})", end=" ", flush=True)
            retained_err += 1

        # Small delay to avoid rate limits
        time.sleep(0.5)

        # ── Retain the fix outcome (separate memory entry) ───────────────────
        outcome_result = retain_outcome(
            incident_id=inc_id,
            service=service,
            root_cause=inc["root_cause"],
            fix_applied=inc["fix_applied"],
            outcome=outcome,
        )

        if outcome_result["success"]:
            print(f"| outcome ✓", end=" ", flush=True)
            retained_ok += 1
        else:
            print(f"| outcome ✗ ({outcome_result['message'][:60]})", end=" ", flush=True)
            retained_err += 1

        time.sleep(0.5)

        # ── For incidents with a failed first attempt, retain it separately ──
        first_fix_failed = inc.get("first_fix_failed")
        if first_fix_failed:
            story = inc.get("story", "")
            failed_result = retain_outcome(
                incident_id=f"{inc_id}-failed",
                service=service,
                root_cause=inc["root_cause"],
                fix_applied=first_fix_failed,
                outcome="failed",
            )
            if failed_result["success"]:
                print(f"| failed-first-attempt ✓")
                retained_ok += 1
            else:
                print(f"| failed-first-attempt ✗ ({failed_result['message'][:60]})")
                retained_err += 1
            time.sleep(0.5)
        else:
            print()

    print()
    print("=" * 60)
    print(f"✅ Done! Retained: {retained_ok} memories | Errors: {retained_err}")
    print(f"🔗 Bank ID: {HINDSIGHT_BANK_ID}")
    print()
    print("Next steps:")
    print("  streamlit run app.py")


if __name__ == "__main__":
    seed_all()
