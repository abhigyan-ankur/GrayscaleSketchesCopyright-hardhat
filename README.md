# Artchain: Artwork Copyright Protection System

Artchain protects original artwork. An artist uploads a drawing; the system checks it against every
artwork already registered and, if it is original, certifies it by recording a tamper-evident
fingerprint on a blockchain. Copies are detected even when cropped, zoomed, recoloured, rotated or
mirrored.

This version runs on a **local Hardhat blockchain**, so it needs no wallet funds, faucets or testnet
tokens. Everything you have scanned stays saved between sessions and is used to check new uploads.

## How detection works

Every upload goes through two stages:

1. **pHash pre-filter.** A 64-bit perceptual hash catches exact and near-exact reposts instantly
   (distance 10 or less out of 64 bits).
2. **SIFT + RANSAC.** SIFT finds scale- and rotation-invariant keypoints; RANSAC checks that the
   matches agree on one geometric transform, which rules out accidental look-alikes. This stage
   decides the verdict:

| SIFT + RANSAC result | Verdict | What happens |
|---|---|---|
| 30+ inliers and 60%+ geometric consistency | **Copy** | Rejected, the submitter gets a violation strike |
| 10 to 29 inliers and 60%+ consistency | **Similar** | Sent to the **review queue** for an admin |
| anything lower | **Different** | Certified as an original |

Extra checks:

- **Mirrored copies.** SIFT and pHash are not mirror-invariant, so each upload is also checked in
  its flipped form. Horizontal and vertical flips (also combined with crops/zooms) are caught.
- **Your own work.** If a match is your own artwork (same account or wallet) it is reported as
  "already registered by you": no violation, nothing logged against you.

## Features

- Certify artwork: image + fingerprint registered on the blockchain, owner = your wallet.
- Plagiarism detection: pHash, SIFT, RANSAC, mirror check.
- **Review queue** for works flagged "similar": an admin approves (certifies) or rejects (confirms a
  copy and adds a strike). Three strikes withhold an account.
- **Downloadable certificate** (PDF or PNG) for every certified work.
- Gallery, Search (check an image without certifying) and a personal Dashboard.
- Accounts with email + password; a linked wallet owns your works.
- **Demo Wallet**: a pre-funded Hardhat account, no MetaMask needed (MetaMask also works).
- Persistent registry: earlier uploads keep being matched after restarts.

## Architecture

```
 React website (Vite)  ──►  FastAPI backend  ──►  Hardhat node (local chain)
   :5173                      :8000                :8545
   Demo Wallet / MetaMask      pHash, SIFT, RANSAC   ArtworkRegistry.sol
   signs the transaction       registry + accounts
                               images + certificates
```

Website flow: **prepare** (detection, store image, pending row) → **wallet signs** the transaction →
**confirm** (backend checks the receipt, row becomes certified). A rejected wallet popup leaves
nothing behind.

## Project structure

```
backend/        Python API and detection engine
  api.py          HTTP endpoints
  pipeline.py     detection flow (pHash → SIFT + RANSAC, mirror, own-work, review queue)
  sift_engine.py  SIFT + RANSAC matching          hasher.py / validator.py   pHash, preprocessing
  registry.py     persistent registry (certified / pending / review / rejected)
  review.py       admin approve / reject          certificate.py            PDF / PNG certificate
  blockchain_client.py  Hardhat bridge: deploys the contract, re-syncs the registry
  storage.py      image + metadata storage        manage.py                 maintenance commands
  accounts_db.py, auth.py, email_service.py       users, login tokens, emails
  data/           everything that persists (git-ignored)
contracts/      ArtworkRegistry.sol, Hardhat config and scripts
frontend/       React website (Upload, Gallery, Search, Dashboard, Review, Login)
```

## Requirements

- Python 3.10 or newer
- Node.js 22 or newer (recommended for Hardhat 3) and npm
- Developed on Fedora Linux; the commands below are for a Linux shell

## Setup (first time)

```bash
git clone https://github.com/ankurabhigyan/Artwork-Copyright-System-Unified-.git
cd Artwork-Copyright-System-Unified-

# backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # defaults work as they are
cd ..

# contracts and frontend
(cd contracts && npm install)
(cd frontend && npm install)
```

Make sure `backend/.gitignore` contains `data/` so images and accounts are never committed.

## Run (three terminals, in this order)

```bash
# 1) local blockchain (leave running)
cd contracts && npx hardhat node

# 2) backend
cd backend && source venv/bin/activate
uvicorn api:app --reload --port 8000

# 3) website
cd frontend && npm run dev
```

