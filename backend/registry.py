"""
registry.py
-----------
Persistent local registry. This is the memory of the system.

Per certified artwork it keeps:
  - metadata + pHash                    -> data/registry/registry.json
  - SIFT keypoints + descriptors        -> data/registry/descriptors/<id>.pkl
  - copy attempts that were caught      -> data/registry/attempts.json

Because all of this lives on disk, a new session (new process, restarted API,
restarted blockchain) still matches new uploads against every earlier work.

Rows with status "pending" were prepared by /api/prepare but not yet signed on
chain. They are invisible to matching and the gallery, so a rejected wallet
popup can never block a re-upload.

On first run, an older backend/registry/ folder (previous version of this
project) is copied into data/registry/ automatically.
"""

import json
import os
import pickle
import shutil
import threading
from datetime import datetime, timezone, timedelta

import cv2

from config import BASE_DIR, REGISTRY_DIR, DESC_DIR

REGISTRY_FILE = os.path.join(REGISTRY_DIR, "registry.json")
ATTEMPTS_FILE = os.path.join(REGISTRY_DIR, "attempts.json")
LEGACY_DIR    = os.path.join(BASE_DIR, "registry")

_LOCK = threading.RLock()


# ── helpers ──────────────────────────────────────────────────────────────────

def norm_addr(addr):
    """Wallet addresses are compared case-insensitively (MetaMask gives lower
    case, the chain gives checksum case)."""
    if isinstance(addr, str) and addr.strip():
        return addr.strip().lower()
    return None


def _read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)          # atomic: a crash can't leave a half-written file


def _desc_path(entry_id):
    return os.path.join(DESC_DIR, f"{entry_id}.pkl")


def _delete_desc(entry_id):
    try:
        os.remove(_desc_path(entry_id))
    except FileNotFoundError:
        pass


def _migrate_legacy():
    """Copies the old backend/registry/ folder into data/registry/ once."""
    if os.path.exists(REGISTRY_FILE) or not os.path.isdir(LEGACY_DIR):
        return
    copied = False
    for name in ("registry.json", "attempts.json"):
        src = os.path.join(LEGACY_DIR, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(REGISTRY_DIR, name))
            copied = True
    src = os.path.join(LEGACY_DIR, "descriptors")
    if os.path.isdir(src):
        shutil.copytree(src, DESC_DIR, dirs_exist_ok=True)
        copied = True
    if copied:
        print(f"[registry] imported earlier registry from {LEGACY_DIR}")


_migrate_legacy()


# ── write API ────────────────────────────────────────────────────────────────

def register_artwork(phash, keypoints, descriptors, title, author, filepath,
                     image_cid=None, metadata_cid=None, owner_address=None,
                     local_image=None, status="certified",
                     tx_hash=None, onchain_id=None) -> dict:
    """Saves metadata + SIFT data for a new artwork and returns the entry."""
    with _LOCK:
        entries = _read_json(REGISTRY_FILE, [])

        # An older unsigned attempt for the very same image is replaced.
        stale = [e for e in entries
                 if e.get("status") == "pending" and e.get("phash") == phash]
        for e in stale:
            _delete_desc(e["id"])
        entries = [e for e in entries if e not in stale]

        entry_id = max((e["id"] for e in entries), default=0) + 1

        kp_data = [
            (kp.pt, kp.size, kp.angle, kp.response, kp.octave, kp.class_id)
            for kp in keypoints
        ]
        with open(_desc_path(entry_id), "wb") as f:
            pickle.dump({"keypoints": kp_data, "descriptors": descriptors}, f)

        entry = {
            "id":            entry_id,
            "title":         title,
            "author":        author,
            "filepath":      filepath,
            "local_image":   local_image,
            "image_cid":     image_cid,
            "metadata_cid":  metadata_cid,
            "phash":         phash,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "kp_count":      len(keypoints),
            "owner_address": norm_addr(owner_address),
            "tx_hash":       tx_hash,
            "onchain_id":    onchain_id,
            "status":        status,
        }
        entries.append(entry)
        _write_json(REGISTRY_FILE, entries)
        return entry


