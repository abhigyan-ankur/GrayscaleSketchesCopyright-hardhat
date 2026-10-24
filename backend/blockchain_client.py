"""
blockchain_client.py
---------------------
Python <-> Solidity bridge for a LOCAL Hardhat node (no tokens, no faucets).

How it works
  * The Hardhat node exposes pre-funded, unlocked accounts, so the backend does
    not need a private key. Account #0 is the "platform" account.
  * If the ArtworkRegistry contract is not on the chain yet (first run, or the
    node was restarted and forgot everything) the client deploys it from the
    bytecode in contract_abi.json.
  * A fresh chain is then re-filled from the persistent registry
    (data/registry/), keeping each artwork's original owner wallet. So
    the chain always matches your saved works, even though Hardhat forgets
    its state whenever the node stops.

Start the node first:   cd contracts && npx hardhat node
"""

import json
import os
import threading

from web3 import Web3

from config import BASE_DIR, RPC_URL, CONTRACT_ADDRESS, CHAIN_STATE_FILE

ABI_PATH = os.path.join(BASE_DIR, "contract_abi.json")
CHAIN_NAME = "Hardhat Local"
FUNDING_HEX = hex(1000 * 10**18)          # 1000 ETH for impersonated owners

_LOCK = threading.RLock()


class BlockchainError(Exception):
    pass


def _load_artifact() -> dict:
    if not os.path.exists(ABI_PATH):
        raise BlockchainError(
            f"contract_abi.json not found at {ABI_PATH}. Copy it from "
            "contracts/artifacts/contracts/ArtworkRegistry.sol/ArtworkRegistry.json"
        )
    with open(ABI_PATH) as f:
        return json.load(f)


