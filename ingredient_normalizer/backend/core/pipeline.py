"""
Normalization pipeline (orchestrator).

Single responsibility: coordinate the stages in order and assemble the
result for one item or a whole list. It owns *sequencing*, not matching —
each matching decision lives in its own module. This is the one place that
knows the overall flow:

    preprocess -> exact (short-circuit) -> fuzzy + semantic -> ensemble -> verdict

Keeping orchestration separate from the matchers means any stage can be
swapped, reordered, or tested in isolation without touching the others.
"""
from dataclasses import dataclass, field

from .. import config
from ..data.inci_reference import InciReference
from . import preprocess
from .ensemble import Candidate, Decision, Verdict, combine, route
from .exact_matcher import ExactMatcher
from .fuzzy_matcher import FuzzyMatcher
from .semantic_matcher import SemanticMatcher


@dataclass
class ItemResult:
    raw: str
    normalized: str
    decision: str
    matched_inci: str | None
    confidence: float
    candidates: list[dict] = field(default_factory=list)
    stage: str = ""            # which stage decided: exact / ensemble / none


class NormalizationPipeline:
    def __init__(self, reference: InciReference | None = None):
        self.reference = reference or InciReference.from_json(config.INCI_SOURCE)
        self.exact = ExactMatcher(self.reference)
        self.fuzzy = FuzzyMatcher(self.reference)
        self.semantic = SemanticMatcher(
            self.reference,
            config.SEMANTIC_MODEL_NAME,
            enabled=config.ENABLE_SEMANTIC,
        )

    @property
    def semantic_available(self) -> bool:
        return self.semantic.available

    # --- single item ----------------------------------------------------
    def normalize_item(self, raw: str) -> ItemResult:
        variants = preprocess.variants(raw)
        primary = variants[0] if variants else ""

        # Stage 1: exact match on any variant -> certain, short-circuit.
        for variant in variants:
            hit = self.exact.match(variant)
            if hit:
                return ItemResult(
                    raw=raw,
                    normalized=primary,
                    decision=Decision.ACCEPTED.value,
                    matched_inci=hit,
                    confidence=1.0,
                    candidates=[{"inci": hit, "score": 1.0}],
                    stage="exact",
                )

        # Stage 2: fuzzy + semantic over the primary variant, then ensemble.
        fuzzy_cands = self.fuzzy.match(primary, top_k=config.TOP_K)
        semantic_cands = self.semantic.match(primary, top_k=config.TOP_K)
        merged = combine(fuzzy_cands, semantic_cands, self.semantic.available)
        verdict: Verdict = route(merged)

        return ItemResult(
            raw=raw,
            normalized=primary,
            decision=verdict.decision.value,
            matched_inci=verdict.best.inci if verdict.best else None,
            confidence=round(verdict.best.score, 4) if verdict.best else (
                round(merged[0].score, 4) if merged else 0.0
            ),
            candidates=[
                {
                    "inci": c.inci,
                    "score": round(c.score, 4),
                    "fuzzy": round(c.fuzzy_score, 4),
                    "semantic": round(c.semantic_score, 4),
                }
                for c in verdict.candidates
            ],
            stage="ensemble",
        )

    # --- batch ----------------------------------------------------------
    def normalize_list(self, items: list[str]) -> list[ItemResult]:
        return [self.normalize_item(item) for item in items if item and item.strip()]

    @staticmethod
    def parse_raw_list(text: str) -> list[str]:
        """
        Turn a pasted ingredient blob into items. Cosmetic INCI lists are
        comma-separated; we also split on newlines and semicolons for the
        messy paste-from-anywhere case.
        """
        import re
        parts = re.split(r"[,;\n]", text)
        return [p.strip() for p in parts if p.strip()]
