"""
pipeline.py — Full pipeline (Hardhat build)

    validate -> pHash -> (chain duplicate check) -> local pHash filter
             -> SIFT + RANSAC -> store image -> register on chain -> save to registry

Two-stage detection:
  Stage 1A — pHash pre-filter: fast, catches exact / near-exact reposts and
             orders which registry entries get compared with SIFT.
  Stage 1B — SIFT + RANSAC: the real arbiter of every accept / reject / review
             verdict (thresholds validated on 6 real plagiarism pairs).

Mirrored copies: SIFT and pHash are not mirror-invariant, so every upload is
also checked in its horizontally flipped form.

Own work: if the match is the uploader's own artwork (same account or same
wallet) it is reported as ALREADY_OWNED. It is not a violation and is not
logged as a copy attempt.

Flagged works ("similar", not a clear copy) are not punished automatically:
they are saved in the review queue (status "review") and an admin approves or
rejects them (see review.py). A strike is only added when a copy is confirmed.

Two ways to finish a CERTIFIED verdict:
  * server-signed (CLI, /api/register): the backend registers on the local
    chain itself using a Hardhat account.
  * wallet-signed (website): pending=True saves a *pending* row; the browser
    signs the transaction and /api/confirm promotes the row to certified.
"""

import numpy as np

from validator   import validate_and_preprocess, ValidationError
from hasher      import compute_phash, phash_distance, PHASH_EXACT_THRESHOLD
from sift_engine import extract_descriptors, extract_mirrored_descriptors, match_against
from registry    import (register_artwork, get_all_entries, load_descriptors,
                         log_attempt, norm_addr)
from storage     import store_artwork, image_url_for


SIFT_CANDIDATE_THRESHOLD = 40


def _is_own(entry: dict, user_id, wallet) -> bool:
    """True if this registered work belongs to the uploader."""
    if user_id is not None and entry.get("user_id") == user_id:
        return True
    w = norm_addr(wallet)
    return bool(w) and norm_addr(entry.get("owner_address")) == w


def _log_copy(verdict, title, author, entry, sift_inliers=None):
    log_attempt(verdict, title, author, entry["id"], entry.get("owner_address"),
                sift_inliers=sift_inliers, matched_user_id=entry.get("user_id"))


def _already_owned(entry, stage, **extra) -> dict:
    return {"status": "ALREADY_OWNED", "stage": stage,
            "reason": "You already registered this artwork.",
            "matched_with": _summary(entry), **extra}


