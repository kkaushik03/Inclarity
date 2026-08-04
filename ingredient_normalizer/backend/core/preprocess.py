"""
Text preprocessing for raw ingredient strings.

Single responsibility: turn a messy, real-world ingredient string into a
clean, comparable token. Nothing here matches anything — it only cleans.
Cosmetic labels are full of noise this has to survive: parenthetical common
names, asterisks/daggers marking allergens or organics, percentages, and
inconsistent casing/whitespace.
"""
import re
import unicodedata

# Common label abbreviations expanded to their full forms so downstream
# matchers see canonical vocabulary.
_ABBREVIATIONS = {
    "vit ": "vitamin ",
    "vit.": "vitamin",
    "&": " and ",
}

# Marks and boilerplate that carry no matching signal.
_NOISE_PATTERN = re.compile(
    r"[*\u2020\u2021\u00ae\u2122\u00b0]"        # * dagger double-dagger (R) (TM) degree
    r"|\d+(\.\d+)?\s*%",                         # percentages: 2%, 0.5 %
    # Colour-index codes (CI 77891) are kept — they are real matching keys.
    flags=re.IGNORECASE,
)

_PARENS = re.compile(r"\(([^)]*)\)")
_WHITESPACE = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    """Fold accented characters to ASCII (e.g. 'aloë' -> 'aloe')."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def extract_parenthetical(text: str) -> tuple[str, list[str]]:
    """
    Split 'Butyrospermum Parkii (Shea) Butter' into its outer form and the
    parenthetical hints ['shea']. Both are useful matching candidates, so we
    return them separately rather than throwing the hint away.
    """
    hints = [h.strip() for h in _PARENS.findall(text)]
    outer = _PARENS.sub(" ", text)
    return outer, hints


def normalize(text: str) -> str:
    """Full normalization pipeline for a single ingredient token."""
    if text is None:
        return ""
    text = strip_accents(text).lower()
    for abbr, full in _ABBREVIATIONS.items():
        text = text.replace(abbr, full)
    text = _NOISE_PATTERN.sub(" ", text)
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9\s-]", " ", text)   # drop stray punctuation
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def variants(raw: str) -> list[str]:
    """
    Produce the set of normalized candidate strings for one raw item:
    the normalized outer form plus any normalized parenthetical hints.
    Deduplicated, order preserved.
    """
    outer, hints = extract_parenthetical(raw)
    candidates = [normalize(outer)] + [normalize(h) for h in hints]
    seen, out = set(), []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out
