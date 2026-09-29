"""
memory.py — Hindsight memory wrapper for IncidentMind.

This module is the heart of the project: it wraps every Hindsight call
(retain / recall) with error handling and clean Python interfaces.

The memory design:
  • One "incident" memory per resolved incident (content = full text blob)
  • One "outcome" memory per fix outcome (content = outcome text, tagged)
  • One "outcome-{id}-failed" entry for incidents whose first fix attempt
    failed, so the agent can explicitly warn against that approach
  • Recall searches both before every LLM call when memory is ON
"""

import json
import logging
from datetime import datetime
from typing import Any

from hindsight_client import Hindsight

from config import (
    HINDSIGHT_API_KEY,
    HINDSIGHT_BASE_URL,
    HINDSIGHT_BANK_ID,
    RECALL_TOP_K,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

def _get_client() -> Hindsight:
    """Return a configured Hindsight client pointed at Hindsight Cloud."""
    return Hindsight(
        base_url=HINDSIGHT_BASE_URL,
        api_key=HINDSIGHT_API_KEY,
        timeout=60.0,
        max_attempts=3,
    )


# ---------------------------------------------------------------------------
# Retain helpers
# ---------------------------------------------------------------------------

def retain_incident(
    incident_id: str,
    service: str,
    symptoms: str,
    error_log: str,
    root_cause: str,
    fix_applied: str,
    time_to_resolve_min: int,
    outcome: str = "pending",  # "worked" | "failed" | "pending"
) -> dict[str, Any]:
    """
    Store a resolved incident in Hindsight memory.

    Returns a dict with keys: success (bool), message (str).
    Never raises — all errors are caught and returned as success=False.
    """
    client = _get_client()

    # Build a rich text blob so semantic recall works well
    content = (
        f"INCIDENT MEMORY\n"
        f"Service: {service}\n"
        f"Symptoms: {symptoms}\n"
        f"Error log excerpt: {error_log[:1000]}\n"
        f"Root cause: {root_cause}\n"
        f"Fix applied: {fix_applied}\n"
        f"Time to resolve: {time_to_resolve_min} minutes\n"
        f"Fix outcome: {outcome}\n"
        f"Incident ID: {incident_id}\n"
    )

    metadata = {
        "incident_id": incident_id,
        "service": service,
        "root_cause": root_cause[:200],
        "fix_applied": fix_applied[:200],
        "outcome": outcome,
        "time_to_resolve_min": str(time_to_resolve_min),
        "type": "incident",
    }

    try:
        resp = client.retain(
            bank_id=HINDSIGHT_BANK_ID,
            content=content,
            document_id=f"incident-{incident_id}",
            metadata=metadata,
            tags=["incident", service, outcome],
        )
        return {"success": resp.success, "message": f"Retained incident {incident_id}"}
    except Exception as exc:
        logger.error("retain_incident failed: %s", exc)
        return {"success": False, "message": str(exc)}


def retain_outcome(
    incident_id: str,
    service: str,
    root_cause: str,
    fix_applied: str,
    outcome: str,  # "worked" | "failed"
) -> dict[str, Any]:
    """
    Store a fix outcome so the agent learns which fixes work for which patterns.
    Uses a separate memory entry with outcome-specific tags for easy recall.

    For "failed" outcomes the document_id is "outcome-{incident_id}" which
    naturally handles both the canonical outcome and the "-failed" variant
    (e.g. "outcome-INC-003-failed") when incident_id ends with "-failed".
    """
    client = _get_client()

    content = (
        f"FIX OUTCOME MEMORY\n"
        f"Service: {service}\n"
        f"Root cause pattern: {root_cause}\n"
        f"Fix that was tried: {fix_applied}\n"
        f"Result: {outcome.upper()}\n"
        f"Lesson: When you see this root cause pattern in {service}, "
        f"the fix '{fix_applied}' {'worked' if outcome == 'worked' else 'FAILED — do not recommend this fix again'}.\n"
        f"Linked incident: {incident_id}\n"
    )

    metadata = {
        "incident_id": incident_id,
        "service": service,
        "root_cause": root_cause[:200],
        "fix_applied": fix_applied[:200],
        "outcome": outcome,
        "type": "outcome",
    }

    try:
        resp = client.retain(
            bank_id=HINDSIGHT_BANK_ID,
            content=content,
            document_id=f"outcome-{incident_id}",
            metadata=metadata,
            tags=["outcome", service, outcome, "fix-result"],
        )
        return {"success": resp.success, "message": f"Retained outcome for {incident_id}"}
    except Exception as exc:
        logger.error("retain_outcome failed: %s", exc)
        return {"success": False, "message": str(exc)}


# ---------------------------------------------------------------------------
# Recall helpers
# ---------------------------------------------------------------------------

def recall_similar_incidents(query: str, top_k: int = RECALL_TOP_K) -> list[dict[str, Any]]:
    """
    Semantic recall of past incidents similar to the query.

    Returns a list of structured dicts (never raises).
    Each dict has: id, text, metadata, score, type.
    """
    client = _get_client()

    try:
        resp = client.recall(
            bank_id=HINDSIGHT_BANK_ID,
            query=query,
            max_tokens=8000,  # give plenty of room for rich memory context
            budget="mid",
        )
        results = []
        for r in resp.results[:top_k]:
            results.append({
                "id": r.id or "",
                "text": r.text or "",
                "type": r.type or "unknown",
                "metadata": r.metadata or {},
                "score": _extract_score(r),
                "document_id": r.document_id or "",
            })
        return results
    except Exception as exc:
        logger.error("recall_similar_incidents failed: %s", exc)
        return []


def recall_fix_outcomes(query: str, service: str | None = None) -> list[dict[str, Any]]:
    """
    Recall past fix outcomes to learn which fixes worked or failed.
    Uses tags_match="all" so only outcome-tagged memories are returned,
    avoiding noise from incident memories.
    """
    client = _get_client()

    try:
        tags = ["outcome"]
        if service:
            tags.append(service)

        resp = client.recall(
            bank_id=HINDSIGHT_BANK_ID,
            query=query,
            max_tokens=4000,
            budget="mid",
            tags=tags,
            tags_match="all",
        )
        results = []
        for r in resp.results[:RECALL_TOP_K]:
            results.append({
                "id": r.id or "",
                "text": r.text or "",
                "type": r.type or "unknown",
                "metadata": r.metadata or {},
                "score": _extract_score(r),
                "document_id": r.document_id or "",
            })
        return results
    except Exception as exc:
        logger.error("recall_fix_outcomes failed: %s", exc)
        return []


def recall_all_context(query: str, service: str | None = None) -> dict[str, list[dict]]:
    """
    Recall both past incidents AND fix outcomes in one call.
    Returns dict with keys 'incidents' and 'outcomes'.
    """
    incidents = recall_similar_incidents(query, top_k=RECALL_TOP_K)
    outcomes = recall_fix_outcomes(query, service=service)

    # Deduplicate by document_id (an incident and its outcome may both match)
    outcome_ids = {o["document_id"] for o in outcomes}
    incidents = [i for i in incidents if i["document_id"] not in outcome_ids]

    return {"incidents": incidents, "outcomes": outcomes}


# ---------------------------------------------------------------------------
# Stats helper (for sidebar)
# ---------------------------------------------------------------------------

def get_memory_stats() -> dict[str, Any]:
    """
    Return basic stats about the memory bank: total memories, outcomes breakdown.
    Counts worked/failed from metadata.outcome rather than recall result counts.
    Logs errors and returns "—" sentinel values instead of 0 on failure.
    """
    client = _get_client()
    try:
        resp = client.list_memories(bank_id=HINDSIGHT_BANK_ID)
        total = resp.total if hasattr(resp, "total") else len(resp.items or [])

        # Count worked/failed from metadata.outcome in all outcome memories
        worked, failed = _count_outcomes_from_metadata()

        return {
            "total_memories": total,
            "fixes_worked": worked,
            "fixes_failed": failed,
            "success_rate": (
                round(worked / (worked + failed) * 100, 1)
                if (worked + failed) > 0
                else None
            ),
        }
    except Exception as exc:
        logger.error("get_memory_stats failed: %s", exc)
        return {
            "total_memories": "—",
            "fixes_worked": "—",
            "fixes_failed": "—",
            "success_rate": None,
        }


def _count_outcomes_from_metadata() -> tuple[int, int]:
    """
    Recall outcome memories and count worked vs failed from metadata.outcome.
    Falls back to (0, 0) on error, logging the exception.
    """
    client = _get_client()
    worked = 0
    failed = 0
    try:
        resp = client.recall(
            bank_id=HINDSIGHT_BANK_ID,
            query="fix outcome result",
            max_tokens=8000,
            budget="high",
            tags=["outcome"],
            tags_match="all",
        )
        for r in resp.results:
            meta = r.metadata or {}
            outcome = meta.get("outcome", "")
            if outcome == "worked":
                worked += 1
            elif outcome == "failed":
                failed += 1
    except Exception as exc:
        logger.error("_count_outcomes_from_metadata failed: %s", exc)
    return worked, failed


def _extract_score(r: Any) -> float:
    """Safely extract a relevance score from a RecallResult."""
    try:
        if r.scores:
            # scores is a dict-like; pick any numeric value
            vals = list(r.scores.values()) if isinstance(r.scores, dict) else [r.scores]
            return round(float(vals[0]), 3) if vals else 0.0
    except Exception:
        pass
    return 0.0