def process_upload(
    filepath: str,
    title: str,
    author: str,
    use_ipfs: bool = True,
    use_blockchain: bool = True,
    check_only: bool = False,
    pending: bool = False,
    owner_address: str = None,
    user_id: int = None,
) -> dict:

    # ── Step 1: Validate ────────────────────────────────────────────────────
    try:
        raw_gray, processed_gray = validate_and_preprocess(filepath)
    except ValidationError as e:
        return {"status": "REJECTED", "reason": str(e), "stage": "validation"}

    # ── Step 2: pHash (original + mirrored) ─────────────────────────────────
    new_phash = compute_phash(processed_gray)
    mirror_phash = compute_phash(np.ascontiguousarray(np.fliplr(processed_gray)))

    # ── Step 2.5: On-chain duplicate pre-check (free, no gas) ───────────────
    if use_blockchain:
        try:
            from blockchain_client import BlockchainClient
            client = BlockchainClient()
            exists, onchain_id = client.is_phash_registered(new_phash)
            if exists:
                onchain_entry = client.get_artwork(onchain_id)
                if owner_address and norm_addr(onchain_entry["owner"]) == norm_addr(owner_address):
                    return {"status": "ALREADY_OWNED", "stage": "blockchain_phash_check",
                            "reason": "You already registered this artwork.",
                            "matched_with": {"id": onchain_id, "title": onchain_entry["title"],
                                             "author": onchain_entry["author"],
                                             "owner": onchain_entry["owner"]}}
                if not check_only:
                    log_attempt("REJECTED", title, author, onchain_id,
                                onchain_entry["owner"], sift_inliers=None)
                return {
                    "status": "REJECTED",
                    "reason": "Exact duplicate — already certified on-chain.",
                    "stage":  "blockchain_phash_check",
                    "matched_with": {
                        "id": onchain_id,
                        "title": onchain_entry["title"],
                        "author": onchain_entry["author"],
                        "owner": onchain_entry["owner"],
                    },
                }
        except Exception as e:
            print(f"  ⚠ Blockchain pre-check unavailable, continuing with local checks: {e}")

    # ── Step 3: SIFT descriptors (original + mirrored) ──────────────────────
    new_kp, new_desc = extract_descriptors(raw_gray)
    if new_desc is None:
        return {"status": "REJECTED", "reason": "Image has too few features.", "stage": "features"}
    mirror_kp, mirror_desc = extract_mirrored_descriptors(raw_gray)

    # ── Step 4: Local registry (certified works only) ───────────────────────
    all_entries = get_all_entries()
    if not all_entries:
        if check_only:
            return {"status": "NO_MATCH_FOUND"}
        return _certify(new_phash, new_kp, new_desc, title, author, filepath,
                        use_ipfs, use_blockchain, sift_inliers=None,
                        registry_was_empty=True, owner_address=owner_address,
                        pending=pending, user_id=user_id)

    # ── Step 5: Stage 1A — pHash exact filter (local, also mirrored) ────────
    for e in all_entries:
        dist = phash_distance(new_phash, e["phash"])
        mdist = phash_distance(mirror_phash, e["phash"])
        if min(dist, mdist) <= PHASH_EXACT_THRESHOLD:
            mirrored = dist > PHASH_EXACT_THRESHOLD
            if _is_own(e, user_id, owner_address):
                return _already_owned(e, "phash_filter", phash_distance=min(dist, mdist),
                                      mirrored=mirrored)
            if not check_only:
                _log_copy("REJECTED", title, author, e)
            return {
                "status": "REJECTED",
                "reason": ("Mirrored (flipped) copy detected." if mirrored
                           else "Exact or near-exact duplicate detected."),
                "stage": "phash_filter", "matched_with": _summary(e),
                "phash_distance": min(dist, mdist), "mirrored": mirrored,
            }

    # ── Step 6: Stage 1B — SIFT + RANSAC (the actual detector) ──────────────
    candidates = sorted(
        [(min(phash_distance(new_phash, e["phash"]),
              phash_distance(mirror_phash, e["phash"])), e) for e in all_entries],
        key=lambda x: x[0],
    )
    top_n = max(5, len([e for d, e in candidates if d <= SIFT_CANDIDATE_THRESHOLD]))

    variants = [(False, new_kp, new_desc)]
    if mirror_desc is not None:
        variants.append((True, mirror_kp, mirror_desc))

    best_inliers, best_entry, best_result, best_mirrored = 0, None, None, False
    for _, entry in candidates[:top_n]:
        try:
            stored_kp, stored_desc = load_descriptors(entry)
        except Exception:
            continue
        for mirrored, kp, desc in variants:
            result = match_against(desc, stored_desc, kp, stored_kp)
            if result["inliers"] > best_inliers:
                best_inliers, best_entry, best_result = result["inliers"], entry, result
                best_mirrored = mirrored

    # ── Step 7: Verdict ─────────────────────────────────────────────────────
    if best_result is None or best_result["verdict"] == "DIFFERENT":
        if check_only:
            return {"status": "NO_MATCH_FOUND"}
        return _certify(new_phash, new_kp, new_desc, title, author, filepath,
                        use_ipfs, use_blockchain, sift_inliers=best_inliers,
                        owner_address=owner_address, pending=pending, user_id=user_id)

    detail = {
        "sift_inliers": best_inliers, "inlier_ratio": best_result["inlier_ratio"],
        "scale_factor": best_result["scale"], "mirrored": best_mirrored,
    }
    own = _is_own(best_entry, user_id, owner_address)

    if best_result["verdict"] == "REVIEW":
        if own:
            # A variation of your own work is fine: certify it as a new work.
            if check_only:
                return {"status": "NO_MATCH_FOUND"}
            return _certify(new_phash, new_kp, new_desc, title, author, filepath,
                            use_ipfs, use_blockchain, sift_inliers=best_inliers,
                            owner_address=owner_address, pending=pending, user_id=user_id)
        out = {"status": "FLAGGED_FOR_REVIEW", "stage": "sift_ransac",
               "matched_with": _summary(best_entry), **detail}
        if not check_only:
            queued = _queue_for_review(new_phash, new_kp, new_desc, title, author,
                                       filepath, best_entry, detail, owner_address, user_id)
            out["review_id"] = queued["id"]
        return out

    # verdict MATCH
    if own:
        return _already_owned(best_entry, "sift_ransac", **detail)
    if not check_only:
        _log_copy("REJECTED", title, author, best_entry, sift_inliers=best_inliers)
    return {
        "status": "REJECTED",
        "reason": ("Mirrored copy detected via geometric fingerprinting." if best_mirrored
                   else "Near-duplicate detected via geometric fingerprinting."),
        "stage": "sift_ransac", "matched_with": _summary(best_entry), **detail,
    }


