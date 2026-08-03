"""
Fuzzy matcher.

Single responsibility: score an unknown token against every known surface
form by lexical similarity, and report the best canonical candidates.
Catches typos ('glycerol' vs 'glycrol'), word-order differences, and partial
overlaps that exact matching misses. Uses token-set ratio so that
'oil sunflower seed' still matches 'sunflower seed oil'.
"""
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from ..data.inci_reference import InciReference
from . import preprocess


@dataclass
class ScoredCandidate:
    inci: str
    score: float          # 0..1
    matched_form: str     # the surface form that produced the score


class FuzzyMatcher:
    def __init__(self, reference: InciReference):
        # Map each normalized surface form -> canonical name, and keep the
        # list of forms as the search space for rapidfuzz.
        self._form_to_inci: dict[str, str] = {}
        for entry in reference.entries:
            for form in entry.surface_forms:
                self._form_to_inci[preprocess.normalize(form)] = entry.inci
        self._forms = list(self._form_to_inci.keys())

    def match(self, normalized_token: str, top_k: int = 3) -> list[ScoredCandidate]:
        """Return up to top_k best canonical candidates, de-duplicated by INCI."""
        if not normalized_token:
            return []
        # scorer returns 0..100; process.extract handles the search space.
        raw = process.extract(
            normalized_token,
            self._forms,
            scorer=fuzz.token_set_ratio,
            limit=top_k * 3,  # over-fetch, then collapse duplicate INCIs
        )
        best_by_inci: dict[str, ScoredCandidate] = {}
        for form, score, _ in raw:
            inci = self._form_to_inci[form]
            cand = ScoredCandidate(inci=inci, score=score / 100.0, matched_form=form)
            if inci not in best_by_inci or cand.score > best_by_inci[inci].score:
                best_by_inci[inci] = cand
        ranked = sorted(best_by_inci.values(), key=lambda c: c.score, reverse=True)
        return ranked[:top_k]
