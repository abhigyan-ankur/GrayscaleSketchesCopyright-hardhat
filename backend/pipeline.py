"""
pipeline.py — Full pipeline: Part 1 (detection) + Part 2 (IPFS) + Part 4 (blockchain)

Flow on CERTIFIED verdict:
  1. Upload image to IPFS       -> image_cid
  2. Upload metadata to IPFS    -> metadata_cid
  3. Register on blockchain     -> tx_hash, on-chain artwork_id
  4. Store everything in local registry (mirrors on-chain state for fast reads)

use_ipfs=False and use_blockchain=False allow offline testing of just
the detection logic without needing Pinata or a funded wallet.
"""

from validator   import validate_and_preprocess, ValidationError
from hasher      import compute_phash, phash_distance, PHASH_EXACT_THRESHOLD
from sift_engine import extract_descriptors, match_against
from registry    import register_artwork, get_all_entries, load_descriptors

SIFT_CANDIDATE_THRESHOLD = 40


def process_upload(
    filepath: str,
    title: str,
    author: str,
    use_ipfs: bool = True,
    use_blockchain: bool = True,
) -> dict:

    # ── Step 1: Validate ────────────────────────────────────────────────────
    try:
        raw_gray, processed_gray = validate_and_preprocess(filepath)
    except ValidationError as e:
        return {"status": "REJECTED", "reason": str(e), "stage": "validation"}

    # ── Step 2: pHash ───────────────────────────────────────────────────────
    new_phash = compute_phash(processed_gray)

    # ── Step 2.5: On-chain duplicate pre-check (free, no gas) ───────────────
    # Check the blockchain FIRST if enabled — this is the authoritative
    # source of truth. Local registry is just a fast local mirror.
    if use_blockchain:
        try:
            from blockchain_client import BlockchainClient
            client = BlockchainClient()
            exists, onchain_id = client.is_phash_registered(new_phash)
            if exists:
                onchain_entry = client.get_artwork(onchain_id)
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

    # ── Step 3: SIFT descriptors ──────────────────────────────────────────────
    new_kp, new_desc = extract_descriptors(raw_gray)
    if new_desc is None:
        return {"status": "REJECTED", "reason": "Image has too few features.", "stage": "features"}

    # ── Step 4: Local registry (mirrors blockchain, faster for SIFT search) ──
    all_entries = get_all_entries()
    if not all_entries:
        return _certify(new_phash, new_kp, new_desc, title, author, filepath,
                        use_ipfs, use_blockchain, sift_inliers=None, registry_was_empty=True)

    # ── Step 5: Stage 1A — pHash exact filter (local) ────────────────────────
    for e in all_entries:
        dist = phash_distance(new_phash, e["phash"])
        if dist <= PHASH_EXACT_THRESHOLD:
            return {
                "status": "REJECTED", "reason": "Exact or near-exact duplicate detected.",
                "stage": "phash_filter", "matched_with": _summary(e), "phash_distance": dist,
            }

    # ── Step 6: Stage 1B — SIFT + RANSAC ────────────────────────────────────
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

    # ── Step 7: Verdict ──────────────────────────────────────────────────────
    if best_result is None or best_result["verdict"] == "DIFFERENT":
        return _certify(new_phash, new_kp, new_desc, title, author, filepath,
                        use_ipfs, use_blockchain, sift_inliers=best_inliers)

    if best_result["verdict"] == "REVIEW":
        return {
            "status": "FLAGGED_FOR_REVIEW", "stage": "sift_ransac",
            "matched_with": _summary(best_entry), "sift_inliers": best_inliers,
            "inlier_ratio": best_result["inlier_ratio"], "scale_factor": best_result["scale"],
        }

    return {
        "status": "REJECTED", "reason": "Near-duplicate detected via geometric fingerprinting.",
        "stage": "sift_ransac", "matched_with": _summary(best_entry), "sift_inliers": best_inliers,
        "inlier_ratio": best_result["inlier_ratio"], "scale_factor": best_result["scale"],
    }


def _certify(phash, kp, desc, title, author, filepath,
             use_ipfs, use_blockchain, sift_inliers=None, registry_was_empty=False) -> dict:

    image_cid = metadata_cid = gateway_url = None
    ipfs_warning = blockchain_warning = None
    tx_hash = onchain_id = None

    # ── IPFS upload ──────────────────────────────────────────────────────────
    if use_ipfs:
        try:
            from ipfs_client import upload_image, upload_metadata, get_gateway_url
            print("  Uploading to IPFS...")
            image_cid    = upload_image(filepath, title, author)
            metadata_cid = upload_metadata({
                "title": title, "author": author, "image_cid": image_cid, "phash": phash
            })
            gateway_url = get_gateway_url(image_cid)
            print(f"  ✓ Image CID : {image_cid}")
            print(f"  ✓ Meta  CID : {metadata_cid}")
        except Exception as e:
            ipfs_warning = str(e)
            print(f"  ⚠ IPFS failed (local fallback): {e}")

    # ── Blockchain registration ─────────────────────────────────────────────
    if use_blockchain and image_cid and metadata_cid:
        try:
            from blockchain_client import BlockchainClient, get_explorer_url
            print("  Registering on blockchain...")
            client = BlockchainClient()
            result = client.register_artwork(title, author, phash, image_cid, metadata_cid)

            if result["success"]:
                tx_hash    = result["tx_hash"]
                onchain_id = result["artwork_id"]
                print(f"  ✓ On-chain ID : {onchain_id}")
                print(f"  ✓ Tx hash     : {tx_hash}")
                print(f"  ✓ Explorer    : {get_explorer_url(tx_hash)}")
            else:
                blockchain_warning = result["error"]
                print(f"  ⚠ Blockchain registration failed: {result['error']}")
        except Exception as e:
            blockchain_warning = str(e)
            print(f"  ⚠ Blockchain unavailable: {e}")
    elif use_blockchain and not image_cid:
        blockchain_warning = "Skipped — blockchain registration requires IPFS CIDs (use_ipfs must succeed first)"

    # ── Local registry (always happens, mirrors on-chain/IPFS state) ────────
    entry = register_artwork(
        phash=phash, keypoints=kp, descriptors=desc, title=title, author=author,
        filepath=gateway_url or filepath, image_cid=image_cid, metadata_cid=metadata_cid,
    )
    entry["tx_hash"]    = tx_hash
    entry["onchain_id"] = onchain_id

    res = {"status": "CERTIFIED", "certificate": entry, "stage": "registration",
           "sift_inliers": sift_inliers}
    if registry_was_empty:
        res["registry_was_empty"] = True
    if ipfs_warning:
        res["ipfs_warning"] = ipfs_warning
    if blockchain_warning:
        res["blockchain_warning"] = blockchain_warning
    return res


def _summary(e):
    cid = e.get("image_cid")
    return {
        "id": e["id"], "title": e["title"], "author": e["author"],
        "registered_on": e["timestamp"],
        "image_url": f"https://gateway.pinata.cloud/ipfs/{cid}" if cid else None,
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
            print(f"     Image CID  : {c['image_cid']}")
            print(f"     IPFS URL   : https://gateway.pinata.cloud/ipfs/{c['image_cid']}")
        if c.get("onchain_id"):
            print(f"     On-chain ID: {c['onchain_id']}")
            print(f"     Tx hash    : {c['tx_hash']}")
            print(f"     Explorer   : https://amoy.polygonscan.com/tx/{c['tx_hash']}")
        if result.get("ipfs_warning"):
            print(f"     ⚠ IPFS: {result['ipfs_warning']}")
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

    print("═" * W + "\n")