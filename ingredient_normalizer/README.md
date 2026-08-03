# INCI Ingredient Normalizer

A multi-stage matching engine that maps messy, real-world cosmetic ingredient
lists onto canonical **INCI** (International Nomenclature of Cosmetic
Ingredients) names — with a confidence score and a human-in-the-loop decision
for every item.

Cosmetic labels are inconsistent: the same ingredient shows up as a trade
name, an INCI name, a common name, a translation, or a typo
(`Water` / `Aqua` / `eau`; `Vitamin C` / `L-Ascorbic Acid`; `glycrol`). Turning
those into a clean, standardized list is a real bottleneck in formulation and
regulatory workflows. This project automates that mapping and, crucially,
**never silently guesses** — low-confidence items are flagged for review
rather than accepted.

## How it works

Each ingredient flows through an ordered pipeline:

```
raw string
  → preprocess        normalize case/accents/noise, pull out parenthetical hints
  → exact match       O(1) lookup against known INCI names + synonyms  (short-circuit)
  → fuzzy match       rapidfuzz token-set similarity (typos, word order)
  → semantic match    sentence-embedding cosine similarity (conceptual synonyms)
  → ensemble          weighted blend of fuzzy + semantic scores
  → route             accept / review / unmatched  by confidence thresholds
```

The **ensemble** is the core idea: fuzzy matching is strong on spelling
variants but blind to meaning; semantic matching catches conceptual synonyms
(`green tea` → `Camellia Sinensis Leaf Extract`) that share almost no
characters. Blending the two is more robust than either alone. If the semantic
model can't be loaded (e.g. offline), the pipeline degrades gracefully to
lexical matching instead of failing.

### Confidence routing

| Blended score        | Decision    | Meaning                                   |
|----------------------|-------------|-------------------------------------------|
| ≥ 0.90               | `accepted`  | auto-accept                               |
| 0.60 – 0.90          | `review`    | surface top-k suggestions for a human     |
| < 0.60               | `unmatched` | nothing guessed; flagged for a human      |

Thresholds and ensemble weights are all in `backend/config.py`.

## Architecture

Built around **Separation of Concerns** and the **Single Responsibility
Principle** — each module does exactly one thing, and the layers depend
inward (API → core → data), never outward.

```
backend/
  config.py                 all tunable thresholds / model name (one place)
  data/
    sample_inci.json        canonical vocabulary (replace for production)
    inci_reference.py       data access layer — load & index the vocabulary
  core/
    preprocess.py           text normalization only
    exact_matcher.py        exact/synonym resolution only
    fuzzy_matcher.py        lexical similarity only
    semantic_matcher.py     embedding similarity only (graceful fallback)
    ensemble.py             score blending + confidence routing only
    pipeline.py             orchestration only (owns sequencing, not logic)
  api/
    schemas.py              JSON (de)serialization boundary
    app.py                  thin Flask HTTP layer — delegates to the pipeline
frontend/
  index.html                structure
  styles.css                presentation (palette in CSS variables)
  app.js                    fetch + render only; no business logic
```

The core never imports Flask; the API never reaches into matching internals;
the frontend holds no matching logic. Any stage can be swapped or tested in
isolation.

## Run it

```bash
cd ingredient_normalizer
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
# optional semantic matching (heavy — not for free-tier hosts):
# pip install -r backend/requirements-ml.txt
cp .env.example .env   # optional local overrides
python -m flask --app backend.api.app run
# or: python -m backend.api.app
# open http://127.0.0.1:5000
```

First run with ML extras downloads the sentence-transformer weights (~90 MB).
Without them the app still runs — it reports "lexical matching only" and uses the
fuzzy/exact stages.

### API

```
GET  /api/health      -> engine status, reference size, semantic availability
POST /api/normalize   -> body {"text": "Water, Glycerine, ..."}  or  {"items": [...]}
                         returns per-item verdicts + a summary roll-up
```

## Deploy (Render / Railway)

Set the service **Root Directory** to `ingredient_normalizer`.

| Setting | Value |
|---------|--------|
| Build command | `pip install -r backend/requirements.txt` |
| Start command | Procfile (`web: gunicorn -b 0.0.0.0:$PORT "backend.api.app:app"`) |
| Python | `runtime.txt` pins 3.12.x |

Copy keys from `.env.example` into the host’s environment dashboard. There are no
required secrets; the important free-tier knob is:

- **`ENABLE_SEMANTIC=false`** — skip loading sentence-transformers / PyTorch so the
  process fits in ~512 MB RAM. Matching falls back to exact + fuzzy only.
  (On Render/Railway this already defaults to off. Do **not** install
  `requirements-ml.txt` on free hosts — that pulls multi‑GB CUDA/Torch wheels.)

For local semantic matching: `pip install -r backend/requirements-ml.txt`.

The host injects `PORT`; gunicorn binds to `0.0.0.0:$PORT`. Do not commit a `.env`
file (see the repo-root `.gitignore`).

## Scope & honesty notes

- **The reference vocabulary here is a small, illustrative sample** (~45
  ingredients). The real INCI dictionary has tens of thousands of entries; drop
  a full dataset into `data/` and only `inci_reference.py` changes. Accuracy
  numbers should be measured against a real reference, not this sample.
- The default embedding model is a general-purpose one. A model fine-tuned on
  chemistry / cosmetic terminology would meaningfully improve semantic matches.
- This is a self-directed project built to explore the ingredient-normalization
  problem space. It uses only public ingredient names and a hand-built sample
  reference — no proprietary data.

## Possible next steps

- Swap in a full INCI dataset and build a labeled evaluation set to report
  precision/recall per decision tier.
- Fine-tune or domain-adapt the embedding model on cosmetic vocabulary.
- Add CI-code (`CI 77891`) and allergen handling as dedicated stages.
- Batch upload (CSV in / CSV out) for whole-formula ingestion.
