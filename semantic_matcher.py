"""
Semantic matcher.

Single responsibility: score an unknown token against the canonical
vocabulary by *meaning*, using sentence embeddings + cosine similarity.
This is what lets 'vitamin c' resolve to 'Ascorbic Acid' or 'green tea'
to 'Camellia Sinensis Leaf Extract' — pairs with near-zero string overlap
that fuzzy matching cannot catch.

Design notes:
  * Reference embeddings are computed once at construction and cached.
  * The model is loaded lazily and defensively. If sentence-transformers
    isn't installed or the weights can't be fetched (offline), this matcher
    reports itself unavailable and returns no candidates — the pipeline then
    runs on lexical signals alone rather than crashing. That graceful
    degradation is intentional: a regulated tool should never hard-fail
    because an optional model is missing.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..data.inci_reference import InciReference
from . import preprocess


@dataclass
class ScoredCandidate:
    inci: str
    score: float          # 0..1 cosine similarity, clamped
    matched_form: str


class SemanticMatcher:
    def __init__(self, reference: InciReference, model_name: str):
        self._reference = reference
        self._model_name = model_name
        self._model = None
        self._available = False
        self._forms: list[str] = []
        self._form_to_inci: dict[str, str] = {}
        self._embeddings = None
        self._try_initialize()

    # --- lifecycle ------------------------------------------------------
    def _try_initialize(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np  # noqa: F401  (used later; import-guard here)
        except Exception:
            self._available = False
            return
        try:
            self._model = SentenceTransformer(self._model_name)
            # Build the search space from normalized surface forms.
            for entry in self._reference.entries:
                for form in entry.surface_forms:
                    norm = preprocess.normalize(form)
                    self._form_to_inci[norm] = entry.inci
            self._forms = list(self._form_to_inci.keys())
            self._embeddings = self._model.encode(
                self._forms, normalize_embeddings=True, convert_to_numpy=True
            )
            self._available = True
        except Exception:
            # Weights unavailable / offline / OOM -> disable cleanly.
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    # --- matching -------------------------------------------------------
    def match(self, normalized_token: str, top_k: int = 3) -> list[ScoredCandidate]:
        if not self._available or not normalized_token:
            return []
        import numpy as np

        query = self._model.encode(
            [normalized_token], normalize_embeddings=True, convert_to_numpy=True
        )[0]
        # Cosine similarity == dot product because vectors are L2-normalized.
        sims = self._embeddings @ query
        best_by_inci: dict[str, ScoredCandidate] = {}
        for idx, sim in enumerate(sims):
            form = self._forms[idx]
            inci = self._form_to_inci[form]
            score = float(max(0.0, min(1.0, sim)))
            if inci not in best_by_inci or score > best_by_inci[inci].score:
                best_by_inci[inci] = ScoredCandidate(
                    inci=inci, score=score, matched_form=form
                )
        ranked = sorted(best_by_inci.values(), key=lambda c: c.score, reverse=True)
        return ranked[:top_k]