def _read_state() -> dict:
    try:
        with open(CHAIN_STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _write_state(state: dict):
    os.makedirs(os.path.dirname(CHAIN_STATE_FILE), exist_ok=True)
    with open(CHAIN_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


class BlockchainClient:
    """One instance per request/session. Construction is cheap; if the chain is
    empty it deploys the contract and re-fills it from the registry."""

    def __init__(self, auto_sync: bool = True):
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
        if not self.w3.is_connected():
            raise BlockchainError(
                f"Cannot reach the Hardhat node at {RPC_URL}. "
                "Start it with:  cd contracts && npx hardhat node"
            )

        accounts = self.w3.eth.accounts
        if not accounts:
            raise BlockchainError("The node has no unlocked accounts. Is it a Hardhat node?")
        self.address = accounts[0]                  # platform account
        self.chain_id = self.w3.eth.chain_id

        artifact = _load_artifact()
        self.abi = artifact["abi"]
        self.bytecode = artifact.get("bytecode")

        with _LOCK:
            address, deployed_now = self._resolve_contract()
            self.contract_address = address
            self.contract = self.w3.eth.contract(address=address, abi=self.abi)
            if deployed_now and auto_sync:
                self.sync_registry()

    # ── contract discovery / deployment ─────────────────────────────────────

    def _has_code(self, address) -> bool:
        try:
            return len(self.w3.eth.get_code(Web3.to_checksum_address(address))) > 0
        except Exception:
            return False

    def _resolve_contract(self):
        state = _read_state()
        for candidate in (CONTRACT_ADDRESS, state.get("contract_address")):
            if candidate and self._has_code(candidate):
                return Web3.to_checksum_address(candidate), False

        if not self.bytecode or self.bytecode in ("0x", ""):
            raise BlockchainError(
                "No contract on the chain and contract_abi.json has no bytecode. "
                "Run `npx hardhat compile` in contracts/ and copy the artifact JSON "
                "into backend/contract_abi.json."
            )
        factory = self.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)
        tx_hash = factory.constructor().transact({"from": self.address})
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        address = Web3.to_checksum_address(receipt.contractAddress)
        _write_state({"contract_address": address, "chain_id": self.chain_id})
        print(f"[chain] deployed ArtworkRegistry at {address}")
        return address, True

    # ── read-only calls ─────────────────────────────────────────────────────

    def is_phash_registered(self, phash: str):
        exists, artwork_id = self.contract.functions.isPhashRegistered(phash).call()
        return exists, artwork_id

    def get_artwork(self, artwork_id: int) -> dict:
        r = self.contract.functions.getArtwork(artwork_id).call()
        return {"id": r[0], "title": r[1], "author": r[2], "phash": r[3],
                "image_cid": r[4], "metadata_cid": r[5], "owner": r[6],
                "timestamp": r[7]}

    def get_total_artworks(self) -> int:
        return self.contract.functions.getTotalArtworks().call()

    def get_artworks_by_owner(self, owner_address: str) -> list:
        ids = self.contract.functions.getArtworksByOwner(
            Web3.to_checksum_address(owner_address)).call()
        return list(ids)

    def get_balance(self) -> float:
        wei = self.w3.eth.get_balance(self.address)
        return float(self.w3.from_wei(wei, "ether"))

    def info(self) -> dict:
        accounts = list(self.w3.eth.accounts)
        return {
            "ready": True,
            "chain_id": self.chain_id,
            "chain_id_hex": hex(self.chain_id),
            "chain_name": CHAIN_NAME,
            "rpc_url": RPC_URL,
            "contract_address": self.contract_address,
            "accounts": accounts[:10],
            "total_artworks": self.get_total_artworks(),
        }

    # ── signing helpers ─────────────────────────────────────────────────────

    def usable_signer(self, owner_address=None) -> str:
        """Returns an address the node can sign for. Original owners that are not
        Hardhat accounts are impersonated; anything that fails falls back to the
        platform account."""
        if not owner_address:
            return self.address
        try:
            checksum = Web3.to_checksum_address(owner_address)
        except Exception:
            return self.address
        if checksum in self.w3.eth.accounts:
            return checksum
        try:
            a = self.w3.provider.make_request("hardhat_impersonateAccount", [checksum])
            b = self.w3.provider.make_request("hardhat_setBalance", [checksum, FUNDING_HEX])
            if "error" not in a and "error" not in b:
                return checksum
        except Exception:
            pass
        return self.address

    # ── write calls ─────────────────────────────────────────────────────────

    def register_artwork(self, title, author, phash, image_cid, metadata_cid,
                         owner=None) -> dict:
        """
        Registers an artwork on the local chain.
        Returns {success, tx_hash, artwork_id, block_number, owner} or
                {success: False, tx_hash, error}.
        """
        try:
            sender = self.usable_signer(owner)
            tx_hash = self.contract.functions.registerArtwork(
                title, author, phash, image_cid, metadata_cid
            ).transact({"from": sender})
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            hex_hash = Web3.to_hex(tx_hash)

            if receipt.status != 1:
                return {"success": False, "tx_hash": hex_hash,
                        "error": "Transaction reverted"}

            artwork_id = None
            try:
                events = self.contract.events.ArtworkCertified().process_receipt(receipt)
                if events:
                    artwork_id = int(events[0]["args"]["id"])
            except Exception:
                pass
            if artwork_id is None:
                artwork_id = self.get_total_artworks()

            return {"success": True, "tx_hash": hex_hash, "artwork_id": artwork_id,
                    "block_number": receipt.blockNumber, "owner": sender}
        except Exception as e:
            msg = str(e)
            if "Duplicate pHash" in msg:
                msg = "Duplicate pHash: artwork already registered on-chain"
            return {"success": False, "tx_hash": None, "error": msg}

    # ── registry replay ─────────────────────────────────────────────────────

    def sync_registry(self) -> dict:
        return sync_registry_to_chain(self)


def sync_registry_to_chain(client) -> dict:
    """
    Makes the chain match the persistent registry: every certified artwork that
    is missing on-chain is registered again, signed by its original owner.

    Entries without an image/metadata id (older local-only test rows) cannot be
    put on the contract; they are skipped but still used for SIFT matching.
    """
    from registry import get_all_entries, update_entry

    summary = {"already_on_chain": 0, "replayed": 0, "skipped_local_only": 0, "failed": 0}
    for e in sorted(get_all_entries(), key=lambda x: x["id"]):
        phash, img, meta = e.get("phash"), e.get("image_cid"), e.get("metadata_cid")
        if not (phash and img and meta):
            summary["skipped_local_only"] += 1
            continue

        exists, onchain_id = client.is_phash_registered(phash)
        if exists:
            summary["already_on_chain"] += 1
            if e.get("onchain_id") != int(onchain_id):
                update_entry(e["id"], onchain_id=int(onchain_id))
            continue

        res = client.register_artwork(e["title"], e["author"], phash, img, meta,
                                      owner=e.get("owner_address"))
        if res["success"]:
            update_entry(e["id"], tx_hash=res["tx_hash"], onchain_id=res["artwork_id"],
                         owner_address=e.get("owner_address") or res["owner"])
            summary["replayed"] += 1
        else:
            summary["failed"] += 1
            print(f"[chain] could not replay '{e['title']}': {res['error']}")

    print(f"[chain] registry sync: {summary}")
    return summary


if __name__ == "__main__":
    try:
        c = BlockchainClient()
        print(f"✓ Connected to {CHAIN_NAME} (chain id {c.chain_id})")
        print(f"✓ Contract : {c.contract_address}")
        print(f"✓ Platform account: {c.address} ({c.get_balance():.2f} ETH)")
        print(f"✓ Artworks on-chain: {c.get_total_artworks()}")
    except BlockchainError as e:
        print(f"✗ {e}")
