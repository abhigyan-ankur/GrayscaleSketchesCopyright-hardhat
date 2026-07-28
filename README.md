# Blockchain-Based Digital Artwork Copyright Protection System

Capstone project — BIT, Department of AI & ML (2025-26)
Guided by Dr. Shruthiba A

## Project Structure

```
artwork-unified/
├── backend/          Part 1, 2, 4 — Python detection engine + IPFS + blockchain bridge
│   ├── validator.py       Image validation and preprocessing
│   ├── hasher.py          pHash generation (coarse pre-filter)
│   ├── sift_engine.py     SIFT + RANSAC geometric verification (primary detector)
│   ├── registry.py        Local registry (mirrors on-chain state)
│   ├── ipfs_client.py     Pinata IPFS upload client
│   ├── blockchain_client.py  web3.py bridge to the smart contract
│   ├── pipeline.py        Orchestrates the full detect -> IPFS -> blockchain flow
│   ├── main.py            CLI entrypoint
│   └── contract_abi.json  ABI copied from contracts/artifacts/ after compile
│
├── contracts/        Part 3 — Solidity smart contract (Hardhat)
│   ├── contracts/ArtworkRegistry.sol   Main contract
│   ├── scripts/deploy.js               Deployment script
│   ├── scripts/register.js             Manual registration test
│   ├── scripts/query.js                Read-only query tests
│   └── hardhat.config.ts               Network config (Polygon Amoy)
│
└── (frontend/ coming in Part 5)
```

## Detection Algorithm (Part 1)

Two-stage pipeline, empirically validated on 6 real-world plagiarism pairs
sourced from Instagram/TikTok reposts:

1. **pHash pre-filter** (threshold <=10) — fast, catches exact reposts only.
   Confirmed via testing: scores 24-34/64 on all real attacks (crop, zoom,
   filter, watermark removal) — cannot reliably detect real plagiarism alone.

2. **SIFT + RANSAC homography** (>=30 inliers AND >=60% inlier ratio) —
   the primary detector. Confirmed 96-99% geometric consistency across all
   6 real copy pairs, robust to crop, scale (up to 3.17x), perspective
   correction, and tone/contrast filtering.

## Deployed Contract

- Network: Polygon Amoy Testnet (chain ID 80002)
- Address: `0x8cb8602857b244fD9ccB27775B6D642bc4b157b2`
- Explorer: https://amoy.polygonscan.com/address/0x8cb8602857b244fD9ccB27775B6D642bc4b157b2

## Setup

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in PINATA_JWT, PRIVATE_KEY, CONTRACT_ADDRESS
python main.py sample_images/your_sketch.jpg "Title" "Author"
```

### Contracts
```bash
cd contracts
npm install
cp .env.example .env   # fill in PRIVATE_KEY
npx hardhat compile
npx hardhat run scripts/deploy.js --network amoy
```

## Status

| Part | Description | Status |
|------|-------------|--------|
| 1 | Detection engine (pHash + SIFT+RANSAC) | Complete |
| 2 | IPFS storage (Pinata) | Complete |
| 3 | Smart contract (Solidity, Polygon Amoy) | Complete |
| 4 | Python <-> blockchain bridge (web3.py) | Complete |
| 5 | React frontend | Planned |
