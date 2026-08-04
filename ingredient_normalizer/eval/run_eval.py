"""
Offline evaluation against ground_truth.csv.

Run from ingredient_normalizer/:
  python -m eval.run_eval

Or from repo root:
  PYTHONPATH=ingredient_normalizer python -m eval.run_eval
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

# Allow `python eval/run_eval.py` from ingredient_normalizer/
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend import config  # noqa: E402
from backend.core.pipeline import NormalizationPipeline  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
GROUND_TRUTH = EVAL_DIR / "ground_truth.csv"
RESULTS_MD = _ROOT / "RESULTS.md"
PREDICTIONS_CSV = EVAL_DIR / "last_predictions.csv"


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _is_correct(expected: str, predicted: str | None, decision: str, candidates: list) -> bool:
    """
    Scoring rules:
      - expected empty  -> correct iff decision == unmatched
      - expected set    -> correct if matched_inci equals expected
                         OR (review tier and expected appears in top-k candidates)
    """
    exp = expected.strip()
    if not exp:
        return decision == "unmatched"
    if _norm(predicted) == _norm(exp):
        return True
    if decision == "review":
        return any(_norm(c.get("inci")) == _norm(exp) for c in candidates)
    return False


def load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run() -> dict:
    rows = load_rows(GROUND_TRUTH)
    pipeline = NormalizationPipeline()

    predictions: list[dict] = []
    latencies: list[float] = []

    n_correct = 0
    tier_total: Counter = Counter()
    tier_correct: Counter = Counter()
    false_accepts = 0
    accept_total = 0
    unknown_total = 0
    unknown_correct = 0

    for row in rows:
        raw = row["raw_input"]
        expected = (row.get("expected_inci") or "").strip()
        result = pipeline.normalize_item(raw)
        latencies.append(result.latency_ms)

        ok = _is_correct(expected, result.matched_inci, result.decision, result.candidates)
        n_correct += 1 if ok else 0
        tier_total[result.decision] += 1
        if ok:
            tier_correct[result.decision] += 1

        if result.decision == "accepted":
            accept_total += 1
            if expected and _norm(result.matched_inci) != _norm(expected):
                false_accepts += 1
            if not expected:
                false_accepts += 1  # accepted an unknown

        if not expected:
            unknown_total += 1
            if result.decision == "unmatched":
                unknown_correct += 1

        predictions.append(
            {
                "raw_input": raw,
                "expected_inci": expected,
                "predicted_inci": result.matched_inci or "",
                "decision": result.decision,
                "confidence": result.confidence,
                "stage": result.stage,
                "latency_ms": result.latency_ms,
                "correct": ok,
                "note": row.get("note", ""),
            }
        )

    n = len(rows)
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else 0.0
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies_sorted else 0.0
    avg_lat = sum(latencies) / n if n else 0.0

    summary = {
        "date": date.today().isoformat(),
        "test_set_size": n,
        "positives": sum(1 for r in rows if (r.get("expected_inci") or "").strip()),
        "unknowns": unknown_total,
        "semantic_available": pipeline.semantic_available,
        "enable_semantic_config": config.ENABLE_SEMANTIC,
        "auto_accept_threshold": config.AUTO_ACCEPT_THRESHOLD,
        "review_threshold": config.REVIEW_THRESHOLD,
        "overall_accuracy": n_correct / n if n else 0.0,
        "n_correct": n_correct,
        "per_tier": {
            tier: {
                "n": tier_total[tier],
                "correct": tier_correct[tier],
                "accuracy": (tier_correct[tier] / tier_total[tier]) if tier_total[tier] else None,
            }
            for tier in ("accepted", "review", "unmatched")
        },
        "false_accept_rate": (false_accepts / accept_total) if accept_total else 0.0,
        "false_accepts": false_accepts,
        "accept_total": accept_total,
        "unknown_handled_rate": (unknown_correct / unknown_total) if unknown_total else None,
        "latency_ms": {
            "avg": round(avg_lat, 3),
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "max": round(max(latencies), 3) if latencies else 0.0,
        },
        "errors": [
            p
            for p in predictions
            if not p["correct"]
        ],
    }

    with PREDICTIONS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(predictions[0].keys()))
        w.writeheader()
        w.writerows(predictions)

    (EVAL_DIR / "last_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def write_results_md(summary: dict) -> None:
    pt = summary["per_tier"]
    err_lines = []
    for e in summary["errors"][:25]:
        err_lines.append(
            f"| {e['raw_input'][:40]} | {e['expected_inci'] or '∅'} | "
            f"{e['predicted_inci'] or '∅'} | {e['decision']} | {e['confidence']} |"
        )
    if len(summary["errors"]) > 25:
        err_lines.append(f"| … | ({len(summary['errors']) - 25} more) | | | |")

    def pct(x: float) -> str:
        return f"{100 * x:.1f}%"

    resume = _resume_bullets(summary)

    md = f"""# Inclarity evaluation results