def update_entry(entry_id: int, **fields) -> dict:
    with _LOCK:
        entries = _read_json(REGISTRY_FILE, [])
        for e in entries:
            if e["id"] == entry_id:
                if "owner_address" in fields:
                    fields["owner_address"] = norm_addr(fields["owner_address"])
                e.update(fields)
                _write_json(REGISTRY_FILE, entries)
                return e
    raise ValueError(f"No entry with id {entry_id}")


def remove_entry(entry_id: int) -> bool:
    with _LOCK:
        entries = _read_json(REGISTRY_FILE, [])
        kept = [e for e in entries if e["id"] != entry_id]
        if len(kept) == len(entries):
            return False
        _write_json(REGISTRY_FILE, kept)
        _delete_desc(entry_id)
        return True


def purge_pending(max_age_hours: int = 24) -> int:
    """Deletes unsigned 'pending' rows older than max_age_hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    with _LOCK:
        entries = _read_json(REGISTRY_FILE, [])
        keep, dropped = [], 0
        for e in entries:
            if e.get("status") == "pending":
                try:
                    old = datetime.fromisoformat(e["timestamp"]) < cutoff
                except Exception:
                    old = True
                if old:
                    _delete_desc(e["id"])
                    dropped += 1
                    continue
            keep.append(e)
        if dropped:
            _write_json(REGISTRY_FILE, keep)
        return dropped


# ── read API ─────────────────────────────────────────────────────────────────

def get_all_entries(include_pending: bool = False) -> list:
    entries = _read_json(REGISTRY_FILE, [])
    if include_pending:
        return entries
    return [e for e in entries if e.get("status", "certified") != "pending"]


def get_entry(entry_id: int):
    for e in _read_json(REGISTRY_FILE, []):
        if e["id"] == entry_id:
            return e
    return None


def get_entries_by_owner(owner_address: str) -> list:
    owner = norm_addr(owner_address)
    if not owner:
        return []
    return [e for e in get_all_entries() if norm_addr(e.get("owner_address")) == owner]


def load_descriptors(entry: dict):
    """Returns (cv2 keypoints, descriptors) for a registry entry."""
    path = _desc_path(entry["id"])
    if not os.path.exists(path):
        legacy = entry.get("desc_path")          # path stored by older versions
        if legacy and os.path.exists(legacy):
            path = legacy
        else:
            raise FileNotFoundError(f"No SIFT data for entry {entry['id']}")
    with open(path, "rb") as f:
        data = pickle.load(f)
    kps = [
        cv2.KeyPoint(x=p[0][0], y=p[0][1], size=p[1], angle=p[2],
                     response=p[3], octave=p[4], class_id=p[5])
        for p in data["keypoints"]
    ]
    return kps, data["descriptors"]


# ── copy-attempt log ─────────────────────────────────────────────────────────

def log_attempt(verdict, attempted_title, attempted_author, matched_artwork_id,
                matched_owner_address, sift_inliers=None):
    """Records a caught copy; powers 'copies of your work caught' stats."""
    with _LOCK:
        attempts = _read_json(ATTEMPTS_FILE, [])
        attempts.append({
            "verdict":               verdict,
            "attempted_title":       attempted_title,
            "attempted_author":      attempted_author,
            "matched_artwork_id":    matched_artwork_id,
            "matched_owner_address": norm_addr(matched_owner_address),
            "sift_inliers":          sift_inliers,
            "timestamp":             datetime.now(timezone.utc).isoformat(),
        })
        _write_json(ATTEMPTS_FILE, attempts)


def get_attempts_against_owner(owner_address: str) -> list:
    owner = norm_addr(owner_address)
    if not owner:
        return []
    return [a for a in _read_json(ATTEMPTS_FILE, [])
            if norm_addr(a.get("matched_owner_address")) == owner]


if __name__ == "__main__":
    entries = get_all_entries(include_pending=True)
    print(f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'} in {REGISTRY_FILE}")
    for e in entries:
        print(f"  [{e['id']}] '{e['title']}' by {e['author']} | pHash {e['phash']} | "
              f"{e.get('status', 'certified')} | on-chain id: {e.get('onchain_id')}")
