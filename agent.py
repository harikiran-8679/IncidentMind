"""
agent.py — LLM reasoning layer for IncidentMind.

Builds prompts enriched with Hindsight memory (recalled incidents +
fix outcomes) and calls Groq with retry + fallback logic.

The LLM NEVER runs without first consulting memory when memory is ON.
Output schema is parsed defensively; malformed JSON falls back to raw text.

Post-parse validation:
  • incident_refs and skipped_fixes citing IDs not in recalled memories
    are stripped out — so the UI never shows hallucinated incident IDs.
  • When memory is OFF: no recall, no incident IDs, confidence capped at 40.
"""

import json
import logging
import time
from typing import Any

from groq import Groq, RateLimitError, APIConnectionError, APIStatusError

from config import (
    GROQ_API_KEY,
    GROQ_PRIMARY_MODEL,
    GROQ_FALLBACK_MODEL,
    GROQ_MAX_TOKENS,
    GROQ_TEMPERATURE,
    GROQ_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groq client singleton
# ---------------------------------------------------------------------------

def _get_groq_client() -> Groq:
    return Groq(api_key=GROQ_API_KEY)


# ---------------------------------------------------------------------------
# Core LLM call with retry + fallback
# ---------------------------------------------------------------------------

def _call_llm(
    messages: list[dict],
    model: str,
    max_retries: int = GROQ_MAX_RETRIES,
) -> str | None:
    """
    Call Groq LLM. Retries on transient errors; returns None on hard failure.
    """
    client = _get_groq_client()
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=GROQ_MAX_TOKENS,
                temperature=GROQ_TEMPERATURE,
            )
            return resp.choices[0].message.content
        except RateLimitError as exc:
            logger.warning("Rate limit on attempt %d: %s", attempt, exc)
            if attempt < max_retries:
                time.sleep(2 ** attempt)  # exponential back-off
        except APIConnectionError as exc:
            logger.warning("Connection error on attempt %d: %s", attempt, exc)
            if attempt < max_retries:
                time.sleep(1)
        except APIStatusError as exc:
            logger.error("API status error (model=%s): %s", model, exc)
            return None  # Don't retry auth / model-not-found errors
        except Exception as exc:
            logger.error("Unexpected error on attempt %d: %s", attempt, exc)
            if attempt < max_retries:
                time.sleep(1)
    return None


def _call_with_fallback(messages: list[dict]) -> tuple[str | None, str]:
    """
    Try primary model first; fall back to secondary on failure.
    Returns (content, model_used).
    """
    result = _call_llm(messages, GROQ_PRIMARY_MODEL)
    if result is not None:
        return result, GROQ_PRIMARY_MODEL

    logger.warning("Primary model failed; trying fallback %s", GROQ_FALLBACK_MODEL)
    result = _call_llm(messages, GROQ_FALLBACK_MODEL)
    if result is not None:
        return result, GROQ_FALLBACK_MODEL

    return None, "none"


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_memory_context(
    recalled_incidents: list[dict],
    recalled_outcomes: list[dict],
) -> str:
    """
    Format Hindsight memories into a structured context block for the LLM.
    Explicitly calls out failed fixes so the LLM can warn against them.
    """
    if not recalled_incidents and not recalled_outcomes:
        return "No relevant past incidents found"

    lines = ["=== HINDSIGHT MEMORY CONTEXT ===\n"]

    if recalled_incidents:
        lines.append(f"### {len(recalled_incidents)} Similar Past Incidents:\n")
        for i, mem in enumerate(recalled_incidents, 1):
            meta = mem.get("metadata", {})
            inc_id = meta.get("incident_id", mem.get("document_id", f"MEM-{i}"))
            service = meta.get("service", "unknown")
            root_cause = meta.get("root_cause", "unknown")
            fix = meta.get("fix_applied", "unknown")
            outcome = meta.get("outcome", "unknown")

            lines.append(
                f"[{i}] Incident {inc_id}\n"
                f"    Service: {service}\n"
                f"    Root cause: {root_cause}\n"
                f"    Fix applied: {fix}\n"
                f"    Outcome: {outcome}\n"
                f"    Memory text: {mem.get('text', '')[:400]}...\n"
            )

    if recalled_outcomes:
        lines.append(f"\n### {len(recalled_outcomes)} Fix Outcome Records:\n")
        failed_fixes = []
        worked_fixes = []

        for out in recalled_outcomes:
            meta = out.get("metadata", {})
            outcome = meta.get("outcome", "unknown")
            fix = meta.get("fix_applied", "unknown")
            svc = meta.get("service", "unknown")
            inc_id = meta.get("incident_id", "?")

            if outcome == "failed":
                failed_fixes.append(f"    ✗ '{fix}' FAILED for {svc} (incident {inc_id})")
            elif outcome == "worked":
                worked_fixes.append(f"    ✓ '{fix}' WORKED for {svc} (incident {inc_id})")

        if worked_fixes:
            lines.append("FIXES THAT WORKED:\n" + "\n".join(worked_fixes))
        if failed_fixes:
            lines.append("\nFIXES THAT FAILED (do NOT recommend these):\n" + "\n".join(failed_fixes))

    lines.append("\n=== END MEMORY CONTEXT ===\n")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are IncidentMind, an elite on-call incident response AI.
