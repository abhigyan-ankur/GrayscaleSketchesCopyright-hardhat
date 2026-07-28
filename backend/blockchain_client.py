"""
blockchain_client.py
---------------------
Part 4: Python <-> Solidity bridge using web3.py.

Wraps the ArtworkRegistry smart contract deployed in Part 3.
This is the Python equivalent of the register.js / query.js scripts
you ran manually in Hardhat — now callable directly from the pipeline.

Environment variables required (add to .env in part1-v3/):
    POLYGON_AMOY_RPC=https://80002.rpc.thirdweb.com
    PRIVATE_KEY=0x...              (same wallet key used in part3-contracts)
    CONTRACT_ADDRESS=0x8cb8602857b244fD9ccB27775B6D642bc4b157b2

Requires:
    contract_abi.json   — copied from part3-contracts/artifacts/.../ArtworkRegistry.json
"""

import os
import json
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL          = os.getenv("POLYGON_AMOY_RPC", "https://80002.rpc.thirdweb.com")
PRIVATE_KEY      = os.getenv("PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
ABI_PATH         = os.path.join(os.path.dirname(__file__), "contract_abi.json")


class BlockchainError(Exception):
    pass


def _load_abi() -> list:
    """Loads the contract ABI from the Hardhat-generated JSON artifact."""
    if not os.path.exists(ABI_PATH):
        raise BlockchainError(
            f"contract_abi.json not found at {ABI_PATH}. "
            "Copy it from part3-contracts/artifacts/contracts/ArtworkRegistry.sol/ArtworkRegistry.json"
        )
    with open(ABI_PATH) as f:
        artifact = json.load(f)
    return artifact["abi"]


class BlockchainClient:
    """
    Wraps the ArtworkRegistry contract. One instance per session.
    """

    def __init__(self):
        if not PRIVATE_KEY:
            raise BlockchainError("PRIVATE_KEY not set in .env")
        if not CONTRACT_ADDRESS:
            raise BlockchainError("CONTRACT_ADDRESS not set in .env")

        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not self.w3.is_connected():
            raise BlockchainError(f"Cannot connect to RPC: {RPC_URL}")

        self.account = self.w3.eth.account.from_key(PRIVATE_KEY)
        self.address = self.account.address

        abi = _load_abi()
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS),
            abi=abi,
        )

    # ── Read-only calls (free, no gas) ──────────────────────────────────────

    def is_phash_registered(self, phash: str) -> tuple[bool, int]:
        """
        Checks if a pHash already exists on-chain.
        Returns (exists: bool, artwork_id: int)
        """
        exists, artwork_id = self.contract.functions.isPhashRegistered(phash).call()
        return exists, artwork_id

    def get_artwork(self, artwork_id: int) -> dict:
        """Fetches full artwork details by ID."""
        result = self.contract.functions.getArtwork(artwork_id).call()
        return {
            "id":           result[0],
            "title":        result[1],
            "author":       result[2],
            "phash":        result[3],
            "image_cid":    result[4],
            "metadata_cid": result[5],
            "owner":        result[6],
            "timestamp":    result[7],
        }

    def get_total_artworks(self) -> int:
        return self.contract.functions.getTotalArtworks().call()

    def get_artworks_by_owner(self, owner_address: str) -> list:
        ids = self.contract.functions.getArtworksByOwner(
            Web3.to_checksum_address(owner_address)
        ).call()
        return list(ids)

    def get_balance(self) -> float:
        """Returns current wallet balance in POL."""
        balance_wei = self.w3.eth.get_balance(self.address)
        return float(self.w3.from_wei(balance_wei, "ether"))

    # ── Write calls (cost gas, require signing) ─────────────────────────────

    def register_artwork(
        self,
        title: str,
        author: str,
        phash: str,
        image_cid: str,
        metadata_cid: str,
    ) -> dict:
        """
        Calls registerArtwork() on the contract. Signs and sends the transaction.

        Returns:
            {
              "success":      bool,
              "tx_hash":      str,
              "artwork_id":   int (if successful),
              "block_number": int (if successful),
              "error":        str (if failed)
            }
        """
        try:
            nonce = self.w3.eth.get_transaction_count(self.address)

            tx = self.contract.functions.registerArtwork(
                title, author, phash, image_cid, metadata_cid
            ).build_transaction({
                "from":     self.address,
                "nonce":    nonce,
                "gas":      500000,
                "gasPrice": self.w3.eth.gas_price,
            })

            signed_tx = self.w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash   = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                # Read back the new total to get the artwork ID
                total = self.get_total_artworks()
                return {
                    "success":      True,
                    "tx_hash":      tx_hash.hex(),
                    "artwork_id":   total,
                    "block_number": receipt.blockNumber,
                }
            else:
                return {"success": False, "tx_hash": tx_hash.hex(),
                        "error": "Transaction reverted"}

        except Exception as e:
            error_msg = str(e)
            if "Duplicate pHash" in error_msg:
                error_msg = "Duplicate pHash: artwork already registered on-chain"
            return {"success": False, "tx_hash": None, "error": error_msg}


def get_explorer_url(tx_hash: str) -> str:
    """Returns the PolygonScan URL for a transaction hash."""
    return f"https://amoy.polygonscan.com/tx/{tx_hash}"


if __name__ == "__main__":
    # Quick connection test
    try:
        client = BlockchainClient()
        print(f"✓ Connected. Wallet: {client.address}")
        print(f"✓ Balance: {client.get_balance():.4f} POL")
        print(f"✓ Total artworks on-chain: {client.get_total_artworks()}")
    except BlockchainError as e:
        print(f"✗ Error: {e}")