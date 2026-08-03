"""
Data access layer for the INCI reference vocabulary.

Single responsibility: load the canonical ingredient list from disk and
expose it in the shapes the matchers need. No matching logic lives here —
this module only knows how to read and index the reference data. Swapping
the JSON file for a database or an API would only change this file.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class InciEntry:
    """One canonical ingredient and the surface forms that map to it."""
    inci: str
    synonyms: List[str] = field(default_factory=list)

    @property
    def surface_forms(self) -> List[str]:
        """Every string that should resolve to this entry, incl. the INCI name."""
        return [self.inci] + list(self.synonyms)


class InciReference:
    """In-memory index over the canonical vocabulary."""

    def __init__(self, entries: List[InciEntry]):
        self._entries = entries
        # surface form (lowercased) -> canonical INCI name
        self._lookup: Dict[str, str] = {}
        for entry in entries:
            for form in entry.surface_forms:
                self._lookup[form.strip().lower()] = entry.inci

    @classmethod
    def from_json(cls, path: Path) -> "InciReference":
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        entries = [
            InciEntry(inci=item["inci"], synonyms=item.get("synonyms", []))
            for item in payload["ingredients"]
        ]
        return cls(entries)

    # --- accessors the matchers rely on ---------------------------------
    @property
    def entries(self) -> List[InciEntry]:
        return self._entries

    @property
    def canonical_names(self) -> List[str]:
        return [e.inci for e in self._entries]

    @property
    def all_surface_forms(self) -> List[str]:
        forms: List[str] = []
        for e in self._entries:
            forms.extend(e.surface_forms)
        return forms

    def canonical_for(self, surface_form: str) -> str | None:
        """Exact (case-insensitive) resolution of a surface form, or None."""
        return self._lookup.get(surface_form.strip().lower())

    def __len__(self) -> int:
        return len(self._entries)
