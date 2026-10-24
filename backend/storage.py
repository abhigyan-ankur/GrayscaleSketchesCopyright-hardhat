"""
storage.py
----------
Keeps the artwork image and its certificate metadata.

Default ("local" mode): the image is copied to data/images/ and served by the
API at /files/<name>. The image and metadata get ids that start with "local-"
(they play the role IPFS CIDs play on a public network, and satisfy the
contract's "CID cannot be empty" rule). Nothing needs the internet.

"auto" mode (set STORAGE_MODE=auto and PINATA_JWT): the image is also pinned
to IPFS. If Pinata fails, the local copy and local ids are used instead, so an
upload never fails because of the network.
"""

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

from config import IMAGES_DIR, METADATA_DIR, STORAGE_MODE, PUBLIC_API_URL

IPFS_GATEWAY = "https://gateway.pinata.cloud/ipfs"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def store_artwork(filepath: str, title: str, author: str, phash: str,
                  allow_ipfs: bool = True) -> dict:
    """
    Returns {local_image, image_cid, metadata_cid, storage, warning}.
    Always keeps a local copy of the image.
    """
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(METADATA_DIR, exist_ok=True)

    digest = _sha256_file(filepath)
    ext = os.path.splitext(filepath)[1].lower() or ".jpg"
    local_name = f"{digest[:32]}{ext}"
    dest = os.path.join(IMAGES_DIR, local_name)
    if not os.path.exists(dest):
        shutil.copy2(filepath, dest)

    image_cid = f"local-{digest[:40]}"
    metadata = {
        "title": title, "author": author, "phash": phash, "image_cid": image_cid,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    result = {"local_image": local_name, "image_cid": image_cid,
              "metadata_cid": None, "storage": "local", "warning": None}

    if allow_ipfs and STORAGE_MODE == "auto" and os.getenv("PINATA_JWT"):
        try:
            import ipfs_client
            ipfs_image = ipfs_client.upload_image(filepath, title, author)
            metadata["image_cid"] = ipfs_image
            ipfs_meta = ipfs_client.upload_metadata(metadata)
            result.update(image_cid=ipfs_image, metadata_cid=ipfs_meta, storage="ipfs")
            return result
        except Exception as e:                      # fall back, never fail the upload
            result["warning"] = f"IPFS unavailable, stored locally instead: {e}"
            metadata["image_cid"] = image_cid

    blob = json.dumps(metadata, sort_keys=True).encode()
    meta_digest = hashlib.sha256(blob).hexdigest()
    with open(os.path.join(METADATA_DIR, f"{meta_digest[:32]}.json"), "wb") as f:
        f.write(blob)
    result["metadata_cid"] = f"local-meta-{meta_digest[:40]}"
    return result


def image_url_for(entry: dict):
    """Best URL the browser can use to show this entry's image (or None)."""
    name = entry.get("local_image")
    if name and os.path.exists(os.path.join(IMAGES_DIR, name)):
        return f"{PUBLIC_API_URL}/files/{name}"
    cid = entry.get("image_cid")
    if cid and not str(cid).startswith("local-"):
        return f"{IPFS_GATEWAY}/{cid}"
    return None
