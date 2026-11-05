"""
review.py
---------
Admin decisions on works the detector flagged as "similar" (SIFT REVIEW band).

Flagged uploads are saved with status "review" (see pipeline._queue_for_review).
No strike is added when they are flagged. An admin then decides:

  approve  the work is original: it is registered on the chain on behalf of the
           submitter (the Hardhat node can sign for any address) and becomes a
           normal certified work, used for matching from then on.
  reject   the work is a copy: it is kept as a record (status "rejected"), the
           copy is logged against the original's owner, and only now does the
           submitter get a violation strike.
"""

from datetime import datetime, timezone

from registry import get_entry, update_entry, get_review_items, log_attempt
from storage import image_url_for
from accounts_db import get_user_by_id, increment_violation
from blockchain_client import BlockchainClient
from email_service import (send_certification_email, send_violation_email,
                           send_withheld_email)


class ReviewError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_item(entry_id: int) -> dict:
    entry = get_entry(entry_id)
    if not entry or not entry.get("review"):
        raise ReviewError(404, f"No review item with id {entry_id}")
    if entry.get("status") != "review":
        raise ReviewError(409, "This item has already been decided.")
    return entry


def list_reviews(decision: str = "open") -> list:
    """decision: 'open' (waiting), 'decided' (approved/rejected) or 'all'."""
    items = []
    for e in get_review_items():
        rv = e["review"]
        decided = rv.get("decision") is not None
        if decision == "open" and decided:
            continue
        if decision == "decided" and not decided:
            continue
        matched = get_entry(rv.get("matched_id")) if rv.get("matched_id") else None
        submitter = get_user_by_id(e["user_id"]) if e.get("user_id") else None
        items.append({
            "id":            e["id"],
            "title":         e["title"],
            "author":        e["author"],
            "image_url":     image_url_for(e),
            "submitted_at":  e["timestamp"],
            "submitted_by":  submitter["email"] if submitter else None,
            "decision":      rv.get("decision"),
            "decided_by":    rv.get("decided_by"),
            "decided_at":    rv.get("decided_at"),
            "sift_inliers":  rv.get("sift_inliers"),
            "inlier_ratio":  rv.get("inlier_ratio"),
            "scale":         rv.get("scale"),
            "mirrored":      bool(rv.get("mirrored")),
            "matched": {
                "id":        rv.get("matched_id"),
                "title":     rv.get("matched_title"),
                "author":    rv.get("matched_author"),
                "image_url": image_url_for(matched) if matched else None,
            },
        })
    items.sort(key=lambda i: i["decided_at"] or i["submitted_at"], reverse=True)
    return items


def approve_review(entry_id: int, admin_email: str) -> dict:
    entry = _open_item(entry_id)
    submitter = get_user_by_id(entry["user_id"]) if entry.get("user_id") else None
    wallet = submitter.get("wallet_address") if submitter else None

    try:
        client = BlockchainClient()
        exists, _ = client.is_phash_registered(entry["phash"])
        if exists:
            raise ReviewError(409, "An identical image is already registered on the chain.")
        res = client.register_artwork(
            entry["title"], entry["author"], entry["phash"],
            entry["image_cid"], entry["metadata_cid"], owner=wallet,
        )
    except ReviewError:
        raise
    except Exception as e:
        raise ReviewError(503, f"Local blockchain not reachable: {e}")

    if not res["success"]:
        raise ReviewError(502, f"Registration failed: {res['error']}")

    review = {**entry["review"], "decision": "approved",
              "decided_by": admin_email, "decided_at": _now()}
    updated = update_entry(
        entry_id, status="certified", tx_hash=res["tx_hash"],
        onchain_id=res["artwork_id"], owner_address=res["owner"], review=review,
    )

    if submitter:
        send_certification_email(
            to_email=submitter["email"], title=updated["title"], author=updated["author"],
            phash=updated["phash"], image_cid=updated.get("image_cid") or "",
            tx_hash=updated.get("tx_hash") or "",
        )
    return updated


def reject_review(entry_id: int, admin_email: str) -> dict:
    entry = _open_item(entry_id)
    rv = entry["review"]
    review = {**rv, "decision": "rejected", "decided_by": admin_email, "decided_at": _now()}
    updated = update_entry(entry_id, status="rejected", review=review)

    matched = get_entry(rv["matched_id"]) if rv.get("matched_id") else None
    if matched:
        log_attempt("REJECTED", entry["title"], entry["author"], matched["id"],
                    matched.get("owner_address"), sift_inliers=rv.get("sift_inliers"),
                    matched_user_id=matched.get("user_id"))

    submitter = get_user_by_id(entry["user_id"]) if entry.get("user_id") else None
    if submitter:
        after = increment_violation(submitter["id"])
        send_violation_email(
            to_email=submitter["email"], attempted_title=entry["title"],
            matched_title=rv.get("matched_title") or "a registered work",
            matched_author=rv.get("matched_author") or "unknown",
            violation_count=after["violation_count"],
        )
        if after["is_withheld"] and not submitter["is_withheld"]:
            send_withheld_email(submitter["email"])
    return updated