def _queue_for_review(phash, kp, desc, title, author, filepath, matched, detail,
                      owner_address, user_id) -> dict:
    """Saves a flagged upload (image + SIFT data) with status 'review'. No strike
    is added now; an admin decides (review.py)."""
    stored = store_artwork(filepath, title, author, phash, allow_ipfs=False)
    return register_artwork(
        phash=phash, keypoints=kp, descriptors=desc, title=title, author=author,
        filepath=filepath, image_cid=stored["image_cid"],
        metadata_cid=stored["metadata_cid"], owner_address=owner_address,
        local_image=stored["local_image"], status="review", user_id=user_id,
        review={
            "matched_id": matched["id"], "matched_title": matched["title"],
            "matched_author": matched["author"],
            "sift_inliers": detail["sift_inliers"], "inlier_ratio": detail["inlier_ratio"],
            "scale": detail["scale_factor"], "mirrored": detail["mirrored"],
            "decision": None,
        },
    )


def _certify(phash, kp, desc, title, author, filepath,
             use_ipfs, use_blockchain, sift_inliers=None, registry_was_empty=False,
             owner_address=None, pending=False, user_id=None) -> dict:

    tx_hash = onchain_id = None
    storage_warning = blockchain_warning = None

    # ── Keep the image + certificate metadata ───────────────────────────────
    print("  Storing artwork...")
    stored = store_artwork(filepath, title, author, phash, allow_ipfs=use_ipfs)
    storage_warning = stored.get("warning")
    print(f"  ✓ Image ID : {stored['image_cid']}  ({stored['storage']})")
    if storage_warning:
        print(f"  ⚠ {storage_warning}")

    # ── Server-signed blockchain registration (CLI / /api/register) ─────────
    if use_blockchain and not pending:
        try:
            from blockchain_client import BlockchainClient
            print("  Registering on the local blockchain...")
            client = BlockchainClient()
            res = client.register_artwork(
                title, author, phash, stored["image_cid"], stored["metadata_cid"],
                owner=owner_address,
            )
            if res["success"]:
                tx_hash, onchain_id = res["tx_hash"], res["artwork_id"]
                owner_address = res["owner"]
                print(f"  ✓ On-chain ID : {onchain_id}")
                print(f"  ✓ Tx hash     : {tx_hash}")
            else:
                blockchain_warning = res["error"]
                print(f"  ⚠ Blockchain registration failed: {res['error']}")
        except Exception as e:
            blockchain_warning = str(e)
            print(f"  ⚠ Blockchain unavailable (will sync when the node is back): {e}")

    # ── Registry (always; this is what future uploads are matched against) ──
    entry = register_artwork(
        phash=phash, keypoints=kp, descriptors=desc, title=title, author=author,
        filepath=filepath, image_cid=stored["image_cid"],
        metadata_cid=stored["metadata_cid"], owner_address=owner_address,
        local_image=stored["local_image"],
        status="pending" if pending else "certified",
        tx_hash=tx_hash, onchain_id=onchain_id, user_id=user_id,
    )

    res = {"status": "CERTIFIED", "certificate": entry, "stage": "registration",
           "sift_inliers": sift_inliers}
    if registry_was_empty:
        res["registry_was_empty"] = True
    if storage_warning:
        res["ipfs_warning"] = storage_warning
    if blockchain_warning:
        res["blockchain_warning"] = blockchain_warning
    return res


