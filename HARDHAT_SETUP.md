# Artchain: Hardhat-only build

No Amoy, no POL, no faucets. The contract runs on a local Hardhat chain, and every
artwork you have scanned stays saved and is still used for matching.

## What changed

| Area | Change |
|---|---|
| `backend/config.py` (new) | One place for paths and settings. Everything persistent lives in `backend/data/`. |
| `backend/registry.py` | Persistent registry (SIFT descriptors, pHash, owners). Imports your old `backend/registry/` folder automatically on first start. |
| `backend/blockchain_client.py` | Talks to the local Hardhat node. No private key needed. Deploys the contract if the chain is empty and re-registers all saved artworks, keeping their original owners. |
| `backend/storage.py` (new) | Keeps images on disk (served at `/files/...`). IPFS is optional. |
| `backend/pipeline.py`, `api.py` | Same pHash + SIFT + RANSAC detection. Adds a *pending* step so a rejected wallet popup no longer blocks a retry or counts as a violation. |
| `backend/manage.py` (new) | `list`, `info`, `sync`, `remove <id>`, `wipe`. |
| `backend/accounts_db.py`, `auth.py` | Accounts DB moves into `data/` (old one is imported once). JWT secret is random and saved instead of a public default. |
| `backend/sift_engine.py` | Crash guard when OpenCV returns a single match. |
| `backend/email_service.py` | No Polygonscan link. |
| `frontend/` | No hardcoded chain. New **Demo Wallet** button (pre-funded Hardhat account, no MetaMask needed). MetaMask still works. Images load from the API. |
| `contracts/hardhat.config.ts` | Adds a `localhost` network. The `amoy` block is kept for your later version. |

## 1. Apply the patch

```bash
cd ~/projects/Artwork-Copyright-System-Unified-
git add -A && git commit -m "before hardhat build"     # safety net; undo any time with git
unzip -o ~/Downloads/artwork-hardhat-patch.zip
printf '\ndata/\n' >> backend/.gitignore                # never commit images/accounts
```

## 2. Install

```bash
cd backend && ds                          # your venv alias
pip install -r requirements.txt
cd ../frontend && npm install
cd ../contracts && npm install            # skip if already done
```

Open a **fresh terminal** (or run `unset PRIVATE_KEY PINATA_JWT CONTRACT_ADDRESS POLYGON_AMOY_RPC`)
so values exported during earlier tests cannot override your `.env`.
`backend/.env` needs nothing for this build; the old Amoy lines are ignored.

## 3. Start (three terminals, in this order)

```bash
# 1) the local blockchain: leave it running
cd contracts && npx hardhat node

# 2) the API
cd backend && ds && uvicorn api:app --reload --port 8000

# 3) the website
cd frontend && npm run dev          # open http://localhost:5173
```

Expected in terminal 2 on first start:

```
[registry] imported earlier registry from .../backend/registry     (only the first time)
[chain] deployed ArtworkRegistry at 0x5FbDB...
[chain] registry sync: {'already_on_chain': 0, 'replayed': N, ...}
```

Check from any terminal: `cd backend && python manage.py info` and `python manage.py list`.

## 4. Use it

1. Sign up / log in on the site.
2. Click **Demo Wallet** (top right). It picks a pre-funded Hardhat account. The dropdown switches between accounts, so you can play "artist" (Account 1) and "copier" (Account 2).
3. **Upload**: certify an original, then upload a cropped / zoomed / filtered version. It is rejected by SIFT + RANSAC and counted against the copier.
4. **Search** checks an image without certifying. **Gallery** and **Dashboard** show saved works. The first certification links your wallet to your account automatically.

Command line works too: `python main.py sample_images/x.jpg "Title" "Author"` (signed by the platform account).

## How persistence works

- `backend/data/` holds the registry, SIFT data, images, accounts and the chain bookkeeping file. Back this folder up.
- Hardhat forgets its chain whenever the node stops. That is normal. On the next API start (or any request that finds an empty chain) the backend redeploys the contract and re-registers every saved work with its original owner.
- Matching always uses the registry, so earlier uploads are compared against even right after a restart.

## Optional: IPFS (needs internet)

In `backend/.env`: `STORAGE_MODE=auto` and `PINATA_JWT=...`. Uploads then also go to Pinata; if Pinata fails, the local copy is used and the upload still succeeds.

## Troubleshooting

| Message | Fix |
|---|---|
| `Cannot reach the Hardhat node` / website says chain not reachable | Start `npx hardhat node` (terminal 1). |
| `HHE22 non-local installation of Hardhat` | `npm install` inside `contracts/`. |
| Website: "Backend is not running" | Start `uvicorn` (terminal 2). |
| Demo Wallet fails, console shows `/rpc` 404 or CORS | `vite.config.js` was not replaced or the dev server was not restarted. Restart `npm run dev`. |
| `Transaction not found on the local chain` on confirm | The node was restarted between signing and confirming. Upload again. |
| MetaMask "nonce too high" after a node restart | MetaMask > Settings > Advanced > Clear activity tab data. (The Demo Wallet never has this problem.) |
| Old test uploads you do not want | `python manage.py list`, then `remove <id>` (or `wipe`). Restart the node too. |

## Honest limits

- On a local chain, "permanent" only lasts while you keep `backend/data/` (the registry rebuilds the chain). Say "local Hardhat blockchain" in your presentation; the same contract is already deployed on Amoy as proof of the public version.
- After a replay, on-chain timestamps are the time of the replay. The certificate page shows the original registration time from the registry.
- Older registry rows that never got image/metadata ids (failed IPFS tests) cannot be put on the contract. They are skipped for the chain but still used for SIFT matching.
