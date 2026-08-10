"""
api.py
------
Part 5 support: thin FastAPI wrapper around pipeline.py.

Exposes the full detect -> IPFS -> blockchain pipeline as HTTP endpoints
so the React frontend can call it.

Run with:
    uvicorn api:app --reload --port 8000

Docs available at:
    http://localhost:8000/docs
"""

import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pipeline import process_upload
from registry import get_all_entries

app = FastAPI(title="Artwork Copyright Protection API")

# Allow the React dev server to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Artwork Copyright Protection API is running"}


@app.post("/api/register")
async def register(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form(...),
):
    """
    Runs an uploaded image through the full pipeline:
    validate -> pHash -> on-chain duplicate check -> SIFT -> IPFS -> blockchain.

    Returns the same result dict that pipeline.print_result() consumes,
    as JSON, for the frontend to render.
    """
    # Save uploaded file to a temp location (pipeline.py expects a filepath)
    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = process_upload(tmp_path, title, author, use_ipfs=True, use_blockchain=True)
        return _serialize_result(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)  # clean up temp file

@app.post("/api/check")
async def check(file: UploadFile = File(...)):
    """
    Checks if an uploaded image matches anything already registered,
    WITHOUT certifying it. Pure verification — no IPFS upload, no
    blockchain write, no local registry write.

    Used by the Search page for "is my work protected?" or
    "is this a copy of something?" queries.
    """
    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = process_upload(
            tmp_path, "Search Check", "Search",
            use_ipfs=True, use_blockchain=True, check_only=True,
        )
        return _serialize_result(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)

@app.get("/api/gallery")
def gallery():
    """Returns all locally registered artworks (mirrors on-chain state)."""
    entries = get_all_entries()
    return [_serialize_entry(e) for e in entries]


def _serialize_result(result: dict) -> dict:
    """Converts a pipeline result dict into a JSON-safe structure."""
    out = {"status": result["status"]}
    
    if result["status"] == "NO_MATCH_FOUND":
        return out
    
    if result["status"] == "CERTIFIED":
        out["certificate"] = _serialize_entry(result["certificate"])
        out["registry_was_empty"] = result.get("registry_was_empty", False)
        out["ipfs_warning"] = result.get("ipfs_warning")
        out["blockchain_warning"] = result.get("blockchain_warning")

    elif result["status"] == "FLAGGED_FOR_REVIEW":
        out["matched_with"] = result.get("matched_with")
        out["sift_inliers"] = result.get("sift_inliers")
        out["inlier_ratio"] = result.get("inlier_ratio")
        out["scale_factor"] = result.get("scale_factor")

    elif result["status"] == "REJECTED":
        out["reason"] = result.get("reason")
        out["stage"] = result.get("stage")
        out["matched_with"] = result.get("matched_with")
        out["sift_inliers"] = result.get("sift_inliers")
        out["inlier_ratio"] = result.get("inlier_ratio")
        out["scale_factor"] = result.get("scale_factor")
        out["phash_distance"] = result.get("phash_distance")

    return out


def _serialize_entry(e: dict) -> dict:
    """Strips non-JSON-safe fields (like desc_path) from a registry entry."""
    return {
        "id":           e.get("id"),
        "title":        e.get("title"),
        "author":       e.get("author"),
        "phash":        e.get("phash"),
        "image_cid":    e.get("image_cid"),
        "metadata_cid": e.get("metadata_cid"),
        "timestamp":    e.get("timestamp"),
        "tx_hash":      e.get("tx_hash"),
        "onchain_id":   e.get("onchain_id"),
        "kp_count":     e.get("kp_count"),
    }