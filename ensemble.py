"""
Ensemble ranking + confidence router.

Single responsibility: combine the per-candidate relevance scores from the fuzzy and
semantic matchers into one unified relevance rank, then map that score to a decision
(accept / review / unmatched). This is the module that turns raw similarity
signals into a workflow-usable ranking verdict.

Why an ensemble: fuzzy and semantic fail in different directions. Fuzzy is
strong on typos and spelling variants but blind to meaning; semantic is
strong on conceptual synonyms but can be over-confident on loosely related
terms. Multi-signal ranking that blends them is more robust than either alone—
similar to recommendation systems that combine multiple ranking signals
(relevance, similarity, confidence) into a unified score.
"""
from dataclasses import dataclass, field
from enum import Enum

from .. import config
from .fuzzy_matcher import ScoredCandidate as FuzzyCand
from .semantic_matcher import ScoredCandidate as SemCand


class Decision(str, Enum):
    ACCEPTED = "accepted"     # high confidence, auto-accept
    CANDIDATE = "candidate"   # medium confidence, top-k candidates for review
    UNMATCHED = "unmatched"   # low confidence, nothing is guessed


@dataclass
class Candidate:
    inci: str
    score: float
    fuzzy_score: float = 0.0
    semantic_score: float = 0.0


@dataclass
class Verdict:
    decision: Decision
    best: Candidate | None
    candidates: list[Candidate] = field(default_factory=list)


def _rank_score(fuzzy: float, semantic: float, semantic_available: bool) -> float:
    """
    Multi-signal relevance ranking. Combines lexical (fuzzy) and semantic signals
    into a unified ranking score. When semantic is unavailable we don't
    silently penalize the item — we fall back to the fuzzy score alone, so a
    typo'd but lexically-close term can still clear the bar.
    """
    if not semantic_available:
        return fuzzy
    return config.FUZZY_WEIGHT * fuzzy + config.SEMANTIC_WEIGHT * semantic


def combine(
    fuzzy_cands: list[FuzzyCand],
    semantic_cands: list[SemCand],
    semantic_available: bool,
) -> list[Candidate]:
    """Merge and rank candidates by unified relevance score across all signals."""
    fuzzy_by_inci = {c.inci: c.score for c in fuzzy_cands}
    sem_by_inci = {c.inci: c.score for c in semantic_cands}
    all_inci = set(fuzzy_by_inci) | set(sem_by_inci)

    ranked: list[Candidate] = []
    for inci in all_inci:
        f = fuzzy_by_inci.get(inci, 0.0)
        s = sem_by_inci.get(inci, 0.0)
        ranked.append(
            Candidate(
                inci=inci,
                score=_rank_score(f, s, semantic_available),
                fuzzy_score=f,
                semantic_score=s,
            )
        )
    ranked.sort(key=lambda c: c.score, reverse=True)
    return ranked


def route(candidates: list[Candidate]) -> Verdict:
    """Apply the confidence thresholds to produce a ranking decision."""
    if not candidates:
        return Verdict(decision=Decision.UNMATCHED, best=None, candidates=[])

    top = candidates[0]
    trimmed = candidates[: config.TOP_K]

    if top.score >= config.AUTO_ACCEPT_THRESHOLD:
        return Verdict(decision=Decision.ACCEPTED, best=top, candidates=trimmed)
    if top.score >= config.REVIEW_THRESHOLD:
        return Verdict(decision=Decision.CANDIDATE, best=top, candidates=trimmed)
    return Verdict(decision=Decision.UNMATCHED, best=None, candidates=trimmed)
