"""
Central configuration for the ingredient normalizer.

Keeping every tunable value here (and nowhere else) is a deliberate
Separation-of-Concerns choice: matching logic should never hard-code a
threshold. If you want to make the matcher stricter or looser, you change
it in exactly one place.
"""
from pathlib import Path

# --- Data ---------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
INCI_SOURCE = DATA_DIR / "sample_inci.json"

# --- Semantic model -----------------------------------------------------
# A small, fast sentence-transformer. Swap for a domain-tuned model to
# improve accuracy on chemistry terms. If the model can't be loaded
# (e.g. offline), the pipeline degrades gracefully to lexical matching.
SEMANTIC_MODEL_NAME = "all-MiniLM-L6-v2"

# --- Ensemble weights ---------------------------------------------------
# How much each signal contributes to the blended score for a candidate.
# Must sum to 1.0. Fuzzy catches typos/word-order; semantic catches
# conceptual synonyms fuzzy misses ("vitamin c" -> "Ascorbic Acid").
FUZZY_WEIGHT = 0.45
SEMANTIC_WEIGHT = 0.55

# --- Confidence routing -------------------------------------------------
# The three-way decision that makes this usable in a regulated workflow:
#   >= AUTO_ACCEPT      -> accept automatically
#   >= REVIEW_THRESHOLD -> surface top-k suggestions for a human to confirm
#   <  REVIEW_THRESHOLD -> flag as unmatched (nothing is silently guessed)
AUTO_ACCEPT_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.60

# Number of candidate suggestions to return for review-tier matches.
TOP_K = 3
