"""
API schemas / serializers.

Single responsibility: translate between HTTP-facing JSON and the core
pipeline's dataclasses. Keeping this here means the core never imports Flask
and the API never reaches into matching internals — each side depends only
on this thin boundary.
"""
from ..core.pipeline import ItemResult


def item_result_to_dict(result: ItemResult) -> dict:
    return {
        "raw": result.raw,
        "normalized": result.normalized,
        "decision": result.decision,
        "matched_inci": result.matched_inci,
        "confidence": result.confidence,
        "stage": result.stage,
        "latency_ms": result.latency_ms,
        "candidates": result.candidates,
    }


def summarize(results: list[ItemResult]) -> dict:
    """Roll-up counts so the UI can show an at-a-glance status bar."""
    counts = {"accepted": 0, "review": 0, "unmatched": 0}
    for r in results:
        counts[r.decision] = counts.get(r.decision, 0) + 1
    return {
        "total": len(results),
        "accepted": counts["accepted"],
        "review": counts["review"],
        "unmatched": counts["unmatched"],
    }
