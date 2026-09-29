"""
test_connection.py — STEP 0 validation script.

Tests:
  1. Hindsight retain  → stores one memory into the bank
  2. Hindsight recall  → retrieves it back
  3. Groq chat call    → gets a response from the primary model

Run:
  source venv/bin/activate
  python test_connection.py
"""

import sys
from config import HINDSIGHT_API_KEY, GROQ_API_KEY, HINDSIGHT_BANK_ID, HINDSIGHT_BASE_URL

print("=" * 60)
print("IncidentMind — Connection Test")
print("=" * 60)

# ── Test 1: Hindsight retain ─────────────────────────────────────────────────
print("\n[1/3] Testing Hindsight retain...")
print(f"      Bank: {HINDSIGHT_BANK_ID}")
print(f"      URL:  {HINDSIGHT_BASE_URL}")

try:
    from hindsight_client import Hindsight

    client = Hindsight(
        base_url=HINDSIGHT_BASE_URL,
        api_key=HINDSIGHT_API_KEY,
        timeout=60.0,
    )

    retain_resp = client.retain(
        bank_id=HINDSIGHT_BANK_ID,
        content=(
            "TEST MEMORY: payments-api went down due to DB connection pool exhaustion. "
            "Fix: increased max_connections. Fix outcome: worked."
        ),
        document_id="test-connection-memory",
        metadata={"type": "test", "service": "payments-api"},
        tags=["test"],
    )

    if retain_resp.success:
        print(f"      ✅ Retain succeeded! Items retained: {retain_resp.items_count}")
    else:
        print(f"      ❌ Retain returned success=False")
        sys.exit(1)

except Exception as exc:
    print(f"      ❌ Retain FAILED: {exc}")
    sys.exit(1)

# ── Test 2: Hindsight recall ─────────────────────────────────────────────────
print("\n[2/3] Testing Hindsight recall...")

try:
    recall_resp = client.recall(
        bank_id=HINDSIGHT_BANK_ID,
        query="database connection pool exhausted payments",
        max_tokens=1024,
        budget="low",
    )

    results = recall_resp.results
    print(f"      ✅ Recall succeeded! Results returned: {len(results)}")
    if results:
        print(f"      First result (truncated): {results[0].text[:120]}...")
    else:
        print(f"      ⚠️  No results yet (memory may need a moment to index)")

except Exception as exc:
    print(f"      ❌ Recall FAILED: {exc}")
    sys.exit(1)

# ── Test 3: Groq chat call ──────────────────────────────────────────────────
print("\n[3/3] Testing Groq chat call...")

from config import GROQ_PRIMARY_MODEL, GROQ_FALLBACK_MODEL

try:
    from groq import Groq

    groq_client = Groq(api_key=GROQ_API_KEY)

    model_used = None
    for model in [GROQ_PRIMARY_MODEL, GROQ_FALLBACK_MODEL]:
        try:
            print(f"      Trying model: {model}")
            resp = groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": "Say 'IncidentMind is ready' and nothing else."}
                ],
                max_tokens=20,
            )
            answer = resp.choices[0].message.content
            model_used = model
            print(f"      ✅ Groq succeeded with {model}")
            print(f"      Response: {answer}")
            break
        except Exception as model_exc:
            print(f"      ⚠️  {model} failed: {model_exc}")

    if model_used is None:
        print("      ❌ Both Groq models failed")
        sys.exit(1)

except Exception as exc:
    print(f"      ❌ Groq FAILED: {exc}")
    sys.exit(1)

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("✅ ALL TESTS PASSED — IncidentMind is ready to run!")
print("=" * 60)
print()
print("Next steps:")
print("  python seed.py      # Load 15 demo incidents into Hindsight")
print("  streamlit run app.py  # Launch the UI")
