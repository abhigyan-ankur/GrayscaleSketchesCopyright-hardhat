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

from pydantic import BaseModel
from registry import update_entry

from fastapi import Depends, Header
from accounts_db import create_user, get_user_by_email, get_user_by_id, link_wallet, increment_violation
from auth import hash_password, verify_password, create_token, decode_token
import jwt as pyjwt


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



class SignupPayload(BaseModel):
    email: str
    password: str


class LoginPayload(BaseModel):
    email: str
    password: str


class LinkWalletPayload(BaseModel):
    wallet_address: str


def get_current_user(authorization: str = Header(None)) -> dict:
    """
    FastAPI dependency — extracts and verifies the JWT from the
    Authorization header ("Bearer <token>"), returns the user record.
    Raises 401 if missing/invalid/expired.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token")

    user = get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@app.post("/api/auth/signup")
def signup(payload: SignupPayload):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if get_user_by_email(payload.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    password_hash = hash_password(payload.password)
    user = create_user(payload.email, password_hash)
    token = create_token(user["id"], user["email"])

    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "wallet_address": user["wallet_address"]},
    }


@app.post("/api/auth/login")
def login(payload: LoginPayload):
    user = get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user["id"], user["email"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "wallet_address": user["wallet_address"],
            "violation_count": user["violation_count"],
            "is_withheld": bool(user["is_withheld"]),
        },
    }


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "wallet_address": user["wallet_address"],
        "violation_count": user["violation_count"],
        "is_withheld": bool(user["is_withheld"]),
    }


@app.get("/api/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
    """
    Returns everything the Dashboard page needs:
      - my certified artworks (owned by my linked wallet)
      - how many submissions of mine got flagged/rejected as copies
      - how many times MY artworks have been copied by others
      - account status (violation count, withheld or not)
    """
    from registry import get_entries_by_owner, get_attempts_against_owner, get_all_entries

    wallet = user.get("wallet_address")

    my_artworks = get_entries_by_owner(wallet) if wallet else []
    copies_of_my_work = get_attempts_against_owner(wallet) if wallet else []

    return {
        "email": user["email"],
        "wallet_address": wallet,
        "violation_count": user["violation_count"],
        "is_withheld": bool(user["is_withheld"]),
        "certified_count": len(my_artworks),
        "copies_caught_count": len(copies_of_my_work),
        "my_artworks": [_serialize_entry(e) for e in my_artworks],
        "copies_of_my_work": copies_of_my_work,
    }


@app.post("/api/auth/link-wallet")
def link_wallet_endpoint(payload: LinkWalletPayload, user: dict = Depends(get_current_user)):
    link_wallet(user["id"], payload.wallet_address)
    return {"status": "ok", "wallet_address": payload.wallet_address}

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

@app.post("/api/prepare")
async def prepare(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """
    Runs detection + IPFS upload, but does NOT write to the blockchain.
    Requires login — used to track violations and send email notifications.

    If the account is withheld (3+ caught copies), submissions are blocked.
    """
    if user["is_withheld"]:
        raise HTTPException(
            status_code=403,
            detail="Your account has been withheld after 3 flagged submissions. "
                   "You can no longer submit new certifications.",
        )

    suffix = os.path.splitext(file.filename)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = process_upload(tmp_path, title, author, use_ipfs=True, use_blockchain=False)

        # ── Handle a caught copy: track violation + notify ──────────────────
        if result["status"] in ("REJECTED", "FLAGGED_FOR_REVIEW") and result.get("matched_with"):
            updated_user = increment_violation(user["id"])

            from email_service import send_violation_email, send_withheld_email
            send_violation_email(
                to_email=user["email"],
                attempted_title=title,
                matched_title=result["matched_with"]["title"],
                matched_author=result["matched_with"]["author"],
                violation_count=updated_user["violation_count"],
            )
            if updated_user["is_withheld"] and not user["is_withheld"]:
                send_withheld_email(user["email"])

        return _serialize_result(result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)

class ConfirmPayload(BaseModel):
    entry_id: int
    tx_hash: str
    onchain_id: int
    owner_address: str



@app.post("/api/confirm")
def confirm(payload: ConfirmPayload, user: dict = Depends(get_current_user)):
    """
    Called by the frontend after the user's MetaMask transaction confirms.
    Patches the local registry entry with the real tx_hash, on-chain ID,
    and owner wallet address. Sends a certification confirmation email.
    """
    try:
        entry = update_entry(
            payload.entry_id,
            tx_hash=payload.tx_hash,
            onchain_id=payload.onchain_id,
            owner_address=payload.owner_address,
        )

        from email_service import send_certification_email
        send_certification_email(
            to_email=user["email"],
            title=entry["title"],
            author=entry["author"],
            phash=entry["phash"],
            image_cid=entry.get("image_cid") or "",
            tx_hash=entry.get("tx_hash") or "",
        )

        return _serialize_entry(entry)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))



    
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