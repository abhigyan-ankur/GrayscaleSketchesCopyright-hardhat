"""
pipeline.py — Full pipeline (Hardhat build)

    validate -> pHash -> (chain duplicate check) -> local pHash filter
             -> SIFT + RANSAC -> store image -> register on chain -> save to registry

Two-stage detection:
  Stage 1A — pHash pre-filter: fast, catches exact / near-exact reposts and
             orders which registry entries get compared with SIFT.
  Stage 1B — SIFT + RANSAC: the real arbiter of every accept / reject / review
             verdict (thresholds validated on 6 real plagiarism pairs).

The registry is persistent (see registry.py), so a new session compares every
new upload against everything certified before.

Two ways to finish a CERTIFIED verdict:
  * server-signed (CLI, /api/register): the backend registers on the local
    chain itself using a Hardhat account.
  * wallet-signed (website): pending=True saves a *pending* row; the browser
    signs the transaction and /api/confirm promotes the row to certified.
"""

from validator   import validate_and_preprocess, ValidationError
from hasher      import compute_phash, phash_distance, PHASH_EXACT_THRESHOLD
from sift_engine import extract_descriptors, match_against
from registry    import register_artwork, get_all_entries, load_descriptors, log_attempt
from storage     import store_artwork, image_url_for


SIFT_CANDIDATE_THRESHOLD = 40


def process_upload(
    filepath: str,
    title: str,
    author: str,
    use_ipfs: bool = True,
    use_blockchain: bool = True,
    check_only: bool = False,
    pending: bool = False,
    owner_address: str = None,
) -> dict:

    # ── Step 1: Validate ────────────────────────────────────────────────────
    try:
        raw_gray, processed_gray = validate_and_preprocess(filepath)
    except ValidationError as e:
        return {"status": "REJECTED", "reason": str(e), "stage": "validation"}

    # ── Step 2: pHash ───────────────────────────────────────────────────────
    new_phash = compute_phash(processed_gray)

    # ── Step 2.5: On-chain duplicate pre-check (free, no gas) ───────────────
    if use_blockchain:
        try:
            from blockchain_client import BlockchainClient
            client = BlockchainClient()
            exists, onchain_id = client.is_phash_registered(new_phash)
            if exists:
                onchain_entry = client.get_artwork(onchain_id)
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

    # ── Step 3: SIFT descriptors ────────────────────────────────────────────
    new_kp, new_desc = extract_descriptors(raw_gray)
    if new_desc is None:
        return {"status": "REJECTED", "reason": "Image has too few features.", "stage": "features"}

    # ── Step 4: Local registry ──────────────────────────────────────────────
    all_entries = get_all_entries()
    if not all_entries:
        if check_only:
            return {"status": "NO_MATCH_FOUND"}
        return _certify(new_phash, new_kp, new_desc, title, author, filepath,
                        use_ipfs, use_blockchain, sift_inliers=None,
                        registry_was_empty=True, owner_address=owner_address,
                        pending=pending)

    # ── Step 5: Stage 1A — pHash exact filter (local) ───────────────────────
    for e in all_entries:
        dist = phash_distance(new_phash, e["phash"])
        if dist <= PHASH_EXACT_THRESHOLD:
            if not check_only:
                log_attempt("REJECTED", title, author, e["id"],
                            e.get("owner_address"), sift_inliers=None)
            return {
                "status": "REJECTED", "reason": "Exact or near-exact duplicate detected.",
                "stage": "phash_filter", "matched_with": _summary(e), "phash_distance": dist,
            }

    # ── Step 6: Stage 1B — SIFT + RANSAC (the actual detector) ──────────────
    candidates = sorted(
        [(phash_distance(new_phash, e["phash"]), e) for e in all_entries], key=lambda x: x[0]
    )
    top_n = max(5, len([e for d, e in candidates if d <= SIFT_CANDIDATE_THRESHOLD]))

    best_inliers, best_entry, best_result = 0, None, None
    for _, entry in candidates[:top_n]:
        try:
            stored_kp, stored_desc = load_descriptors(entry)
        except Exception:
            continue
        result = match_against(new_desc, stored_desc, new_kp, stored_kp)
        if result["inliers"] > best_inliers:
            best_inliers, best_entry, best_result = result["inliers"], entry, result

    # ── Step 7: Verdict ─────────────────────────────────────────────────────
    if best_result is None or best_result["verdict"] == "DIFFERENT":
        if check_only:
            return {"status": "NO_MATCH_FOUND"}
        return _certify(new_phash, new_kp, new_desc, title, author, filepath,
                        use_ipfs, use_blockchain, sift_inliers=best_inliers,
                        owner_address=owner_address, pending=pending)

    if best_result["verdict"] == "REVIEW":
        if not check_only:
            log_attempt("FLAGGED_FOR_REVIEW", title, author, best_entry["id"],
                        best_entry.get("owner_address"), sift_inliers=best_inliers)
        return {
            "status": "FLAGGED_FOR_REVIEW", "stage": "sift_ransac",
            "matched_with": _summary(best_entry), "sift_inliers": best_inliers,
            "inlier_ratio": best_result["inlier_ratio"], "scale_factor": best_result["scale"],
        }

    if not check_only:
        log_attempt("REJECTED", title, author, best_entry["id"],
                    best_entry.get("owner_address"), sift_inliers=best_inliers)
    return {
        "status": "REJECTED", "reason": "Near-duplicate detected via geometric fingerprinting.",
        "stage": "sift_ransac", "matched_with": _summary(best_entry), "sift_inliers": best_inliers,
        "inlier_ratio": best_result["inlier_ratio"], "scale_factor": best_result["scale"],
    }


def _certify(phash, kp, desc, title, author, filepath,
             use_ipfs, use_blockchain, sift_inliers=None, registry_was_empty=False,
             owner_address=None, pending=False) -> dict:

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
        tx_hash=tx_hash, onchain_id=onchain_id,
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

    elif s == "FLAGGED_FOR_REVIEW":
        m = result["matched_with"]
        print(f"  ⚠  FLAGGED FOR REVIEW")
        print(f"     Similar to : '{m['title']}' by {m['author']}")
        print(f"     Inliers    : {result['sift_inliers']} "
              f"(ratio:{result['inlier_ratio']:.0%} scale:{result['scale_factor']:.2f}x)")

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
            print(f"  ✗  REJECTED — plagiarism detected")
            print(f"     Matches   : '{m['title']}' by {m['author']}")
            print(f"     Inliers   : {result['sift_inliers']} "
                  f"(ratio:{result['inlier_ratio']:.0%} scale:{result['scale_factor']:.2f}x)")
        elif stage == "phash_filter":
            m = result["matched_with"]
            print(f"  ✗  REJECTED — exact duplicate (pHash dist:{result['phash_distance']})")
            print(f"     Matches   : '{m['title']}' by {m['author']}")
        else:
            print(f"  ✗  REJECTED — {result['reason']}")

    elif s == "NO_MATCH_FOUND":
        print("  ✓  NO MATCH — nothing registered looks like this image")

    print("═" * W + "\n")
