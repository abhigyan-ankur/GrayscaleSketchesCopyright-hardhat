"""
config.py
---------
Central settings for the Hardhat-only build.

Everything that must survive a restart lives under DATA_DIR (backend/data/ by
default): the artwork registry, SIFT descriptors, stored images, user accounts
and the chain bookkeeping file.
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DATA_DIR         = os.path.abspath(os.getenv("DATA_DIR") or os.path.join(BASE_DIR, "data"))
REGISTRY_DIR     = os.path.join(DATA_DIR, "registry")
DESC_DIR         = os.path.join(REGISTRY_DIR, "descriptors")
IMAGES_DIR       = os.path.join(DATA_DIR, "images")
METADATA_DIR     = os.path.join(DATA_DIR, "metadata")
ACCOUNTS_DB      = os.path.join(DATA_DIR, "accounts.db")
CHAIN_STATE_FILE = os.path.join(DATA_DIR, "chain_state.json")
SECRET_FILE      = os.path.join(DATA_DIR, "jwt_secret.txt")

for _d in (DATA_DIR, REGISTRY_DIR, DESC_DIR, IMAGES_DIR, METADATA_DIR):
    os.makedirs(_d, exist_ok=True)

# Local Hardhat node. No private key is needed: the node exposes unlocked,
# pre-funded accounts, and the backend signs through them.
RPC_URL = os.getenv("RPC_URL") or "http://127.0.0.1:8545"

# Optional. If empty (or no contract exists there) the backend deploys the
# contract itself and remembers the address in data/chain_state.json.
CONTRACT_ADDRESS = (os.getenv("CONTRACT_ADDRESS") or "").strip() or None

# Used to build image links the browser can open.
PUBLIC_API_URL = (os.getenv("PUBLIC_API_URL") or "http://localhost:8000").rstrip("/")

# "local" (default): images are kept on disk and served by the API, no internet.
# "auto": also pin to IPFS through Pinata when PINATA_JWT is set; falls back to
#         local storage if Pinata fails.
STORAGE_MODE = (os.getenv("STORAGE_MODE") or "local").strip().lower()
