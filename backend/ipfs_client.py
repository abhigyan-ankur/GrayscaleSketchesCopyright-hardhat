"""
ipfs_client.py — Pinata IPFS upload client (Part 2)
"""
import os, json, requests
from dotenv import load_dotenv
load_dotenv()

PINATA_JWT        = os.getenv("PINATA_JWT")
PINATA_UPLOAD_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"
PINATA_JSON_URL   = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
IPFS_GATEWAY      = "https://gateway.pinata.cloud/ipfs"

class IPFSError(Exception): pass

def _headers():
    if not PINATA_JWT:
        raise IPFSError("PINATA_JWT not set. Add it to your .env file.")
    return {"Authorization": f"Bearer {PINATA_JWT}"}

def upload_image(filepath: str, title: str, author: str) -> str:
    """Upload artwork image to IPFS. Returns CID."""
    meta = json.dumps({"name": f"{title} by {author}", "keyvalues": {"title": title, "author": author}})
    opts = json.dumps({"cidVersion": 1})
    try:
        with open(filepath, "rb") as f:
            r = requests.post(PINATA_UPLOAD_URL, headers=_headers(),
                files={"file": (os.path.basename(filepath), f),
                       "pinataMetadata": (None, meta),
                       "pinataOptions": (None, opts)}, timeout=60)
    except requests.exceptions.Timeout:
        raise IPFSError("Upload timed out.")
    except requests.exceptions.ConnectionError:
        raise IPFSError("Cannot connect to Pinata.")
    if r.status_code != 200:
        raise IPFSError(f"Upload failed ({r.status_code}): {r.text}")
    return r.json()["IpfsHash"]

def upload_metadata(metadata: dict) -> str:
    """Upload certificate JSON to IPFS. Returns CID."""
    payload = {
        "pinataContent":  metadata,
        "pinataMetadata": {"name": f"cert_{metadata.get('title', '')}"},
        "pinataOptions":  {"cidVersion": 1}
    }
    try:
        r = requests.post(PINATA_JSON_URL,
            headers={**_headers(), "Content-Type": "application/json"},
            data=json.dumps(payload), timeout=30)
    except Exception as e:
        raise IPFSError(str(e))
    if r.status_code != 200:
        raise IPFSError(f"Metadata upload failed ({r.status_code}): {r.text}")
    return r.json()["IpfsHash"]

def get_gateway_url(cid: str) -> str:
    return f"{IPFS_GATEWAY}/{cid}"

def test_connection() -> bool:
    try:
        r = requests.get("https://api.pinata.cloud/data/testAuthentication",
                         headers=_headers(), timeout=10)
        if r.status_code == 200:
            print("✓ Pinata connected:", r.json().get("message"))
            return True
        print("✗ Auth failed:", r.text)
        return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False

if __name__ == "__main__":
    test_connection()