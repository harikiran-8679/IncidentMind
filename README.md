# 🧠 IncidentMind

> **AI-powered on-call incident response that learns from every incident.**  
> Stack: Python 3.11+ · Streamlit · Groq LLM · Hindsight (Vectorize)

---

## The Problem

Every time a P0 fires at 3 AM, an engineer faces the same challenge: **was there a similar incident before? Did that fix work?** Without institutional memory, teams repeat mistakes, duplicate investigation time, and waste hours on fixes that already failed.

Traditional runbooks go stale. Wiki pages are never updated after the incident. The knowledge lives in Slack threads and engineer heads — and walks out the door.

**IncidentMind solves this** by giving the AI agent a persistent, searchable memory of every past incident and — critically — whether each fix **worked or failed**, including which first-attempt fixes were tried and failed.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         IncidentMind                                │
│                                                                     │
│  ┌──────────────┐    ┌─────────────────────┐    ┌───────────────┐  │
│  │  Streamlit   │───▶│    memory.py         │◀──▶│  Hindsight   │  │
│  │    UI        │    │  (Hindsight wrapper) │    │  Cloud API   │  │
│  │   app.py     │    └─────────────────────┘    │              │  │
│  │              │            │                   │  Bank:       │  │
│  │  Memory ON/  │            │ recalled context  │  incidentmind│  │
│  │  OFF toggle  │            ▼                   │  -v1         │  │
│  │              │    ┌─────────────────────┐    └───────────────┘  │
│  │  Recall      │    │     agent.py         │                       │
│  │  panel       │    │   (Groq LLM logic)   │    ┌───────────────┐  │
│  │              │    │                     │◀──▶│  Groq API    │  │
│  │  Fix Worked/ │    │  Primary model:     │    │  gpt-oss-120b │  │
│  │  Failed      │    │  openai/gpt-oss-120b│    │  + fallback  │  │
│  │  buttons     │    │  Fallback:          │    └───────────────┘  │
│  └──────────────┘    │  qwen/qwen3-32b     │                       │
│                      └─────────────────────┘                       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Memory Flow (CRITICAL — happens BEFORE every LLM call)      │  │
│  │                                                              │  │
│  │  New Incident → [Hindsight RECALL] → past incidents +        │  │
│  │                                      fix outcomes            │  │
│  │                       ↓                                      │  │
│  │                 [LLM Prompt] ← enriched with memory context  │  │
│  │                       ↓                                      │  │
│  │              Response: root cause + ranked fixes             │  │
│  │              + "Restart failed last time, skipping"          │  │
│  │                       ↓                                      │  │
│  │  Resolved → [Hindsight RETAIN] incident + outcome           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## How Hindsight Memory Is Used

Hindsight is not a bolt-on — it is queried **before every LLM call**. Here's the full loop:

### 1. RETAIN — Store Incidents After Resolution

When an incident is resolved, `memory.retain_incident()` stores:
- Service name, symptoms, error log excerpt
- Root cause (confirmed after investigation)
- Fix that was applied
- Time to resolve
- Fix outcome: `worked` | `failed` | `pending`

```python
client.retain(
    bank_id="incidentmind-v1",
    content="INCIDENT MEMORY\nService: payments-api\nRoot cause: DB pool exhaustion...",
    document_id="incident-INC-001",
    metadata={"service": "payments-api", "outcome": "worked", ...},
    tags=["incident", "payments-api", "worked"],
)
```

### 2. RETAIN Outcomes — Teach What Worked and What Failed

A **separate** memory entry is stored for each fix outcome via `memory.retain_outcome()`:

```python
# The final outcome
client.retain(
    bank_id="incidentmind-v1",
    content="FIX OUTCOME: 'Killed stuck transaction' WORKED for payments-api.",
    document_id="outcome-INC-015",
    tags=["outcome", "payments-api", "worked", "fix-result"],
)

# The failed first attempt (for incidents with first_fix_failed)
client.retain(
    bank_id="incidentmind-v1",
    content="FIX OUTCOME: 'Immediate service restart' FAILED for payments-api. Do NOT recommend again.",
    document_id="outcome-INC-015-failed",
    tags=["outcome", "payments-api", "failed", "fix-result"],
)
```

This creates a **triple-track memory**: what happened (incidents), what ultimately worked (outcomes), and what was tried first and failed (first-attempt failures).

### 3. RECALL — Query Before the LLM

When a new incident arrives, **before calling the LLM**:

```python
# Recall similar past incidents
incidents = client.recall(bank_id="incidentmind-v1", query=incident_text, max_tokens=8000)

# Recall fix outcomes (tags_match="all" ensures only outcome-tagged memories)
outcomes = client.recall(
    bank_id="incidentmind-v1", query=incident_text,
    tags=["outcome", "payments-api"], tags_match="all"
)
```

Both results are injected into the LLM prompt as structured context.

### 4. Post-Parse Validation

