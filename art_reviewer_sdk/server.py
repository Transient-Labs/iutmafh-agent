"""Minimal web UI for the direct art reviewer.

Run from the repo root:
    uv run uvicorn art_reviewer_sdk.server:app --port 8000

One page (GET /), one endpoint (POST /review) that calls the same
review_image() the CLI uses.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from review import DEFAULT_MODEL, review_image

app = FastAPI(title="Art Reviewer")


@app.get("/")
def index():
    # Dev tool — never cache the page, so edits show on a plain refresh.
    return FileResponse(
        HERE / "index.html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.post("/review")
def post_review(
    image: UploadFile,
    model: str = Form(default=""),
    temperature: str = Form(default=""),
    top_p: str = Form(default=""),
    max_tokens: str = Form(default=""),
    description: str = Form(default=""),
    preferences: str = Form(default=""),
):
    model = model or os.environ.get("ART_REVIEWER_MODEL", DEFAULT_MODEL)
    data = image.file.read()
    if not data:
        raise HTTPException(400, "empty upload")
    mime = image.content_type or "image/jpeg"

    knobs = {}
    try:
        if temperature:
            knobs["temperature"] = float(temperature)
        if top_p:
            knobs["top_p"] = float(top_p)
        if max_tokens:
            knobs["max_tokens"] = int(max_tokens)
    except ValueError as exc:
        raise HTTPException(400, f"bad knob value: {exc}")

    try:
        review = review_image(model, data, mime, knobs, description, preferences)
    except Exception as exc:  # surface provider errors to the page
        raise HTTPException(502, f"{type(exc).__name__}: {exc}")
    return {"model": model, "review": review}
