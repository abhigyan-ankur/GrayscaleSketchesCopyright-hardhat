"""
api.py
------
FastAPI wrapper around pipeline.py for the React frontend (Hardhat build).

Run with:
    uvicorn api:app --reload --port 8000
Docs:
    http://localhost:8000/docs

On startup it connects to the local Hardhat node, deploys the contract if the
chain is empty, and re-registers every saved artwork so the chain matches the
persistent registry.
"""

import os
import shutil
import tempfile
from contextlib import asynccontextmanager

import jwt as pyjwt
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from web3 import Web3

from config import IMAGES_DIR
from pipeline import process_upload
from registry import (get_all_entries, get_entry, update_entry, purge_pending,
                      get_entries_by_owner, get_attempts_against_owner, norm_addr)
from storage import image_url_for
from blockchain_client import BlockchainClient, BlockchainError
from accounts_db import (create_user, get_user_by_email, get_user_by_id,
                         link_wallet, increment_violation)
from auth import hash_password, verify_password, create_token, decode_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    purge_pending(24)
    try:
        client = BlockchainClient()          # deploys the contract if needed
        client.sync_registry()               # re-fills a fresh chain from the registry
        print(f"[chain] ready: contract {client.contract_address}, "
              f"{client.get_total_artworks()} artwork(s) on-chain")
    except Exception as e:
        print(f"[chain] ⚠ not ready yet: {e}\n"
              f"        Start the node (cd contracts && npx hardhat node); "
              f"the API will sync on the next request.")
    yield


app = FastAPI(title="Artwork Copyright Protection API (Hardhat)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(IMAGES_DIR, exist_ok=True)
app.mount("/files", StaticFiles(directory=IMAGES_DIR), name="files")


# ── helpers ──────────────────────────────────────────────────────────────────

def _save_upload(file: UploadFile) -> str:
    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        return tmp.name


def _serialize_entry(e: dict) -> dict:
    """Strips internal fields; adds a browser-ready image_url."""
    return {
        "id":            e.get("id"),
        "title":         e.get("title"),
        "author":        e.get("author"),
        "phash":         e.get("phash"),
        "image_cid":     e.get("image_cid"),
        "metadata_cid":  e.get("metadata_cid"),
        "image_url":     image_url_for(e),
        "timestamp":     e.get("timestamp"),
        "tx_hash":       e.get("tx_hash"),
        "onchain_id":    e.get("onchain_id"),
        "owner_address": e.get("owner_address"),
        "kp_count":      e.get("kp_count"),
        "status":        e.get("status", "certified"),
    }


def _serialize_result(result: dict) -> dict:
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


# ── health + chain ───────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Artwork Copyright Protection API is running"}


@app.get("/api/chain/info")
def chain_info():
    """Chain id, RPC, contract address and the Hardhat demo accounts. The frontend
    reads this instead of hardcoding addresses. Calling it also heals a node that
    was restarted (redeploys + re-syncs)."""
    try:
        return BlockchainClient().info()
    except BlockchainError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Local blockchain not reachable: {e}")


@app.post("/api/chain/sync")
def chain_sync():
    try:
        return BlockchainClient().sync_registry()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── detection endpoints ──────────────────────────────────────────────────────

@app.post("/api/register")
async def register(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form(...),
):
    """Server-signed registration (no wallet): detect -> store -> register on the
    local chain with the platform account."""
    tmp_path = _save_upload(file)
    try:
        result = process_upload(tmp_path, title, author, use_ipfs=True, use_blockchain=True)
        return _serialize_result(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


@app.post("/api/check")
async def check(file: UploadFile = File(...)):
    """Is this image already registered? Pure lookup, nothing is saved."""
    tmp_path = _save_upload(file)
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
    """All certified artworks (mirrors on-chain state)."""
    return [_serialize_entry(e) for e in get_all_entries()]


# ── accounts ─────────────────────────────────────────────────────────────────

class SignupPayload(BaseModel):
    email: str
    password: str


class LoginPayload(BaseModel):
    email: str
    password: str


class LinkWalletPayload(BaseModel):
    wallet_address: str


def get_current_user(authorization: str = Header(None)) -> dict:
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

    user = create_user(payload.email, hash_password(payload.password))
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


@app.post("/api/auth/link-wallet")
def link_wallet_endpoint(payload: LinkWalletPayload, user: dict = Depends(get_current_user)):
    wallet = norm_addr(payload.wallet_address)
    link_wallet(user["id"], wallet)
    return {"status": "ok", "wallet_address": wallet}


@app.get("/api/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
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


# ── website flow: prepare (detect + store) -> wallet signs -> confirm ────────

@app.post("/api/prepare")
async def prepare(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """
    Detection + storing, but NO blockchain write. A CERTIFIED verdict creates a
    *pending* registry row that only becomes certified once /api/confirm sees
    the signed transaction. Rejecting the wallet popup therefore leaves nothing
    behind.
    """
    if user["is_withheld"]:
        raise HTTPException(
            status_code=403,
            detail="Your account has been withheld after 3 flagged submissions. "
                   "You can no longer submit new certifications.",
        )

    tmp_path = _save_upload(file)
    try:
        result = process_upload(tmp_path, title, author, use_ipfs=True,
                                use_blockchain=False, pending=True,
                                owner_address=user.get("wallet_address"))

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
    onchain_id: int | None = None
    owner_address: str | None = None


@app.post("/api/confirm")
def confirm(payload: ConfirmPayload, user: dict = Depends(get_current_user)):
    """
    Called after the wallet's transaction is mined. The backend checks the
    receipt on the local chain (so a made-up hash is refused) and then promotes
    the pending row to certified.
    """
    entry = get_entry(payload.entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"No entry with id {payload.entry_id}")

    try:
        client = BlockchainClient(auto_sync=False)
        receipt = client.w3.eth.get_transaction_receipt(payload.tx_hash)
    except Exception as e:
        raise HTTPException(status_code=400,
                            detail=f"Transaction not found on the local chain: {e}")

    if receipt.status != 1:
        raise HTTPException(status_code=400, detail="That transaction failed on-chain.")
    if Web3.to_checksum_address(receipt["to"]) != Web3.to_checksum_address(client.contract_address):
        raise HTTPException(status_code=400, detail="Transaction was not sent to the registry contract.")

    owner = norm_addr(receipt["from"])
    onchain_id = payload.onchain_id
    if onchain_id is None:
        try:
            exists, found = client.is_phash_registered(entry["phash"])
            onchain_id = int(found) if exists else None
        except Exception:
            onchain_id = None

    updated = update_entry(
        payload.entry_id,
        status="certified",
        tx_hash=payload.tx_hash,
        onchain_id=onchain_id,
        owner_address=owner,
    )

    if not user.get("wallet_address"):           # first certification links the wallet
        link_wallet(user["id"], owner)

    from email_service import send_certification_email
    send_certification_email(
        to_email=user["email"],
        title=updated["title"],
        author=updated["author"],
        phash=updated["phash"],
        image_cid=updated.get("image_cid") or "",
        tx_hash=updated.get("tx_hash") or "",
    )
    return _serialize_entry(updated)
