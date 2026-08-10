"""Web UI for the board of art reviewers.

Run from the repo root (port 8001 so it can run alongside the single-reviewer
app on 8000):
    uv run uvicorn art_board_sdk.server:app --port 8001

Routes:
    GET  /                     the UI
    POST /board-review         run the board on an uploaded image + fields
    GET  /catalog              metadata for the stored artworks (artworks.json)
    GET  /catalog/image/{id}   the stored artwork's image bytes
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

import board  # noqa: E402  (puts ../art_reviewer_sdk on sys.path for `review`)
from review import DEFAULT_MODEL  # noqa: E402

app = FastAPI(title="Art Reviewer Board")

# Stored artwork catalog — reuse the single-reviewer SDK's workbook catalog as the
# single source of truth. Image + preference paths in it are relative to WORKBOOKS.
WORKBOOKS = HERE.parent / "art_reviewer_sdk" / "workbooks"
CATALOG_PATH = WORKBOOKS / "artworks.json"


def _load_catalog() -> dict:
    if not CATALOG_PATH.is_file():
        return {}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _pref_text(rel: str | None) -> str | None:
    """Load a collector-preference profile (path relative to WORKBOOKS) as text."""
    if not rel:
        return None
    p = (WORKBOOKS / rel).resolve()
    return p.read_text(encoding="utf-8") if p.is_file() else None


@app.get("/")
def index():
    # Dev tool — never cache, so edits show on a plain refresh.
    return FileResponse(HERE / "index.html",
                        headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/catalog")
def catalog():
    """Field values (and the two collector-preference profiles) for each stored
    artwork, so the UI can auto-fill the form. Images load via /catalog/image."""
    out = {}
    for cid, a in _load_catalog().items():
        prefs = a.get("preferences", {}) or {}
        out[cid] = {
            "title": a.get("artwork_title", ""),
            "artist": a.get("artist", ""),
            "work_type": a.get("work_type", ""),
            "description": a.get("description", ""),
            "media_note": a.get("media_note", ""),
            "preferences": {
                "related": _pref_text(prefs.get("related")),
                "unrelated": _pref_text(prefs.get("unrelated")),
            },
        }
    return out


@app.get("/catalog/image/{cid}")
def catalog_image(cid: str):
    a = _load_catalog().get(cid)
    if not a:
        raise HTTPException(404, "unknown artwork")
    p = (WORKBOOKS / a["artwork_path"]).resolve()
    if not p.is_file():
        raise HTTPException(404, f"image not found: {p}")
    return FileResponse(p)


@app.post("/board-review")
def post_board_review(
    image: UploadFile,
    model: str = Form(default=""),
    description: str = Form(default=""),
    preferences: str = Form(default=""),
    artwork_name: str = Form(default=""),
    artist: str = Form(default=""),
    work_type: str = Form(default=""),
    media_note: str = Form(default=""),
):
    # Same inputs as the single-reviewer UI, minus the prompt selector: the five
    # board prompts are fixed (board_prompts/*.py + the adjudicator).
    model = model or DEFAULT_MODEL
    data = image.file.read()
    if not data:
        raise HTTPException(400, "empty upload")
    mime = image.content_type or "image/jpeg"
    try:
        result = board.run_board(
            model, data, mime,
            description=description, preferences=preferences,
            artwork_name=artwork_name, artist=artist, work_type=work_type,
            media_note=media_note,
        )
    except Exception as exc:  # surface provider / prompt errors to the page
        raise HTTPException(502, f"{type(exc).__name__}: {exc}")
    return result


@app.post("/board-review-stream")
def post_board_review_stream(
    image: UploadFile,
    model: str = Form(default=""),
    description: str = Form(default=""),
    preferences: str = Form(default=""),
    artwork_name: str = Form(default=""),
    artist: str = Form(default=""),
    work_type: str = Form(default=""),
    media_note: str = Form(default=""),
):
    """Same as /board-review but streams NDJSON progress events (start,
    reviewer_done×N, adjudicator_start, done) so the UI can animate the board."""
    model = model or DEFAULT_MODEL
    data = image.file.read()  # read before streaming; the UploadFile closes after return
    if not data:
        raise HTTPException(400, "empty upload")
    mime = image.content_type or "image/jpeg"

    def gen():
        try:
            for ev in board.run_board_stream(
                model, data, mime,
                description=description, preferences=preferences,
                artwork_name=artwork_name, artist=artist, work_type=work_type,
                media_note=media_note,
            ):
                yield json.dumps(ev) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "message": f"{type(exc).__name__}: {exc}"}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")
