"""
Flask application (HTTP layer only).

Single responsibility: expose the normalization pipeline over HTTP and serve
the static frontend. No matching logic lives here — every route delegates to
the pipeline and serializes via schemas. The pipeline is built once at
startup (loading the reference and embedding model is expensive) and reused.
"""
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from ..core.pipeline import NormalizationPipeline
from . import schemas

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = Flask(__name__, static_folder=None)
pipeline = NormalizationPipeline()  # built once, reused across requests


@app.get("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "reference_size": len(pipeline.reference),
            "semantic_available": pipeline.semantic_available,
        }
    )


@app.post("/api/normalize")
def normalize():
    """
    Body: {"text": "<pasted ingredient list>"}  OR  {"items": ["...", "..."]}
    Returns per-item verdicts plus a summary roll-up.
    """
    payload = request.get_json(silent=True) or {}

    if "items" in payload and isinstance(payload["items"], list):
        items = [str(x) for x in payload["items"]]
    else:
        items = NormalizationPipeline.parse_raw_list(str(payload.get("text", "")))

    if not items:
        return jsonify({"error": "No ingredients provided."}), 400

    results = pipeline.normalize_list(items)
    return jsonify(
        {
            "summary": schemas.summarize(results),
            "results": [schemas.item_result_to_dict(r) for r in results],
        }
    )

# --- static frontend ----------------------------------------------------

@app.get("/")
def homepage():
    return send_from_directory(FRONTEND_DIR, "homepage.html")


@app.get("/app")
def app_page():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename: str):
    return send_from_directory(FRONTEND_DIR, filename)