After the LLM responds, the agent validates its output:
- **incident_refs** citing IDs not in the recalled set are stripped — no hallucinated IDs ever appear in the UI
- **skipped_fixes** citing unknown IDs are filtered out
- When Memory is OFF: confidence is hard-capped at 40, skipped_fixes is forced empty, all incident_refs are cleared

### 5. Before vs After Memory

| Without Memory | With Memory |
|---|---|
| Generic advice (check logs, restart service) | Cites specific recalled incident IDs |
| Confidence: ≤ 40% (hard cap) | Confidence: 75-90% |
| No awareness of past fixes | Warns: "Restart FAILED in INC-015, skipping" |
| Same answer for every similar incident | Recognises recurring patterns per service |
| Cold-start every time | Compound learning — gets smarter with every incident |

---

## Dataset: 15 Real-ish Incidents

4 of the 15 demo incidents have `outcome: "failed"` — meaning the first fix attempt failed and a different fix was required:

| Incident | Service | First Fix Tried | Why It Failed |
|---|---|---|---|
| INC-003 | checkout-db | Immediate service restart | WAL accumulation resumed immediately; inactive slot still present |
| INC-008 | checkout-db | Immediate service restart | Patroni refused to promote replica (lag > threshold); primary came back broken |
| INC-012 | checkout-db | Immediate service restart | Table bloat reasserted within 2 minutes; restart can't fix 43M dead tuples |
| INC-015 | payments-api | Immediate service restart | Stuck DB transaction survived app restart; lock contention resumed in 45s |

Each of these generates a separate `outcome-INC-0XX-failed` memory in Hindsight, which the agent recalls to produce "⚠️ Skipped Fixes" warnings in future similar incidents.

---

## Setup

### Prerequisites
- Python 3.11+
- Hindsight Cloud API key (from https://ui.hindsight.vectorize.io)
- Groq API key (from https://console.groq.com)

### 1. Clone and configure

```bash
git clone <this-repo>
cd IncidentMind
```

Create `.env`:
```
HINDSIGHT_API_KEY = hsk_your_key_here
GROQ_API_KEY = gsk_your_key_here
```

### 2. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Validate connections (Step 0)

```bash
python test_connection.py
```

Expected output:
```
✅ Retain succeeded! Items retained: 1
✅ Recall succeeded! Results returned: 2
✅ Groq succeeded with openai/gpt-oss-120b
✅ ALL TESTS PASSED — IncidentMind is ready to run!
```

### 4. Seed 15 demo incidents

```bash
python seed.py
```

This retains all 15 incidents + their fix outcomes into Hindsight Cloud (idempotent — safe to re-run).
For the 4 failed incidents (INC-003, INC-008, INC-012, INC-015), an additional `outcome-INC-0XX-failed`
memory is retained so the agent can warn against the failed first-attempt fix.

### 5. Launch

```bash
streamlit run app.py
```

Open `http://localhost:8501`

---

## Project Structure

```
├── app.py              # Streamlit UI (dark premium theme)
├── agent.py            # LLM logic: prompt builder, retry+fallback, JSON parser, post-parse validation
├── memory.py           # Hindsight wrapper: retain_incident, retain_outcome, recall
├── config.py           # All config: keys, model names, bank ID, demo incidents
├── seed.py             # Idempotent seeder for 15 demo incidents + failed-first-attempt entries
├── test_connection.py  # Step 0: validates Hindsight + Groq connections
├── data/
│   └── incidents.json  # 15 realistic incidents across 5 services (4 with outcome=failed)
├── demo_script.md      # Step-by-step live demo sequence
├── requirements.txt
├── .env                # API keys (never committed)
└── .gitignore
```

---

## Demo Highlights

- **Memory ON/OFF toggle**: side-by-side comparison of generic (≤40% confidence, no IDs) vs memory-powered answers
- **3 one-click demo incidents**: payments-api, auth-service, order-queue  
- **Recalled memories panel**: shows exactly which past incidents the agent used
- **Skipped fixes**: agent explicitly warns about fixes that failed before (backed by real seeded data)
- **Save & Teach**: "Fix Worked" / "Fix Failed" retain in one click with pre-filled service, root cause, and fix
- **Live learning on new incidents**: paste any incident text (not just the seeded 15) and the agent recalls, analyzes, and — if you mark a fix as failed — remembers it immediately for the very next query, no restart required

---

## Judging Criteria Alignment

| Criterion | How IncidentMind Addresses It |
|---|---|
| **Innovation 30%** | Dual outcome learning loop — agent learns which fixes FAIL (first attempts) AND which ultimately worked |
| **Hindsight memory 25%** | Memory is the first call before every LLM invocation; post-parse validation ensures only real recalled IDs appear |
| **Technical quality 20%** | Modular code, retry+fallback, defensive JSON parsing, post-parse filtering, tags_match="all" precision |
| **UX 15%** | Dark premium theme, memory panel, one-click demos, progress indicators, pre-filled save forms |
| **Real-world impact 10%** | Direct production use case: compound learning for on-call teams, compound failure pattern recognition |