You analyze incidents using your memory of past incidents and fix outcomes.

CRITICAL RULES:
1. Always cite the past incident IDs that informed your analysis.
2. If memory shows a fix FAILED before, explicitly say "⚠️ [fix] failed in incident [ID], skipping."
3. If memory shows a fix WORKED, boost its rank and say "✓ Proven fix from incident [ID]."
4. Your confidence score (0-100) must reflect how many similar memories you found.
5. Without memory context, you must note that this is a cold-start analysis.

REQUIRED OUTPUT FORMAT (valid JSON only, no markdown code blocks):
{
  "likely_root_cause": "concise one-sentence root cause",
  "confidence": 85,
  "fix_steps": [
    {"rank": 1, "step": "description", "rationale": "why", "memory_backed": true, "incident_refs": ["INC-001"]},
    {"rank": 2, "step": "description", "rationale": "why", "memory_backed": false, "incident_refs": []}
  ],
  "skipped_fixes": [
    {"fix": "description", "reason": "failed in incident INC-003"}
  ],
  "memory_summary": "Agent recalled N incidents. Key insight: ...",
  "urgency": "P0|P1|P2|P3",
  "estimated_resolution_min": 15
}"""

MEMORY_OFF_SYSTEM_PROMPT = """You are IncidentMind in generic mode (Memory is OFF).
You analyze incidents using only your training knowledge, with no past incident data.

CRITICAL RULES for Memory-OFF mode:
1. Do NOT cite any incident IDs — you have no memory to reference.
2. Do NOT include any skipped_fixes — you have no failure history.
3. Keep confidence at or below 40 — this is a cold-start analysis.
4. memory_summary must clearly state: "Memory is OFF — generic cold-start analysis, no past incidents recalled."
5. Give standard textbook advice only.