Open **http://localhost:5173**. On start the backend deploys the contract if the chain is empty and
re-registers every saved artwork, so the blockchain always matches your saved data. API docs are at
http://localhost:8000/docs.

## Using it

1. **Sign up.** The first account created is the admin (or list emails in `ADMIN_EMAILS`).
2. Click **Demo Wallet** in the top bar (the dropdown switches between accounts, so you can play an
   artist and a copier). MetaMask works too if it is set to the Hardhat Local network.
3. **Upload** a drawing: it is checked, then your wallet signs the registration. A certified work
   shows a **Download certificate** button; the same buttons are in the Gallery and Dashboard.
4. Upload a cropped, zoomed, recoloured or flipped version from another account: it is rejected.
5. **Search** checks an image without certifying it.
6. Admins open **Review** to approve or reject works flagged as similar.

Command line (signed by the platform account): `python main.py image.jpg "Title" "Author"` from `backend/`.

## Configuration (`backend/.env`, all optional)

| Variable | Default | Meaning |
|---|---|---|
| `RPC_URL` | `http://127.0.0.1:8545` | Hardhat node |
| `PUBLIC_API_URL` | `http://localhost:8000` | base of image links |
| `STORAGE_MODE` | `local` | `local` keeps images on disk; `auto` also pins to IPFS when `PINATA_JWT` is set |
| `PINATA_JWT` | none | Pinata token for IPFS (optional) |
| `ADMIN_EMAILS` | first account | comma-separated admin emails |
| `JWT_SECRET` | random, saved in `data/` | login token secret |
| `CONTRACT_ADDRESS` | auto | only needed to point at an existing deployment |
| `DATA_DIR` | `backend/data` | where everything persistent lives |
| `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` | none | enables email notifications |

## Your data

Everything persistent is in `backend/data/`: registry, SIFT descriptors, images, accounts and the
chain bookkeeping file. **Back this folder up.** The Hardhat chain itself forgets everything when the
node stops; the backend rebuilds it from the registry on the next start.

```bash
cd backend
python manage.py list           # every saved artwork and its status
python manage.py info           # data folder and chain status
python manage.py sync           # re-register saved artworks on the chain
python manage.py remove <id>    # delete one artwork
python manage.py wipe           # delete all artworks and images (accounts are kept)
```

## API overview

| Endpoint | Purpose |
|---|---|
| `GET /api/chain/info` | chain id, contract address, demo accounts (also heals a restarted node) |
| `POST /api/auth/signup`, `/login`, `GET /api/auth/me`, `POST /api/auth/link-wallet` | accounts |
| `POST /api/prepare` → `POST /api/confirm` | website upload: detect, then confirm the signed transaction |
| `POST /api/check` | Search: check an image without saving anything |
| `POST /api/register` | server-signed registration (no wallet) |
| `GET /api/gallery`, `GET /api/dashboard` | certified works, personal stats |
| `GET /api/certificate/{id}?format=pdf\|png` | certificate download |
| `GET /api/admin/reviews?decision=open\|decided\|all` | review queue (admin) |
| `POST /api/admin/reviews/{id}/approve`, `/reject` | decide a flagged work (admin) |

## Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot reach the Hardhat node` | start `npx hardhat node` first |
| `HHE22 non-local installation of Hardhat` | run `npm install` inside `contracts/` |
| Website says "Backend is not running" | start `uvicorn` |
| Demo Wallet fails, `/rpc` error in the console | restart `npm run dev` (the dev server proxies `/rpc` to the node) |
| `Transaction not found on the local chain` | the node restarted between signing and confirming; upload again |
| MetaMask "nonce too high" after a node restart | MetaMask → Settings → Advanced → Clear activity tab data (the Demo Wallet has no such issue) |
| A test upload you want gone | `python manage.py remove <id>` |

## Limitations

- The blockchain is a **local development chain**: it is only as durable as `backend/data/`, and
  on-chain timestamps after a restart are the time of the re-registration (the certificate shows the
  original registration time from the registry). The contract was deployed earlier on Polygon Amoy; a
  public-testnet version is possible later (the `amoy` network is still in `contracts/hardhat.config.ts`).
- Approving a flagged work registers it on the submitter's behalf, which works because the local node
  can sign for any address. On a public chain the user would sign it themselves.
- Works registered before accounts were linked to artworks are recognised as "yours" through the
  wallet only.
- Detection thresholds come from tests on a small set of real plagiarism pairs. Check them against
  your own images before relying on them.
