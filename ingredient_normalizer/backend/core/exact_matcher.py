"""
Exact matcher.

Single responsibility: resolve an already-normalized token to a canonical
INCI name when it is a known surface form (the INCI name itself or a listed
synonym). This is the cheapest, highest-precision stage — if it hits, we are
certain, and the expensive stages can be skipped.
"""
from ..data.inci_reference import InciReference
from . import preprocess


class ExactMatcher:
    def __init__(self, reference: InciReference):
        # Pre-normalize every known surface form once, so lookups are O(1)
        # and use the *same* normalization the incoming tokens go through.
        self._index: dict[str, str] = {}
        for entry in reference.entries:
            for form in entry.surface_forms:
                self._index[preprocess.normalize(form)] = entry.inci

    def match(self, normalized_token: str) -> str | None:
        """Return the canonical INCI name for an exact hit, else None."""
        return self._index.get(normalized_token)
