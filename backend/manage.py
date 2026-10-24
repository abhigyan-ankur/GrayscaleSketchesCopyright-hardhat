"""
manage.py — look after the persistent registry and the local chain.

    python manage.py list            show every saved artwork
    python manage.py info            data folder, chain status, counts
    python manage.py sync            re-register saved artworks on the local chain
    python manage.py remove <id>     delete one artwork (e.g. a test upload)
    python manage.py wipe            delete ALL artworks, images and caught-copy logs
                                     (accounts are kept)
"""

import os
import shutil
import sys

from config import DATA_DIR, REGISTRY_DIR, DESC_DIR, IMAGES_DIR, METADATA_DIR
from registry import get_all_entries, remove_entry


def cmd_list():
    entries = get_all_entries(include_pending=True)
    if not entries:
        print("Registry is empty.")
        return
    print(f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}:\n")
    for e in entries:
        onchain = e.get("onchain_id")
        print(f"  [{e['id']:>3}] {e['title']!r} by {e['author']}")
        print(f"        pHash {e['phash']}  keypoints {e.get('kp_count')}  "
              f"status {e.get('status', 'certified')}  "
              f"on-chain {'#' + str(onchain) if onchain else '—'}")


def cmd_info():
    entries = get_all_entries(include_pending=True)
    print(f"Data folder : {DATA_DIR}")
    print(f"Artworks    : {len(entries)} "
          f"({sum(1 for e in entries if e.get('status') == 'pending')} pending)")
    try:
        from blockchain_client import BlockchainClient
        c = BlockchainClient(auto_sync=False)
        print(f"Chain       : Hardhat id {c.chain_id}, contract {c.contract_address}, "
              f"{c.get_total_artworks()} artwork(s) on-chain")
    except Exception as e:
        print(f"Chain       : not reachable ({e})")


def cmd_sync():
    from blockchain_client import BlockchainClient
    BlockchainClient().sync_registry()


def cmd_remove(entry_id):
    print("Removed." if remove_entry(int(entry_id)) else f"No entry with id {entry_id}.")
    print("Note: if it was already on the chain it stays there until the node restarts.")


def cmd_wipe():
    if input("Delete ALL artworks, images and logs? Accounts are kept. Type 'yes': ") != "yes":
        print("Cancelled.")
        return
    for d in (REGISTRY_DIR, IMAGES_DIR, METADATA_DIR):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
    os.makedirs(DESC_DIR, exist_ok=True)
    print("Wiped. Restart the Hardhat node as well so the chain is empty too.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "list":
        cmd_list()
    elif args[0] == "info":
        cmd_info()
    elif args[0] == "sync":
        cmd_sync()
    elif args[0] == "remove" and len(args) == 2:
        cmd_remove(args[1])
    elif args[0] == "wipe":
        cmd_wipe()
    else:
        print(__doc__)
