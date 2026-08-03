"""
Central configuration for the ingredient normalizer.

Keeping every tunable value here (and nowhere else) is a deliberate
Separation-of-Concerns choice: matching logic should never hard-code a
threshold. If you want to make the matcher stricter or looser, you change
it in exactly one place. Values can be overridden via environment variables
(see .env.example) without touching code.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the ingredient_normalizer package root when present.
# Platforms like Render/Railway inject env vars directly; this is for local use.
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PACKAGE_ROOT / ".env")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


# --- Data ---------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
INCI_SOURCE = DATA_DIR / "sample_inci.json"

# --- Semantic model -----------------------------------------------------
# A small, fast sentence-transformer. Swap for a domain-tuned model to
# improve accuracy on chemistry terms. If the model can't be loaded
# (e.g. offline), the pipeline degrades gracefully to lexical matching.
# Free-tier PaaS hosts (Render/Railway) default OFF to avoid PyTorch OOM;
# override with ENABLE_SEMANTIC=true when you have enough RAM.
SEMANTIC_MODEL_NAME = os.environ.get("SEMANTIC_MODEL_NAME", "all-MiniLM-L6-v2")
_ON_PAAS = bool(
    os.environ.get("RENDER")
    or os.environ.get("RAILWAY_ENVIRONMENT")
    or os.environ.get("DYNO")
)
ENABLE_SEMANTIC = _env_bool("ENABLE_SEMANTIC", default=not _ON_PAAS)

# --- Ensemble weights ---------------------------------------------------
# How much each signal contributes to the blended score for a candidate.
# Must sum to 1.0. Fuzzy catches typos/word-order; semantic catches
# conceptual synonyms fuzzy misses ("vitamin c" -> "Ascorbic Acid").
FUZZY_WEIGHT = _env_float("FUZZY_WEIGHT", 0.45)
SEMANTIC_WEIGHT = _env_float("SEMANTIC_WEIGHT", 0.55)

# --- Confidence routing -------------------------------------------------
# The three-way decision that makes this usable in a regulated workflow:
#   >= AUTO_ACCEPT      -> accept automatically
#   >= REVIEW_THRESHOLD -> surface top-k suggestions for a human to confirm
#   <  REVIEW_THRESHOLD -> flag as unmatched (nothing is silently guessed)
AUTO_ACCEPT_THRESHOLD = _env_float("AUTO_ACCEPT_THRESHOLD", 0.90)
REVIEW_THRESHOLD = _env_float("REVIEW_THRESHOLD", 0.60)

# Number of candidate suggestions to return for review-tier matches.
TOP_K = _env_int("TOP_K", 3)
