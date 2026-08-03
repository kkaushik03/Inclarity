"""
Flask application (HTTP layer only).

Single responsibility: expose the normalization pipeline over HTTP and serve
the static frontend. No matching logic lives here — every route delegates to
the pipeline and serializes via schemas. The pipeline is built once on first
use (loading the reference — and optionally the embedding model — is
expensive) and reused.
"""
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from ..core.pipeline import NormalizationPipeline
from . import schemas

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

app = Flask(__name__, static_folder=None)
_pipeline: NormalizationPipeline | None = None


def get_pipeline() -> NormalizationPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = NormalizationPipeline()
    return _pipeline


@app.get("/api/health")
def health():
    pipeline = get_pipeline()
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

    results = get_pipeline().normalize_list(items)
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
    if filename.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(FRONTEND_DIR, filename)


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
