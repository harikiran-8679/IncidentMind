"""
app.py — IncidentMind Streamlit UI

Dark, premium, memory-first interface for on-call incident response.
Memory is the star: all UI panels showcase what Hindsight recalled.
"""

import time
import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="IncidentMind — AI Incident Response",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS / Theme ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ─── Base theme ─── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ─── Background + main surface ─── */
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1526 50%, #0a0e1a 100%);
    color: #e2e8f0;
}

/* ─── Sidebar ─── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1629 0%, #111827 100%);
    border-right: 1px solid #1e293b;
}

/* ─── Headers ─── */
h1 { 
    background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700;
    font-size: 2rem !important;
}
h2, h3 { color: #93c5fd; font-weight: 600; }
h4 { color: #c4b5fd; font-weight: 500; }

/* ─── Text areas + inputs ─── */
.stTextArea textarea {
    background: #0f172a !important;
    color: #e2e8f0 !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
}
.stTextArea textarea:focus {
    border-color: #60a5fa !important;
    box-shadow: 0 0 0 2px rgba(96,165,250,0.2) !important;
}

/* ─── Buttons ─── */
.stButton > button {
    background: linear-gradient(135deg, #1e40af, #7c3aed) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(96,165,250,0.35) !important;
}

/* ─── Metric cards ─── */
[data-testid="metric-container"] {
    background: #0f172a !important;
    border: 1px solid #1e293b !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}

/* ─── Expanders ─── */
.streamlit-expanderHeader {
    background: #0f172a !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px !important;
    color: #93c5fd !important;
}

/* ─── Alerts / info boxes ─── */
.stAlert {
    border-radius: 8px !important;
    border-left: 4px solid !important;
}

/* ─── Dividers ─── */
hr { border-color: #1e293b !important; }

/* ─── Code blocks ─── */
code, .stCode {
    background: #0f172a !important;
    color: #86efac !important;
    font-family: 'JetBrains Mono', monospace !important;
}

/* ─── Toggle ─── */
[data-testid="stToggle"] { accent-color: #60a5fa; }

/* ─── Custom memory card ─── */
.memory-card {
    background: linear-gradient(135deg, #0f172a, #111827);
    border: 1px solid #1e3a5f;
    border-left: 4px solid #3b82f6;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 8px 0;
    transition: border-color 0.2s;
}
.memory-card:hover { border-left-color: #60a5fa; }
.memory-card.outcome-worked { border-left-color: #22c55e; }
.memory-card.outcome-failed { border-left-color: #ef4444; }
.memory-card.outcome-pending { border-left-color: #f59e0b; }

/* ─── Analysis box ─── */
.analysis-box {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px;
}

/* ─── Pill badges ─── */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    margin: 2px;
}
.badge-blue { background: #1e3a5f; color: #93c5fd; }
.badge-green { background: #14532d; color: #86efac; }
.badge-red { background: #7f1d1d; color: #fca5a5; }
.badge-yellow { background: #78350f; color: #fde68a; }
.badge-purple { background: #3b0764; color: #d8b4fe; }

/* ─── Toggle bar for Memory ON/OFF ─── */
.memory-toggle-on {
    background: linear-gradient(90deg, #1e3a5f, #1e293b);
    border: 2px solid #3b82f6;
    border-radius: 10px;
    padding: 10px 16px;
    text-align: center;
    font-weight: 700;
    color: #60a5fa;
    font-size: 1rem;
}
.memory-toggle-off {
    background: #1a1a2e;
    border: 2px solid #4b5563;
    border-radius: 10px;
    padding: 10px 16px;
    text-align: center;
    font-weight: 700;
    color: #9ca3af;
    font-size: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ── Imports (after page config) ───────────────────────────────────────────────
from config import DEMO_INCIDENTS, HINDSIGHT_BANK_ID
from memory import (
    recall_all_context,
    retain_incident,
    retain_outcome,
    get_memory_stats,
)
from agent import analyze_incident, synthesize_learnings

# ── Session state defaults ────────────────────────────────────────────────────
if "memory_on" not in st.session_state:
    st.session_state.memory_on = True
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None
# incident_input is the canonical widget key — initialise only if absent
if "incident_input" not in st.session_state:
    st.session_state.incident_input = ""
if "recalled_memories" not in st.session_state:
    st.session_state.recalled_memories = {"incidents": [], "outcomes": []}
if "save_form" not in st.session_state:
    st.session_state.save_form = {"service": "", "root_cause": "", "fix_applied": "", "time_min": 30}
if "prev_memory_on" not in st.session_state:
    st.session_state.prev_memory_on = st.session_state.memory_on


# ── Helper: detect service from incident text ────────────────────────────────
KNOWN_SERVICES = ["payments-api", "auth-service", "checkout-db", "order-queue", "search-indexer"]

def detect_service(text: str) -> str:
    """Return the first known service name found in text, or 'payments-api'."""
    lower = text.lower()
    for svc in KNOWN_SERVICES:
        if svc in lower:
            return svc
    return "payments-api"


# ── Helper: urgency badge ─────────────────────────────────────────────────────
URGENCY_COLORS = {"P0": "badge-red", "P1": "badge-yellow", "P2": "badge-blue", "P3": "badge-green"}

def urgency_badge(level: str) -> str:
    cls = URGENCY_COLORS.get(level, "badge-blue")
    return f'<span class="badge {cls}">{level}</span>'


def outcome_badge(outcome: str) -> str:
    mapping = {"worked": "badge-green ✓", "failed": "badge-red ✗", "pending": "badge-yellow ?"}
    text, cls = (outcome, "badge-blue")
    for k, v in mapping.items():
        if k in outcome.lower():
            parts = v.split(" ")
            cls = parts[0]
            text = outcome + " " + parts[1] if len(parts) > 1 else outcome
            break
    return f'<span class="badge {cls}">{text}</span>'


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 IncidentMind")
    st.markdown(f"<small style='color:#475569'>Bank: `{HINDSIGHT_BANK_ID}`</small>", unsafe_allow_html=True)
    st.divider()

    # Memory stats
    st.markdown("### 📊 Memory Stats")
    with st.spinner("Loading stats..."):
        stats = get_memory_stats()

    col1, col2 = st.columns(2)
    col1.metric("Memories", stats.get("total_memories", "—"))
    col2.metric("Fix Success Rate",
                f"{stats.get('success_rate', 0) or 0}%" if stats.get("success_rate") else "—")

    fixes_w = stats.get("fixes_worked", 0)
    fixes_f = stats.get("fixes_failed", 0)
    # Only show progress bar if we have valid numeric counts
    if isinstance(fixes_w, int) and isinstance(fixes_f, int) and (fixes_w + fixes_f) > 0:
        st.progress(fixes_w / (fixes_w + fixes_f), text=f"✓ {fixes_w} worked  ✗ {fixes_f} failed")
    else:
        st.caption(f"✓ {fixes_w} worked  ✗ {fixes_f} failed")

    st.divider()

    # What the agent has learned
    st.markdown("### 💡 What the Agent Has Learned")
    recalled = st.session_state.recalled_memories
    all_mems = recalled.get("incidents", []) + recalled.get("outcomes", [])

    if all_mems:
        with st.spinner("Synthesising patterns..."):
            learnings = synthesize_learnings(all_mems)
        st.markdown(learnings)
    else:
        st.caption("_Run an analysis to see learnings._")

    st.divider()

    # Quick tips
    st.markdown("### 🎯 Demo Tips")
    st.markdown("""
- Toggle **Memory OFF** then **ON** on the same incident to see the difference  
- Use the **Demo Incidents** buttons for a one-click demo  
- After resolving, click **Fix Worked / Failed** to teach the agent  
""")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("# 🧠 IncidentMind")
st.markdown("**AI-powered on-call response that learns from every incident via Hindsight memory**")
st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# MEMORY TOGGLE + DEMO INCIDENTS — top bar
# ─────────────────────────────────────────────────────────────────────────────
top_left, top_right = st.columns([3, 5])

with top_left:
    memory_on = st.toggle(
        "🧠 Memory ON",
        value=st.session_state.memory_on,
        help="When ON, the agent recalls similar past incidents from Hindsight BEFORE calling the LLM.",
        key="memory_toggle",
    )

    # Detect toggle flip → clear last_analysis so stale results aren't shown
    if memory_on != st.session_state.prev_memory_on:
        st.session_state.last_analysis = None
        st.session_state.recalled_memories = {"incidents": [], "outcomes": []}
        st.session_state.prev_memory_on = memory_on

    st.session_state.memory_on = memory_on

    if memory_on:
        st.markdown(
            '<div class="memory-toggle-on">🧠 HINDSIGHT MEMORY: ACTIVE</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="memory-toggle-off">⚫ MEMORY: OFF — Generic Mode (no past incidents, confidence ≤ 40%)</div>',
            unsafe_allow_html=True,
        )

with top_right:
    st.markdown("**🎬 One-click Demo Incidents:**")
    demo_cols = st.columns(len(DEMO_INCIDENTS))
    for i, demo in enumerate(DEMO_INCIDENTS):
        with demo_cols[i]:
            if st.button(demo["label"], key=f"demo_{i}", use_container_width=True):
                # Write directly to the widget's own key so the text_area
                # picks up the value on the very next script run.
                st.session_state.incident_input = demo["text"]
                st.rerun()

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# INCIDENT INPUT
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### 📋 Paste Incident Alert + Error Log")

# Apply any pending clear BEFORE the widget is instantiated so Streamlit
# doesn't raise WidgetAlreadyInstantiatedError.
if st.session_state.pop("_clear_pending", False):
    st.session_state.incident_input = ""
    st.session_state.last_analysis = None
    st.session_state.recalled_memories = {"incidents": [], "outcomes": []}

incident_text = st.text_area(
    "Incident",
    height=220,
    placeholder=(
        "Paste your alert + error log here...\n\n"
        "Example:\n"
        "ALERT: payments-api P0 — 98% of requests timing out\n"
        "ERROR [payments-api] Connection pool exhausted: max_connections=100\n"
        "ERROR [payments-api] PSQLException: FATAL: remaining connection slots reserved\n"
        "Metrics: latency_p99=28s, active_connections=100, queue_depth=342"
    ),
    label_visibility="collapsed",
    key="incident_input",
)
# incident_text reflects whatever is in the widget — no write-back needed;
# Streamlit keeps st.session_state.incident_input in sync automatically.

analyze_col, clear_col, _ = st.columns([2, 1, 5])

with analyze_col:
    analyze_clicked = st.button(
        "🔍 Analyze Incident",
        type="primary",
        use_container_width=True,
        disabled=not incident_text.strip(),
    )

with clear_col:
    if st.button("🗑️ Clear", use_container_width=True):
        # Set a flag; the actual clear happens BEFORE the text_area
        # on the next script run to avoid WidgetAlreadyInstantiatedError.
        st.session_state._clear_pending = True
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS — runs when button clicked
# ─────────────────────────────────────────────────────────────────────────────
if analyze_clicked and incident_text.strip():
    progress = st.progress(0, text="Starting analysis...")

    # Step 1: Recall from Hindsight
    recalled = {"incidents": [], "outcomes": []}
    if st.session_state.memory_on:
        progress.progress(20, text="🧠 Querying Hindsight memory...")
        service_hint = detect_service(incident_text)
        recalled = recall_all_context(incident_text, service=service_hint)
        st.session_state.recalled_memories = recalled
    else:
        st.session_state.recalled_memories = {"incidents": [], "outcomes": []}

    progress.progress(50, text="🤖 Calling LLM for analysis...")

    # Step 2: LLM analysis
    start = time.time()
    result = analyze_incident(
        incident_text=incident_text,
        memory_on=st.session_state.memory_on,
        recalled_incidents=recalled.get("incidents", []),
        recalled_outcomes=recalled.get("outcomes", []),
    )
    elapsed = time.time() - start

    progress.progress(90, text="Rendering results...")
    st.session_state.last_analysis = result
    st.session_state.analysis_time = elapsed

    # Pre-fill the save form with detected service and analysis results
    st.session_state.save_form = {
        "service": detect_service(incident_text),
        "root_cause": result.get("likely_root_cause", ""),
        "fix_applied": (
            result.get("fix_steps", [{}])[0].get("step", "")
            if result.get("fix_steps") else ""
        ),
        "time_min": result.get("estimated_resolution_min", 30),
    }

    progress.progress(100, text="Done!")
    time.sleep(0.3)
    progress.empty()

# ─────────────────────────────────────────────────────────────────────────────
# RESULTS DISPLAY
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.last_analysis:
    result = st.session_state.last_analysis
    recalled = st.session_state.recalled_memories

    # If memory was used, show the dual-column layout
    if st.session_state.memory_on and (recalled.get("incidents") or recalled.get("outcomes")):
        left_col, right_col = st.columns([5, 4])
    else:
        left_col = st.container()
        right_col = None

    # ── LEFT: Analysis Results ────────────────────────────────────────────
    with left_col:
        total_inc = len(recalled.get("incidents", []))
        total_out = len(recalled.get("outcomes", []))

        if st.session_state.memory_on and (total_inc + total_out) > 0:
            memory_label = f"🧠 Memory-Powered Analysis ({total_inc} incidents + {total_out} outcome records recalled)"
        elif st.session_state.memory_on:
            memory_label = "🧠 Memory-Powered Analysis (no similar incidents found)"
        else:
            memory_label = "⚫ Generic Analysis — Memory OFF (no past incidents, confidence ≤ 40%)"

        st.markdown(f"### {memory_label}")

        if "error" in result and "likely_root_cause" not in result:
            st.error(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        else:
            # ── Urgency + model badge ────────────────────────────────────
            urgency = result.get("urgency", "P2")
            model = result.get("model_used", "unknown")
            confidence = result.get("confidence", 0)
            elapsed = st.session_state.get("analysis_time", 0)

            header_cols = st.columns(4)
            header_cols[0].metric("Urgency", urgency)
            header_cols[1].metric("Confidence", f"{confidence}%")
            header_cols[2].metric("Est. Resolution", f"{result.get('estimated_resolution_min', '?')} min")
            header_cols[3].metric("Analysis Time", f"{elapsed:.1f}s")

            st.markdown(f"<small>Model: `{model}`</small>", unsafe_allow_html=True)
            st.divider()

            # ── Root Cause ───────────────────────────────────────────────
            st.markdown("#### 🔍 Root Cause")
            root_cause = result.get("likely_root_cause", "Could not determine root cause")
            st.markdown(
                f'<div class="analysis-box"><strong>{root_cause}</strong></div>',
                unsafe_allow_html=True,
            )

            # ── Memory summary ───────────────────────────────────────────
            if result.get("memory_summary"):
                st.markdown("#### 🧠 Memory Insight")
                st.info(result["memory_summary"])

            # ── Fix steps ────────────────────────────────────────────────
            st.markdown("#### 🔧 Ranked Fix Steps")
            fix_steps = result.get("fix_steps", [])
            if fix_steps:
                for step in fix_steps:
                    rank = step.get("rank", "?")
                    s = step.get("step", "")
                    rationale = step.get("rationale", "")
                    backed = step.get("memory_backed", False)
                    refs = step.get("incident_refs", [])
                    refs_txt = ", ".join(refs) if refs else ""

                    backed_badge = (
                        '<span class="badge badge-green">✓ Memory-backed</span>'
                        if backed
                        else '<span class="badge badge-purple">💡 LLM-inferred</span>'
                    )
                    refs_badge = (
                        f'<span class="badge badge-blue">📎 {refs_txt}</span>'
                        if refs_txt
                        else ""
                    )

                    st.markdown(
                        f"""
<div class="memory-card">
  <strong>#{rank} — {s}</strong><br>
  <small style="color:#94a3b8">{rationale}</small><br>
  {backed_badge} {refs_badge}
</div>""",
                        unsafe_allow_html=True,
                    )
            else:
                st.warning("No fix steps generated.")

            # ── Skipped fixes ────────────────────────────────────────────
            skipped = result.get("skipped_fixes", [])
            if skipped:
                st.markdown("#### ⚠️ Skipped Fixes (Failed Before)")
                for sf in skipped:
                    st.markdown(
                        f'<div class="memory-card outcome-failed">'
                        f'<span class="badge badge-red">✗ SKIPPED</span> '
                        f'<strong>{sf.get("fix", "")}</strong><br>'
                        f'<small style="color:#94a3b8">{sf.get("reason", "")}</small>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    # ── RIGHT: Recalled Memories Panel ───────────────────────────────────
    if right_col:
        with right_col:
            total_recalled = len(recalled.get("incidents", [])) + len(recalled.get("outcomes", []))
            st.markdown(f"### 📚 Recalled {total_recalled} Past Memories")

            if recalled.get("incidents"):
                st.markdown("**Similar Incidents:**")
                for mem in recalled["incidents"]:
                    meta = mem.get("metadata", {})
                    inc_id = meta.get("incident_id", "?")
                    service = meta.get("service", "?")
                    root = meta.get("root_cause", "")[:120]
                    outcome = meta.get("outcome", "pending")
                    # Hide empty/zero relevance scores
                    score = mem.get("score", 0)

                    card_class = f"memory-card outcome-{outcome}"
                    score_badge = (
                        f'<span class="badge badge-blue">rel: {score:.2f}</span>'
                        if score and score > 0
                        else ""
                    )
                    st.markdown(
                        f"""<div class="{card_class}">
  <strong>{inc_id}</strong> — <code>{service}</code>
  {outcome_badge(outcome)}
  {score_badge}<br>
  <small style="color:#94a3b8">{root}</small>
</div>""",
                        unsafe_allow_html=True,
                    )

            if recalled.get("outcomes"):
                # Only render cards that have all three required fields
                valid_outcomes = [
                    m for m in recalled["outcomes"]
                    if (
                        m.get("metadata", {}).get("fix_applied", "").strip()
                        and m.get("metadata", {}).get("service", "").strip()
                        and m.get("metadata", {}).get("incident_id", "").strip()
                    )
                ]
                if valid_outcomes:
                    st.markdown("**Fix Outcomes Learned:**")
                    for mem in valid_outcomes:
                        meta = mem.get("metadata", {})
                        fix = meta["fix_applied"][:80]
                        outcome = meta.get("outcome", "unknown")
                        inc_id = meta["incident_id"]
                        svc = meta["service"]

                        card_class = f"memory-card outcome-{outcome}"
                        emoji = "✅" if outcome == "worked" else "❌" if outcome == "failed" else "⏳"
                        st.markdown(
                            f"""<div class="{card_class}">
  {emoji} <strong>{fix}</strong><br>
  <small style="color:#94a3b8">{inc_id} · <code>{svc}</code></small>
  {outcome_badge(outcome)}
</div>""",
                            unsafe_allow_html=True,
                        )

    # ─── Separator ─────────────────────────────────────────────────────
    st.divider()

    # ─── Action Buttons ─────────────────────────────────────────────────
    st.markdown("### 📝 Record Outcome & Save to Memory")

    action_col1, action_col2, action_col3 = st.columns(3)

    with action_col1:
        if st.button("✅ Fix Worked", use_container_width=True, key="fix_worked"):
            st.session_state.show_save = True
            st.session_state.save_outcome = "worked"

    with action_col2:
        if st.button("❌ Fix Failed", use_container_width=True, key="fix_failed"):
            st.session_state.show_save = True
            st.session_state.save_outcome = "failed"

    with action_col3:
        if st.button("💾 Save Resolved Incident", use_container_width=True, key="save_inc"):
            st.session_state.show_save_incident = True

    # ─── Save Incident Form ──────────────────────────────────────────────
    if st.session_state.get("show_save") or st.session_state.get("show_save_incident"):
        save_outcome_label = st.session_state.get("save_outcome", "pending")
        with st.form("save_incident_form"):
            st.markdown(f"#### Save to Hindsight Memory (Outcome: **{save_outcome_label}**)")

            # Default service to the detected service from the incident text
            prefilled = st.session_state.get("save_form", {})
            default_service = prefilled.get("service") or detect_service(incident_text)

            form_cols = st.columns(2)
            service_input = form_cols[0].text_input("Service name", value=default_service)
            inc_id_input = form_cols[1].text_input("Incident ID", value=f"INC-{int(time.time()) % 10000:04d}")
            root_cause_input = st.text_area(
                "Root cause",
                value=prefilled.get("root_cause") or result.get("likely_root_cause", ""),
                height=80,
            )
            fix_input = st.text_area(
                "Fix applied",
                value=prefilled.get("fix_applied") or (
                    result.get("fix_steps", [{}])[0].get("step", "")
                    if result.get("fix_steps") else ""
                ),
                height=80,
            )
            time_min_input = st.number_input(
                "Resolution time (minutes)",
                min_value=1,
                value=int(prefilled.get("time_min") or 30),
            )

            outcome_val = st.session_state.get("save_outcome", "pending")

            if st.form_submit_button("🧠 Retain to Hindsight", type="primary"):
                with st.spinner("Storing in Hindsight memory..."):
                    # Retain the incident
                    r1 = retain_incident(
                        incident_id=inc_id_input,
                        service=service_input,
                        symptoms=incident_text[:500],
                        error_log=incident_text[:1000],
                        root_cause=root_cause_input,
                        fix_applied=fix_input,
                        time_to_resolve_min=int(time_min_input),
                        outcome=outcome_val,
                    )
                    # Retain the outcome
                    r2 = retain_outcome(
                        incident_id=inc_id_input,
                        service=service_input,
                        root_cause=root_cause_input,
                        fix_applied=fix_input,
                        outcome=outcome_val,
                    )

                if r1["success"] and r2["success"]:
                    st.success(f"✅ Incident {inc_id_input} + outcome retained! Hindsight will use this in future recalls.")
                    st.session_state.show_save = False
                    st.session_state.show_save_incident = False
                else:
                    st.error(f"Partial failure: {r1['message']} | {r2['message']}")

    # ─── Raw output expander ─────────────────────────────────────────────
    with st.expander("🔍 Raw LLM Output"):
        st.code(result.get("raw_text", "No raw output"), language="json")

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    """<div style="text-align:center; color:#475569; font-size:0.8rem">
    🧠 <strong>IncidentMind</strong> · Powered by 
    <a href="https://hindsight.vectorize.io" style="color:#60a5fa">Hindsight</a> memory + 
    <a href="https://groq.com" style="color:#a78bfa">Groq</a> LLM · 
    Built for Hack with Hyderabad 2026
    </div>""",
    unsafe_allow_html=True,
)