**Date:** {summary['date']}  
**Test set:** [`eval/ground_truth.csv`](eval/ground_truth.csv) — **{summary['test_set_size']}** rows  
({summary['positives']} labeled positives, {summary['unknowns']} intentional unknowns)  
**Mode:** semantic={'ON' if summary['semantic_available'] else 'OFF'} (`ENABLE_SEMANTIC={summary['enable_semantic_config']}`)  
**Thresholds:** auto-accept ≥ {summary['auto_accept_threshold']}, review ≥ {summary['review_threshold']}

## Metrics

| Metric | Value |
|--------|-------|
| Overall accuracy | **{pct(summary['overall_accuracy'])}** ({summary['n_correct']}/{summary['test_set_size']}) |
| False-accept rate | **{pct(summary['false_accept_rate'])}** ({summary['false_accepts']}/{summary['accept_total']} accepted) |
| Unknowns correctly unmatched | {pct(summary['unknown_handled_rate'] or 0)} |
| Avg latency / lookup | **{summary['latency_ms']['avg']} ms** |
| p50 latency | {summary['latency_ms']['p50']} ms |
| p95 latency | {summary['latency_ms']['p95']} ms |

### Per-tier

| Tier | N | Correct | Accuracy |
|------|---|--------:|----------|
| accepted | {pt['accepted']['n']} | {pt['accepted']['correct']} | {pct(pt['accepted']['accuracy'] or 0)} |
| review | {pt['review']['n']} | {pt['review']['correct']} | {pct(pt['review']['accuracy'] or 0)} |
| unmatched | {pt['unmatched']['n']} | {pt['unmatched']['correct']} | {pct(pt['unmatched']['accuracy'] or 0)} |

Scoring: positives count as correct if the predicted INCI matches, or if the tier is
`review` and the expected INCI appears in top-k candidates. Unknowns (empty
`expected_inci`) count as correct only when the decision is `unmatched`.

## Errors (sample)

| raw_input | expected | predicted | decision | confidence |
|-----------|----------|-----------|----------|------------|
{chr(10).join(err_lines) if err_lines else "| — | none | — | — | — |"}

Full row-level output: [`eval/last_predictions.csv`](eval/last_predictions.csv)

## Resume bullets (from this run)

{resume}

## Reproduce

```bash
cd ingredient_normalizer
pip install -r backend/requirements.txt
ENABLE_SEMANTIC=false python -m eval.run_eval
```
"""
    RESULTS_MD.write_text(md, encoding="utf-8")


def _resume_bullets(summary: dict) -> str:
    oa = 100 * summary["overall_accuracy"]
    fa = 100 * summary["false_accept_rate"]
    avg = summary["latency_ms"]["avg"]
    lat = f"{avg:.2f} ms" if avg >= 0.01 else "<0.01 ms"
    n = summary["test_set_size"]
    return f"""
- Built and deployed **Inclarity**, a full-stack INCI normalization engine (Python/Flask + vanilla JS) that maps messy cosmetic ingredient strings to canonical names via exact, fuzzy (RapidFuzz), and optional semantic matching
- Designed a **3-tier confidence-routing system** (Accept / Review / Unmatched); on a **{n}-item** messy ground-truth set (lexical mode), achieved **{oa:.1f}%** overall accuracy with a **{fa:.1f}%** false-accept rate and **~{lat}** average lookup latency
- Shipped end-to-end on **Render**; expanded the in-memory reference from a small sample to **175 INCI entries** across **50+** functional categories ([live demo](https://inclarity.onrender.com))
""".strip()


if __name__ == "__main__":
    # Match free-tier / production lexical behavior unless caller overrides.
    import os

    os.environ.setdefault("ENABLE_SEMANTIC", "false")
    # Re-read config flags that were already imported — set before import ideally.
    # Pipeline reads config at construction; ENABLE_SEMANTIC was already bound.
    # Force via env before pipeline build by reloading config module values:
    config.ENABLE_SEMANTIC = config._env_bool("ENABLE_SEMANTIC", False)

    summary = run()
    write_results_md(summary)
    print(json.dumps({k: summary[k] for k in summary if k != "errors"}, indent=2))
    print(f"\nWrote {RESULTS_MD}")
    print(f"Wrote {PREDICTIONS_CSV}")
    if summary["false_accept_rate"] > 0.05:
        print(
            "\nWARNING: false-accept rate > 5%. "
            "Consider raising AUTO_ACCEPT_THRESHOLD before publishing accuracy."
        )