REQUIRED OUTPUT FORMAT (valid JSON only, no markdown code blocks):
{
  "likely_root_cause": "concise one-sentence root cause",
  "confidence": 35,
  "fix_steps": [
    {"rank": 1, "step": "description", "rationale": "why", "memory_backed": false, "incident_refs": []},
    {"rank": 2, "step": "description", "rationale": "why", "memory_backed": false, "incident_refs": []}
  ],
  "skipped_fixes": [],
  "memory_summary": "Memory is OFF — generic cold-start analysis, no past incidents recalled.",
  "urgency": "P0|P1|P2|P3",
  "estimated_resolution_min": 30
}"""


def analyze_incident(
    incident_text: str,
    memory_on: bool = True,
    recalled_incidents: list[dict] | None = None,
    recalled_outcomes: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Analyze an incident and return a structured response dict.

    When memory_on=True, recalled_incidents and recalled_outcomes are injected
    into the prompt before calling the LLM.

    Returns a dict with keys matching the JSON schema above, plus:
      - raw_text: the raw LLM output
      - model_used: which model answered
      - memory_on: bool
      - error: error message if LLM failed
    """
    if not incident_text or not incident_text.strip():
        return {"error": "Empty incident text provided", "memory_on": memory_on}

    recalled_incidents = recalled_incidents or []
    recalled_outcomes = recalled_outcomes or []

    # Build the set of valid recalled incident IDs for post-parse filtering
    valid_recalled_ids: set[str] = set()
    for mem in recalled_incidents + recalled_outcomes:
        meta = mem.get("metadata", {})
        inc_id = meta.get("incident_id", "")
        if inc_id:
            # Also allow the base ID if this is a "-failed" variant
            valid_recalled_ids.add(inc_id)
            if inc_id.endswith("-failed"):
                valid_recalled_ids.add(inc_id[:-7])

    # Build user message
    user_content_parts = []

    if memory_on:
        if recalled_incidents or recalled_outcomes:
            memory_ctx = _build_memory_context(recalled_incidents, recalled_outcomes)
        else:
            memory_ctx = "No relevant past incidents found"
        user_content_parts.append(memory_ctx)
    # Memory OFF: use separate system prompt, no memory context injected

    user_content_parts.append(f"=== CURRENT INCIDENT ===\n{incident_text}")
    user_content_parts.append(
        "\nAnalyze this incident and return ONLY the JSON response (no markdown)."
    )

    system_prompt = SYSTEM_PROMPT if memory_on else MEMORY_OFF_SYSTEM_PROMPT

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(user_content_parts)},
    ]

    raw_text, model_used = _call_with_fallback(messages)

    if raw_text is None:
        return {
            "error": "LLM call failed after retries on both models",
            "memory_on": memory_on,
            "model_used": "none",
        }

    # Parse JSON response defensively
    parsed = _safe_parse_json(raw_text)
    parsed["raw_text"] = raw_text
    parsed["model_used"] = model_used
    parsed["memory_on"] = memory_on

    # ── Post-parse validation ────────────────────────────────────────────────
    if not memory_on:
        # Memory OFF: enforce hard caps
        parsed["confidence"] = min(parsed.get("confidence", 35), 40)
        parsed["skipped_fixes"] = []
        # Strip any hallucinated incident_refs from fix steps
        for step in parsed.get("fix_steps", []):
            step["incident_refs"] = []
            step["memory_backed"] = False
        parsed["memory_summary"] = "Memory is OFF — generic cold-start analysis, no past incidents recalled."
    elif valid_recalled_ids:
        # Memory ON: strip refs to IDs not actually recalled
        for step in parsed.get("fix_steps", []):
            step["incident_refs"] = [
                ref for ref in step.get("incident_refs", [])
                if ref in valid_recalled_ids
            ]
        parsed["skipped_fixes"] = [
            sf for sf in parsed.get("skipped_fixes", [])
            if any(rid in sf.get("reason", "") for rid in valid_recalled_ids)
        ]
    else:
        # Memory ON but nothing recalled — clear all refs
        parsed["memory_summary"] = "No relevant past incidents found"
        for step in parsed.get("fix_steps", []):
            step["incident_refs"] = []
            step["memory_backed"] = False
        parsed["skipped_fixes"] = []

    return parsed


# ---------------------------------------------------------------------------
# Sidebar "What the Agent Learned" synthesis
# ---------------------------------------------------------------------------

def synthesize_learnings(recalled_memories: list[dict]) -> str:
    """
    Ask the LLM to summarise patterns in recalled memories for the sidebar.
    Returns a markdown-formatted string. Never raises.
    """
    if not recalled_memories:
        return "_No past incidents to analyse yet. Seed the database to see learnings._"

    # Condense memories to avoid token overflow
    memory_text = "\n\n".join(
        f"• [{m.get('metadata', {}).get('service', '?')}] "
        f"{m.get('metadata', {}).get('root_cause', m.get('text', '')[:200])}"
        for m in recalled_memories[:10]
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are an SRE knowledge distiller. Given a list of past incident memories, "
                "produce 3-5 concise bullet-point insights about recurring patterns, "
                "which services fail most, and which fixes consistently work or fail. "
                "Keep each bullet under 40 words. Use markdown. Start with '**Patterns Learned:**'"
            ),
        },
        {"role": "user", "content": memory_text},
    ]

    raw, _ = _call_with_fallback(messages)
    return raw or "_Could not generate learnings summary._"


# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------

def _safe_parse_json(text: str) -> dict:
    """
    Try to extract and parse JSON from LLM output.
    Returns a dict with whatever was parsed, or error info.
    """
    # Strip markdown code fences if present
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        # Remove first and last fence lines
        inner = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if inner.endswith("```"):
            inner = inner[: inner.rfind("```")]
        clean = inner.strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Try to extract JSON object from mixed text
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(clean[start:end])
            except json.JSONDecodeError:
                pass

    # Fall back: return a best-effort dict from the raw text
    return {
        "likely_root_cause": _extract_line(text, "root_cause") or "See raw analysis below",
        "confidence": 50,
        "fix_steps": [{"rank": 1, "step": text[:500], "rationale": "raw output", "memory_backed": False, "incident_refs": []}],
        "skipped_fixes": [],
        "memory_summary": "JSON parse failed; raw output shown.",
        "urgency": "P2",
        "estimated_resolution_min": 30,
        "parse_error": True,
    }


def _extract_line(text: str, key: str) -> str | None:
    """Attempt to extract a value from a key: value line in text."""
    for line in text.split("\n"):
        if key.lower() in line.lower() and ":" in line:
            return line.split(":", 1)[-1].strip().strip('"').strip("'")
    return None
