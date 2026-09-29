# IncidentMind — Live Demo Script

**Purpose:** Step-by-step sequence showing the agent evolving from a generic chatbot to a memory-expert, live in 5 minutes.

---

## Pre-Demo Checklist

```bash
source venv/bin/activate
python seed.py          # must complete first — seeds 15 incidents + failed-first-attempt entries
streamlit run app.py    # open http://localhost:8501
```

---

## Act 1 — Cold Start (Memory OFF)

**Goal:** Show what the agent looks like WITHOUT memory. Generic, uncertain, no incident history.

1. Open `http://localhost:8501`
2. Toggle **Memory OFF** (switch at top left) — banner shows "⚫ MEMORY: OFF — Generic Mode"
3. Click **🔴 payments-api Timeout Storm** demo button
4. Click **🔍 Analyze Incident**

**Expected output:**
- Confidence: ≤ 40% (hard cap enforced)
- Root cause: Generic "possible database issue or network problem"
- Fix steps: Standard textbook advice (restart service, check logs, increase timeout)
- **No cited incident IDs** (stripped by post-parse validation)
- **No skipped fixes** (enforced to empty when Memory OFF)
- Memory summary: "Memory is OFF — generic cold-start analysis, no past incidents recalled."
- Heading: "⚫ Generic Analysis — Memory OFF (no past incidents, confidence ≤ 40%)"

**Say to audience:** *"Without memory, this is just a generic chatbot. Every engineer already knows to check the logs. Notice: confidence is capped at 40%, no incident history, no learning."*

---

## Act 2 — Memory ON, First Incident

**Goal:** Show memory turning on and finding strong matches.

1. Toggle **Memory ON** — toggling automatically clears the previous result
2. Use the same **🔴 payments-api Timeout Storm** incident text
3. Click **🔍 Analyze Incident**

**Expected output:**
- Recalled memories panel appears on the right
- 2-3 incidents recalled (INC-001, INC-010 — pool exhaustion; INC-015 — pool exhaustion + lock contention, **outcome: failed**)
- Confidence: ~70-80%
- Root cause: "Database connection pool exhaustion — likely caused by slow query or lock contention"
- Fix steps marked ✓ Memory-backed with **real** recalled incident refs
- Memory summary: "Recalled 3 similar incidents all showing connection pool exhaustion..."
- **No hallucinated IDs** — post-parse filter removes any ID not in the recalled set

**Say to audience:** *"Now the agent found past incidents with the SAME root cause. Watch the confidence jump from ≤40% to ~75%."*

---

## Act 3 — Outcome Learning ("Failed Fix" Warning)

**Purpose:** Show the agent explicitly skipping a fix that failed before — using real seeded data.

**Data facts (from incidents.json):**
- INC-015 (`payments-api`): outcome=`failed`, `first_fix_failed`="Immediate service restart"
  - Story: restart flushed app-side pool but the stuck DB transaction remained; failure rate climbed back within 45s
- INC-008 (`checkout-db`): outcome=`failed`, `first_fix_failed`="Immediate service restart"
- INC-012 (`checkout-db`): outcome=`failed`, `first_fix_failed`="Immediate service restart"
- INC-003 (`checkout-db`): outcome=`failed`, `first_fix_failed`="Immediate service restart"

Each has a separate `outcome-INC-0XX-failed` memory in Hindsight.

1. Paste this custom incident (or click the **🔴 payments-api Timeout Storm** demo):
```
ALERT: payments-api degraded — 40% of charges failing
Service: payments-api  Time: 2026-09-28T18:00Z

ERROR [payments-api] HikariPool: Connection pool exhausted after 30s wait
ERROR [payments-api] deadlock detected: Process 47281 waits for ShareLock
WARN  [payments-api] Long-running transaction age=842s
Metrics: failure_rate=40%, active_connections=97/100, deadlocks_per_min=8
```

2. Click **🔍 Analyze Incident** (Memory ON)

**Expected output:**
- Skipped Fixes section appears: *"⚠️ Immediate service restart — failed in INC-015-failed, skipping"*
- Recommended fix: `pg_terminate_backend()` + statement_timeout (proven pattern from INC-001/INC-010)
- Confidence: ~80-85%

**Say to audience:** *"The agent remembered that a simple restart FAILED last time for this exact pattern, and skipped it. That's the Hindsight outcome-failed memory in action."*

---

## Act 4 — Expert Mode (Incident 12)

**Purpose:** Show the agent at its best — finding the checkout-db autovacuum pattern (INC-012) and also recalling its failed first attempt.

1. Paste this incident:
```
ALERT: checkout-db — Write latency degraded to 9s+, service degraded
Service: checkout-db  Time: 2026-09-28T20:00Z

WARN  [checkout-db] autovacuum blocked on table: orders
WARN  [checkout-db] table bloat ratio: orders=91%
ERROR [checkout-service] UPDATE orders SET status=? took 9100ms
ERROR [checkout-service] Deadlock on orders table — 12 concurrent updates
INFO  [checkout-db] seq_scan: 5100/hour on 850GB table (expected: 0)
Metrics: write_latency_p99=9100ms, seq_scans=5100/hr, disk_pct=56
```

2. Click **🔍 Analyze Incident**

**Expected output:**
- Recalled: INC-012 (table bloat, **outcome: failed** — restart didn't help), INC-003 (replication, **outcome: failed**), INC-008 (disk/failover, **outcome: failed**)
- Memory insight: "checkout-db incidents frequently fail on the first attempt (service restart) — root cause must be addressed at DB layer"
- Skipped fix: "Immediate service restart — failed in INC-012, INC-008, INC-003"
- Root cause: "Autovacuum blocked/disabled causing dead tuple accumulation and sequential scans"
- Fix: `VACUUM ANALYZE orders`, `pg_repack` — all memory-backed from INC-012

**Say to audience:** *"Three checkout-db incidents all show the same pattern: service restarts fail because the root cause is at the DB layer. The agent skips the restart and goes straight to VACUUM ANALYZE."*

---

## Act 5 — "Fix Failed" in One Click

**Purpose:** Show the one-click Fix Failed → retain flow.

1. After any analysis (e.g. the checkout-db incident above), click **❌ Fix Failed**
2. The form opens with:
   - **Service** pre-filled to `checkout-db` (auto-detected from incident text)
   - **Root cause** pre-filled from the analysis
   - **Fix applied** pre-filled from the top-ranked fix step
3. Adjust the fix text if needed, click **🧠 Retain to Hindsight**
4. Watch the sidebar memory count increase

**Say to audience:** *"One click. The failed outcome is now in memory. The next engineer working a checkout-db incident will see this as a ✗ SKIPPED fix."*

---

## Act 6 — Save & Teach (Fix Worked)

1. After any analysis, click **✅ Fix Worked**
2. Form pre-fills service, root cause, and fix from the analysis
3. Click **🧠 Retain to Hindsight**

**Say to audience:** *"Every resolved incident makes the next engineer faster. This is compound learning."*

---

## Key Talking Points

| Without Memory | With Memory |
|---|---|
| Generic advice | Cites real past incident IDs |
| ≤ 40% confidence (hard cap) | 75-90% confidence |
| No skipped fixes | Warns about proven failures |
| Same answer every time | Learns from every incident |
| Treats each incident fresh | Recognises recurring patterns |

---

## Architecture (show the diagram in README.md)

The key differentiator: **Hindsight is queried BEFORE the LLM**, not as an afterthought.

```
Incident → [Hindsight Recall] → [Memory Context] → [Groq LLM] → Response
                                        ↑
                              Past incidents + fix outcomes
                              + failed-first-attempt entries
```
