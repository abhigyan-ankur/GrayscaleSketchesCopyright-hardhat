"""
registry.py
-----------
Local registry — stand-in for the blockchain smart contract (Part 3).

Stores per artwork:
  - phash          : hex string (for fast coarse pre-filter)
  - descriptors    : serialised SIFT descriptor matrix (for Stage 1B)
  - keypoints      : serialised SIFT keypoint coordinates
  - title, author  : metadata
  - timestamp      : UTC ISO string (proof-of-registration time)
  - filepath       : local path (becomes IPFS CID in Part 2)

Storage format:
  registry/registry.json   — metadata + phash (human readable)
  registry/descriptors/    — binary .pkl files (one per artwork ID)
    Why separate? SIFT descriptor matrices are ~2MB each — keeping
    them out of the JSON keeps registry.json readable and fast to load
    for the pHash pre-filter step.

Interface (matches what Part 3 blockchain calls will look like):
  register_artwork(...)  → entry dict
  get_all_entries()      → list of entry dicts (metadata only)
  load_descriptors(id)   → (keypoints, descriptors) numpy objects


import json
import os
import pickle
from datetime import datetime, timezone

REGISTRY_DIR  = os.path.join(os.path.dirname(__file__), "registry")
REGISTRY_FILE = os.path.join(REGISTRY_DIR, "registry.json")
DESC_DIR      = os.path.join(REGISTRY_DIR, "descriptors")


def _load_meta() -> list:
    if not os.path.exists(REGISTRY_FILE):
        return []
    with open(REGISTRY_FILE, "r") as f:
        return json.load(f)


def _save_meta(entries: list):
    os.makedirs(REGISTRY_DIR, exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def register_artwork(
    phash:       str,
    keypoints:   list,
    descriptors, # np.ndarray
    title:       str,
    author:      str,
    filepath:    str,
) -> dict:
    
    Registers a new artwork. Saves metadata to JSON and descriptors to disk.
    Returns the created certificate entry.
    
    os.makedirs(DESC_DIR, exist_ok=True)
    entries = _load_meta()
    entry_id = len(entries) + 1

    # Save descriptor binary separately
    desc_path = os.path.join(DESC_DIR, f"{entry_id}.pkl")
    # Serialise keypoints as (pt, size, angle, response, octave, class_id) tuples
    kp_data = [
        (kp.pt, kp.size, kp.angle, kp.response, kp.octave, kp.class_id)
        for kp in keypoints
    ]
    with open(desc_path, "wb") as f:
        pickle.dump({"keypoints": kp_data, "descriptors": descriptors}, f)

    entry = {
        "id":        entry_id,
        "title":     title,
        "author":    author,
        "filepath":  filepath,
        "phash":     phash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "desc_path": desc_path,
        "kp_count":  len(keypoints),
    }
    entries.append(entry)
    _save_meta(entries)
    return entry


def get_all_entries() -> list:
    Returns all registry entries (metadata only, no descriptors).
    return _load_meta()


def load_descriptors(entry: dict) -> tuple:
    
    Loads SIFT keypoints and descriptors for a registry entry.

    Returns:
        (keypoints_list, descriptors_ndarray)
    
    with open(entry["desc_path"], "rb") as f:
        data = pickle.load(f)

    # Reconstruct cv2.KeyPoint objects from stored tuples
    keypoints = [
        cv2.KeyPoint(
            x=pt[0][0], y=pt[0][1],
            size=pt[1], angle=pt[2],
            response=pt[3], octave=pt[4], class_id=pt[5]
        )
        for pt in data["keypoints"]
    ]
    return keypoints, data["descriptors"]


# late import to avoid circular at module level
import cv2


if __name__ == "__main__":
    entries = get_all_entries()
    print(f"{len(entries)} artwork(s) registered.")
    for e in entries:
        print(f"  [{e['id']}] '{e['title']}' by {e['author']} | "
              f"pHash: {e['phash']} | keypoints: {e['kp_count']} | {e['timestamp']}")
"""
#part2

"""
registry.py (v2 — stores IPFS CIDs)
"""
import json, os, pickle, cv2
from datetime import datetime, timezone

REGISTRY_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry")
REGISTRY_FILE = os.path.join(REGISTRY_DIR, "registry.json")
DESC_DIR      = os.path.join(REGISTRY_DIR, "descriptors")

def _load_meta():
    if not os.path.exists(REGISTRY_FILE): return []
    with open(REGISTRY_FILE) as f: return json.load(f)

def _save_meta(entries):
    os.makedirs(REGISTRY_DIR, exist_ok=True)
    with open(REGISTRY_FILE, "w") as f: json.dump(entries, f, indent=2)

def register_artwork(phash, keypoints, descriptors, title, author,
                     filepath, image_cid=None, metadata_cid=None):
    os.makedirs(DESC_DIR, exist_ok=True)
    entries  = _load_meta()
    entry_id = len(entries) + 1

    desc_path = os.path.join(DESC_DIR, f"{entry_id}.pkl")
    kp_data = [
        (kp.pt, kp.size, kp.angle, kp.response, kp.octave, kp.class_id)
        for kp in keypoints
    ]
    with open(desc_path, "wb") as f:
        pickle.dump({"keypoints": kp_data, "descriptors": descriptors}, f)

    entry = {
        "id":           entry_id,
        "title":        title,
        "author":       author,
        "filepath":     filepath,
        "image_cid":    image_cid,
        "metadata_cid": metadata_cid,
        "phash":        phash,
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "desc_path":    desc_path,
        "kp_count":     len(keypoints),
    }
    entries.append(entry)
    _save_meta(entries)
    return entry

def get_all_entries(): return _load_meta()

def load_descriptors(entry):
    with open(entry["desc_path"], "rb") as f:
        data = pickle.load(f)
    kps = [
        cv2.KeyPoint(x=p[0][0], y=p[0][1], size=p[1], angle=p[2],
                     response=p[3], octave=p[4], class_id=p[5])
        for p in data["keypoints"]
    ]
    return kps, data["descriptors"]

if __name__ == "__main__":
    entries = get_all_entries()
    print(f"{len(entries)} artwork(s) registered.")
    for e in entries:
        cid = e.get("image_cid") or "local only"
        print(f"  [{e['id']}] '{e['title']}' by {e['author']} | CID: {cid} | {e['timestamp']}")