def _summary(e):
    return {
        "id": e["id"], "title": e["title"], "author": e["author"],
        "registered_on": e["timestamp"],
        "image_url": image_url_for(e),
    }


def print_result(result: dict):
    W = 64
    print("\n" + "═" * W)
    s = result["status"]

    if s == "CERTIFIED":
        c = result["certificate"]
        print(f"  ✓  CERTIFIED")
        print(f"     Title      : {c['title']}")
        print(f"     Author     : {c['author']}")
        print(f"     pHash      : {c['phash']}")
        print(f"     Keypoints  : {c['kp_count']}")
        print(f"     Time       : {c['timestamp']}")
        if c.get("image_cid"):
            print(f"     Image ID   : {c['image_cid']}")
        if c.get("onchain_id"):
            print(f"     On-chain ID: {c['onchain_id']}")
            print(f"     Tx hash    : {c['tx_hash']}")
            print(f"     Owner      : {c.get('owner_address')}")
        if result.get("ipfs_warning"):
            print(f"     ⚠ Storage: {result['ipfs_warning']}")
        if result.get("blockchain_warning"):
            print(f"     ⚠ Blockchain: {result['blockchain_warning']}")

    elif s == "ALREADY_OWNED":
        m = result["matched_with"]
        print(f"  ℹ  ALREADY REGISTERED BY YOU")
        print(f"     '{m['title']}' (no violation recorded)")

    elif s == "FLAGGED_FOR_REVIEW":
        m = result["matched_with"]
        print(f"  ⚠  FLAGGED FOR REVIEW")
        print(f"     Similar to : '{m['title']}' by {m['author']}"
              f"{'  (mirrored)' if result.get('mirrored') else ''}")
        print(f"     Inliers    : {result['sift_inliers']} "
              f"(ratio:{result['inlier_ratio']:.0%} scale:{result['scale_factor']:.2f}x)")
        if result.get("review_id"):
            print(f"     Sent to the review queue as #{result['review_id']}; "
                  f"an admin will approve or reject it.")

    elif s == "REJECTED":
        stage = result.get("stage", "")
        if stage == "blockchain_phash_check":
            m = result["matched_with"]
            print(f"  ✗  REJECTED — already certified on-chain")
            print(f"     On-chain ID: {m['id']}")
            print(f"     Matches    : '{m['title']}' by {m['author']}")
            print(f"     Owner addr : {m['owner']}")
        elif stage == "sift_ransac":
            m = result["matched_with"]
            print(f"  ✗  REJECTED — plagiarism detected"
                  f"{' (mirrored copy)' if result.get('mirrored') else ''}")
            print(f"     Matches   : '{m['title']}' by {m['author']}")
            print(f"     Inliers   : {result['sift_inliers']} "
                  f"(ratio:{result['inlier_ratio']:.0%} scale:{result['scale_factor']:.2f}x)")
        elif stage == "phash_filter":
            m = result["matched_with"]
            print(f"  ✗  REJECTED — {'mirrored copy' if result.get('mirrored') else 'exact duplicate'}"
                  f" (pHash dist:{result['phash_distance']})")
            print(f"     Matches   : '{m['title']}' by {m['author']}")
        else:
            print(f"  ✗  REJECTED — {result['reason']}")

    elif s == "NO_MATCH_FOUND":
        print("  ✓  NO MATCH — nothing registered looks like this image")

    print("═" * W + "\n")
